"""Parse the product catalogue CSV with flexible header names."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from .cleaning import clean_id, clean_str
from .json_parser import ParseError

# Map many possible header spellings onto our canonical column names.
_HEADER_ALIASES = {
    "product_id": {"productid", "product_id", "id", "sku"},
    "name": {"productname", "product_name", "name", "title"},
    "category": {"category", "productcategory", "product_category", "type"},
}


def _canonical(header: str) -> str | None:
    key = re.sub(r"[\s\-]", "", header.strip().lower())
    for canonical, aliases in _HEADER_ALIASES.items():
        if key in aliases or key.replace("_", "") in {a.replace("_", "") for a in aliases}:
            return canonical
    return None


@dataclass
class ParsedProducts:
    products: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_products(text: str) -> ParsedProducts:
    text = text.lstrip("﻿")
    if not text.strip():
        raise ParseError("CSV is empty")
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ParseError("CSV has no rows")

    # Spreadsheet-exported files sometimes wrap each whole row in quotes, e.g.
    # "ProductID,ProductName,Category" -> it arrives as ONE cell. Split those cells again.
    if all(len(r) == 1 for r in rows) and any(d in rows[0][0] for d in ",;\t|"):
        delim = next(d for d in ",;\t|" if d in rows[0][0])
        rows = [next(csv.reader([r[0]], delimiter=delim)) for r in rows]

    header = [_canonical(h) for h in rows[0]]
    if "product_id" not in header:
        raise ParseError(f"CSV header must contain a product id column, got {rows[0]}")

    out = ParsedProducts()
    seen: dict[str, dict] = {}
    for line_no, row in enumerate(rows[1:], start=2):
        record = {col: row[i] if i < len(row) else None for i, col in enumerate(header) if col}
        product_id = clean_id(record.get("product_id"))
        if not product_id:
            out.warnings.append(f"line {line_no} skipped: missing product id")
            continue
        category = clean_str(record.get("category"))
        if category:
            category = category.title()
        else:
            out.warnings.append(f"product {product_id}: missing category -> 'Uncategorized'")
            category = "Uncategorized"
        if product_id in seen:
            out.warnings.append(f"product {product_id}: duplicate row on line {line_no}, last one wins")
        seen[product_id] = {"product_id": product_id, "name": clean_str(record.get("name")), "category": category}
    out.products = list(seen.values())
    return out
