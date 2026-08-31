"""Command-line entrypoint - the deterministic half of the job agent.

The AI half (scoring jobs, drafting answers, tailoring resumes) is done by
Claude Code on your Pro plan - see CLAUDE.md and .claude/commands/.

Typical loop
------------
    python -m app.main discover           # refresh data/jobs.json from job boards
    /analyze                              # (in Claude Code) score DISCOVERED jobs
    python -m app.main requeue            # promote strong matches to the queue
    python -m app.main queue              # see what's ready to apply to
    python -m app.main prepare --job-id <id>
    /prepare <id>                         # (in Claude Code) draft any open answers
    python -m app.main prepare --job-id <id>   # re-run to apply them
    python -m app.main sync               # publish JSON to GitHub Pages
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.config import DASHBOARD_DIR
from app.logging_setup import get_logger
from app.models import Job, JobStatus

log = get_logger("app.main")


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _find_job(job_id: str) -> Job | None:
    from app.services import json_store

    for j in json_store.load_jobs():
        if j.id == job_id or j.id.startswith(job_id):
            return j
    return None


# --- commands ------------------------------------------------------------

def cmd_discover(args: argparse.Namespace) -> int:
    from app.services.pipeline import run_pipeline

    result = run_pipeline(sync=args.sync or None)
    print(result.summary())
    if result.pending_analysis:
        print(
            f"\n{result.pending_analysis} job(s) need scoring. "
            "Run `/analyze` in Claude Code, then `python -m app.main requeue`."
        )
    return 0


def cmd_requeue(args: argparse.Namespace) -> int:
    from app.services.analysis import reconcile_queue

    res = reconcile_queue()
    print(res.summary())
    return 0


def cmd_analysis_request(args: argparse.Namespace) -> int:
    from app.services.analysis import export_request

    path = export_request()
    print(f"Wrote {path}")
    print("Point Claude Code at it with `/analyze`.")
    return 0


def cmd_ingest_analysis(args: argparse.Namespace) -> int:
    from app.services.analysis import ingest_results

    res = ingest_results(args.file)
    print(res.summary())
    return 0


def cmd_add_jobs(args: argparse.Namespace) -> int:
    """Insert jobs from a JSON file (used by /ingest-alerts and manual adds).

    File shape: {"jobs": [ {company, title, url, location?, description?, remote?,
    source?}, ... ]}  or a bare list of such objects.
    """
    import json as _json
    from pathlib import Path

    from app.services.pipeline import ingest_records

    raw = _json.loads(Path(args.file).read_text(encoding="utf-8"))
    records = raw.get("jobs", raw) if isinstance(raw, dict) else raw
    if not isinstance(records, list):
        log.error("%s must contain a list of job objects (or {\"jobs\": [...]})", args.file)
        return 2

    added, dups, rejected = ingest_records(
        records, default_source=args.source, apply_filter=args.filter
    )
    print(f"added={added} duplicates={dups} rejected_by_filter={rejected}")
    if added:
        print("Run `/analyze` in Claude Code, then `python -m app.main requeue`.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from collections import Counter

    from app.services import json_store

    jobs = json_store.load_jobs()
    apps = json_store.load_applications()
    jc = Counter(j.status for j in jobs)
    ac = Counter(a.status for a in apps)
    print(f"jobs: {len(jobs)}")
    for k in sorted(jc):
        print(f"  {k:<12} {jc[k]}")
    print(f"applications: {len(apps)}")
    for k in sorted(ac):
        print(f"  {k:<12} {ac[k]}")
    pending = sum(1 for j in jobs if j.match_score is None)
    if pending:
        print(f"\n{pending} job(s) await `/analyze`.")
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    from app.services.pipeline import list_queue

    queue = list_queue()
    if not queue:
        print("Application queue is empty.")
        return 0
    for j in queue:
        review = "  (needs human review)" if j.requires_human_review else ""
        print(f"[{j.id}] {j.title} @ {j.company}  score={j.match_score}{review}")
        print(f"       {j.url}")
    return 0


def cmd_select_resume(args: argparse.Namespace) -> int:
    from app.agents.resume_agent import choose_resume
    from app.services import json_store

    job = _find_job(args.job_id)
    if not job:
        log.error("No job with id %s", args.job_id)
        return 1
    profile = json_store.load_profile()
    print(f"{choose_resume(job, profile)}   (for {job.title} @ {job.company})")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    from app.agents.application_agent import prepare_application
    from app.agents.resume_agent import choose_resume
    from app.services import json_store, resume_service

    job = _find_job(args.job_id)
    if not job:
        log.error("No job with id %s", args.job_id)
        return 1

    profile = json_store.load_profile()
    resume_file = args.resume or job.resume_hint or choose_resume(job, profile)
    resume_full = str(resume_service.resume_path(resume_file))

    prepared = asyncio.run(
        prepare_application(job, profile, resume_full, keep_open_seconds=args.keep_open)
    )

    _print_json(
        {
            "job": f"{job.title} @ {job.company}",
            "resume": prepared.resume,
            "fields_filled": prepared.fields_filled,
            "answers": [qa.to_dict() for qa in prepared.answers],
            "unanswered": prepared.unanswered,
            "answers_stub": prepared.stub_path,
            "missing_required": prepared.missing_required,
            "needs_human": prepared.needs_human,
            "submit_found": prepared.submit_found,
            "error": prepared.error,
            "ready_for_human_submit": prepared.ready_for_human_submit,
        }
    )

    app_row = prepared.to_application(job.match_score)
    json_store.upsert_application(app_row)

    if prepared.needs_claude:
        print(
            f"\n{len(prepared.unanswered)} question(s) need answers. In Claude Code run:\n"
            f"    /prepare {job.id}\n"
            f"then re-run:  python -m app.main prepare --job-id {job.id}"
        )
        return 0

    job.status = JobStatus.APPLIED
    json_store.update_job(job)

    if args.sync:
        from app.services import git_sync

        git_sync.schedule_sync(message=f"Prepared application: {job.company} - {job.title}")

    print("\nApplication row saved (status=REVIEW). Review the form, then submit by hand.")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    from app.browser.browser import manual_login

    asyncio.run(manual_login(args.url, wait_seconds=args.wait))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from app.services import git_sync

    ok = git_sync.commit_and_push(message=args.message)
    return 0 if ok else 1


def cmd_dashboard(args: argparse.Namespace) -> int:
    import functools
    import http.server
    import socketserver

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(DASHBOARD_DIR.parent)
    )
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/dashboard/index.html"
        print(f"Serving dashboard at {url}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from app.services import scheduler

    scheduler.start(run_immediately=not args.no_immediate)
    return 0


# --- parser ------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="job-agent", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("discover", help="Discover -> filter -> dedupe -> store jobs.json (no AI)")
    d.add_argument("--sync", action="store_true", help="git commit+push data/ afterwards")
    d.set_defaults(func=cmd_discover)

    rq = sub.add_parser("requeue", help="Recompute QUEUED/SKIPPED from scores + thresholds")
    rq.set_defaults(func=cmd_requeue)

    aj = sub.add_parser("add-jobs", help="Insert jobs from a JSON file (LinkedIn/Naukri alert emails, manual)")
    aj.add_argument("--file", required=True)
    aj.add_argument("--source", default="manual", help="source tag for records that don't set their own")
    aj.add_argument("--filter", action="store_true", help="also apply the keyword/location filter")
    aj.set_defaults(func=cmd_add_jobs)

    ar = sub.add_parser("analysis-request", help="Export profile+pending jobs for Claude Code")
    ar.set_defaults(func=cmd_analysis_request)

    ia = sub.add_parser("ingest-analysis", help="Apply data/analysis_results.json to jobs.json")
    ia.add_argument("--file", default=None)
    ia.set_defaults(func=cmd_ingest_analysis)

    st = sub.add_parser("status", help="Show job/application counts by status")
    st.set_defaults(func=cmd_status)

    q = sub.add_parser("queue", help="List jobs in the application queue")
    q.set_defaults(func=cmd_queue)

    sr = sub.add_parser("select-resume", help="Deterministic best-resume pick for a job")
    sr.add_argument("--job-id", required=True)
    sr.set_defaults(func=cmd_select_resume)

    pr = sub.add_parser("prepare", help="Fill an application form and STOP before submit")
    pr.add_argument("--job-id", required=True)
    pr.add_argument("--resume", help="Override resume filename")
    pr.add_argument("--keep-open", type=int, default=0, help="Seconds to keep the browser open")
    pr.add_argument("--sync", action="store_true")
    pr.set_defaults(func=cmd_prepare)

    lg = sub.add_parser("login", help="Open a site and pause for manual login (persists session)")
    lg.add_argument("--url", required=True)
    lg.add_argument("--wait", type=int, default=180)
    lg.set_defaults(func=cmd_login)

    sy = sub.add_parser("sync", help="Commit + push data/ to GitHub")
    sy.add_argument("-m", "--message", default="Update job data")
    sy.set_defaults(func=cmd_sync)

    db = sub.add_parser("dashboard", help="Serve the static dashboard locally")
    db.add_argument("--port", type=int, default=8000)
    db.set_defaults(func=cmd_dashboard)

    rn = sub.add_parser("run", help="Start the discovery scheduler (foreground)")
    rn.add_argument("--no-immediate", action="store_true", help="Don't run once at startup")
    rn.set_defaults(func=cmd_run)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        log.exception("command failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
