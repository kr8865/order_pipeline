"""Central configuration. Values can be overridden with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

try:  # read backend/.env if present (keeps secrets like MONGODB_URI out of the code)
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Storage: MongoDB (Atlas). Set MONGODB_URI in backend/.env - never commit it.
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB = os.getenv("MONGODB_DB", "order_analytics")

# All prices in the source data are assumed to be in this currency.
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "INR")

# An order is flagged as delayed if its shipment status says so OR delivery took longer than this.
DELIVERY_SLA_DAYS = int(os.getenv("DELIVERY_SLA_DAYS", "5"))

# External APIs
EXCHANGE_RATE_API = os.getenv("EXCHANGE_RATE_API", "https://open.er-api.com/v6/latest/{base}")
REST_COUNTRIES_API = os.getenv(
    "REST_COUNTRIES_API", "https://restcountries.com/v3.1/all?fields=name,currencies,cca2"
)
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "6"))

# Cache TTLs (seconds)
ANALYTICS_CACHE_TTL = int(os.getenv("ANALYTICS_CACHE_TTL", "60"))
FX_CACHE_TTL = int(os.getenv("FX_CACHE_TTL", "3600"))

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
