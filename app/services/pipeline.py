"""Discovery pipeline (deterministic - no AI).

discover -> normalize -> basic filters -> deduplicate -> store in jobs.json

New jobs land with status=DISCOVERED. The scoring step is done by Claude Code
(see `.claude/commands/analyze.md` and `app/services/analysis.py`), followed by
`python -m app.main requeue`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.config import settings
from app.logging_setup import get_logger
from app.models import Job
from app.services import git_sync, job_discovery, json_store

log = get_logger(__name__)

# Phrases that disqualify a job no matter where they appear in the body.
_HARD_BODY_BLOCK = (
    "immediate joiner", "immediate joining", "security clearance",
    "must be a us citizen", "us citizens only", "active clearance",
)


@dataclass
class PipelineResult:
    discovered: int = 0
    after_basic_filter: int = 0
    unique: int = 0
    added: int = 0
    pending_analysis: int = 0

    def summary(self) -> str:
        return (
            f"discovered={self.discovered} basic_ok={self.after_basic_filter} "
            f"unique={self.unique} added={self.added} pending_analysis={self.pending_analysis}"
        )


def _wb(hay: str, term: str) -> bool:
    """Word-boundary containment - so 'intern' does not match 'internet'."""
    return re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", hay) is not None


def _basic_match(job: Job, keywords: list[str], locations: list[str], exclude: list[str]) -> bool:
    title = job.title.lower()
    body = f"{job.title} {job.location} {job.description}".lower()

    if any(phrase in body for phrase in _HARD_BODY_BLOCK):
        return False
    # Seniority/junk exclusions are judged on the TITLE only - a new-grad JD that
    # merely mentions "work with senior engineers" should not be dropped.
    if any(_wb(title, term) for term in exclude):
        return False

    if keywords:
        in_title = any(_wb(title, kw) for kw in keywords)
        in_body = sum(1 for kw in keywords if _wb(body, kw))
        # Accept if a keyword is in the title, or at least two distinct keywords
        # appear anywhere (kills jobs that merely name a language in passing).
        if not (in_title or in_body >= 2):
            return False

    if locations:
        if job.remote:
            return True
        loc_hay = job.location.lower()
        if not any(loc.lower() in loc_hay or loc.lower() in body for loc in locations):
            return False

    return True


def _near_duplicate(a: Job, b: Job) -> bool:
    if a.dedupe_key == b.dedupe_key:
        return True
    same_company = SequenceMatcher(None, a.company.lower(), b.company.lower()).ratio() > 0.9
    same_title = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio() > 0.92
    return same_company and same_title


def deduplicate(jobs: list[Job], known: list[Job]) -> list[Job]:
    seen = list(known)
    unique: list[Job] = []
    for job in jobs:
        if any(_near_duplicate(job, other) for other in seen):
            continue
        seen.append(job)
        unique.append(job)
    return unique


def run_pipeline(*, sync: bool | None = None) -> PipelineResult:
    search_config = json_store.load_search_config()
    result = PipelineResult()

    raw = job_discovery.discover_jobs(search_config)
    result.discovered = len(raw)

    keywords = search_config.get("keywords", [])
    locations = search_config.get("locations", [])
    exclude = search_config.get("exclude_keywords", [])
    filtered = [j for j in raw if _basic_match(j, keywords, locations, exclude)]
    result.after_basic_filter = len(filtered)

    known = json_store.load_jobs()
    unique = deduplicate(filtered, known)
    result.unique = len(unique)

    if unique:
        added, skipped = json_store.upsert_jobs(unique)
        result.added = added
        log.info("pipeline: stored %d new jobs (%d dup skipped at write)", added, skipped)

    result.pending_analysis = sum(
        1 for j in json_store.load_jobs() if j.match_score is None
    )
    log.info("pipeline done: %s", result.summary())

    do_sync = settings.git_auto_sync if sync is None else sync
    if do_sync and result.added:
        git_sync.schedule_sync(message=f"Discovery: +{result.added} jobs")

    return result


def list_queue() -> list[Job]:
    from app.models import JobStatus

    return [j for j in json_store.load_jobs() if j.status == JobStatus.QUEUED]


_JOB_KEYS = set(Job.__dataclass_fields__)  # type: ignore[attr-defined]


def ingest_records(records: list[dict], default_source: str = "manual",
                   apply_filter: bool = False) -> tuple[int, int, int]:
    """Insert externally-supplied job dicts (e.g. from Gmail job-alert emails or
    a manual list) into jobs.json.

    Always drops anything matching `exclude_keywords`. If `apply_filter` is set,
    also applies the keyword/location filter (off by default - alert emails are
    already targeted by the alert you created).

    Returns (added, duplicates, rejected_by_filter).
    """
    search_config = json_store.load_search_config()
    keywords = search_config.get("keywords", [])
    locations = search_config.get("locations", [])
    exclude = search_config.get("exclude_keywords", [])

    jobs: list[Job] = []
    rejected = 0
    for rec in records:
        if not isinstance(rec, dict) or not rec.get("url") or not rec.get("title"):
            continue
        rec = {**rec}
        rec.setdefault("source", default_source)
        job = Job.from_dict({k: v for k, v in rec.items() if k in _JOB_KEYS})
        if not _basic_match(job, keywords if apply_filter else [], locations if apply_filter else [], exclude):
            rejected += 1
            continue
        jobs.append(job)

    known = json_store.load_jobs()
    unique = deduplicate(jobs, known)
    added, dup_at_write = json_store.upsert_jobs(unique) if unique else (0, 0)
    duplicates = (len(jobs) - len(unique)) + dup_at_write
    log.info("ingest_records[%s]: added=%d duplicates=%d rejected=%d",
             default_source, added, duplicates, rejected)
    return added, duplicates, rejected
