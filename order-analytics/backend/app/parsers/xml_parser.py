"""Parse shipment XML. Uses defusedxml-style safety by refusing DTD/entities."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .cleaning import clean_id, normalize_status, to_int
from .json_parser import ParseError


@dataclass
class ParsedShipments:
    shipments: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _text(node: ET.Element, *names: str) -> str | None:
    """Read a child element's text OR an attribute, trying several names."""
    for name in names:
        child = node.find(name)
        if child is not None and child.text is not None:
            return child.text
        if name in node.attrib:
            return node.attrib[name]
    return None


def parse_shipments(text: str) -> ParsedShipments:
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ParseError("XML with DTD/entities is not allowed")
    try:
        root = ET.fromstring(text.lstrip("﻿").strip())
    except ET.ParseError as exc:
        raise ParseError(f"Invalid XML: {exc}") from exc

    out = ParsedShipments()
    nodes = root.findall(".//shipment") or ([root] if root.tag == "shipment" else [])
    for idx, node in enumerate(nodes):
        shipment_id = clean_id(_text(node, "shipment_id", "id"))
        order_id = clean_id(_text(node, "order_id"))
        if not order_id:
            out.warnings.append(f"shipment[{idx}] skipped: missing order_id")
            continue
        if not shipment_id:
            shipment_id = f"S-{order_id}"
            out.warnings.append(f"shipment for order {order_id}: missing shipment_id, generated {shipment_id}")
        raw_days = _text(node, "delivery_days")
        days = to_int(raw_days)
        if days is None and raw_days is not None:
            out.warnings.append(f"shipment {shipment_id}: invalid delivery_days {raw_days!r}")
        status = normalize_status(_text(node, "status"))
        if status is None:
            out.warnings.append(f"shipment {shipment_id}: missing status")
        out.shipments.append({
            "shipment_id": shipment_id, "order_id": order_id,
            "delivery_days": days, "status": status,
        })
    return out
