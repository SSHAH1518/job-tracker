"""Resume selection - deterministic keyword routing.

Claude Code can override the choice by editing the job's `resume` hint in
data/jobs.json or by passing `--resume` to `prepare`. Tailored-resume generation
from the master profile is a later milestone; `tailoring_prompt` returns the
context to hand Claude Code for that.
"""
from __future__ import annotations

import json
from typing import Any

from app.logging_setup import get_logger
from app.models import Job
from app.services import resume_service

log = get_logger(__name__)


def choose_resume(job: Job, profile: dict[str, Any] | None = None) -> str:
    available = resume_service.available_resumes()
    if not available:
        raise FileNotFoundError(
            "No resume PDFs found in data/resumes/. Add at least master_resume.pdf."
        )
    best, _candidates = resume_service.route(job)
    log.info("Resume for %s @ %s -> %s", job.title, job.company, best)
    return best


def tailoring_prompt(job: Job, profile: dict[str, Any]) -> str:
    """Text to give Claude Code when you want tailoring notes for a resume."""
    return (
        "Suggest 3-5 concrete, TRUTHFUL tweaks to emphasise on the resume for this "
        "application (reorder bullets, surface a project, mirror the job's wording). "
        "Never fabricate.\n\n"
        f"PROFILE:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"JOB: {job.title} @ {job.company}\n{(job.description or '')[:3000]}"
    )
