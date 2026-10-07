from datetime import date

import pytest

from app.parsers import ParseError, parse_orders, parse_products, parse_shipments
from app.services.ingestion import DEFAULT_FILES, read_text


def test_repairs_spreadsheet_quoted_sample_json():
    parsed = parse_orders(read_text(DEFAULT_FILES["json"]))
    assert [o["order_id"] for o in parsed.orders] == ["1001", "1002"]
    assert len(parsed.items) == 3
    assert parsed.items[0]["line_total"] == 1000
    assert parsed.orders[0]["order_date"] == date(2024, 1, 1)


def test_handles_missing_and_bad_values():
    text = '''{"orders": [
      {"order_id": 5, "customer": "c9", "order_date": "05/01/2024",
       "items": [{"product_id": "p1", "qty": "2", "price": "1,000"},
                 {"product_id": "", "qty": 1, "price": 5},
                 {"product_id": "P2", "qty": "abc", "price": 10}]},
      {"customer": {"id": "C1"}},
      {"order_id": "6", "order_date": "not-a-date", "items": []}
    ]}'''
    p = parse_orders(text)
    assert [o["order_id"] for o in p.orders] == ["5", "6"]
    assert p.orders[0]["customer_id"] == "C9"
    assert p.orders[0]["order_date"] == date(2024, 1, 5)
    assert p.items[0] == {"order_id": "5", "product_id": "P1", "qty": 2, "unit_price": 1000.0, "line_total": 2000.0}
    assert p.items[1]["qty"] == 0  # invalid qty -> 0 with a warning
    assert p.orders[1]["order_date"] is None
    assert len(p.warnings) >= 4


def test_invalid_json_raises():
    with pytest.raises(ParseError):
        parse_orders("{not json")


def test_xml_parsing_and_status_normalisation():
    xml = """<shipments>
      <shipment><shipment_id>S1</shipment_id><order_id>1</order_id><delivery_days>x</delivery_days><status>delivered</status></shipment>
      <shipment><order_id>2</order_id><delivery_days>4</delivery_days></shipment>
      <shipment><shipment_id>S3</shipment_id></shipment>
    </shipments>"""
    p = parse_shipments(xml)
    assert p.shipments[0] == {"shipment_id": "S1", "order_id": "1", "delivery_days": None, "status": "Delivered"}
    assert p.shipments[1]["shipment_id"] == "S-2"
    assert len(p.shipments) == 2


def test_xml_rejects_entities():
    with pytest.raises(ParseError):
        parse_shipments('<!DOCTYPE x [<!ENTITY a "b">]><shipments/>')


def test_csv_flexible_headers_and_missing_category():
    p = parse_products("Product ID;Product Name;Category\np1;Pen;stationery\nP2;Cup;\n")
    assert p.products == [
        {"product_id": "P1", "name": "Pen", "category": "Stationery"},
        {"product_id": "P2", "name": "Cup", "category": "Uncategorized"},
    ]


def test_csv_sample_file():
    p = parse_products(read_text(DEFAULT_FILES["csv"]))
    assert {x["product_id"]: x["category"] for x in p.products} == {
        "P101": "Electronics", "P102": "Electronics", "P103": "Furniture"}


def test_csv_rows_wrapped_in_quotes():
    text = '"ProductID,ProductName,Category"\n"P101,Laptop,Electronics"\n"P103,Chair,Furniture"\n'
    p = parse_products(text)
    assert [(x["product_id"], x["category"]) for x in p.products] == [("P101", "Electronics"), ("P103", "Furniture")]
