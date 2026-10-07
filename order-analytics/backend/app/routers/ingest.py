"""/ingest/* endpoints.

Each endpoint accepts EITHER an uploaded file (multipart field `file`) OR, when no file is sent,
loads the bundled sample file from backend/data. Add `?background=true` to process asynchronously
and poll GET /ingest/jobs/{job_id}.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..repository import get_repo
from ..parsers import ParseError
from ..services import ingestion, jobs
from ..services.cache import cache

router = APIRouter(prefix="/ingest", tags=["ingest"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_ALLOWED_EXT = {"json": (".json", ".txt"), "xml": (".xml", ".txt"), "csv": (".csv", ".txt")}


async def _read_upload(kind: str, file: UploadFile | None) -> tuple[str, str]:
    if file is None:
        path = ingestion.DEFAULT_FILES[kind]
        return ingestion.read_text(path), path.name
    name = file.filename or "upload"
    if not name.lower().endswith(_ALLOWED_EXT[kind]):
        raise HTTPException(415, f"Expected a {kind.upper()} file, got '{name}'")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 20 MB)")
    if not raw.strip():
        raise HTTPException(400, "Uploaded file is empty")
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc), name
        except UnicodeDecodeError:
            continue
    raise HTTPException(400, "Could not decode file")


async def _handle(kind: str, file: UploadFile | None, background: bool, tasks: BackgroundTasks) -> dict:
    text, name = await _read_upload(kind, file)
    if background:
        job_id = jobs.create_job(kind, name)
        tasks.add_task(jobs.run_job, job_id, ingestion.ingest, kind, text)
        return {"status": "accepted", "job_id": job_id, "poll": f"/ingest/jobs/{job_id}"}
    try:
        result = await run_in_threadpool(ingestion.ingest, kind, text)
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"status": "ok", "file": name, **result}


@router.post("/json", summary="Load orders (nested JSON)")
async def ingest_json(tasks: BackgroundTasks, file: UploadFile | None = File(None),
                      background: bool = Query(False)):
    return await _handle("json", file, background, tasks)


@router.post("/xml", summary="Load shipments (XML)")
async def ingest_xml(tasks: BackgroundTasks, file: UploadFile | None = File(None),
                     background: bool = Query(False)):
    return await _handle("xml", file, background, tasks)


@router.post("/csv", summary="Load products (CSV)")
async def ingest_csv(tasks: BackgroundTasks, file: UploadFile | None = File(None),
                     background: bool = Query(False)):
    return await _handle("csv", file, background, tasks)


@router.post("/sample", summary="Reset the database and load bundled files (sample or demo dataset)")
async def ingest_sample(reset: bool = Query(True), dataset: Literal["sample", "demo"] = "sample"):
    if dataset == "demo" and not (ingestion.DATA_DIR / "demo" / "Orders.json").exists():
        raise HTTPException(404, "Demo data not found - run: python scripts/generate_demo_data.py")
    if reset:
        await run_in_threadpool(get_repo().reset)
        cache.clear()
    results = await run_in_threadpool(ingestion.ingest_defaults, dataset)
    return {"status": "ok", "results": results}


@router.get("/jobs/{job_id}", summary="Status of a background ingest job")
def job_status(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
