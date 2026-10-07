"""Parse and flatten nested order JSON.

Input shape (per order):
    {"order_id": "1001", "customer": {"id": "C001", "name": "Rahul"},
     "items": [{"product_id": "P101", "qty": 2, "price": 500}, ...],
     "order_date": "2024-01-01"}

The supplied Orders.json is *not* valid JSON - it was exported through a spreadsheet, so most
lines are wrapped in double quotes and inner quotes are doubled (""order_id""). `load_json_text`
detects that and repairs it before parsing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .cleaning import clean_id, clean_str, to_date, to_float, to_int


class ParseError(ValueError):
    pass


def _repair_spreadsheet_quoted_json(text: str) -> str:
    fixed_lines = []
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        fixed_lines.append(s.replace('""', '"'))
    return "\n".join(fixed_lines)


def load_json_text(text: str) -> Any:
    text = text.lstrip("﻿")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_repair_spreadsheet_quoted_json(text))
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON (even after repair): {exc.msg} at line {exc.lineno}") from exc


@dataclass
class ParsedOrders:
    orders: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    customers: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_orders(text: str) -> ParsedOrders:
    data = load_json_text(text)
    raw_orders = data.get("orders", []) if isinstance(data, dict) else data
    if not isinstance(raw_orders, list):
        raise ParseError("Expected a list of orders or an object with an 'orders' list")

    out = ParsedOrders()
    seen_customers: dict[str, dict] = {}

    for idx, raw in enumerate(raw_orders):
        if not isinstance(raw, dict):
            out.warnings.append(f"orders[{idx}] skipped: not an object")
            continue
        order_id = clean_id(raw.get("order_id") or raw.get("id"))
        if not order_id:
            out.warnings.append(f"orders[{idx}] skipped: missing order_id")
            continue

        customer = raw.get("customer") or {}
        if not isinstance(customer, dict):  # tolerate "customer": "C001"
            customer = {"id": customer}
        customer_id = clean_id(customer.get("id") or raw.get("customer_id"))
        if customer_id:
            seen_customers[customer_id] = {"customer_id": customer_id, "name": clean_str(customer.get("name"))}
        else:
            out.warnings.append(f"order {order_id}: missing customer id")

        order_date = to_date(raw.get("order_date"))
        if order_date is None:
            out.warnings.append(f"order {order_id}: missing/invalid order_date {raw.get('order_date')!r}")

        out.orders.append({"order_id": order_id, "customer_id": customer_id, "order_date": order_date})

        for j, item in enumerate(raw.get("items") or []):
            if not isinstance(item, dict):
                out.warnings.append(f"order {order_id} item[{j}] skipped: not an object")
                continue
            product_id = clean_id(item.get("product_id"))
            qty = to_int(item.get("qty") or item.get("quantity"), default=None)
            price = to_float(item.get("price") or item.get("unit_price"), default=None)
            if not product_id:
                out.warnings.append(f"order {order_id} item[{j}] skipped: missing product_id")
                continue
            if qty is None or qty < 0:
                out.warnings.append(f"order {order_id} item {product_id}: invalid qty {item.get('qty')!r}, using 0")
                qty = 0
            if price is None or price < 0:
                out.warnings.append(f"order {order_id} item {product_id}: invalid price {item.get('price')!r}, using 0")
                price = 0.0
            out.items.append({
                "order_id": order_id, "product_id": product_id, "qty": qty,
                "unit_price": price, "line_total": round(qty * price, 2),
            })

    out.customers = list(seen_customers.values())
    return out
