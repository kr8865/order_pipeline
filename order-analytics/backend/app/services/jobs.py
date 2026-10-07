"""Async processing (bonus): run large ingests in the background and poll their status."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def create_job(kind: str, filename: str | None) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {"job_id": job_id, "kind": kind, "filename": filename, "status": "queued",
                         "created_at": datetime.now(timezone.utc).isoformat(), "result": None, "error": None}
    return job_id


def run_job(job_id: str, fn, *args) -> None:
    with _lock:
        _jobs[job_id]["status"] = "running"
    try:
        result = fn(*args)
        with _lock:
            _jobs[job_id].update(status="completed", result=result)
    except Exception as exc:  # surfaced to the client via GET /ingest/jobs/{id}
        with _lock:
            _jobs[job_id].update(status="failed", error=str(exc))


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None
