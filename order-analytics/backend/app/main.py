"""FastAPI application entry point.

Run:  uvicorn app.main:app --reload   (from the backend/ folder)
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import CORS_ORIGINS
from .repository import describe, get_repo
from .routers import analytics, ingest
from .services.ingestion import ingest_defaults

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    repo = get_repo()
    repo.init()
    log.info("Storage backend: %s", describe())
    if repo.count_orders() == 0:
        log.info("Empty database - loading bundled sample data")
        ingest_defaults()
    yield


app = FastAPI(title="Order Analytics API", version="1.0.0", lifespan=lifespan,
              description="Ingest orders (JSON), shipments (XML) and products (CSV); serve analytics.")

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ---- Consistent error envelope: {"error": {"status": .., "message": .., "details": ..}} ----
@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"status": exc.status_code, "message": exc.detail}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422,
                        content={"error": {"status": 422, "message": "Invalid request", "details": details}})


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": {"status": 500, "message": "Internal server error"}})


app.include_router(ingest.router)
app.include_router(analytics.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "storage": describe()}
