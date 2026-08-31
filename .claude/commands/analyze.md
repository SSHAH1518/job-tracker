---
description: Score every unscored job in data/jobs.json against data/profile.json
---

You are acting as a careful technical recruiter for ONE candidate.

## Steps

1. Read `data/profile.json` (the candidate) and `CLAUDE.md` (candidate context +
   the scoring-field contract + the queue rule).
2. Read `data/jobs.json`. Work on every job where `match_score` is `null` or
   `status` is `"DISCOVERED"`. If `$ARGUMENTS` names a job id, do only that one.
3. For each such job, judge fit **honestly** against the profile and add these
   fields to the job object, then set `"status": "ANALYZED"`:

   | field | type | notes |
   |-------|------|-------|
   | `match_score` | int 0-100 | 85+ strong, 70-84 worth applying, 50-69 stretch, <50 poor |
   | `recommendation` | `"APPLY"` / `"MAYBE"` / `"SKIP"` | `APPLY` only if the candidate meets most core requirements |
   | `matching_skills` | string[] | |
   | `missing_skills` | string[] | |
   | `relevant_projects` | string[] | names **from `profile.json`**, not the job |
   | `relevant_experience` | string[] | names **from `profile.json`** (e.g. "Tata 1mg") |
   | `reason` | string | 1-3 sentences |
   | `requires_human_review` | bool | true for unclear seniority, visa/clearance, senior titles, big skill gaps, "immediate joiner" wording |
   | `resume_hint` | string (optional) | a filename from `data/resumes/` if one clearly fits best |

4. Hard rules:
   - Do not invent skills or experience the candidate lacks.
   - The candidate graduates **June 2027** — mark anything requiring an immediate
     start as `SKIP` + `requires_human_review: true`.
   - Weigh the known gaps from `CLAUDE.md` (DSA evidence, no cloud, no MLOps).
5. Write the updated array back to `data/jobs.json` (preserve every existing
   field and job; atomic-safe — just edit the file).
6. Run `python -m app.main requeue` and report its summary plus a short list of
   the newly `QUEUED` jobs (id, title, company, score).

Do **not** open a browser or prepare any application here.
