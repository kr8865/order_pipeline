"""Aggregations served to the dashboard. Results are cached and invalidated on every ingest."""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

from ..config import ANALYTICS_CACHE_TTL, BASE_CURRENCY, DELIVERY_SLA_DAYS
from .cache import cached
from .currency import convert
from .transform import apply_filters, load_item_frame, to_order_frame

_FREQ = {"day": "D", "week": "W-MON", "month": "MS"}


def _data_version():
    from ..repository import get_repo
    return get_repo().data_version()


def _fx(currency: str | None) -> tuple[float, dict]:
    code = (currency or BASE_CURRENCY).upper()
    _, rate, source = convert(1.0, code)
    return rate, {"code": code, "base": BASE_CURRENCY, "rate": rate, "source": source}


def _money(v: float, rate: float) -> float:
    return round(float(v) * rate, 2)


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def _pick_granularity(df: pd.DataFrame, requested: str) -> str:
    if requested in _FREQ:
        return requested
    dates = df["order_date"].dropna()
    if dates.empty:
        return "day"
    span = (dates.max() - dates.min()).days
    return "day" if span <= 45 else "week" if span <= 180 else "month"


def _kpis(items: pd.DataFrame, orders: pd.DataFrame, rate: float) -> dict:
    total_orders = int(len(orders))
    total_revenue = float(items["line_total"].sum()) if total_orders else 0.0
    delayed = int(orders["is_delayed"].sum()) if total_orders else 0
    shipped = orders[orders["delivery_days"].notna()] if total_orders else orders
    return {
        "total_orders": total_orders,
        "total_revenue": _money(total_revenue, rate),
        "delayed_orders": delayed,
        "delayed_pct": round(100 * delayed / total_orders, 1) if total_orders else 0.0,
        "avg_order_value": _money(total_revenue / total_orders, rate) if total_orders else 0.0,
        "units_sold": int(items["qty"].sum()) if total_orders else 0,
        "avg_delivery_days": _clean(round(float(shipped["delivery_days"].mean()), 1)) if len(shipped) else None,
        "customers": int(orders["customer_id"].nunique()) if total_orders else 0,
    }


def _pct_change(now, before):
    if now is None or before in (None, 0):
        return None
    return round(100 * (now - before) / before, 1)


def _top(items: pd.DataFrame, by: list[str], rate: float, n: int = 5) -> list[dict]:
    if items.empty:
        return []
    t = (items.groupby(by).agg(revenue=("line_total", "sum"), orders=("order_id", "nunique"), units=("qty", "sum"))
         .reset_index().sort_values("revenue", ascending=False).head(n))
    return [{**{k: getattr(r, k) for k in by}, "revenue": _money(r.revenue, rate),
             "orders": int(r.orders), "units": int(r.units)} for r in t.itertuples()]


