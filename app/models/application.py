"""Application data model - one row per job we prepared/submitted."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Optional


class ApplicationStatus:
    # Kept in sync with the <select> in dashboard/index.html
    DISCOVERED = "DISCOVERED"
    REVIEW = "REVIEW"           # form prepared, waiting for human to submit
    APPLIED = "APPLIED"
    OA = "OA"                   # online assessment
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"


@dataclass
class QuestionAnswer:
    question: str
    answer: str
    generated: bool = True     # False if taken verbatim from profile.answers

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Application:
    job_id: str
    company: str
    role: str
    status: str = ApplicationStatus.REVIEW
    match_score: Optional[int] = None
    resume: str = ""                       # exact filename used
    application_url: str = ""
    notes: str = ""
    questions: list[dict[str, Any]] = field(default_factory=list)

    id: str = ""
    date_applied: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"app_{self.job_id}"

    def mark_applied(self) -> None:
        self.status = ApplicationStatus.APPLIED
        self.date_applied = date.today().isoformat()
        self.touch()

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Application":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})
