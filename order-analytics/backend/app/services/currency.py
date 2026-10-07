"""Currency conversion using a free public FX API, with caching and an offline fallback.

Primary source: open.er-api.com (no API key). If the call fails (offline, rate-limited) we
fall back to approximate static rates and say so in the response (`source: "fallback"`).
Currency names come from the REST Countries API (the external API suggested in the brief).
"""
from __future__ import annotations

import logging

import httpx

from ..config import BASE_CURRENCY, EXCHANGE_RATE_API, FX_CACHE_TTL, HTTP_TIMEOUT_SECONDS, REST_COUNTRIES_API
from .cache import cache

log = logging.getLogger(__name__)

# Approximate INR-based rates, used only when the live API is unreachable.
_FALLBACK_FROM_INR = {
    "INR": 1.0, "USD": 0.012, "EUR": 0.0105, "GBP": 0.0090, "JPY": 1.75, "AED": 0.044,
    "SGD": 0.0155, "AUD": 0.018, "CAD": 0.0165, "CNY": 0.085,
}
_FALLBACK_NAMES = {
    "INR": "Indian rupee", "USD": "United States dollar", "EUR": "Euro", "GBP": "British pound",
    "JPY": "Japanese yen", "AED": "UAE dirham", "SGD": "Singapore dollar", "AUD": "Australian dollar",
    "CAD": "Canadian dollar", "CNY": "Chinese yuan",
}


def _fallback_rates(base: str) -> dict[str, float]:
    base_in_inr = _FALLBACK_FROM_INR.get(base)
    if not base_in_inr:
        return {base: 1.0}
    return {cur: round(v / base_in_inr, 6) for cur, v in _FALLBACK_FROM_INR.items()}


def get_rates(base: str = BASE_CURRENCY) -> dict:
    base = base.upper()
    key = f"fx:{base}"
    hit = cache.get(key)
    if hit:
        return hit
    try:
        resp = httpx.get(EXCHANGE_RATE_API.format(base=base), timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
        body = resp.json()
        if body.get("result") not in (None, "success") or "rates" not in body:
            raise ValueError(f"unexpected FX payload: {body.get('error-type') or body.get('result')}")
        data = {"base": base, "rates": body["rates"], "source": "live",
                "updated": body.get("time_last_update_utc")}
        cache.set(key, data, FX_CACHE_TTL)
    except Exception as exc:  # network errors, bad payloads -> degrade gracefully
        log.warning("FX API unavailable (%s); using fallback rates", exc)
        data = {"base": base, "rates": _fallback_rates(base), "source": "fallback", "updated": None}
        cache.set(key, data, 300)  # retry the live API again in 5 minutes
    return data


def convert(amount: float, to_currency: str, base: str = BASE_CURRENCY) -> tuple[float, float, str]:
    """Return (converted_amount, rate, source)."""
    to_currency = to_currency.upper()
    if to_currency == base.upper():
        return amount, 1.0, "identity"
    fx = get_rates(base)
    rate = fx["rates"].get(to_currency)
    if rate is None:
        raise KeyError(to_currency)
    return round(amount * rate, 2), rate, fx["source"]


def list_currencies() -> list[dict]:
    """Currencies (code, name, symbol) gathered from REST Countries, cached for a day."""
    hit = cache.get("fx:currencies")
    if hit:
        return hit
    try:
        resp = httpx.get(REST_COUNTRIES_API, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
        found: dict[str, dict] = {}
        for country in resp.json():  # deeply nested: country -> currencies -> {CODE: {name, symbol}}
            for code, info in (country.get("currencies") or {}).items():
                entry = found.setdefault(code, {"code": code, "name": info.get("name"),
                                                "symbol": info.get("symbol"), "countries": 0})
                entry["countries"] += 1
        available = set(get_rates()["rates"])
        result = sorted((c for c in found.values() if c["code"] in available), key=lambda c: c["code"])
        cache.set("fx:currencies", result, 86400)
        return result
    except Exception as exc:
        log.warning("REST Countries unavailable (%s); using fallback list", exc)
        return [{"code": c, "name": n, "symbol": None, "countries": None} for c, n in _FALLBACK_NAMES.items()]
