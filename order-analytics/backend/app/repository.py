"""Storage layer: MongoDB (Atlas or local) via pymongo.

All database access lives in this file; ingestion, analytics and the API only call these methods.

MongoDB document design
  orders    {_id: order_id, order_id, customer: {id, name}, order_date, items: [{product_id, qty, unit_price, line_total}]}
            -> items are EMBEDDED: an order is always read and written as one unit.
  products  {_id: product_id, product_id, name, category}
  shipments {_id: shipment_id, shipment_id, order_id, delivery_days, status}
  customers {_id: customer_id, customer_id, name}
  products and shipments are separate collections because they come from separate files
  and are joined at query time with $lookup.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

from .config import MONGODB_DB, MONGODB_URI


class MongoRepository:

    def __init__(self, uri: str, db_name: str, client=None):
        if client is None:
            from pymongo import MongoClient
            client = MongoClient(uri, serverSelectionTimeoutMS=8000, appname="order-analytics")
        self.client = client
        self.mdb = client[db_name]

    @staticmethod
    def _dt(d):
        # BSON has no date-only type: store midnight UTC datetimes.
        return datetime(d.year, d.month, d.day) if isinstance(d, date) and not isinstance(d, datetime) else d

    def init(self):
        self.mdb.orders.create_index("order_date")
        self.mdb.orders.create_index("customer.id")
        self.mdb.orders.create_index("items.product_id")
        self.mdb.shipments.create_index("order_id")
        self.mdb.products.create_index("category")

    def reset(self):
        for name in ("orders", "products", "shipments", "customers"):
            self.mdb[name].delete_many({})
        self.init()
        self.bump_version()

    # ---- data version: lets every server process (and scripts/seed.py) invalidate cached analytics ----
    def bump_version(self) -> None:
        self.mdb.meta.update_one({"_id": "data"}, {"$inc": {"version": 1}}, upsert=True)

    def data_version(self) -> int:
        doc = self.mdb.meta.find_one({"_id": "data"})
        return int(doc.get("version", 0)) if doc else 0

    def existing_ids(self, collection: str, ids) -> set[str]:
        """Which of these _ids are already stored (used to report new vs updated records)."""
        ids = list(set(ids))
        return set(self.mdb[collection].distinct("_id", {"_id": {"$in": ids}})) if ids else set()

    def count_orders(self) -> int:
        return self.mdb.orders.count_documents({})

    def save_orders(self, customers, orders, items) -> list[str]:
        from pymongo import ReplaceOne
        names = {c["customer_id"]: c["name"] for c in customers}
        by_order: dict[str, list] = {o["order_id"]: [] for o in orders}
        for it in items:
            by_order[it["order_id"]].append({k: it[k] for k in ("product_id", "qty", "unit_price", "line_total")})
        if customers:
            self.mdb.customers.bulk_write([ReplaceOne({"_id": c["customer_id"]}, {"_id": c["customer_id"], **c}, upsert=True)
                                           for c in customers])
        if orders:
            self.mdb.orders.bulk_write([ReplaceOne({"_id": o["order_id"]}, {
                "_id": o["order_id"], "order_id": o["order_id"],
                "customer": {"id": o["customer_id"], "name": names.get(o["customer_id"])},
                "order_date": self._dt(o["order_date"]), "items": by_order[o["order_id"]],
            }, upsert=True) for o in orders])
        referenced = {it["product_id"] for it in items}
        known = set(self.mdb.products.distinct("_id", {"_id": {"$in": list(referenced)}}))
        missing = sorted(referenced - known)
        if missing:
            from pymongo import UpdateOne
            self.mdb.products.bulk_write([UpdateOne({"_id": pid}, {"$setOnInsert": {"product_id": pid, "name": None, "category": None}}, upsert=True)
                                          for pid in missing])
        self.bump_version()
        return missing

    def save_shipments(self, shipments) -> set[str]:
        from pymongo import ReplaceOne
        known = set(self.mdb.orders.distinct("_id"))
        if shipments:  # one shipment per order: drop older records for these orders in ONE request
            self.mdb.shipments.delete_many({"order_id": {"$in": [s["order_id"] for s in shipments]},
                                            "_id": {"$nin": [s["shipment_id"] for s in shipments]}})
        if shipments:
            self.mdb.shipments.bulk_write([ReplaceOne({"_id": s["shipment_id"]}, {"_id": s["shipment_id"], **s}, upsert=True)
                                           for s in shipments])
        self.bump_version()
        return known

    def save_products(self, products):
        from pymongo import ReplaceOne
        if products:
            self.mdb.products.bulk_write([ReplaceOne({"_id": p["product_id"]}, {"_id": p["product_id"], **p}, upsert=True)
                                          for p in products])
        self.bump_version()

    def item_rows(self, start: date | None = None, end: date | None = None) -> list[dict]:
        """Flatten + join inside MongoDB with an aggregation pipeline (one row per order line).

        A date range is applied as the FIRST stage ($match on the indexed order_date), so MongoDB
        only joins the orders that are actually needed instead of the whole collection."""
        pipeline = []
        if start or end:
            rng = {}
            if start:
                rng["$gte"] = self._dt(start)
            if end:
                rng["$lt"] = self._dt(end) + timedelta(days=1)  # end date is inclusive
            pipeline.append({"$match": {"order_date": rng}})
        pipeline += [
            {"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {"from": "products", "localField": "items.product_id", "foreignField": "_id", "as": "product"}},
            {"$lookup": {"from": "shipments", "localField": "order_id", "foreignField": "order_id", "as": "shipment"}},
            {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$shipment", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0, "order_id": 1, "order_date": 1,
                "customer_id": "$customer.id", "customer_name": "$customer.name",
                "product_id": "$items.product_id", "product_name": "$product.name", "category": "$product.category",
                "qty": "$items.qty", "unit_price": "$items.unit_price", "line_total": "$items.line_total",
                "shipment_id": "$shipment.shipment_id", "delivery_days": "$shipment.delivery_days",
                "shipment_status": "$shipment.status",
            }},
        ]
        return list(self.mdb.orders.aggregate(pipeline))

    def data_quality(self) -> dict:
        """Counts of data problems that live outside the joined order rows."""
        order_ids = self.mdb.orders.distinct("_id")
        return {
            "products_total": self.mdb.products.count_documents({}),
            "products_uncategorized": self.mdb.products.count_documents(
                {"$or": [{"category": None}, {"category": "Uncategorized"}]}),
            "products_placeholder": self.mdb.products.count_documents({"name": None}),
            "shipments_total": self.mdb.shipments.count_documents({}),
            "shipments_orphan": self.mdb.shipments.count_documents({"order_id": {"$nin": order_ids}}),
        }


class ConfigError(RuntimeError):
    pass


_override = None


def use_repo(repo) -> None:
    """Swap the repository (used by tests to inject an in-memory mongomock client)."""
    global _override
    _override = repo
    get_repo.cache_clear()


@lru_cache(maxsize=1)
def get_repo() -> MongoRepository:
    if _override is not None:
        return _override
    if not MONGODB_URI:
        raise ConfigError("MONGODB_URI is not set. Copy backend/.env.example to backend/.env and add your "
                          "MongoDB Atlas connection string.")
    return MongoRepository(MONGODB_URI, MONGODB_DB)


def describe() -> dict:
    return {"database": "mongodb", "name": get_repo().mdb.name}
