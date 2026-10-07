"""Transformations: join orders + items + products + shipments into analysis-ready DataFrames.

Derived fields
  * line_total        = qty * unit_price
  * order_value       = sum(line_total) per order   (total order value)
  * delivery_status   = shipment status, or 'Pending' when no shipment exists yet
  * is_delayed        = status == 'Delayed' OR delivery_days > DELIVERY_SLA_DAYS
"""
from __future__ import annotations

import pandas as pd

from ..config import DELIVERY_SLA_DAYS
from ..repository import get_repo

ITEM_COLUMNS = ["order_id", "order_date", "customer_id", "customer_name", "product_id", "product_name",
                "category", "qty", "unit_price", "line_total", "shipment_id", "delivery_days",
                "shipment_status", "delivery_status", "is_delayed"]


def load_item_frame(start_date=None, end_date=None) -> pd.DataFrame:
    """One row per order line, fully joined and cleaned. The optional date range is pushed down to MongoDB."""
    df = pd.DataFrame(get_repo().item_rows(start_date, end_date), columns=ITEM_COLUMNS[:-2])
    if df.empty:
        return pd.DataFrame(columns=ITEM_COLUMNS)

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0)
    df["line_total"] = (df["qty"] * df["unit_price"]).round(2)  # recompute: never trust stored totals
    df["delivery_days"] = pd.to_numeric(df["delivery_days"], errors="coerce")
    df["category"] = df["category"].fillna("Uncategorized")
    df["product_name"] = df["product_name"].fillna(df["product_id"])
    df["customer_name"] = df["customer_name"].fillna("Unknown")
    df["delivery_status"] = df["shipment_status"].fillna("Pending")
    df["is_delayed"] = (df["delivery_status"].eq("Delayed")
                        | df["delivery_days"].gt(DELIVERY_SLA_DAYS).fillna(False)).astype(bool)
    # Keep the delivery_status consistent with the delay flag (e.g. 'Delivered' in 9 days -> late).
    df.loc[df["is_delayed"] & df["delivery_status"].eq("Delivered"), "delivery_status"] = "Delayed"
    return df[ITEM_COLUMNS]


def to_order_frame(items: pd.DataFrame) -> pd.DataFrame:
    """Aggregate item rows to one row per order with total order value."""
    if items.empty:
        return pd.DataFrame(columns=["order_id", "order_date", "customer_id", "customer_name", "order_value",
                                     "item_count", "categories", "delivery_days", "delivery_status",
                                     "is_delayed", "shipment_id"])
    grouped = items.groupby("order_id", as_index=False).agg(
        order_date=("order_date", "first"),
        customer_id=("customer_id", "first"),
        customer_name=("customer_name", "first"),
        order_value=("line_total", "sum"),
        item_count=("qty", "sum"),
        categories=("category", lambda s: sorted(set(s.dropna()))),
        delivery_days=("delivery_days", "first"),
        delivery_status=("delivery_status", "first"),
        is_delayed=("is_delayed", "max"),
        shipment_id=("shipment_id", "first"),
    )
    grouped["order_value"] = grouped["order_value"].round(2)
    return grouped.sort_values(["order_date", "order_id"], ascending=[False, True], na_position="last")


def apply_filters(items: pd.DataFrame, start_date=None, end_date=None, categories=None,
                  statuses=None, search: str | None = None) -> pd.DataFrame:
    df = items
    if start_date is not None:
        df = df[df["order_date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        df = df[df["order_date"] <= pd.Timestamp(end_date)]
    if categories:
        df = df[df["category"].isin(categories)]
    if statuses:
        df = df[df["delivery_status"].isin(statuses)]
    if search:
        s = search.strip().lower()
        df = df[df["order_id"].str.lower().str.contains(s, regex=False)
                | df["customer_name"].str.lower().str.contains(s, regex=False)
                | df["product_name"].astype(str).str.lower().str.contains(s, regex=False)]
    return df
