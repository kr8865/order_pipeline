"""Generate a larger, deliberately messy dataset in the SAME formats as the sample files.

    python scripts/generate_demo_data.py            # writes data/demo/*.{json,xml,csv}
    python scripts/generate_demo_data.py --orders 500 --seed 7

Then upload them from the dashboard's "Data" page (or POST them to /ingest/*).
Messiness included on purpose: missing dates, string quantities, mixed date formats,
lower-case statuses, missing shipments, unknown product ids, blank categories.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "demo"

CATALOGUE = [
    ("P101", "Laptop", "Electronics", 52000), ("P102", "Phone", "Electronics", 18000),
    ("P103", "Chair", "Furniture", 2500), ("P104", "Desk", "Furniture", 7500),
    ("P105", "Headphones", "Electronics", 3200), ("P106", "Bookshelf", "Furniture", 4800),
    ("P107", "T-Shirt", "Apparel", 600), ("P108", "Jeans", "Apparel", 1800),
    ("P109", "Sneakers", "Footwear", 3500), ("P110", "Sandals", "Footwear", 900),
    ("P111", "Blender", "Home Appliances", 2800), ("P112", "Microwave", "Home Appliances", 8900),
    ("P113", "Novel", "Books", 350), ("P114", "Cookbook", "Books", 650),
]
NAMES = ["Rahul", "Anita", "Priya", "Arjun", "Sneha", "Vikram", "Kavya", "Rohan", "Isha", "Aman",
         "Neha", "Karan", "Pooja", "Siddharth", "Meera", "Aditya", "Tanvi", "Yash", "Riya", "Dev"]


def main(n_orders: int, seed: int) -> None:
    rng = random.Random(seed)
    OUT.mkdir(parents=True, exist_ok=True)

    # Products CSV (one blank category to exercise missing-value handling)
    lines = ["ProductID,ProductName,Category"]
    for pid, name, cat, _ in CATALOGUE:
        lines.append(f"{pid},{name},{'' if pid == 'P114' else cat}")
    (OUT / "Products.csv").write_text("\n".join(lines) + "\n")

    start = date(2024, 1, 1)
    orders, shipments = [], []
    for i in range(n_orders):
        oid = str(2000 + i)
        d = start + timedelta(days=rng.randint(0, 180))
        fmt = rng.choice(["%Y-%m-%d"] * 8 + ["%d/%m/%Y", "%d-%m-%Y"])
        cust = rng.randrange(len(NAMES))
        items = []
        for prod in rng.sample(CATALOGUE, rng.choice([1, 1, 2, 2, 3])):
            pid, _, _, base = prod
            qty = rng.choice([1, 1, 1, 2, 2, 3, 4])
            items.append({"product_id": pid, "qty": str(qty) if rng.random() < 0.05 else qty,
                          "price": round(base * rng.uniform(0.9, 1.1))})
        if rng.random() < 0.01:
            items.append({"product_id": "P999", "qty": 1, "price": 999})  # not in catalogue
        orders.append({"order_id": oid, "customer": {"id": f"C{cust + 1:03d}", "name": NAMES[cust]},
                       "items": items,
                       "order_date": None if rng.random() < 0.01 else d.strftime(fmt)})
        if rng.random() < 0.93:  # some orders have not shipped yet
            days = max(1, int(rng.gauss(4, 2)))
            status = "Delayed" if days > 5 else rng.choice(["Delivered", "delivered", "Delivered"])
            if d > start + timedelta(days=170) and rng.random() < 0.5:
                status = "In Transit"
            shipments.append((f"S{i + 1:04d}", oid, days, status))

    (OUT / "Orders.json").write_text(json.dumps({"orders": orders}, indent=2))
    xml = ["<shipments>"] + [
        f"  <shipment>\n    <shipment_id>{s}</shipment_id>\n    <order_id>{o}</order_id>\n"
        f"    <delivery_days>{d}</delivery_days>\n    <status>{st}</status>\n  </shipment>"
        for s, o, d, st in shipments] + ["</shipments>"]
    (OUT / "Shipment.xml").write_text("\n".join(xml) + "\n")
    print(f"Wrote {len(orders)} orders, {len(shipments)} shipments, {len(CATALOGUE)} products to {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.orders, a.seed)
