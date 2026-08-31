"""Central configuration. Reads .env once and exposes typed settings.

Nothing secret is hard-coded here - values come from environment variables
(loaded from a local .env file that is git-ignored).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


# --- Paths ------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RESUMES_DIR = DATA_DIR / "resumes"
DASHBOARD_DIR = ROOT_DIR / "dashboard"
LOGS_DIR = ROOT_DIR / "logs"

JOBS_FILE = "jobs.json"
APPLICATIONS_FILE = "applications.json"
PROFILE_FILE = "profile.json"
SEARCH_CONFIG_FILE = "search_config.json"


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Pipeline thresholds
    min_match_score: int = _get_int("MIN_MATCH_SCORE", 75)
    min_basic_match: float = _get_float("MIN_BASIC_MATCH", 0.12)

    # Git sync
    git_auto_sync: bool = _get_bool("GIT_AUTO_SYNC", False)
    git_remote: str = os.getenv("GIT_REMOTE", "origin")
    git_branch: str = os.getenv("GIT_BRANCH", "main")
    git_sync_debounce: int = _get_int("GIT_SYNC_DEBOUNCE", 30)

    # Browser
    browser_headless: bool = _get_bool("BROWSER_HEADLESS", False)
    browser_profile_dir: str = os.getenv("BROWSER_PROFILE_DIR", "data/browser_profile")

    # Scheduler
    discovery_interval_hours: int = _get_int("DISCOVERY_INTERVAL_HOURS", 4)

    # Optional aggregator API keys (both have free tiers; auto-skipped if unset)
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
    jooble_api_key: str = os.getenv("JOOBLE_API_KEY", "")

    @property
    def browser_profile_path(self) -> Path:
        p = Path(self.browser_profile_dir)
        return p if p.is_absolute() else ROOT_DIR / p


settings = Settings()
