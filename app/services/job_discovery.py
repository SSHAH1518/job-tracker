"""Job discovery - pulls raw postings from every configured source and returns
normalized :class:`Job` objects (status=DISCOVERED, no score yet).

Two groups of sources, all controlled by data/search_config.json:

`aggregators` (automatic - no per-company setup, this is the default engine):
  * themuse, remotive, remoteok, arbeitnow, hn_hiring  - keyless
  * adzuna, jooble                                      - free API key via .env
  (implemented in app/services/aggregators.py)

`sources` (targeted - you name specific boards / pages / URLs):
  * greenhouse  - boards-api.greenhouse.io public JSON
  * lever       - api.lever.co public JSON
  * ashby       - api.ashbyhq.com posting-api public JSON
  * rss         - any RSS/Atom job feed (feedparser)
  * seed_urls   - explicit job posting URLs, fetched + text-extracted
  * html_pages  - generic careers pages scraped with Playwright

Network/parse failures for one source are logged and skipped; the others run.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.logging_setup import get_logger
from app.models import Job

log = get_logger(__name__)

_DEFAULT_UA = "job-agent/1.0 (+personal job search automation)"


def _cfg(search_config: dict[str, Any]) -> tuple[dict, dict, int, int, str]:
    sources = search_config.get("sources", {})
    limits = search_config.get("limits", {})
    return (
        sources,
        limits,
        int(limits.get("max_jobs_per_source", 60)),
        int(limits.get("request_timeout_seconds", 20)),
        limits.get("user_agent", _DEFAULT_UA),
    )


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _get_json(url: str, timeout: int, ua: str) -> Any:
    resp = requests.get(url, headers={"User-Agent": ua, "Accept": "application/json"}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# --- Greenhouse ------------------------------------------------------------

def from_greenhouse(boards: Iterable[str], limit: int, timeout: int, ua: str) -> list[Job]:
    jobs: list[Job] = []
    for token in boards:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            data = _get_json(url, timeout, ua)
        except Exception as exc:  # noqa: BLE001
            log.warning("greenhouse[%s] failed: %s", token, exc)
            continue
        for item in data.get("jobs", [])[:limit]:
            loc = (item.get("location") or {}).get("name", "")
            jobs.append(
                Job(
                    company=token.replace("-", " ").title(),
                    title=item.get("title", "").strip(),
                    url=item.get("absolute_url", ""),
                    location=loc,
                    source="greenhouse",
                    description=_html_to_text(item.get("content", "")),
                    remote="remote" in loc.lower(),
                )
            )
        log.info("greenhouse[%s]: %d jobs", token, min(len(data.get("jobs", [])), limit))
    return jobs


# --- Lever ---------------------------------------------------------------

def from_lever(companies: Iterable[str], limit: int, timeout: int, ua: str) -> list[Job]:
    jobs: list[Job] = []
    for slug in companies:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            data = _get_json(url, timeout, ua)
        except Exception as exc:  # noqa: BLE001
            log.warning("lever[%s] failed: %s", slug, exc)
            continue
        for item in data[:limit]:
            cats = item.get("categories", {}) or {}
            loc = cats.get("location", "") or ""
            jobs.append(
                Job(
                    company=slug.replace("-", " ").title(),
                    title=item.get("text", "").strip(),
                    url=item.get("hostedUrl", ""),
                    location=loc,
                    source="lever",
                    description=item.get("descriptionPlain")
                    or _html_to_text(item.get("description", "")),
                    remote="remote" in loc.lower(),
                    employment_type=cats.get("commitment", "") or "",
                )
            )
        log.info("lever[%s]: %d jobs", slug, min(len(data), limit))
    return jobs


# --- Ashby -------------------------------------------------------------

def from_ashby(orgs: Iterable[str], limit: int, timeout: int, ua: str) -> list[Job]:
    jobs: list[Job] = []
    for org in orgs:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true"
        try:
            data = _get_json(url, timeout, ua)
        except Exception as exc:  # noqa: BLE001
            log.warning("ashby[%s] failed: %s", org, exc)
            continue
        for item in data.get("jobs", [])[:limit]:
            loc = item.get("location", "") or ""
            jobs.append(
                Job(
                    company=org.replace("-", " ").title(),
                    title=item.get("title", "").strip(),
                    url=item.get("jobUrl") or item.get("applyUrl", ""),
                    location=loc,
                    source="ashby",
                    description=item.get("descriptionPlain")
                    or _html_to_text(item.get("descriptionHtml", "")),
                    remote=bool(item.get("isRemote")) or "remote" in loc.lower(),
                    employment_type=item.get("employmentType", "") or "",
                )
            )
        log.info("ashby[%s]: %d jobs", org, min(len(data.get("jobs", [])), limit))
    return jobs


# --- RSS ---------------------------------------------------------------

def from_rss(feeds: Iterable[str], limit: int, timeout: int, ua: str) -> list[Job]:
    try:
        import feedparser
    except ImportError:  # pragma: no cover
        log.warning("feedparser not installed; skipping RSS")
        return []

    jobs: list[Job] = []
    for feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url, agent=ua)
        except Exception as exc:  # noqa: BLE001
            log.warning("rss[%s] failed: %s", feed_url, exc)
            continue
        source_title = (parsed.feed.get("title") if parsed.feed else "") or "rss"
        for entry in parsed.entries[:limit]:
            title = entry.get("title", "").strip()
            company = ""
            # WeWorkRemotely-style "Company: Role"
            if ":" in title:
                head, _, tail = title.partition(":")
                if len(head) < 40:
                    company, title = head.strip(), tail.strip()
            summary = _html_to_text(entry.get("summary", "") or entry.get("description", ""))
            jobs.append(
                Job(
                    company=company or source_title,
                    title=title,
                    url=entry.get("link", ""),
                    location="",
                    source="rss",
                    description=summary,
                    remote="remote" in (title + summary).lower(),
                )
            )
        log.info("rss[%s]: %d entries", feed_url, min(len(parsed.entries), limit))
    return jobs


# --- Seed URLs ---------------------------------------------------------

# Hosts that reject plain HTTP with a login wall - fetch these through the
# persistent (logged-in) Playwright profile instead. Opening a single posting
# you are authorized to view is fine; bulk-scraping listings is not.
DEFAULT_BROWSER_HOSTS = (
    "linkedin.com", "naukri.com", "glassdoor.com", "glassdoor.co.in",
    "instahyre.com", "wellfound.com", "angel.co", "hirist.com",
)

def _seed_job_from_html(url: str, html: str, page_title: str, h1: str, source: str) -> Job:
    soup = BeautifulSoup(html or "", "lxml")
    title = (page_title or (soup.title.string if soup.title else "") or "").strip()
    og_title = soup.find("meta", property="og:title")
    og_site = soup.find("meta", property="og:site_name")
    role = (h1 or (og_title["content"] if og_title and og_title.get("content") else "") or title).strip()
    company = ""
    location = ""

    # LinkedIn: "<Company> hiring <Role> in <Location> | LinkedIn"
    m = re.search(r"^(.*?)\s+hiring\s+(.*?)\s+in\s+(.*?)\s*[|\-–]", title)
    if m:
        company, role, location = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    if not company and og_site and og_site.get("content"):
        company = og_site["content"].strip()
    if not company:
        m2 = re.search(r"\b(?:at|@|\|)\s+([A-Z][\w&.\-' ]{2,40})", role)
        if m2:
            company = m2.group(1).strip()

    text = _html_to_text(html)[:8000]
    return Job(
        company=company or (urlparse(url).hostname or "Unknown"),
        title=role or "Unknown role",
        url=url,
        location=location,
        source=source,
        description=text,
        remote="remote" in (role + " " + text[:400]).lower(),
    )


async def _fetch_seed_browser(urls: list[str], timeout: int) -> list[tuple[str, str, str, str]]:
    from app.browser.browser import browser_session

    out: list[tuple[str, str, str, str]] = []
    async with browser_session(headless=None) as session:
        page = session.page
        for url in urls:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                await page.wait_for_timeout(2500)
                html = await page.content()
                title = await page.title()
                h1 = ""
                loc = page.locator("h1").first
                if await loc.count():
                    h1 = ((await loc.inner_text()) or "").strip()
                out.append((url, html, title, h1))
            except Exception as exc:  # noqa: BLE001
                log.warning("seed_url(browser)[%s] failed: %s", url, exc)
    return out


def from_seed_urls(
    urls: Iterable[str],
    timeout: int,
    ua: str,
    browser_hosts: Iterable[str] = DEFAULT_BROWSER_HOSTS,
) -> list[Job]:
    browser_hosts = tuple(h.lower() for h in browser_hosts)
    plain: list[str] = []
    via_browser: list[str] = []
    for url in urls:
        host = (urlparse(url).hostname or "").lower()
        if any(host == h or host.endswith("." + h) for h in browser_hosts):
            via_browser.append(url)
        else:
            plain.append(url)

    jobs: list[Job] = []

    for url in plain:
        try:
            resp = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("seed_url[%s] failed: %s", url, exc)
            continue
        jobs.append(_seed_job_from_html(url, resp.text, "", "", source="seed_url"))

    if via_browser:
        try:
            for url, html, title, h1 in asyncio.run(_fetch_seed_browser(via_browser, timeout)):
                jobs.append(_seed_job_from_html(url, html, title, h1, source="seed_url_browser"))
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "seed_urls browser fetch failed (run `python -m app.main login --url "
                "https://www.linkedin.com` first): %s",
                exc,
            )

    log.info("seed_urls: %d jobs (%d plain, %d via browser)", len(jobs), len(plain), len(via_browser))
    return jobs


# --- Generic HTML pages (Playwright) ---------------------------------------

async def _scrape_pages_async(pages: list[dict], limit: int, ua: str) -> list[Job]:
    from playwright.async_api import async_playwright

    jobs: list[Job] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=ua)
        for spec in pages:
            page_url = spec.get("url")
            selector = spec.get("link_selector", "a")
            if not page_url:
                continue
            try:
                page = await ctx.new_page()
                await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                links = page.locator(selector)
                n = min(await links.count(), limit)
                for i in range(n):
                    el = links.nth(i)
                    href = await el.get_attribute("href")
                    text = (await el.inner_text() or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        from urllib.parse import urljoin

                        href = urljoin(page_url, href)
                    jobs.append(
                        Job(
                            company=spec.get("company", page_url.split("/")[2]),
                            title=text or "See posting",
                            url=href,
                            location="",
                            source="html_page",
                            description="",
                        )
                    )
                await page.close()
            except Exception as exc:  # noqa: BLE001
                log.warning("html_page[%s] failed: %s", page_url, exc)
        await ctx.close()
        await browser.close()
    log.info("html_pages: %d jobs", len(jobs))
    return jobs


def from_html_pages(pages: list[dict], limit: int, ua: str) -> list[Job]:
    if not pages:
        return []
    try:
        return asyncio.run(_scrape_pages_async(pages, limit, ua))
    except Exception as exc:  # noqa: BLE001
        log.warning("html_pages scraping failed: %s", exc)
        return []


# --- Orchestration -------------------------------------------------------

def discover_jobs(search_config: dict[str, Any]) -> list[Job]:
    sources, _limits, per_source, timeout, ua = _cfg(search_config)
    keywords = search_config.get("keywords", [])
    locations = search_config.get("locations", [])
    jobs: list[Job] = []

    # --- automatic aggregators (default engine) ---
    aggregators_cfg = search_config.get("aggregators", {})
    if aggregators_cfg:
        from app.services import aggregators

        jobs += aggregators.discover(keywords, locations, aggregators_cfg, per_source, timeout)

    gh = sources.get("greenhouse", {})
    if gh.get("enabled") and gh.get("boards"):
        jobs += from_greenhouse(gh["boards"], per_source, timeout, ua)

    lv = sources.get("lever", {})
    if lv.get("enabled") and lv.get("companies"):
        jobs += from_lever(lv["companies"], per_source, timeout, ua)

    ab = sources.get("ashby", {})
    if ab.get("enabled") and ab.get("orgs"):
        jobs += from_ashby(ab["orgs"], per_source, timeout, ua)

    rss = sources.get("rss", {})
    if rss.get("enabled") and rss.get("feeds"):
        jobs += from_rss(rss["feeds"], per_source, timeout, ua)

    seeds = sources.get("seed_urls", {})
    if seeds.get("enabled") and seeds.get("urls"):
        jobs += from_seed_urls(
            seeds["urls"], timeout, ua,
            seeds.get("browser_hosts", DEFAULT_BROWSER_HOSTS),
        )

    html = sources.get("html_pages", {})
    if html.get("enabled") and html.get("pages"):
        jobs += from_html_pages(html["pages"], per_source, ua)

    # normalize: drop entries without a URL or title
    normalized = [j for j in jobs if j.url and j.title]
    log.info("discover_jobs: %d raw -> %d normalized", len(jobs), len(normalized))
    return normalized
