# Claude-Powered Job Application Automation — Phase 2 (Claude Pro / Claude Code)

A **local, zero-extra-cost** job-application assistant for Somin Shah (2027 batch).

- **Claude Code** (on your existing Claude Pro plan) is the orchestrator — it
  scores jobs against your profile, drafts application answers, and suggests
  resume tailoring. No Anthropic API key, no per-call charges.
- **Python + Playwright** do only deterministic work: job discovery from public
  boards, filtering/deduplication, form filling, resume upload. **No AI calls in
  the Python code.**
- **JSON files** are the storage. **GitHub Pages** serves a static, read-only
  dashboard you open from your phone. **git** publishes updated JSON.

```
            YOUR PC
              │
        Claude Code  ── reads profile.json + jobs.json, scores, drafts answers
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
 Python    Playwright   JSON
(discover) (fill form)  (data/)
   └──────────┼──────────┘
              ▼
           GitHub ──► GitHub Pages ──► phone / laptop
```

## The loop

| # | Step | Who | Command |
|---|------|-----|---------|
| 1 | Discover jobs | Python | `python -m app.main discover` |
| 2 | Score jobs vs. profile | **Claude Code** | `/analyze` |
| 3 | Promote strong matches to the queue | Python | `python -m app.main requeue` |
| 4 | See what's ready | Python | `python -m app.main queue` |
| 5 | Fill the form, **stop before submit** | Playwright | `python -m app.main prepare --job-id <id>` |
| 6 | Draft any open free-text answers | **Claude Code** | `/prepare <id>` |
| 7 | Re-run prepare to apply the answers | Python | `python -m app.main prepare --job-id <id>` |
| 8 | Review the browser, click Submit yourself | **You** | — |
| 9 | Publish JSON to the dashboard | Python | `python -m app.main sync` |

`python -m app.main status` shows counts at any time.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env            # tweak thresholds if you want (no API key needed)
```

Then:

1. **`data/profile.json`** — your details. It is **git-ignored** (holds your
   email/phone); `cp data/profile.example.json data/profile.json` and fill it in,
   or keep the one you already have. Add a one-line `answers.why_this_company`
   base paragraph.
2. **`data/search_config.json`** — put real Greenhouse/Lever/Ashby tokens for
   companies you care about, and paste target-program posting URLs into
   `sources.seed_urls.urls` (Amazon SDE I Intern 2027, JPMorgan SEP 2027, etc. —
   those big programs have no public board API).
3. **`data/resumes/`** — drop in `master_resume.pdf`, `software_engineering.pdf`,
   `machine_learning.pdf`, `data_science.pdf` (see `data/resumes/README.md`).

## Project layout

```
CLAUDE.md              how Claude Code drives the system (read this)
.claude/commands/      /discover  /analyze  /prepare  /sync   slash commands
app/
  main.py              CLI: discover, requeue, status, queue, prepare, sync, run, …
  config.py            .env-driven settings (no API key)
  services/
    job_discovery.py   greenhouse, lever, ashby, RSS, seed URLs, HTML scrape
    pipeline.py        discover → filter → dedupe → store
    analysis.py        queue reconciliation + Claude-Code hand-off helpers
    resume_service.py  keyword → resume routing
    json_store.py      atomic JSON reads/writes
    git_sync.py        debounced commit + push of data/
    scheduler.py       APScheduler discovery interval
  agents/
    resume_agent.py       deterministic resume pick + tailoring prompt
    answer_agent.py        canned answers + answers-stub file handling
    application_agent.py   open form → fill → upload resume → validate → STOP
  browser/
    browser.py         persistent Playwright context (keeps you logged in)
    forms.py           generic field inspection + deterministic mapping
    sites/             greenhouse / lever / ashby / generic handlers
  models/              Job, Application dataclasses
data/
  profile.json         you (filled)
  search_config.json   sources / keywords / locations
  jobs.json            discovered + scored jobs
  applications.json    prepared / submitted applications  (dashboard reads this)
  answers/<id>.json    per-job answer drafts (git-ignored)
  resumes/             your PDFs (git-ignored)
