# Job Application Agent — how Claude Code drives it

This project is a **local, zero-extra-cost** job-application assistant.
**Claude Code (this tool, on the user's Claude Pro plan) is the orchestrator** —
it does every reasoning step. Python + Playwright do only deterministic work and
**never call an AI API** (there is no `anthropic` dependency, no API key).

## The loop

| Step | Who | Command |
|------|-----|---------|
| 1. Discover jobs | Python | `python -m app.main discover` |
| 1b. Pull jobs from LinkedIn/Naukri alert emails | **Claude Code** | `/ingest-alerts` |
| 2. Score jobs vs. profile | **Claude Code** | `/analyze` |
| 3. Promote strong matches | Python | `python -m app.main requeue` |
| 4. Inspect the queue | Python | `python -m app.main queue` |
| 5. Fill the form, stop before submit | Python + Playwright | `python -m app.main prepare --job-id <id>` |
| 6. Draft any open free-text answers | **Claude Code** | `/prepare <id>` |
| 7. Re-run prepare to apply answers | Python | `python -m app.main prepare --job-id <id>` |
| 8. Human reviews the browser and clicks Submit | **You** | — |
| 9. Publish JSON to the dashboard | Python | `python -m app.main sync` |

The Playwright agent **never clicks the final Submit** — that is always the human.

## Data contracts

All under `data/` (JSON, atomic writes):

- **`profile.json`** — the candidate. Single source of truth for matching,
  deterministic form autofill, and answer drafting. Read it, never invent facts
  beyond it.
- **`search_config.json`** — keywords / locations / exclude lists plus two source
  groups: `aggregators` (automatic — The Muse, Remotive, RemoteOK, Arbeitnow, HN
  "Who is hiring", and — with a free key — Adzuna / Jooble; no per-company setup)
  and `sources` (targeted boards, RSS, and pasted posting URLs). Everything pulled
  is filtered by the keyword/location/exclude lists before it lands in jobs.json.
- **`jobs.json`** — `{ "jobs": [ Job, … ] }`. Discovery appends `status:"DISCOVERED"`
  entries. `/analyze` fills the scoring fields (below) and sets `status:"ANALYZED"`.
- **`applications.json`** — `{ "applications": [ Application, … ] }`. Written by
  `prepare`. This is what the dashboard shows.
- **`answers/<job_id>.json`** — per-job free-text answer stubs. `prepare` writes
  the empty stub; `/prepare` fills the `answer` fields; `prepare` (re-run) applies
  them. Git-ignored working files.
- **`skill_confirmations.json`** — `{ "confirmed": [...], "ruled_out": [...],
  "notes": { job_id: "…" }, "updated": "…" }`. Skills the candidate has
  personally confirmed he can do (or ruled out) when `/analyze` asked him about a
  job that was otherwise a fit. `/analyze` reads this and treats a confirmed
  skill like one in `profile.json`; it never auto-SKIPs a level/timing/location-OK
  job on a skill gap without asking first.

### Job scoring fields (what `/analyze` writes onto each job)

```jsonc
{
  "match_score": 87,                // int 0-100
  "recommendation": "APPLY",        // "APPLY" | "MAYBE" | "SKIP"
  "matching_skills": ["Python", "Flask"],
  "missing_skills": ["AWS"],
  "relevant_projects": ["City-Level Demand Forecasting"],   // names from profile.json
  "relevant_experience": ["Tata 1mg"],                      // names from profile.json
  "reason": "Strong backend + Python match; DSA depth unproven.",  // 1-3 sentences
  "requires_human_review": false,
  "resume_hint": "software_engineering.pdf",   // optional; overrides the keyword router
  "status": "ANALYZED"
}
```

The **queue rule** (enforced by `requeue`, not by you): a job becomes `QUEUED`
iff `match_score >= MIN_MATCH_SCORE` (`.env`, default 75) **and**
`recommendation == "APPLY"`. Everything else scored becomes `SKIPPED`.

## Candidate context (see `profile.json` for the full record)

Somin Shah, B.Tech (Electronics & Computer Engineering, Data Science honours),
KJ Somaiya, **graduating June 2027**. CGPA ~9.5/10. Two internships:
**Tata 1mg** (backend / AI-tooling infra) and **Neuriot** (data science /
forecasting). Applies to both **SWE/SDE** and **Data Science / ML** tracks.
Known gaps to weigh in scoring: limited competitive-programming/DSA evidence,
no cloud platform yet, no MLOps/big-data tooling. **Not** eligible for
"immediate joiner" roles — only 2027-batch / graduate-program / internship-track
postings.

## Safety rules (hard constraints)

- Never fabricate qualifications, experience, education, projects, or answers.
  If the profile lacks something, write `NEEDS_HUMAN` in the answer.
- Never click a final Submit button; leave that to the human.
- Never put secrets (passwords, tokens) in any JSON/HTML/JS.
- Don't bypass CAPTCHAs or anti-bot systems.
- Record the exact resume filename and every answer on the application row.
- Prefer editing `data/*.json` directly (it's the native interface) and then
  running the matching `python -m app.main` command to reconcile.
