"""Analysis support - deterministic glue around the step Claude Code performs.

Claude Code (run by you) reads data/profile.json + data/jobs.json, scores each
DISCOVERED job, and writes these fields back onto the job in data/jobs.json:

    match_score           int 0-100
    recommendation        "APPLY" | "MAYBE" | "SKIP"
    matching_skills       [str]
    missing_skills        [str]
    relevant_projects     [str]     (names from the profile)
    relevant_experience   [str]     (names from the profile)
    reason                str       (1-3 sentences)
    requires_human_review bool
    status                "ANALYZED"

Then `python -m app.main requeue` runs `reconcile_queue()` which promotes strong
matches to QUEUED and everything else to SKIPPED, using the thresholds in .env.

`export_request()` writes a compact bundle for Claude Code to work from when you
don't want it to scan the whole jobs.json.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.config import DATA_DIR, settings
from app.logging_setup import get_logger
from app.models import Job, JobStatus
from app.services import json_store

log = get_logger(__name__)

ANALYSIS_FIELDS = (
    "match_score",
    "recommendation",
    "matching_skills",
    "missing_skills",
    "relevant_projects",
    "relevant_experience",
    "reason",
    "requires_human_review",
)

# Reused in the /analyze slash command documentation.
ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "match_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "recommendation": {"type": "string", "enum": ["APPLY", "MAYBE", "SKIP"]},
        "matching_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "relevant_projects": {"type": "array", "items": {"type": "string"}},
        "relevant_experience": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
        "requires_human_review": {"type": "boolean"},
    },
    "required": ["id", "match_score", "recommendation", "reason", "requires_human_review"],
    "additionalProperties": False,
}

REQUEST_FILE = "analysis_request.json"
RESULTS_FILE = "analysis_results.json"


@dataclass
class ReconcileResult:
    analyzed: int = 0
    queued: int = 0
    skipped: int = 0
    needs_review: int = 0
    unscored: int = 0

    def summary(self) -> str:
        return (
            f"analyzed={self.analyzed} queued={self.queued} skipped={self.skipped} "
            f"needs_review={self.needs_review} unscored={self.unscored}"
        )


def pending_jobs() -> list[Job]:
    """Jobs still waiting for Claude Code to score them."""
    return [
        j for j in json_store.load_jobs()
        if j.status == JobStatus.DISCOVERED or j.match_score is None
    ]


def _trim(text: str, limit: int = 4000) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + " …[truncated]"


def export_request(path: str | None = None) -> str:
    """Write {profile, jobs:[...]} for the pending jobs. Returns the file path."""
    profile = json_store.load_profile()
    jobs = pending_jobs()
    bundle = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "instructions": (
            "For each job, score it against the profile and return objects matching "
            "ANALYSIS_SCHEMA to data/analysis_results.json, then run "
            "`python -m app.main ingest-analysis`."
        ),
        "thresholds": {
            "min_match_score": settings.min_match_score,
            "queue_rule": "status QUEUED iff match_score >= min_match_score AND recommendation == 'APPLY'",
        },
        "profile": profile,
        "jobs": [
            {
                "id": j.id,
                "company": j.company,
                "title": j.title,
                "location": j.location,
                "remote": j.remote,
                "employment_type": j.employment_type,
                "url": j.url,
                "description": _trim(j.description),
            }
            for j in jobs
        ],
    }
    target = path or REQUEST_FILE
    json_store.save_json(target, bundle)
    log.info("Wrote analysis request for %d jobs -> %s", len(jobs), DATA_DIR / target)
    return str(DATA_DIR / target)


def apply_result(job: Job, result: dict[str, Any]) -> Job:
    """Copy scoring fields from a result dict onto a job (no queue decision yet)."""
    if "match_score" in result and result["match_score"] is not None:
        job.match_score = int(result["match_score"])
    if result.get("recommendation"):
        job.recommendation = result["recommendation"]
    for key in ("matching_skills", "missing_skills", "relevant_projects", "relevant_experience"):
        if isinstance(result.get(key), list):
            setattr(job, key, [str(x) for x in result[key]])
    if result.get("reason"):
        job.reason = str(result["reason"])
    job.requires_human_review = bool(result.get("requires_human_review", job.requires_human_review))
    job.status = JobStatus.ANALYZED
    job.analyzed_at = datetime.now().isoformat(timespec="seconds")
    return job


def ingest_results(path: str | None = None) -> ReconcileResult:
    """Read data/analysis_results.json ([{id, match_score, ...}]) and apply it."""
    raw = json_store.load_json(path or RESULTS_FILE, default=None)
    if raw is None:
        raise FileNotFoundError(
            f"{DATA_DIR / (path or RESULTS_FILE)} not found. Have Claude Code write it first."
        )
    results = raw.get("results", raw) if isinstance(raw, dict) else raw
    by_id = {r["id"]: r for r in results if isinstance(r, dict) and r.get("id")}

    jobs = json_store.load_jobs()
    applied = 0
    for i, job in enumerate(jobs):
        if job.id in by_id:
            jobs[i] = apply_result(job, by_id[job.id])
            applied += 1
    json_store.save_jobs(jobs)
    log.info("Ingested %d analysis results", applied)
    return reconcile_queue()


def reconcile_queue() -> ReconcileResult:
    """Deterministic guard: set QUEUED / SKIPPED from the scored fields + thresholds."""
    jobs = json_store.load_jobs()
    res = ReconcileResult()
    changed = False

    for job in jobs:
        if job.status in {JobStatus.APPLIED, JobStatus.ERROR}:
            continue
        if job.match_score is None:
            res.unscored += 1
            continue

        res.analyzed += 1
        if job.requires_human_review:
            res.needs_review += 1

        strong = job.match_score >= settings.min_match_score and job.recommendation == "APPLY"
        new_status = JobStatus.QUEUED if strong else JobStatus.SKIPPED
        if job.status != new_status:
            job.status = new_status
            changed = True
        if new_status == JobStatus.QUEUED:
            res.queued += 1
        else:
            res.skipped += 1

    if changed:
        json_store.save_jobs(jobs)
    log.info("reconcile_queue: %s", res.summary())
    return res