dashboard/             static index.html + style.css + app.js
```

## Job discovery

`python -m app.main discover` pulls from two groups (config in
`search_config.json`; every failure is logged and skipped; results are filtered
by your `keywords` / `locations` / `exclude_keywords` before landing in
`jobs.json`).

### `aggregators` — automatic, no per-company setup (the default engine)

| Source | Key? | Coverage |
|---|---|---|
| **The Muse** | none | tech/data roles incl. India, filter by level |
| **Remotive** | none | remote software/data |
| **RemoteOK** | none | remote |
| **Arbeitnow** | none | remote + EU |
| **HN "Who is hiring?"** | none | latest monthly thread, startups/remote |
| **Adzuna** | free (`ADZUNA_APP_ID` / `ADZUNA_APP_KEY`) | **best India coverage** |
| **Jooble** | free (`JOOBLE_API_KEY`) | broad India aggregator |

The keyless ones work immediately. Add the two free keys in `.env` for much
stronger India coverage — discovery still runs without them.

### `sources` — targeted (you name the board / page / URL)

- **greenhouse / lever / ashby** — public board JSON APIs (add tokens for
  companies you want to track directly)
- **rss** — any RSS/Atom job feed
- **seed_urls** — explicit posting URLs, fetched + text-extracted — **use this for
  Amazon / JPMorgan / Goldman / Deloitte / Microsoft program postings** (Workday /
  internal portals with no public API). URLs on `linkedin.com` / `naukri.com` /
  `glassdoor.com` / etc. are opened through your **logged-in Playwright profile**
  (run `python -m app.main login --url https://www.linkedin.com` once) so the
  login wall doesn't block them.
- **html_pages** — generic careers-page scrape with Playwright (fragile)

### LinkedIn / Naukri

The agent does **not** scrape LinkedIn/Naukri listings (ToS + anti-bot). Instead:

1. **Aggregators recover cross-posts.** Companies post the same req to LinkedIn,
   Naukri, and Adzuna/Jooble — the aggregator engine already catches much of it.
2. **Job-alert email ingestion.** Create saved job alerts on LinkedIn/Naukri;
   they email you matches. Run `/ingest-alerts` in Claude Code — it reads those
   emails from Gmail and adds the postings via `python -m app.main add-jobs`.
   Nothing scraped; it's your inbox.
3. **Paste a posting URL** into `seed_urls` — it's fetched through your logged-in
   browser profile (see above).

## Safety rules enforced

- The application agent **never clicks the final Submit** — it fills, uploads the
  resume, validates required fields, and hands off to you.
- Answers come only from `profile.json`; anything unknown becomes `NEEDS_HUMAN`.
- The exact resume filename and every answer are stored on the application row.
- No passwords / tokens in JSON/HTML/JS. Browser logins use a persistent,
  git-ignored Chromium profile (`python -m app.main login --url <site>`).
- CAPTCHAs / anti-bot systems are never bypassed.
- JSON writes are atomic (`.tmp` + `os.replace`); git sync is debounced.

## GitHub Pages deployment

1. `git init`, create a **private** repo, push.
2. Repo → Settings → Pages → deploy from `main` / root.
3. Open `https://<user>.github.io/<repo>/dashboard/index.html` on your phone.
4. Set `GIT_AUTO_SYNC=1` in `.env` so `discover` / `prepare` publish automatically,
   or run `python -m app.main sync` (or `/sync`) manually.

**Privacy:** `profile.json` and `applications.json` hold your email/phone/notes —
use a **private** repo, or strip personal fields before publishing. All git
writes happen from this local machine via your authenticated git install; no
token ever goes near the dashboard.

## Scheduling on Windows

Point Task Scheduler at:

```
<path>\.venv\Scripts\python.exe -m app.main run
```

run at logon, "Start in" = this folder. It refreshes `jobs.json` every
`DISCOVERY_INTERVAL_HOURS`; you still run `/analyze` in Claude Code to score them.
