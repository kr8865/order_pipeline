"""Seed MongoDB with the bundled data.

    python scripts/seed.py                 # reset + load the original sample files (2 orders)
    python scripts/seed.py --dataset demo  # reset + load the 300-order demo dataset (generated if missing)
    python scripts/seed.py --no-reset      # add/update without wiping existing data
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR  # noqa: E402
from app.repository import get_repo  # noqa: E402
from app.services.ingestion import ingest_defaults  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["sample", "demo"], default="sample")
    ap.add_argument("--no-reset", action="store_true")
    args = ap.parse_args()

    if args.dataset == "demo" and not (DATA_DIR / "demo" / "Orders.json").exists():
        from generate_demo_data import main as generate
        generate(300, 42)

    repo = get_repo()
    repo.client.admin.command("ping")  # fail fast with a clear error if Atlas is unreachable
    print(f"Connected to MongoDB, database '{repo.mdb.name}'")
    if not args.no_reset:
        repo.reset()
        print("Cleared collections: orders, products, shipments, customers")
    else:
        repo.init()
    for r in ingest_defaults(args.dataset):
        print(f"  {r['source']:>4}: loaded {r['loaded']}  ({r['warning_count']} warnings)")
        for w in r["warnings"][:5]:
            print(f"        - {w}")
    print(f"Done. Orders in database: {repo.count_orders()}")


if __name__ == "__main__":
    main()
