import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        c.post("/ingest/sample")
        yield c


def test_summary_matches_hand_calculation(client):
    body = client.get("/analytics/summary").json()
    k = body["kpis"]
    # 1001: 2*500 + 1*1200 = 2200 ; 1002: 3*200 = 600
    assert k["total_orders"] == 2
    assert k["total_revenue"] == 2800
    assert k["delayed_orders"] == 1
    assert {c["category"]: c["revenue"] for c in body["category_revenue"]} == {"Electronics": 2200, "Furniture": 600}
    assert [t["revenue"] for t in body["revenue_trend"]] == [2200, 600]


def test_filters(client):
    k = client.get("/analytics/summary", params={"category": "Furniture"}).json()["kpis"]
    assert (k["total_orders"], k["total_revenue"]) == (1, 600)
    k = client.get("/analytics/summary", params={"status": "Delivered"}).json()["kpis"]
    assert (k["total_orders"], k["delayed_orders"]) == (1, 0)
    k = client.get("/analytics/summary", params={"start_date": "2024-01-02"}).json()["kpis"]
    assert k["total_orders"] == 1


def test_bad_date_range_returns_error_envelope(client):
    r = client.get("/analytics/summary", params={"start_date": "2024-02-01", "end_date": "2024-01-01"})
    assert r.status_code == 400
    assert r.json()["error"]["message"]


def test_pagination(client):
    r = client.get("/orders", params={"page": 1, "page_size": 1}).json()
    assert r["pagination"] == {"page": 1, "page_size": 1, "total": 2, "pages": 2, "has_next": True, "has_prev": False}
    assert len(r["data"]) == 1
    assert client.get("/orders", params={"page_size": 1000}).status_code == 422


def test_order_detail_and_404(client):
    d = client.get("/orders/1001").json()
    assert d["order_value"] == 2200 and len(d["items"]) == 2
    assert client.get("/orders/nope").status_code == 404


def test_category_drilldown(client):
    d = client.get("/analytics/category/electronics").json()
    assert d["category"] == "Electronics"
    assert {p["product_id"] for p in d["products"]} == {"P101", "P102"}


def test_upload_and_reingest_is_idempotent(client):
    xml = b"<shipments><shipment><shipment_id>S002</shipment_id><order_id>1002</order_id>" \
          b"<delivery_days>2</delivery_days><status>Delivered</status></shipment></shipments>"
    r = client.post("/ingest/xml", files={"file": ("s.xml", xml, "application/xml")})
    assert r.status_code == 200 and r.json()["loaded"]["shipments"] == 1
    assert client.get("/analytics/summary").json()["kpis"]["delayed_orders"] == 0  # cache invalidated
    client.post("/ingest/json")
    client.post("/ingest/json")
    assert client.get("/analytics/summary").json()["kpis"]["total_revenue"] == 2800


def test_wrong_file_type_and_invalid_content(client):
    assert client.post("/ingest/csv", files={"file": ("x.json", b"{}", "application/json")}).status_code == 415
    assert client.post("/ingest/json", files={"file": ("x.json", b"{oops", "application/json")}).status_code == 422


def test_background_job(client):
    r = client.post("/ingest/csv?background=true").json()
    job = client.get(f"/ingest/jobs/{r['job_id']}").json()
    assert job["status"] == "completed"


def test_currency_conversion_falls_back_offline(client):
    r = client.get("/orders/1001", params={"currency": "USD"}).json()
    assert r["currency"]["code"] == "USD" and 0 < r["order_value"] < 2200


def test_summary_extras(client):
    body = client.get("/analytics/summary", params={"start_date": "2024-01-02", "end_date": "2024-01-02"}).json()
    # previous period = 2024-01-01 (one day): 1 order worth 2200 -> today 1 order worth 600
    assert body["comparison"]["previous"]["total_revenue"] == 2200
    assert body["comparison"]["change_pct"]["total_revenue"] == -72.7
    full = client.get("/analytics/summary").json()
    assert full["comparison"] is None
    assert full["top_customers"][0]["customer_name"] == "Rahul"
    assert full["top_products"][0]["product_name"] == "Phone"
    assert full["revenue_trend"][1]["delayed"] == 1 and full["revenue_trend"][1]["by_status"]["Delayed"] == 1


def test_data_quality(client):
    body = client.get("/analytics/data-quality").json()
    checks = {c["key"]: c["count"] for c in body["checks"]}
    assert body["totals"]["orders"] == 2
    assert checks["orders_without_shipment"] == 0 and checks["items_unknown_product"] == 0
