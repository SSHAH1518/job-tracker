# Job Agent — TODO

Status as of 2026-09-01: engine built, 26 jobs discovered + scored, 1 queued
(MixRank, 82). Local git commit done on `main`; not yet pushed.

## 1. Push to GitHub + GitHub Pages  ← start here
- [ ] Create an **empty public** repo on github.com named `job-tracker`
      (no README, no .gitignore, no license).
- [ ] Add the remote and push:
      ```
      git remote add origin https://github.com/<you>/job-tracker.git
      git push -u origin main
      ```
- [ ] Repo → **Settings → Pages** → Source: *Deploy from a branch* →
      Branch: `main` / folder: `/ (root)` → Save.
- [ ] Wait ~1 min, then open on your phone:
      `https://<you>.github.io/job-tracker/dashboard/index.html`
- [ ] (Optional) set `GIT_AUTO_SYNC=1` in `.env` once you trust it, so
      `discover` / `prepare` publish automatically. Otherwise run
      `python -m app.main sync` manually.

## 2. Accounts / local setup
- [ ] Re-run `python -m app.main discover` and confirm the Adzuna `401` is gone
      (ID was fixed today).
- [ ] `python -m app.main login --url https://www.linkedin.com` (log in, wait).
      Repeat for `https://www.naukri.com`. Sessions persist for browser-backed
      seed fetch.
- [ ] Add role-specific resumes to `data/resumes/`:
      `software_engineering.pdf`, `machine_learning.pdf`, `data_science.pdf`
      (only `master_resume.pdf` is there now). PDFs stay local (git-ignored).

## 3. Profile polish (`data/profile.json` — git-ignored)
- [ ] Write a real one-paragraph `answers.why_this_company` base text.
- [ ] Add project GitHub links (currently `TODO`) and ICTEAH 2025 paper details.

## 4. Get the *real* opportunities into the pipeline
- [ ] Paste posting URLs into `data/search_config.json` →
      `sources.seed_urls.urls` (these have no API — must be pasted):
      - Amazon — SDE I Intern 2027 (amazon.jobs)
      - JPMorganChase — 2027 Software Engineer Program, India
      - Goldman Sachs — 2027 New Analyst Program, Engineering, India
      - Deloitte USI — Campus27, Technology / AI & Data track
      - Microsoft — Early-in-Profession India (SWE / Data & Applied Science)
- [ ] Set up **LinkedIn + Naukri job alerts** (keywords: `2027 batch`,
      `SDE-1`, `Data Scientist fresher`, `graduate engineer trainee`,
      `Python SQL fresher`), then run `/ingest-alerts` in Claude Code.
- [ ] Re-run: `python -m app.main discover` → `/analyze` → `python -m app.main requeue`.

## 5. Applications
- [ ] Review all scored jobs: `python -m app.main dashboard` (or the Pages URL).
- [ ] MixRank (queued): `python -m app.main prepare --job-id e1c28ca3ed9b`,
      then `/prepare e1c28ca3ed9b` in Claude Code, review the browser, submit by hand.
- [ ] Work the MAYBE list (score ≥ 45) — open each real posting (Jooble/HN
      links are redirects/snippets) before deciding:
      Labcorp DS Intern (62), dscout (58), Enveritas backend (55),
      GitLab backend/observability (55), Mastercard SWE II ×2 (52/50),
      Netomi SDE-2 (50), Sophos full-stack (48), Lendable Summer Intern 2027 (45).
- [ ] After each change: `python -m app.main sync`.

## 6. Skills (from the 2027 plan — the actual gaps)
- [ ] Daily DSA practice (LeetCode) — biggest gap for Amazon/JPMorgan/Goldman OAs.
- [ ] AWS Cloud Practitioner cert + one deployed project.
- [ ] Docker + one shipped model (turns "built a model" into "shipped a model").

## Notes
- Loop: `discover` → `/analyze` → `requeue` → `queue` → `prepare` → `/prepare` → submit → `sync`.
- `/ingest-alerts` pulls LinkedIn/Naukri alert emails from Gmail.
- Full reference: `README.md` and `CLAUDE.md`.