@cached("analytics:summary", ANALYTICS_CACHE_TTL, version_fn=_data_version)
def summary(start_date: date | None = None, end_date: date | None = None,
            categories: tuple[str, ...] = (), statuses: tuple[str, ...] = (),
            currency: str | None = None, granularity: str = "auto") -> dict:
    # Date range is filtered inside MongoDB; category/status are derived fields, filtered in pandas.
    items = apply_filters(load_item_frame(start_date, end_date), start_date, end_date,
                          list(categories), list(statuses))
    orders = to_order_frame(items)
    rate, fx = _fx(currency)
    kpis = _kpis(items, orders, rate)
    total_orders, total_revenue = kpis["total_orders"], float(items["line_total"].sum()) if len(items) else 0.0

    # Comparison with the previous period of the same length (only when a full date range is chosen).
    comparison = None
    if start_date and end_date:
        span = (end_date - start_date).days + 1
        p_start, p_end = start_date - timedelta(days=span), start_date - timedelta(days=1)
        p_items = apply_filters(load_item_frame(p_start, p_end), p_start, p_end, list(categories), list(statuses))
        prev = _kpis(p_items, to_order_frame(p_items), rate)
        comparison = {
            "previous_start": p_start, "previous_end": p_end, "previous": prev,
            "change_pct": {k: _pct_change(kpis[k], prev[k])
                           for k in ("total_orders", "total_revenue", "delayed_orders", "avg_order_value",
                                     "avg_delivery_days")},
        }

    # Trend per period: revenue, orders, and delivery outcome counts (feeds the trend chart,
    # the KPI sparklines and the "delivery performance over time" chart).
    gran = _pick_granularity(items, granularity)
    trend = []
    dated_orders = orders.dropna(subset=["order_date"]) if total_orders else orders
    dated_items = items.dropna(subset=["order_date"])
    if not dated_items.empty:
        freq = _FREQ[gran]
        rev = dated_items.groupby(pd.Grouper(key="order_date", freq=freq))["line_total"].sum()
        g = dated_orders.groupby(pd.Grouper(key="order_date", freq=freq))
        status_counts = (dated_orders.groupby([pd.Grouper(key="order_date", freq=freq), "delivery_status"])
                         .size().unstack(fill_value=0))
        t = pd.DataFrame({"revenue": rev, "orders": g["order_id"].count(), "delayed": g["is_delayed"].sum(),
                          "avg_delivery_days": g["delivery_days"].mean()}).join(status_counts).fillna(0)
        for period, r in t.iterrows():
            trend.append({
                "period": period.strftime("%Y-%m-%d"), "revenue": _money(r["revenue"], rate),
                "orders": int(r["orders"]), "delayed": int(r["delayed"]),
                "on_time": int(r["orders"] - r["delayed"]),
                "avg_delivery_days": round(float(r["avg_delivery_days"]), 1) if r["avg_delivery_days"] else None,
                "by_status": {st: int(r[st]) for st in status_counts.columns},
            })

    # Category-level aggregation
    cats = []
    if total_orders:
        c = items.groupby("category").agg(revenue=("line_total", "sum"), units=("qty", "sum"),
                                          orders=("order_id", "nunique")).reset_index()
        for r in c.sort_values("revenue", ascending=False).itertuples():
            cats.append({"category": r.category, "revenue": _money(r.revenue, rate), "units": int(r.units),
                         "orders": int(r.orders),
                         "share": round(100 * r.revenue / total_revenue, 1) if total_revenue else 0.0})

    # Delivery performance by status
    perf = []
    if total_orders:
        d = orders.groupby("delivery_status").agg(orders=("order_id", "count"), revenue=("order_value", "sum"),
                                                  avg_days=("delivery_days", "mean")).reset_index()
        for r in d.sort_values("orders", ascending=False).itertuples():
            perf.append({"status": r.delivery_status, "orders": int(r.orders),
                         "share": round(100 * r.orders / total_orders, 1),
                         "revenue": _money(r.revenue, rate),
                         "avg_delivery_days": _clean(round(float(r.avg_days), 1)) if pd.notna(r.avg_days) else None})

    shipped = orders[orders["delivery_days"].notna()] if total_orders else orders
    days_hist = []
    if len(shipped):
        h = shipped.groupby("delivery_days")["order_id"].count().reset_index()
        days_hist = [{"days": int(r.delivery_days), "orders": int(r.order_id),
                      "late": bool(r.delivery_days > DELIVERY_SLA_DAYS)} for r in h.itertuples()]

    return {
        "filters": {"start_date": start_date, "end_date": end_date, "categories": list(categories),
                    "statuses": list(statuses), "granularity": gran},
        "currency": fx,
        "sla_days": DELIVERY_SLA_DAYS,
        "kpis": kpis,
        "comparison": comparison,
        "revenue_trend": trend,
        "category_revenue": cats,
        "delivery_performance": perf,
        "delivery_days_distribution": days_hist,
        "top_customers": _top(items, ["customer_id", "customer_name"], rate),
        "top_products": _top(items, ["product_id", "product_name", "category"], rate),
    }


@cached("analytics:quality", ANALYTICS_CACHE_TTL, version_fn=_data_version)
def data_quality() -> dict:
    """Data-quality report: how much of the data was missing or inconsistent, and how it was handled."""
    from ..repository import get_repo
    items = load_item_frame()
    orders = to_order_frame(items)
    repo = get_repo().data_quality()
    checks = [
        ("orders_missing_date", int(orders["order_date"].isna().sum()) if len(orders) else 0,
         "Orders with a missing or unparseable date", "Kept; excluded from date filters and the trend chart"),
        ("orders_without_shipment", int(orders["shipment_id"].isna().sum()) if len(orders) else 0,
         "Orders with no shipment record", "Shown with delivery status 'Pending'"),
        ("orders_without_items", int((orders["item_count"] == 0).sum()) if len(orders) else 0,
         "Orders with no valid line items", "Counted with value 0"),
        ("items_unknown_product", int((items["product_id"].notna() & (items["product_name"] == items["product_id"])).sum())
         if len(items) else 0,
         "Order lines whose product is not in the catalogue", "Placeholder product created, category 'Uncategorized'"),
        ("products_uncategorized", repo["products_uncategorized"],
         "Products with no category", "Grouped under 'Uncategorized'"),
        ("shipments_orphan", repo["shipments_orphan"],
         "Shipments for orders that were never loaded", "Ignored in analytics until the order arrives"),
        ("late_deliveries_marked_delivered",
         int(((items["shipment_status"] == "Delivered") & items["is_delayed"]).groupby(items["order_id"]).any().sum())
         if len(items) else 0,
         "Shipments marked 'Delivered' but over the SLA", "Re-classified as 'Delayed'"),
    ]
    return {
        "totals": {"orders": int(len(orders)), "order_lines": int(items["product_id"].notna().sum()) if len(items) else 0,
                   "products": repo["products_total"], "shipments": repo["shipments_total"]},
        "sla_days": DELIVERY_SLA_DAYS,
        "checks": [{"key": k, "count": n, "label": label, "handling": how} for k, n, label, how in checks],
    }


