"""JSON storage with atomic writes plus typed helpers for our specific files.

Atomic write: serialize to a sibling .tmp file, then os.replace() it over the
target. os.replace is atomic on the same filesystem, so a crash mid-write
leaves the previous good file intact.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from app.config import (
    APPLICATIONS_FILE,
    DATA_DIR,
    JOBS_FILE,
    PROFILE_FILE,
    SEARCH_CONFIG_FILE,
)
from app.models import Application, Job

_LOCK = threading.RLock()


# --- Generic --------------------------------------------------------------

def _path(filename: str) -> Path:
    p = Path(filename)
    return p if p.is_absolute() else DATA_DIR / p


def load_json(filename: str, default: Any | None = None) -> Any:
    path = _path(filename)
    if not path.exists():
        return {} if default is None else default
    with _LOCK:
        return json.loads(path.read_text(encoding="utf-8"))


def save_json(filename: str, data: Any) -> None:
    path = _path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _LOCK:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)


# --- Profile / search config -------------------------------------------------

def load_profile() -> dict[str, Any]:
    return load_json(PROFILE_FILE, default={})


def load_search_config() -> dict[str, Any]:
    return load_json(SEARCH_CONFIG_FILE, default={})


# --- Jobs ------------------------------------------------------------------

def load_jobs() -> list[Job]:
    raw = load_json(JOBS_FILE, default={"jobs": []})
    return [Job.from_dict(j) for j in raw.get("jobs", [])]


def save_jobs(jobs: list[Job]) -> None:
    save_json(JOBS_FILE, {"jobs": [j.to_dict() for j in jobs]})


def upsert_jobs(new_jobs: list[Job]) -> tuple[int, int]:
    """Merge new_jobs into jobs.json. Returns (added, skipped_duplicates)."""
    with _LOCK:
        existing = load_jobs()
        by_id = {j.id: j for j in existing}
        by_key = {j.dedupe_key: j for j in existing}

        added = 0
        skipped = 0
        for job in new_jobs:
            if job.id in by_id or job.dedupe_key in by_key:
                skipped += 1
                continue
            existing.append(job)
            by_id[job.id] = job
            by_key[job.dedupe_key] = job
            added += 1

        if added:
            save_jobs(existing)
        return added, skipped


def update_job(job: Job) -> None:
    with _LOCK:
        jobs = load_jobs()
        for i, existing in enumerate(jobs):
            if existing.id == job.id:
                jobs[i] = job
                break
        else:
            jobs.append(job)
        save_jobs(jobs)


# --- Applications -----------------------------------------------------------

def load_applications() -> list[Application]:
    raw = load_json(APPLICATIONS_FILE, default={"applications": []})
    return [Application.from_dict(a) for a in raw.get("applications", [])]


def save_applications(apps: list[Application]) -> None:
    save_json(APPLICATIONS_FILE, {"applications": [a.to_dict() for a in apps]})


def upsert_application(app: Application) -> None:
    with _LOCK:
        apps = load_applications()
        for i, existing in enumerate(apps):
            if existing.id == app.id or existing.job_id == app.job_id:
                app.updated_at = existing.updated_at
                app.touch()
                apps[i] = app
                save_applications(apps)
                return
        apps.append(app)
        save_applications(apps)
