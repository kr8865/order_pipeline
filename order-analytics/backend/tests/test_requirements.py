"""One test per requirement in the exercise brief (Excercise.docx).

Run:  pytest tests/test_requirements.py -v
Each test name says which bullet of the brief it proves.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

# The three files exactly as supplied in the brief's Drive folder (spreadsheet-quoted JSON/CSV).
ORDERS_JSON = b'''{
"  ""orders"": ["
    {
"      ""order_id"": ""1001"","
"      ""customer"": {""id"": ""C001"", ""name"": ""Rahul""},"
"      ""items"": ["
"        {""product_id"": ""P101"", ""qty"": 2, ""price"": 500},"
"        {""product_id"": ""P102"", ""qty"": 1, ""price"": 1200}"
"      ],"
"      ""order_date"": ""2024-01-01"""
"    },"
    {
"      ""order_id"": ""1002"","
"      ""customer"": {""id"": ""C002"", ""name"": ""Anita""},"
"      ""items"": ["
"        {""product_id"": ""P103"", ""qty"": 3, ""price"": 200}"
"      ],"
"      ""order_date"": ""2024-01-02"""
    }
  ]
}'''
SHIPMENT_XML = b"""<shipments>
  <shipment><shipment_id>S001</shipment_id><order_id>1001</order_id><delivery_days>3</delivery_days><status>Delivered</status></shipment>
  <shipment><shipment_id>S002</shipment_id><order_id>1002</order_id><delivery_days>7</delivery_days><status>Delayed</status></shipment>
</shipments>"""
PRODUCTS_CSV = b'"ProductID,ProductName,Category"\r\n"P101,Laptop,Electronics"\r\n"P102,Phone,Electronics"\r\n"P103,Chair,Furniture"\r\n'


@pytest.fixture()
def client():
    with TestClient(app) as c:
        c.post("/ingest/sample")  # reset
        for kind, name, body in (("csv", "Products.csv", PRODUCTS_CSV), ("json", "Orders.json", ORDERS_JSON),
                                 ("xml", "Shipment.xml", SHIPMENT_XML)):
            r = c.post(f"/ingest/{kind}", files={"file": (name, body)})
            assert r.status_code == 200, r.text
        yield c


# ---------------- 1. API DEVELOPMENT ----------------
def test_1_ingest_endpoints_load_json_xml_csv(client):
    r = client.post("/ingest/json", files={"file": ("Orders.json", ORDERS_JSON)}).json()
    assert r["loaded"] == {"orders": 2, "items": 3, "customers": 2}
    assert client.post("/ingest/xml", files={"file": ("Shipment.xml", SHIPMENT_XML)}).json()["loaded"] == {"shipments": 2}
    assert client.post("/ingest/csv", files={"file": ("Products.csv", PRODUCTS_CSV)}).json()["loaded"] == {"products": 3}


def test_1_analytics_summary_returns_aggregated_metrics(client):
    s = client.get("/analytics/summary").json()
    assert {"kpis", "revenue_trend", "category_revenue", "delivery_performance"} <= s.keys()


# ---------------- 2. DATA PROCESSING ----------------
def test_2_flatten_nested_json_orders_and_items(client):
    o = client.get("/orders/1001").json()
    assert [(i["product_id"], i["qty"], i["unit_price"]) for i in o["items"]] == [("P101", 2, 500), ("P102", 1, 1200)]


def test_2_join_orders_shipments_products(client):
    o = client.get("/orders/1002").json()
    assert o["items"][0]["category"] == "Furniture"          # from products.csv
    assert o["shipment"]["delivery_days"] == 7               # from shipment.xml


def test_2_missing_values_inconsistencies_type_conversion(client):
    messy = b'{"orders":[{"order_id":3003,"customer":"c9","order_date":"05/02/2024",' \
            b'"items":[{"product_id":"p101","qty":"2","price":"1,000"},{"product_id":"","qty":1,"price":5}]}]}'
    r = client.post("/ingest/json", files={"file": ("m.json", messy)}).json()
    assert r["warning_count"] >= 1                           # missing product id reported, not crashed
    o = client.get("/orders/3003").json()
    assert o["order_date"] == "2024-02-05" and o["customer"]["id"] == "C9"
    assert o["items"][0]["product_id"] == "P101" and o["order_value"] == 2000   # "2" * "1,000"
    assert o["shipment"]["status"] == "Pending"              # no shipment yet -> Pending


# ---------------- 3. COMPLEX TRANSFORMATIONS ----------------
def test_3_total_order_value(client):
    assert client.get("/orders/1001").json()["order_value"] == 2200


def test_3_delivery_delay_flag(client):
    assert client.get("/orders/1002").json()["shipment"]["is_delayed"] is True
    assert client.get("/orders/1001").json()["shipment"]["is_delayed"] is False


def test_3_category_level_aggregation(client):
    cats = {c["category"]: c["revenue"] for c in client.get("/analytics/summary").json()["category_revenue"]}
    assert cats == {"Electronics": 2200, "Furniture": 600}


def test_3_currency_conversion_using_api(client):
    s = client.get("/analytics/summary", params={"currency": "USD"}).json()
    assert s["currency"]["code"] == "USD" and s["currency"]["source"] in ("live", "fallback")
    assert 0 < s["kpis"]["total_revenue"] < 2800
    assert client.get("/currency/convert", params={"amount": 100, "to": "EUR"}).json()["converted"] > 0


# ---------------- 5. PERFORMANCE & DESIGN ----------------
def test_5_error_handling_and_response_structure(client):
    bad = client.post("/ingest/json", files={"file": ("x.json", b"{oops")})
    assert bad.status_code == 422 and bad.json()["error"]["message"]
    assert client.get("/orders/does-not-exist").json()["error"]["status"] == 404
    assert client.get("/analytics/summary", params={"start_date": "2024-02-01", "end_date": "2024-01-01"}).status_code == 400


# ---------------- FRONTEND-FACING FEATURES ----------------
def test_kpis_total_orders_revenue_delayed(client):
    k = client.get("/analytics/summary").json()["kpis"]
    assert (k["total_orders"], k["total_revenue"], k["delayed_orders"]) == (2, 2800, 1)


def test_filters_date_category_status(client):
    q = lambda **p: client.get("/analytics/summary", params=p).json()["kpis"]["total_orders"]
    assert q(start_date="2024-01-02", end_date="2024-01-02") == 1
    assert q(category="Electronics") == 1
    assert q(status="Delayed") == 1


def test_drill_down_category_to_products(client):
    d = client.get("/analytics/category/Electronics").json()
    assert {p["product_name"] for p in d["products"]} == {"Laptop", "Phone"}


# ---------------- ADVANCED REQUIREMENTS ----------------
def test_advanced_api_pagination(client):
    p = client.get("/orders", params={"page": 2, "page_size": 1}).json()["pagination"]
    assert p == {"page": 2, "page_size": 1, "total": 2, "pages": 2, "has_next": False, "has_prev": True}


def test_advanced_caching(client):
    client.get("/analytics/summary", params={"granularity": "week"})
    t = time.perf_counter(); client.get("/analytics/summary", params={"granularity": "week"}); cached = time.perf_counter() - t
    assert cached < 0.05  # served from cache


def test_advanced_async_processing(client):
    job = client.post("/ingest/csv?background=true", files={"file": ("p.csv", PRODUCTS_CSV)}).json()
    assert job["status"] == "accepted"
    assert client.get(f"/ingest/jobs/{job['job_id']}").json()["status"] == "completed"