@cached("analytics:category", ANALYTICS_CACHE_TTL, version_fn=_data_version)
def category_drilldown(category: str, start_date=None, end_date=None,
                       statuses: tuple[str, ...] = (), currency: str | None = None) -> dict | None:
    all_items = load_item_frame()
    match = [c for c in all_items["category"].unique() if c.lower() == category.lower()]
    if not match:
        return None
    items = apply_filters(all_items, start_date, end_date, [match[0]], list(statuses))
    rate, fx = _fx(currency)
    products = []
    if not items.empty:
        p = items.groupby(["product_id", "product_name"]).agg(
            revenue=("line_total", "sum"), units=("qty", "sum"), orders=("order_id", "nunique"),
            avg_price=("unit_price", "mean"), delayed=("is_delayed", "sum")).reset_index()
        for r in p.sort_values("revenue", ascending=False).itertuples():
            products.append({"product_id": r.product_id, "product_name": r.product_name,
                             "revenue": _money(r.revenue, rate), "units": int(r.units), "orders": int(r.orders),
                             "avg_price": _money(r.avg_price, rate), "delayed_lines": int(r.delayed)})
    return {"category": match[0], "currency": fx,
            "revenue": _money(items["line_total"].sum(), rate) if not items.empty else 0.0,
            "orders": int(items["order_id"].nunique()), "products": products}


def list_orders(page: int, page_size: int, start_date=None, end_date=None, categories=(), statuses=(),
                search: str | None = None, sort: str = "order_date", order: str = "desc",
                delayed_only: bool = False, currency: str | None = None) -> dict:
    items = apply_filters(load_item_frame(), start_date, end_date, list(categories), list(statuses), search)
    orders = to_order_frame(items)
    if delayed_only and not orders.empty:
        orders = orders[orders["is_delayed"]]
    if sort in {"order_date", "order_value", "order_id", "delivery_days", "customer_name"} and not orders.empty:
        orders = orders.sort_values(sort, ascending=(order == "asc"), na_position="last")
    rate, fx = _fx(currency)
    total = int(len(orders))
    pages = max(1, math.ceil(total / page_size))
    chunk = orders.iloc[(page - 1) * page_size: page * page_size]
    rows = [{
        "order_id": r.order_id,
        "order_date": r.order_date.strftime("%Y-%m-%d") if pd.notna(r.order_date) else None,
        "customer_id": r.customer_id, "customer_name": r.customer_name,
        "order_value": _money(r.order_value, rate), "item_count": int(r.item_count),
        "categories": list(r.categories), "delivery_days": _clean(None if pd.isna(r.delivery_days) else int(r.delivery_days)),
        "delivery_status": r.delivery_status, "is_delayed": bool(r.is_delayed), "shipment_id": _clean(r.shipment_id),
    } for r in chunk.itertuples()]
    return {"data": rows, "currency": fx,
            "pagination": {"page": page, "page_size": page_size, "total": total, "pages": pages,
                           "has_next": page < pages, "has_prev": page > 1}}


def order_detail(order_id: str, currency: str | None = None) -> dict | None:
    items = load_item_frame()
    items = items[items["order_id"].str.upper() == order_id.strip().upper()]
    if items.empty:
        return None
    rate, fx = _fx(currency)
    head = to_order_frame(items).iloc[0]
    return {
        "order_id": head.order_id,
        "order_date": head.order_date.strftime("%Y-%m-%d") if pd.notna(head.order_date) else None,
        "customer": {"id": head.customer_id, "name": head.customer_name},
        "order_value": _money(head.order_value, rate), "currency": fx,
        "shipment": {"shipment_id": _clean(head.shipment_id),
                     "delivery_days": None if pd.isna(head.delivery_days) else int(head.delivery_days),
                     "status": head.delivery_status, "is_delayed": bool(head.is_delayed)},
        "items": [{"product_id": r.product_id, "product_name": r.product_name, "category": r.category,
                   "qty": int(r.qty), "unit_price": _money(r.unit_price, rate), "line_total": _money(r.line_total, rate)}
                  for r in items.dropna(subset=["product_id"]).itertuples()],
    }


@cached("analytics:filters", ANALYTICS_CACHE_TTL, version_fn=_data_version)
def filter_options() -> dict:
    items = load_item_frame()
    dates = items["order_date"].dropna()
    return {
        "categories": sorted(items["category"].dropna().unique().tolist()),
        "statuses": sorted(items["delivery_status"].dropna().unique().tolist()),
        "min_date": dates.min().strftime("%Y-%m-%d") if not dates.empty else None,
        "max_date": dates.max().strftime("%Y-%m-%d") if not dates.empty else None,
        "base_currency": BASE_CURRENCY,
    }
