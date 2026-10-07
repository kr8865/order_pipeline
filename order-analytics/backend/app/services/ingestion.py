"""Ingestion service: parse raw text -> save through the repository (SQL or MongoDB).

Saves are upserts keyed on natural IDs, so re-loading the same file is idempotent and newer files
overwrite older values. Re-ingesting an order replaces its line items.
"""
from __future__ import annotations

from pathlib import Path

from ..config import DATA_DIR
from ..parsers import parse_orders, parse_products, parse_shipments
from ..repository import get_repo
from .cache import cache


def _result(source: str, counts: dict, warnings: list[str], new: int = 0, updated: int = 0) -> dict:
    # new = IDs that were not in the database before; updated = IDs that already existed and were replaced
    return {"source": source, "loaded": counts, "new": new, "updated": updated,
            "warnings": warnings, "warning_count": len(warnings)}


def _split_new(collection: str, ids: list[str]) -> tuple[int, int]:
    ids = set(ids)
    existing = get_repo().existing_ids(collection, ids)
    return len(ids - existing), len(ids & existing)


def ingest_orders_text(text: str) -> dict:
    parsed = parse_orders(text)
    new, updated = _split_new("orders", [o["order_id"] for o in parsed.orders])
    missing = get_repo().save_orders(parsed.customers, parsed.orders, parsed.items)
    parsed.warnings += [f"product {pid} referenced by an order but not in catalogue yet" for pid in missing]
    cache.clear("analytics")
    return _result("json", {"orders": len(parsed.orders), "items": len(parsed.items),
                            "customers": len(parsed.customers)}, parsed.warnings, new, updated)


def ingest_shipments_text(text: str) -> dict:
    parsed = parse_shipments(text)
    new, updated = _split_new("shipments", [s["shipment_id"] for s in parsed.shipments])
    known_orders = get_repo().save_shipments(parsed.shipments)
    parsed.warnings += [f"shipment {s['shipment_id']}: order {s['order_id']} not ingested yet"
                        for s in parsed.shipments if s["order_id"] not in known_orders]
    cache.clear("analytics")
    return _result("xml", {"shipments": len(parsed.shipments)}, parsed.warnings, new, updated)


def ingest_products_text(text: str) -> dict:
    parsed = parse_products(text)
    new, updated = _split_new("products", [p["product_id"] for p in parsed.products])
    get_repo().save_products(parsed.products)
    cache.clear("analytics")
    return _result("csv", {"products": len(parsed.products)}, parsed.warnings, new, updated)


INGESTERS = {
    "json": ingest_orders_text,
    "xml": ingest_shipments_text,
    "csv": ingest_products_text,
}

DEFAULT_FILES = {
    "json": DATA_DIR / "Orders.json",
    "xml": DATA_DIR / "Shipment.xml",
    "csv": DATA_DIR / "Products.csv",
}


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}")


def ingest(kind: str, text: str) -> dict:
    return INGESTERS[kind](text)


def ingest_defaults(dataset: str = "sample") -> list[dict]:
    """Load bundled files: 'sample' = the 3 original files, 'demo' = generated data in data/demo.
    Products first so categories resolve immediately."""
    folder = DATA_DIR / "demo" if dataset == "demo" else DATA_DIR
    if dataset == "demo" and not (folder / "Orders.json").exists():
        raise FileNotFoundError("Demo data not found - run: python scripts/generate_demo_data.py")
    return [ingest(kind, read_text(folder / DEFAULT_FILES[kind].name)) for kind in ("csv", "json", "xml")]
