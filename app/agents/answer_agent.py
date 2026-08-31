"""Application answers - deterministic only.

Free-text answers are drafted by Claude Code, not by this module. The flow:

  1. `application_agent` fills what it can from `profile.answers` (canned) and
     writes the questions it could NOT answer to data/answers/<job_id>.json with
     empty "answer" fields.
  2. You run `/prepare <job_id>` in Claude Code; it fills those answers
     truthfully from the profile (or writes "NEEDS_HUMAN").
  3. You re-run `python -m app.main prepare --job-id <job_id>`; this module loads
     the filled file and the form is completed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import DATA_DIR
from app.logging_setup import get_logger

log = get_logger(__name__)

ANSWERS_DIR = DATA_DIR / "answers"

# question substring -> profile.answers key
_CANNED_MAP: dict[str, str] = {
    "relocate": "willing_to_relocate",
    "notice period": "notice_period",
    "when can you start": "earliest_start_date",
    "start date": "earliest_start_date",
    "available to start": "earliest_start_date",
    "current ctc": "current_ctc",
    "current salary": "current_ctc",
    "expected ctc": "expected_ctc",
    "expected salary": "expected_ctc",
    "salary expectation": "expected_ctc",
    "graduation": "graduation_date",
    "sponsorship": "sponsorship_needed",
    "require visa": "sponsorship_needed",
    "gender": "gender",
    "race": "race_ethnicity",
    "ethnicity": "race_ethnicity",
    "veteran": "veteran_status",
    "disability": "disability_status",
}

_PLACEHOLDER = re.compile(r"^\s*(todo|needs_human|)\s*$", re.I)


def _normalize(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", q.lower()).strip()


def canned_answer(question: str, profile: dict[str, Any]) -> str | None:
    q = question.lower()
    answers = profile.get("answers", {})
    for needle, key in _CANNED_MAP.items():
        if needle in q and answers.get(key) and not _PLACEHOLDER.match(str(answers[key])):
            return str(answers[key])
    return None


def answers_path(job_id: str) -> Path:
    return ANSWERS_DIR / f"{job_id}.json"


def load_answers(job_id: str) -> dict[str, str]:
    """Return {normalized_question: answer} for answers already drafted, skipping
    empty / TODO / NEEDS_HUMAN entries."""
    path = answers_path(job_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("answers file %s is not valid JSON", path)
        return {}
    out: dict[str, str] = {}
    for item in data.get("questions", []):
        ans = str(item.get("answer", "")).strip()
        if ans and not _PLACEHOLDER.match(ans):
            out[_normalize(item.get("question", ""))] = ans
    return out


def match_answer(question: str, drafted: dict[str, str]) -> str | None:
    key = _normalize(question)
    if key in drafted:
        return drafted[key]
    # loose containment match
    for k, v in drafted.items():
        if k and (k in key or key in k):
            return v
    return None


def write_stub(job_id: str, job_title: str, company: str, questions: list[str],
               job_context: str = "") -> Path:
    """Write/merge the answers stub file for Claude Code to fill."""
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    path = answers_path(job_id)

    existing: dict[str, str] = {}
    if path.exists():
        try:
            for item in json.loads(path.read_text(encoding="utf-8")).get("questions", []):
                existing[_normalize(item["question"])] = item.get("answer", "")
        except Exception:  # noqa: BLE001
            pass

    payload = {
        "job_id": job_id,
        "job": f"{job_title} @ {company}",
        "job_context": job_context,
        "instructions": (
            "Fill each empty \"answer\" using ONLY facts from data/profile.json. "
            "Never fabricate. If the profile lacks the info, put \"NEEDS_HUMAN\". "
            "Keep short fields to one line; essays to 3-5 sentences, first person."
        ),
        "questions": [
            {"question": q, "answer": existing.get(_normalize(q), "")}
            for q in questions
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote answers stub with %d question(s) -> %s", len(questions), path)
    return path
