"""Controlled Git synchronization for the data/ directory.

The dashboard on GitHub Pages is static; this is the bridge that publishes fresh
JSON. Uses your local, already-authenticated git installation - no tokens in
code. A debounce prevents a commit per tiny change.
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from app.config import ROOT_DIR, settings
from app.logging_setup import get_logger

log = get_logger(__name__)

_debounce_timer: threading.Timer | None = None
_lock = threading.Lock()


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def is_git_repo() -> bool:
    return (ROOT_DIR / ".git").exists() and _run("rev-parse", "--git-dir").returncode == 0


def has_changes(paths: list[str] | None = None) -> bool:
    paths = paths or ["data/"]
    result = _run("status", "--porcelain", "--", *paths)
    return bool(result.stdout.strip())


def commit_and_push(message: str = "Update job data", paths: list[str] | None = None) -> bool:
    """Stage the given paths, commit, and push. Returns True if something was pushed."""
    if not is_git_repo():
        log.warning("Not a git repository - skipping sync. Run `git init` and add a remote.")
        return False
    paths = paths or ["data/"]

    if not has_changes(paths):
        log.info("git sync: nothing to commit")
        return False

    add = _run("add", "--", *paths)
    if add.returncode != 0:
        log.error("git add failed: %s", add.stderr.strip())
        return False

    commit = _run("commit", "-m", message)
    if commit.returncode != 0:
        log.error("git commit failed: %s", commit.stderr.strip() or commit.stdout.strip())
        return False
    log.info("git sync: committed (%s)", message)

    push = _run("push", settings.git_remote, settings.git_branch)
    if push.returncode != 0:
        log.error("git push failed: %s", push.stderr.strip())
        return False

    log.info("git sync: pushed to %s/%s", settings.git_remote, settings.git_branch)
    return True


def schedule_sync(message: str = "Update job data") -> None:
    """Debounced push: repeated calls within GIT_SYNC_DEBOUNCE collapse into one."""
    global _debounce_timer
    if not settings.git_auto_sync:
        log.debug("GIT_AUTO_SYNC disabled; not scheduling sync")
        return
    with _lock:
        if _debounce_timer is not None:
            _debounce_timer.cancel()
        _debounce_timer = threading.Timer(
            settings.git_sync_debounce, commit_and_push, kwargs={"message": message}
        )
        _debounce_timer.daemon = True
        _debounce_timer.start()
        log.info("git sync scheduled in %ds", settings.git_sync_debounce)


def flush_sync(message: str = "Update job data") -> bool:
    """Cancel any pending debounce and push immediately (use on shutdown)."""
    global _debounce_timer
    with _lock:
        if _debounce_timer is not None:
            _debounce_timer.cancel()
            _debounce_timer = None
    return commit_and_push(message=message)
