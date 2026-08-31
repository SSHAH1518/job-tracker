---
description: Pull jobs from LinkedIn / Naukri / Indeed job-alert emails in Gmail into jobs.json
---

You have access to the user's Gmail. Turn their job-alert emails into jobs.

Lookback window: `$ARGUMENTS` if given (e.g. `14d`), otherwise `7d`.

## Steps

1. Search Gmail with each of these queries (replace `7d` with the window):
   - `from:jobalerts-noreply@linkedin.com newer_than:7d`
   - `from:jobs-noreply@linkedin.com newer_than:7d`
   - `from:(alerts@naukri.com OR jobalerts@naukri.com OR info@naukri.com) newer_than:7d`
   - `from:alert@indeed.com newer_than:7d`
   - `from:(no-reply@instahyre.com) newer_than:7d`
   - `subject:("job alert" OR "new jobs for you" OR "jobs for you") newer_than:7d`
2. Read the matching messages. Each alert email lists several postings. For every
   posting extract:
   - `company`
   - `title`
   - `url` — the "View job" / "Apply" link. **Strip tracking parameters** (drop
     everything from `?` onward for LinkedIn `/jobs/view/<id>` links; keep the
     canonical posting URL).
   - `location` (if shown)
   - `remote` — true if the listing says Remote
   - `source` — `"linkedin_alert"`, `"naukri_alert"`, `"indeed_alert"`, etc.
   - `description` — leave `""`; the real description is fetched later.
3. De-duplicate within your batch by URL (and by company+title when URLs differ
   only by tracking params).
4. Write `data/_inbox_jobs.json`:
   ```json
   { "jobs": [ { "company": "...", "title": "...", "url": "...", "location": "...", "remote": false, "source": "linkedin_alert", "description": "" } ] }
   ```
5. Run `python -m app.main add-jobs --file data/_inbox_jobs.json`.
6. Report how many were added / were duplicates / were rejected, then remind me
   to run `/analyze`.

Do **not** log into LinkedIn/Naukri or scrape their websites - only read the
emails already in the inbox.
