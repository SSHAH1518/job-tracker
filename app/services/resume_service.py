"""Resume selection - deterministic keyword routing over the PDFs in data/resumes/."""
from __future__ import annotations

from pathlib import Path

from app.config import RESUMES_DIR
from app.logging_setup import get_logger
from app.models import Job

log = get_logger(__name__)

MASTER_RESUME = "master_resume.pdf"

# filename -> keywords that route a job to it (checked against title + description)
RESUME_ROUTES: dict[str, list[str]] = {
    "machine_learning.pdf": [
        "machine learning", "ml engineer", "mle", "deep learning", "nlp",
        "computer vision", "pytorch", "tensorflow", "llm", "ai engineer", "research",
    ],
    "data_science.pdf": [
        "data scientist", "data science", "analytics", "statistician",
        "experimentation", "a/b testing", "data analyst",
    ],
    "software_engineering.pdf": [
        "software engineer", "backend", "full stack", "full-stack", "frontend",
        "platform", "infrastructure", "sde", "developer", "api", "services",
    ],
}


def available_resumes() -> list[str]:
    if not RESUMES_DIR.exists():
        return []
    return sorted(p.name for p in RESUMES_DIR.glob("*.pdf"))


def resume_path(filename: str) -> Path:
    return RESUMES_DIR / filename


def route(job: Job) -> tuple[str, list[str]]:
    """Return (best_choice, all_plausible_choices).

    best_choice is guaranteed to exist on disk (falls back to master, then to
    whatever single resume is present).
    """
    present = set(available_resumes())
    text = f"{job.title}\n{job.description}".lower()

    scored: list[tuple[int, str]] = []
    for filename, keywords in RESUME_ROUTES.items():
        if filename not in present:
            continue
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scored.append((hits, filename))

    scored.sort(reverse=True)
    plausible = [f for _, f in scored]

    if plausible:
        best = plausible[0]
    elif MASTER_RESUME in present:
        best = MASTER_RESUME
    elif present:
        best = sorted(present)[0]
    else:
        raise FileNotFoundError("No resume PDFs in data/resumes/.")

    # Always allow master as a tie-break candidate for the LLM step
    candidates = plausible or []
    if MASTER_RESUME in present and MASTER_RESUME not in candidates:
        candidates = candidates + [MASTER_RESUME]
    return best, candidates or [best]
