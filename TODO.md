# Job Agent — TODO

Status as of 2026-09-08 (session 2): 113 jobs, all scored. **4 applied** —
Amazon SDE I Intern 2027 (85), MixRank (82), **Nuvama Group – Intern AI
Engineering (86)**, **FanCode – SWE Internship Backend (76)**. Stripe, Lexsi Labs
and GE Appliances were reviewed and declined. **1 QUEUED** — Iris Software –
MLOps Intern (76, review: confirm it's paid + 2027-eligible).

Shortlisting was reworked this session: `/analyze` now asks before dropping a job
whose only gap is a missing skill (see `data/skill_confirmations.json` for what
Somin confirmed — React basics/ramp, cloud+Docker basics, Java+Spring ramp; ruled
out Node.js/TS, R, .NET/C#, onsite-abroad). 13 previously-buried roles were
promoted to review-worthy leads — see section 4.

## 1. Applications — keep the pipeline moving
- [x] `applications.json` rows for MixRank, Nuvama, FanCode (2026-09-08).
- [ ] Watch for the **Amazon Online Assessment** invite (DSA-heavy). Update the
      Amazon application row status to `OA` when it arrives.
- [ ] Work the 1 QUEUED role — **Iris Software MLOps Intern (c4b20642f3b7)**:
      open the LinkedIn posting, confirm it's paid and open to the 2027 batch,
      then `python -m app.main prepare --job-id c4b20642f3b7` → `/prepare` →
      review the browser → submit by hand → `sync`.

## 2. Publish to the dashboard
- [x] `python -m app.main sync` run 2026-09-08 (2 applications, 113 scored jobs
      pushed to GitHub Pages).
- [ ] Confirm **Settings → Pages** is enabled (Deploy from branch: `main` /
      root) and the phone URL loads:
      `https://SSHAH1518.github.io/job-tracker/dashboard/index.html`
- [ ] (Optional) set `GIT_AUTO_SYNC=1` in `.env` once trusted.

## 3. Get the *real* 2027-batch roles into the pipeline
- [x] Naukri session logged in and persisted to `data/browser_profile/`
      (2026-09-08 — confirmed via `is_login` / `nauk_at` / `nauk_rt` cookies).
      LinkedIn still needs a `python -m app.main login --url https://www.linkedin.com`.
- [x] LinkedIn job alerts are live and flowing — `/ingest-alerts` on 2026-09-08
      pulled 39 new postings from the last 7 days of digests. Re-run it every
      few days.
- [ ] Set up **Naukri job alerts** now that you're logged in (keywords: `2027
      batch`, `SDE-1`, `Data Scientist fresher`, `graduate engineer trainee`,
      `Python SQL fresher`) so `/ingest-alerts` can pull them from Gmail — none
      have arrived yet.
- [ ] The 4 Amazon SDE I Intern 2027 req URLs are already in
      `search_config.json` → `seed_urls.urls`. Amazon rotates/closes these every
      few weeks — if `discover` logs a 404, pull fresh req URLs from amazon.jobs.
- [ ] Replace the 4 **program-hub** seed URLs (JPMorgan / Goldman / Microsoft /
      Deloitte) with live India requisition URLs: open each hub in the
      logged-in browser, copy the real posting URL, paste it over the hub URL.
      Those portals 403 plain fetchers, which is why the hubs are placeholders.
- [ ] Re-run: `python -m app.main discover` → `/analyze` →
      `python -m app.main requeue`.

## 4. Review-worthy leads (open the real posting before deciding)
Re-scored 2026-09-08 after the skill Q&A. All `requires_human_review` — the open
question per role is the skill/level note in `missing_skills`, not a skill Somin
lacks outright. Sorted by score:
- [ ] **S&P Global — Java Software Engineer II**, Chennai (70) — Java yes / Spring
      ramp; confirm the "Engineer II" level takes 2027-batch.
- [ ] **GitLab — Backend Eng, Monitoring & Anomaly Detection**, remote (68) —
      maps to the Tata 1mg Sentry work; reads mid/senior, kept as a strong name.
- [ ] **Enveritas — Backend Software Engineer**, remote worldwide (66) — Python/
      PostgreSQL core match; confirm they take strong juniors.
- [ ] **Sophos — Full Stack Software Engineer**, India (66) — backend fits,
      frontend is a ramp; confirm seniority.
- [ ] **S&P Global — Backend Python (Kensho)**, Hyderabad (64) — strongest
      non-Amazon lead; high DSA/ML bar.
- [ ] **MSD — Specialist, Full-Stack GenAI/Agentic**, Hyderabad (64) — GenAI/
      agentic is an unusually strong match; "Specialist" implies a few years.
- [ ] Deeter Analytics — ML Engineer, remote worldwide (62, timing) ·
      Darukaa.Earth — AI/ML Intern, Mumbai (62) · dscout — SWE, India (60) ·
      Kyndryl — Full Stack, Bangalore (60) · DroneStark — SWE Intern, Mumbai (58)
- [ ] After each change: `python -m app.main sync`.

## 5. Profile polish (`data/profile.json` — git-ignored)
- [ ] Write a real one-paragraph `answers.why_this_company` base text
      (still `TODO`).
- [ ] Add project GitHub links (`projects[].link` still `https://github.com/TODO/...`).
- [ ] Fill in `publications[0]` — the ICTEAH 2025 paper is
      "AI-Powered Smart Spectacles for Real-Time Problem Solving" (add venue
      details / DOI / link).

## 6. Skills (the actual gaps from scoring)
- [ ] Daily DSA practice (LeetCode) — the flagged risk on Amazon and the reason
      several SDE-2 / III roles scored low.
- [ ] AWS Cloud Practitioner cert + one deployed project.
- [ ] Docker + one shipped model.

## Notes
- Loop: `discover` → `/analyze` → `requeue` → `queue` → `prepare` → `/prepare`
  → submit → `sync`.
- Queue rule (enforced by `requeue`): `QUEUED` iff `match_score >=
  MIN_MATCH_SCORE` (default 75) **and** `recommendation == "APPLY"`.
- `/ingest-alerts` pulls LinkedIn/Naukri/Indeed alert emails from Gmail.
- Full reference: `README.md` and `CLAUDE.md`.
