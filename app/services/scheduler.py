"""Scheduler - runs the deterministic discovery pipeline on an interval.

Scoring is NOT automated (it needs Claude Code, which is interactive); the
scheduler just refreshes jobs.json and logs how many jobs await `/analyze`.
Uses APScheduler's blocking scheduler so `python -m app.main run` stays in the
foreground. Windows Task Scheduler can launch that command at login.
"""
from __future__ import annotations

import signal

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.logging_setup import get_logger
from app.services import git_sync
from app.services.pipeline import run_pipeline

log = get_logger(__name__)


def _job() -> None:
    log.info("scheduled run: starting discovery")
    try:
        result = run_pipeline()
        log.info("scheduled run complete: %s", result.summary())
        if result.pending_analysis:
            log.info(
                "%d job(s) await scoring - run `/analyze` in Claude Code, then "
                "`python -m app.main requeue`.",
                result.pending_analysis,
            )
    except Exception:  # noqa: BLE001
        log.exception("scheduled discovery run failed")


def start(run_immediately: bool = True) -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _job,
        trigger=IntervalTrigger(hours=settings.discovery_interval_hours),
        id="discovery",
        max_instances=1,
        coalesce=True,
    )

    if run_immediately:
        scheduler.add_job(_job, id="discovery_now")

    def _shutdown(signum, frame):  # noqa: ANN001
        log.info("shutting down scheduler (signal %s)", signum)
        git_sync.flush_sync(message="Scheduler shutdown sync")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    try:
        signal.signal(signal.SIGTERM, _shutdown)
    except (AttributeError, ValueError):  # SIGTERM not available on some Windows setups
        pass

    log.info(
        "scheduler started: every %dh (run_immediately=%s)",
        settings.discovery_interval_hours, run_immediately,
    )
    scheduler.start()
