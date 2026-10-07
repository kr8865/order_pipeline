"""/analytics/*, /orders/*, /currency/* read endpoints."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from ..config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from ..services import analytics, currency

router = APIRouter(tags=["analytics"])


def _split(values: list[str] | None) -> tuple[str, ...]:
    """Accept both ?category=A&category=B and ?category=A,B."""
    out: list[str] = []
    for v in values or []:
        out += [p.strip() for p in v.split(",") if p.strip()]
    return tuple(sorted(set(out)))


def _check_dates(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise HTTPException(400, "start_date must be on or before end_date")


async def _safe(fn, *args, **kwargs):
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except KeyError as exc:
        raise HTTPException(400, f"Unsupported currency: {exc.args[0]}") from exc


@router.get("/analytics/summary", summary="Aggregated KPIs, revenue trend, category & delivery metrics")
async def get_summary(
    start_date: date | None = None, end_date: date | None = None,
    category: list[str] | None = Query(None), status: list[str] | None = Query(None),
    currency: str | None = Query(None, min_length=3, max_length=3),
    granularity: Literal["auto", "day", "week", "month"] = "auto",
):
    _check_dates(start_date, end_date)
    return await _safe(analytics.summary, start_date, end_date, _split(category), _split(status),
                       currency.upper() if currency else None, granularity)


@router.get("/analytics/category/{category}", summary="Drill-down: products within a category")
async def get_category(category: str, start_date: date | None = None, end_date: date | None = None,
                       status: list[str] | None = Query(None), currency: str | None = None):
    _check_dates(start_date, end_date)
    data = await _safe(analytics.category_drilldown, category, start_date, end_date, _split(status),
                       currency.upper() if currency else None)
    if data is None:
        raise HTTPException(404, f"Category '{category}' not found")
    return data


@router.get("/analytics/data-quality", summary="Missing / inconsistent data found during processing")
async def get_data_quality():
    return await run_in_threadpool(analytics.data_quality)


@router.get("/analytics/filters", summary="Available filter values")
async def get_filters():
    return await run_in_threadpool(analytics.filter_options)


@router.get("/orders", summary="Paginated, filterable list of orders with derived fields")
async def get_orders(
    page: int = Query(1, ge=1), page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    start_date: date | None = None, end_date: date | None = None,
    category: list[str] | None = Query(None), status: list[str] | None = Query(None),
    search: str | None = Query(None, max_length=100), delayed_only: bool = False,
    sort: Literal["order_date", "order_value", "order_id", "delivery_days", "customer_name"] = "order_date",
    order: Literal["asc", "desc"] = "desc", currency: str | None = None,
):
    _check_dates(start_date, end_date)
    return await _safe(analytics.list_orders, page, page_size, start_date, end_date, _split(category),
                       _split(status), search, sort, order, delayed_only, currency.upper() if currency else None)


@router.get("/orders/{order_id}", summary="Single order with line items and shipment")
async def get_order(order_id: str, currency: str | None = None):
    data = await _safe(analytics.order_detail, order_id, currency.upper() if currency else None)
    if data is None:
        raise HTTPException(404, f"Order '{order_id}' not found")
    return data


@router.get("/currency/rates", summary="Exchange rates (live, cached, with offline fallback)")
async def get_rates(base: str | None = None):
    return await run_in_threadpool(currency.get_rates, (base or analytics.BASE_CURRENCY).upper())


@router.get("/currency/list", summary="Supported currencies (names via REST Countries API)")
async def get_currencies():
    return await run_in_threadpool(currency.list_currencies)


@router.get("/currency/convert", summary="Convert an amount from the base currency")
async def convert_amount(amount: float = Query(..., ge=0), to: str = Query(..., min_length=3, max_length=3)):
    try:
        value, rate, source = await run_in_threadpool(currency.convert, amount, to)
    except KeyError as exc:
        raise HTTPException(400, f"Unsupported currency: {to}") from exc
    return {"amount": amount, "from": analytics.BASE_CURRENCY, "to": to.upper(), "rate": rate,
            "converted": value, "source": source}
