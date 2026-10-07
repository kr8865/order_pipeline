# Order Analytics — Full Stack (Python + React)

A full-stack solution (Python + MongoDB Atlas + React) to the **Full Stack Developer exercise**: a FastAPI backend that ingests orders (JSON), shipments (XML) and products (CSV), cleans and joins them, and serves analytics; and a React dashboard that visualises them.

```
order-analytics/
├── backend/                 FastAPI + MongoDB (pymongo) + pandas
│   ├── app/
│   │   ├── main.py          App, CORS, error envelope, startup auto-load
│   │   ├── config.py        Settings (SLA days, base currency, API URLs, cache TTLs)
│   │   ├── repository.py    All MongoDB access: collections, indexes, upserts, $lookup pipeline
│   │   ├── parsers/         JSON / XML / CSV parsers + cleaning helpers
│   │   ├── services/        ingestion, transform, analytics, currency, cache, jobs
│   │   └── routers/         /ingest/*  and  /analytics/*, /orders/*, /currency/*
│   ├── data/                The 3 original files (+ demo/ after running the generator)
│   ├── scripts/seed.py      Seed MongoDB (sample or 300-order demo dataset)
│   ├── scripts/generate_demo_data.py
│   ├── .env.example         Copy to .env and add your Atlas connection string
│   └── tests/               17 pytest tests (run on in-memory mongomock, no Atlas needed)
└── frontend/                React 18 + Vite + Redux Toolkit (RTK Query) + Recharts
    └── src/
        ├── app/store.js     Redux store
        ├── services/api.js  RTK Query API layer (caching, loading/error states, invalidation)
        ├── features/filters/filtersSlice.js   Global filter state (persisted)
        ├── components/      KpiCard, Card, FilterBar, Charts, Modal, Pagination, Drilldowns…
        └── pages/           Dashboard, Orders, Data (upload)
```

## Run it

You need **Python 3.10+** and **Node 18+**.

**0. MongoDB Atlas**
1. In Atlas: **Database Access** → create a user. **Network Access** → *Add Current IP Address*.
2. **Database → Connect → Drivers** → copy the `mongodb+srv://...` string.
3. `cp backend/.env.example backend/.env` and paste it as `MONGODB_URI` (with your password). `.env` is git-ignored.

**1. Backend** (terminal 1)
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed.py --dataset demo   # seed Atlas (or: python scripts/seed.py for the original 2 orders)
uvicorn app.main:app --reload --port 8000
```
API docs (Swagger): http://localhost:8000/docs · `GET /health` shows which database is connected. If the database is empty on startup, the 3 sample files are loaded automatically.

**2. Frontend** (terminal 2)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Go to **Data → Load demo dataset** for a richer dashboard (the original sample has only 2 orders).

**Tests:** `cd backend && pytest -q` (uses in-memory mongomock, so no Atlas connection needed)

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/ingest/json` | Load orders. Multipart `file`, or no file = bundled `Orders.json`. `?background=true` runs async |
| POST | `/ingest/xml` | Load shipments |
| POST | `/ingest/csv` | Load products |
| POST | `/ingest/sample?dataset=sample\|demo` | Reset DB and load a bundled dataset |
| GET | `/ingest/jobs/{id}` | Status of a background ingest |
| GET | `/analytics/summary` | KPIs, revenue trend, category aggregation, delivery performance |
| GET | `/analytics/category/{name}` | Drill-down: products within a category |
| GET | `/analytics/data-quality` | Missing / inconsistent data found while cleaning, and how each case was handled |
| GET | `/analytics/filters` | Available categories, statuses, date range |
| GET | `/orders` | Paginated orders (`page`, `page_size`, `sort`, `order`, `search`, `delayed_only`) |
| GET | `/orders/{id}` | One order with items and shipment |
| GET | `/currency/rates`, `/currency/list`, `/currency/convert` | FX via external APIs |

