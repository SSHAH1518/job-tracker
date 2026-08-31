"""Job data model. Plain dataclass with dict (de)serialization so the same
shape round-trips through jobs.json and the JavaScript dashboard.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


class JobStatus:
    DISCOVERED = "DISCOVERED"      # freshly found, not yet analyzed
    ANALYZED = "ANALYZED"          # Claude has scored it
    QUEUED = "QUEUED"             # strong match, waiting to be applied
    SKIPPED = "SKIPPED"          # below threshold / filtered out
    APPLIED = "APPLIED"          # an application row exists
    ERROR = "ERROR"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


@dataclass
class Job:
    company: str
    title: str
    url: str
    location: str = ""
    source: str = "unknown"
    description: str = ""
    remote: bool = False
    employment_type: str = ""

    # Filled by Claude analysis
    match_score: Optional[int] = None
    recommendation: Optional[str] = None        # APPLY | MAYBE | SKIP
    matching_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    relevant_projects: list[str] = field(default_factory=list)
    relevant_experience: list[str] = field(default_factory=list)
    reason: str = ""
    requires_human_review: bool = False

    # Optional resume filename Claude Code prefers for this job (overrides the
    # deterministic keyword router in resume_service).
    resume_hint: str = ""

    status: str = JobStatus.DISCOVERED
    id: str = ""
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    analyzed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.make_id(self.company, self.title, self.url)

    @staticmethod
    def make_id(company: str, title: str, url: str) -> str:
        """Stable id used for deduplication. URL is the strongest signal;
        company+title is the fallback for the same job on multiple boards."""
        basis = url.strip().lower() or f"{_slug(company)}|{_slug(title)}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]

    @property
    def dedupe_key(self) -> str:
        return f"{_slug(self.company)}::{_slug(self.title)}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
