"""Automatic job discovery via public aggregator APIs.

These need no per-company setup - point them at the candidate's keywords/locations
and they return a broad pool that the pipeline's keyword/location filter narrows.

Keyless (work out of the box):
  * themuse    - themuse.com public jobs API (good tech + India coverage)
  * remotive   - remotive.com remote jobs API
  * remoteok   - remoteok.com remote jobs API
  * arbeitnow  - arbeitnow.com job board API (remote + EU)
  * hn_hiring  - latest "Ask HN: Who is hiring?" thread via the Algolia API

Free API key (auto-skipped if the key is unset in .env):
  * adzuna     - api.adzuna.com (best India coverage) - ADZUNA_APP_ID / ADZUNA_APP_KEY
  * jooble     - jooble.org/api - JOOBLE_API_KEY

Every connector fails soft: an error in one is logged and the rest still run.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from app.config import settings
from app.logging_setup import get_logger
from app.models import Job
from app.services.net import get_json, html_to_text

log = get_logger(__name__)

_URL_RE = re.compile(r"https?://[^\s<>\"')]+")


def _kw_match(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


_GLOBAL_HINTS = (
    "worldwide", "world wide", "anywhere in the world", "work from anywhere",
    "fully remote", "globally remote", "remote, global", "global remote",
    "any time zone", "any timezone", "all time zones", "asia", "india", "apac",
)


def _geo_ok(text: str, location: str, locations: list[str]) -> bool:
    """Keep a remote role only if it looks reachable from India (named location
    match, or language that implies a global/APAC hire). Filters out the huge
    US-only / EU-only remote firehose."""
    blob = f"{location} {text}".lower()
    named = [l.lower() for l in locations if l.lower() not in {"remote", ""}]
    if any(n in blob for n in named):
        return True
    return any(h in blob for h in _GLOBAL_HINTS)


def _first_url(text: str) -> str:
    m = _URL_RE.search(text or "")
    return m.group(0).rstrip(".,)") if m else ""


# --- The Muse -----------------------------------------------------------

def from_themuse(keywords, locations, sc, limit, timeout) -> list[Job]:
    categories = sc.get("categories", ["Software Engineer", "Data Science", "Data and Analytics"])
    levels = sc.get("levels", ["Entry Level", "Internship"])
    muse_locations = sc.get("locations") or ["India", "Flexible / Remote"]
    pages = int(sc.get("pages", 3))

    jobs: list[Job] = []
    for page in range(pages):
        data = get_json(
            "https://www.themuse.com/api/public/jobs",
            timeout=timeout,
            params={
                "page": page,
                "category": categories,
                "level": levels,
                "location": muse_locations,
                "descending": "true",
            },
        )
        results = data.get("results", [])
        for item in results:
            loc = ", ".join(l.get("name", "") for l in item.get("locations", []))
            jobs.append(
                Job(
                    company=(item.get("company") or {}).get("name", "Unknown"),
                    title=item.get("name", "").strip(),
                    url=(item.get("refs") or {}).get("landing_page", ""),
                    location=loc,
                    source="themuse",
                    description=html_to_text(item.get("contents", "")),
                    remote="remote" in loc.lower() or "flexible" in loc.lower(),
                )
            )
        if page + 1 >= data.get("page_count", 0) or not results:
            break
        if len(jobs) >= limit:
            break
    return jobs[:limit]


# --- Remotive ---------------------------------------------------------

def from_remotive(keywords, locations, sc, limit, timeout) -> list[Job]:
    searches = sc.get("searches") or (keywords[:5] or ["software"])
    per = min(int(sc.get("per_search", 50)), 100)

    seen: set[str] = set()
    jobs: list[Job] = []
    for term in searches:
        data = get_json(
            "https://remotive.com/api/remote-jobs",
            timeout=timeout,
            params={"search": term, "limit": per},
        )
        for item in data.get("jobs", []):
            url = item.get("url", "")
            if url in seen:
                continue
            seen.add(url)
            jobs.append(
                Job(
                    company=item.get("company_name", "Unknown"),
                    title=item.get("title", "").strip(),
                    url=url,
                    location=item.get("candidate_required_location", "Remote"),
                    source="remotive",
                    description=html_to_text(item.get("description", "")),
                    remote=True,
                    employment_type=item.get("job_type", "") or "",
                )
            )
        if len(jobs) >= limit:
            break
    return jobs[:limit]


# --- RemoteOK ---------------------------------------------------------

def from_remoteok(keywords, locations, sc, limit, timeout) -> list[Job]:
    data = get_json("https://remoteok.com/api", timeout=timeout)
    jobs: list[Job] = []
    for item in data:
        if not isinstance(item, dict) or not (item.get("position") or item.get("title")):
            continue  # first element is a legal/metadata notice
        title = item.get("position") or item.get("title", "")
        tags = " ".join(item.get("tags", []) or [])
        blob = f"{title} {tags} {item.get('description', '')}"
        if not _kw_match(blob, keywords):
            continue
        jobs.append(
            Job(
                company=item.get("company", "Unknown"),
                title=title.strip(),
                url=item.get("url") or item.get("apply_url", ""),
                location=item.get("location", "Remote") or "Remote",
                source="remoteok",
                description=html_to_text(item.get("description", "")) or tags,
                remote=True,
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


# --- Arbeitnow --------------------------------------------------------

def from_arbeitnow(keywords, locations, sc, limit, timeout) -> list[Job]:
    pages = int(sc.get("pages", 3))
    geo_filter = bool(sc.get("geo_filter", True))
    url = "https://www.arbeitnow.com/api/job-board-api"
    jobs: list[Job] = []
    for _ in range(pages):
        data = get_json(url, timeout=timeout)
        for item in data.get("data", []):
            blob = f"{item.get('title', '')} {' '.join(item.get('tags', []) or [])} {item.get('description', '')}"
            if not _kw_match(blob, keywords):
                continue
            if geo_filter and not _geo_ok(blob, item.get("location", ""), locations):
                continue
            jobs.append(
                Job(
                    company=item.get("company_name", "Unknown"),
                    title=item.get("title", "").strip(),
                    url=item.get("url", ""),
                    location=item.get("location", "") or "",
                    source="arbeitnow",
                    description=html_to_text(item.get("description", "")),
                    remote=bool(item.get("remote")),
                    employment_type=", ".join(item.get("job_types", []) or []),
                )
            )
        nxt = (data.get("links") or {}).get("next")
        if not nxt or nxt == url or len(jobs) >= limit:
            break
        url = nxt
    return jobs[:limit]


# --- Hacker News "Who is hiring?" -----------------------------------------

def from_hn_hiring(keywords, locations, sc, limit, timeout) -> list[Job]:
    # search_by_date => newest first, so the first "Who is hiring?" hit is current.
    search = get_json(
        "https://hn.algolia.com/api/v1/search_by_date",
        timeout=timeout,
        params={"tags": "story,author_whoishiring", "query": "who is hiring", "hitsPerPage": 20},
    )
    hits = [
        h for h in search.get("hits", [])
        if "who is hiring" in (h.get("title", "").lower())
        and "wants to be hired" not in (h.get("title", "").lower())
    ]
    if not hits:
        return []
    thread = max(hits, key=lambda h: h.get("created_at_i", 0))
    log.info("hn_hiring: using thread %r (%s)", thread.get("title"), thread.get("created_at"))
    item = get_json(
        f"https://hn.algolia.com/api/v1/items/{thread['objectID']}", timeout=timeout
    )

    title_terms = sc.get("title_terms") or [
        "software engineer", "backend engineer", "back-end engineer", "frontend engineer",
        "full stack", "full-stack", "sde", "data scientist", "data engineer",
        "machine learning", "ml engineer", "ai engineer", "platform engineer",
        "software developer", "backend developer", "python developer", "research engineer",
        "engineer", "developer", "intern",
    ]
    only_remote = bool(sc.get("only_remote", True))
    geo_filter = bool(sc.get("geo_filter", True))
    jobs: list[Job] = []
    for child in item.get("children", []):
        raw = child.get("text") or ""
        if not raw:
            continue
        text = html_to_text(raw)
        if geo_filter and not _geo_ok(text, "", locations):
            continue
        first_line = re.split(r"[.\n]", text, maxsplit=1)[0].strip()

        # HN top lines are usually "Company | Role | Location | ..." (pipe or 2+ spaces)
        segments = [s.strip(" –—-:") for s in re.split(r"\s*[|•·]\s*|\s{2,}", first_line) if s.strip()]
        if not segments:
            continue
        company = segments[0][:80] or "HN (Who is hiring)"

        role = ""
        for seg in segments[1:]:
            if any(term in seg.lower() for term in title_terms):
                role = seg
                break
        if not role and " - " in first_line:
            parts = [p.strip() for p in first_line.split(" - ")]
            role = next((p for p in parts if any(t in p.lower() for t in title_terms)), "")
        if not role:
            continue  # no recognisable engineering role on the headline - skip

        remote = "remote" in text.lower()
        if only_remote and not remote:
            continue
        loc_seg = next(
            (s for s in segments[1:] if s != role and re.search(r"remote|onsite|hybrid|,|USA|US\b|EU\b|UK\b", s, re.I)),
            "",
        )
        jobs.append(
            Job(
                company=company,
                title=role[:140],
                url=_first_url(raw) or f"https://news.ycombinator.com/item?id={child.get('id')}",
                location=loc_seg or ("Remote" if remote else "See post"),
                source="hn_hiring",
                description=text[:4000],
                remote=remote,
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


# --- Adzuna (key-gated) ------------------------------------------------

def from_adzuna(keywords, locations, sc, limit, timeout) -> list[Job]:
    if not (settings.adzuna_app_id and settings.adzuna_app_key):
        log.info("adzuna: ADZUNA_APP_ID / ADZUNA_APP_KEY not set - skipping")
        return []
    country = sc.get("country", "in")
    pages = int(sc.get("pages", 3))
    max_days_old = int(sc.get("max_days_old", 30))
    whats = sc.get("queries") or [
        "software engineer", "data scientist", "machine learning engineer",
        "graduate engineer", "backend developer",
    ]
    where = sc.get("where", "")

    jobs: list[Job] = []
    for what in whats:
        for page in range(1, pages + 1):
            data = get_json(
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}",
                timeout=timeout,
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "results_per_page": 50,
                    "what": what,
                    "where": where,
                    "max_days_old": max_days_old,
                    "content-type": "application/json",
                },
            )
            results = data.get("results", [])
            for item in results:
                jobs.append(
                    Job(
                        company=(item.get("company") or {}).get("display_name", "Unknown"),
                        title=item.get("title", "").strip(),
                        url=item.get("redirect_url", ""),
                        location=(item.get("location") or {}).get("display_name", ""),
                        source="adzuna",
                        description=html_to_text(item.get("description", "")),
                        remote="remote" in (item.get("title", "") + item.get("description", "")).lower(),
                        employment_type=item.get("contract_time", "") or "",
                    )
                )
            if not results or len(jobs) >= limit:
                break
        if len(jobs) >= limit:
            break
    return jobs[:limit]


# --- Jooble (key-gated) ---------------------------------------------------

def from_jooble(keywords, locations, sc, limit, timeout) -> list[Job]:
    if not settings.jooble_api_key:
        log.info("jooble: JOOBLE_API_KEY not set - skipping")
        return []
    kw = sc.get("keywords") or " ".join(keywords[:6]) or "software engineer"
    where = sc.get("location") or (locations[0] if locations else "India")
    pages = int(sc.get("pages", 2))

    jobs: list[Job] = []
    for page in range(1, pages + 1):
        data = get_json(
            f"https://jooble.org/api/{settings.jooble_api_key}",
            timeout=timeout,
            method="POST",
            json_body={"keywords": kw, "location": where, "page": str(page)},
        )
        results = data.get("jobs", [])
        for item in results:
            jobs.append(
                Job(
                    company=item.get("company", "Unknown") or "Unknown",
                    title=item.get("title", "").strip(),
                    url=item.get("link", ""),
                    location=item.get("location", "") or "",
                    source="jooble",
                    description=html_to_text(item.get("snippet", "")),
                    remote="remote" in (item.get("title", "") + item.get("location", "")).lower(),
                    employment_type=item.get("type", "") or "",
                )
            )
        if not results or len(jobs) >= limit:
            break
    return jobs[:limit]


_RUNNERS: list[tuple[str, Callable]] = [
    ("themuse", from_themuse),
    ("remotive", from_remotive),
    ("remoteok", from_remoteok),
    ("arbeitnow", from_arbeitnow),
    ("hn_hiring", from_hn_hiring),
    ("adzuna", from_adzuna),
    ("jooble", from_jooble),
]


def discover(
    keywords: list[str],
    locations: list[str],
    cfg: dict[str, Any],
    limit: int,
    timeout: int,
) -> list[Job]:
    jobs: list[Job] = []
    for name, fn in _RUNNERS:
        sc = cfg.get(name, {})
        if not sc.get("enabled", False):
            continue
        try:
            got = fn(keywords, locations, sc, limit, timeout)
        except Exception as exc:  # noqa: BLE001
            log.warning("aggregator[%s] failed: %s", name, exc)
            continue
        log.info("aggregator[%s]: %d jobs", name, len(got))
        jobs += got
    return jobs
