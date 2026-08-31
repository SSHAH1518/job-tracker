"""Application agent - prepares an application and STOPS before final submit.

No AI here. It fills deterministic profile fields, applies canned answers plus
any answers Claude Code has already drafted into data/answers/<job_id>.json,
uploads the selected resume, validates required fields, and hands off to you.

If some free-text questions are still unanswered it writes/updates the answers
stub file and reports `needs_claude` - you then run `/prepare <job_id>` in
Claude Code and re-run `python -m app.main prepare --job-id <job_id>`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents import answer_agent
from app.browser.browser import browser_session
from app.browser.forms import (
    collect_open_questions,
    fill_fields,
    find_missing_required,
    inspect_fields,
    locate_submit,
    map_profile_values,
    upload_resume,
)
from app.browser.sites import get_handler
from app.logging_setup import get_logger
from app.models import Job, JobStatus
from app.models.application import Application, ApplicationStatus, QuestionAnswer

log = get_logger(__name__)


@dataclass
class PreparedApplication:
    job_id: str
    company: str
    role: str
    application_url: str
    resume: str
    answers: list[QuestionAnswer] = field(default_factory=list)
    fields_filled: int = 0
    missing_required: list[str] = field(default_factory=list)
    needs_human: list[str] = field(default_factory=list)
    unanswered: list[str] = field(default_factory=list)
    stub_path: Optional[str] = None
    submit_found: bool = False
    error: Optional[str] = None

    @property
    def needs_claude(self) -> bool:
        return bool(self.unanswered)

    @property
    def ready_for_human_submit(self) -> bool:
        return self.error is None and not self.missing_required and not self.unanswered

    def to_application(self, match_score: Optional[int]) -> Application:
        notes = []
        if self.unanswered:
            notes.append("Awaiting Claude Code answers: " + "; ".join(self.unanswered))
        if self.missing_required:
            notes.append("Missing required: " + ", ".join(self.missing_required))
        if self.needs_human:
            notes.append("Needs human: " + "; ".join(self.needs_human))
        if self.error:
            notes.append("Error: " + self.error)
        return Application(
            job_id=self.job_id,
            company=self.company,
            role=self.role,
            status=ApplicationStatus.REVIEW,
            match_score=match_score,
            resume=self.resume,
            application_url=self.application_url,
            notes=" | ".join(notes),
            questions=[qa.to_dict() for qa in self.answers],
        )


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


async def prepare_application(
    job: Job,
    profile: dict[str, Any],
    resume_path: str,
    *,
    keep_open_seconds: int = 0,
) -> PreparedApplication:
    handler = get_handler(job.url)
    drafted = answer_agent.load_answers(job.id)
    prepared = PreparedApplication(
        job_id=job.id,
        company=job.company,
        role=job.title,
        application_url=job.url,
        resume=_basename(resume_path),
    )

    async with browser_session() as session:
        page = session.page
        try:
            log.info("[%s] opening application form for %s @ %s", handler.name, job.title, job.company)
            await handler.open_application_form(page, job.url)
            prepared.application_url = page.url

            fields = await inspect_fields(page)
            if not fields:
                prepared.error = "No form fields detected on the page."
                return prepared

            values = map_profile_values(fields, profile)
            values.update(await handler.extra_field_values(page, profile))
            prepared.fields_filled = await fill_fields(page, values)

            open_qs = collect_open_questions(fields, values)
            job_ctx = f"{job.title} at {job.company}. {job.reason}".strip()
            still_open: list[str] = []

            for qf in open_qs:
                label = qf.label or qf.key
                ans = answer_agent.canned_answer(label, profile) or answer_agent.match_answer(label, drafted)
                if ans and ans != "NEEDS_HUMAN":
                    source_generated = answer_agent.canned_answer(label, profile) is None
                    prepared.answers.append(
                        QuestionAnswer(question=label, answer=ans, generated=source_generated)
                    )
                    await fill_fields(page, {qf.selector: ans})
                elif ans == "NEEDS_HUMAN":
                    prepared.needs_human.append(label)
                else:
                    still_open.append(label)

            if still_open:
                prepared.unanswered = still_open
                prepared.stub_path = str(
                    answer_agent.write_stub(job.id, job.title, job.company, still_open, job_ctx)
                )

            if not await upload_resume(page, resume_path):
                prepared.needs_human.append("resume upload (no file input found)")

            prepared.missing_required = await find_missing_required(page)
            submit = await locate_submit(page)
            prepared.submit_found = submit is not None

            log.info(
                "Prepared %s @ %s: filled=%d unanswered=%d missing_required=%s (STOPPED before submit)",
                job.title, job.company, prepared.fields_filled,
                len(prepared.unanswered), prepared.missing_required,
            )

            if keep_open_seconds and not prepared.needs_claude:
                log.info("Leaving browser open %ds for human review…", keep_open_seconds)
                await page.wait_for_timeout(keep_open_seconds * 1000)

        except Exception as exc:  # noqa: BLE001
            prepared.error = str(exc)
            log.exception("prepare_application failed for %s @ %s", job.title, job.company)

    return prepared


def prepare_application_sync(
    job: Job, profile: dict[str, Any], resume_path: str, keep_open_seconds: int = 0
) -> PreparedApplication:
    return asyncio.run(
        prepare_application(job, profile, resume_path, keep_open_seconds=keep_open_seconds)
    )