Every analytics/orders endpoint accepts `start_date`, `end_date`, `category`, `status` (repeat or comma-separate) and `currency` (e.g. `USD`).
Errors always look like `{"error": {"status": 400, "message": "...", "details": [...]}}`.

## Design decisions

**Storage: MongoDB Atlas.** Orders arrive as nested JSON (customer + items[]), which maps directly onto a MongoDB document, so an order is stored and read as one unit. Data persists in the cloud, ingests are idempotent upserts keyed on natural IDs (`_id` = order_id / product_id / shipment_id, so re-uploading a file updates documents instead of duplicating them) and are written with `bulk_write` for speed. All database code sits in `app/repository.py`.

**Data model (collections):**
- `orders` — `{_id, order_id, customer: {id, name}, order_date, items: [{product_id, qty, unit_price, line_total}]}` (items embedded)
- `products` — `{_id: product_id, name, category}`
- `shipments` — `{_id: shipment_id, order_id, delivery_days, status}`
- `customers` — `{_id: customer_id, name}`

Products and shipments come from separate files, so they're separate collections joined at query time with an aggregation pipeline (`$unwind` items → `$lookup` products → `$lookup` shipments), which also flattens orders into one row per line. Indexes: `order_date`, `items.product_id`, `customer.id`, `shipments.order_id`, `products.category`. pandas does the final aggregation.

**Data processing / messy data:**
- The supplied `Orders.json` is **not valid JSON**. It went through a spreadsheet, so lines are wrapped in quotes and inner quotes are doubled (`""order_id""`). The parser detects this and repairs it.
- Nested JSON is flattened: order → customer, order → items → one row per line.
- Type conversion: IDs normalised (`1001`, `"1001"`, `1001.0` → `"1001"`), quantities/prices from strings (`"1,000"`, `"₹500"`), several date formats.
- Missing values: missing order IDs or product IDs are skipped with a warning, an invalid qty or price becomes 0 with a warning, a missing category becomes `Uncategorized`, and an order with no shipment shows as `Pending`.
- Inconsistencies: status casing normalised (`delivered` → `Delivered`), orders that reference unknown products get placeholder rows, and duplicate CSV rows are reported.
- Every ingest returns a `warnings` list, which the UI shows as data-quality warnings.
- XML with DTD/entities is rejected for safety.

**Derived fields:** `line_total = qty × price`; **total order value** = sum of lines; **delay flag** = status is `Delayed` **or** delivery took longer than the SLA (5 days, configurable); **category aggregation** = revenue, units, orders and share per category; **currency conversion** uses a live FX API (open.er-api.com, no key needed) cached for an hour. If that API is unreachable it falls back to approximate rates and the UI shows an "approx. FX rates" badge. Currency names come from the **REST Countries API** (the API suggested in the exercise's `Hit External API.xlsx`).

**Performance:** analytics responses are cached (60 s TTL) and the cache is cleared on every ingest. There is also GZip compression, DB indexes on join/filter columns, server-side pagination, and background ingest jobs.

**Frontend:** Redux Toolkit keeps global filter state (persisted to localStorage). RTK Query handles API calls, caching, loading and error states, and refetches automatically after an upload (tag invalidation). Drill-down works like this:
- Click a **trend point** to zoom into that period.
- Click a **category bar** to see a product breakdown, with a link to that category's orders.
- Click a **delivery slice** to filter by status.
- Click a **KPI card** to open the orders list.
- Click an **order row** to see the order's details.

The Revenue vs Orders toggle and the day/week/month granularity switch apply to the charts. The layout is responsive down to phone width.

## Requirements coverage (Excercise.docx → where it is)

Every bullet below is proven by a test in `backend/tests/test_requirements.py` (`pytest tests/test_requirements.py -v`).

| Brief | Implementation |
|---|---|
| `/ingest/json`, `/ingest/xml`, `/ingest/csv` | `routers/ingest.py` → parsers in `app/parsers/` (upload a file, or omit it to load the bundled sample) |
| `/analytics/summary` | `services/analytics.py::summary` (KPIs, trend, categories, delivery performance, top lists, period comparison) |
| Flatten nested JSON | `parsers/json_parser.py` (orders → customer + one row per item); repairs the spreadsheet-quoted file |
| Parse XML | `parsers/xml_parser.py` (rejects DTD/entities for safety) |
| Join orders + shipments + products | MongoDB aggregation `$unwind` + `$lookup` in `repository.py::item_rows` |
| Missing values / inconsistencies / type conversion | `parsers/cleaning.py`; every ingest returns `warnings`; `/analytics/data-quality` summarises them |
| Total order value, delay flag, category aggregation | `services/transform.py`, `services/analytics.py` |
| Currency conversion (API) | `services/currency.py`: open.er-api.com live rates (cached 1 h, offline fallback) + REST Countries for names |
| Storage decision | MongoDB Atlas (see below) |
| Modular code, separation of concerns, error handling, response structure | parsers → services → routers → repository layers; one error envelope `{"error": {...}}` |
| KPI cards: Total Orders / Revenue / Delayed | Dashboard top row (+ avg delivery time), each with change vs previous period and a sparkline |
| Charts: revenue trend / category-wise revenue / delivery performance | combined bar+line trend, category donut, stacked delivery-outcome bars + delivery-time histogram |
| Filters: date range / category / delivery status | `components/FilterBar.jsx` (Redux state), applied to every chart and the orders table |
| Dynamic fetching with loading + error states | RTK Query (`services/api.js`): skeletons, "Updating…", error card with retry |
| Toggle views (Revenue vs Orders) | "Both / Revenue / Orders" on the trend chart, "Revenue / Orders" on the category donut |
| Drill-down | category → products modal → filtered orders; trend point → that period; status → filter; KPI → orders; row → order detail |
| Reusable components | `components/ui.jsx` (Card, KpiCard, Segmented, Modal, Pagination, states), `components/charts/Charts.jsx` |
| API pagination | `GET /orders?page=&page_size=` with `pagination` metadata |
| Caching (optional) | TTL cache on analytics, cleared on every ingest; RTK Query client cache |
| Async processing (bonus) | `?background=true` on ingest + `GET /ingest/jobs/{id}` |
| State management (Redux / Context) | Redux Toolkit store + filters slice |
| Responsive design | sidebar collapses to a top bar; grids reflow down to phone width |

### Why MongoDB (the brief lists in-memory / SQLite / PostgreSQL)
The brief says *"decision-making is part of evaluation"*. I chose MongoDB because:
- the main input is **nested JSON**; an order with its items maps 1:1 to a document, so it is stored and read as one unit;
- products and shipments arrive from separate files, so they live in their own collections and are joined at query time with `$lookup`;
- re-uploading a file is an idempotent upsert keyed on the natural id (`_id = order_id`), done with `bulk_write`;
- the date filter is pushed into the pipeline's first `$match` (on an indexed field), so only the needed orders are joined.
All database code is isolated in `repository.py`, so switching to PostgreSQL would only replace that file.

## Interview cheat-sheet
- **How is a delayed order defined?** Shipment status is `Delayed` **or** delivery took longer than `DELIVERY_SLA_DAYS` (5). A "Delivered" shipment over the SLA is re-classified as Delayed and reported in data quality.
- **What happens with dirty data?** The bad record is skipped or defaulted with a warning; it never crashes the import. The warnings are returned by the API, shown in the UI, and summarised on the dashboard.
- **What if the FX API is down?** Approximate rates are used, and the UI shows an "approx. FX rates" badge.
- **How does the UI stay in sync after an upload?** The upload mutation invalidates the `Data` tag, so RTK Query refetches every dashboard query. The backend clears its analytics cache on ingest.
- **How would this scale?** Move the pandas aggregations into MongoDB pipelines (`$group`), use Redis for the cache, and a task queue (Celery/RQ) for background ingest.
