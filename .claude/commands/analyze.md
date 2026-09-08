---
description: Score every unscored job in data/jobs.json against data/profile.json
---

You are acting as a careful technical recruiter for ONE candidate.

## Steps

1. Read `data/profile.json` (the candidate) and `CLAUDE.md` (candidate context +
   the scoring-field contract + the queue rule). Also read
   `data/skill_confirmations.json` if it exists — it holds skills the candidate
   has personally confirmed he can do (or explicitly ruled out) in past sessions;
   treat a confirmed skill exactly like one in the profile.
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

5. **Ask the human before writing off a job on skills alone.** After a first
   pass, collect every job that would be `MAYBE`/`SKIP` *only* because of a
   missing skill or tool that is plausibly within reach — i.e. the role's level,
   timing, location and work authorisation all fit, and the sole blocker is one
   or more skills the candidate might already have or could pick up quickly
   (common cases: a frontend framework like React/Angular/Vue, Node.js/
   TypeScript, Java/Spring, a cloud platform, Docker/CI-CD, R, .NET/C#, a
   specific database dialect). Do **not** include jobs blocked by seniority
   ("Senior"/"Staff"/"III"/"5+ years"), visa/relocation, wrong domain
   (embedded/firmware, bioinformatics, SDET when it is not a target track), or
   "immediate joiner" wording — those stay auto-scored.

   Group the collected jobs by the skill(s) in question. For each group, give the
   candidate a short plain-language summary — the role(s), company, level, and
   the exact requirement(s) in doubt — and ask directly whether he can do it or
   ramp into it quickly. Use `AskUserQuestion` for the common skill clusters
   first (one question per cluster), then follow up in plain text for any job
   that is still genuinely role-specific and ambiguous.

   Record every answer in `data/skill_confirmations.json` as
   `{ "confirmed": ["React (basics, can ramp)", ...], "ruled_out": ["Angular", ...],
   "notes": { "<job_id>": "<what he said>" }, "updated": "<date>" }` (merge with
   any existing file; keep prior entries). Then re-score the affected jobs
   treating each confirmed skill as present, and note the confirmation in the
   `reason` (e.g. "candidate confirmed he can pick up React").

   If this command is run non-interactively (no human to ask), skip the asking,
   score conservatively, and leave those jobs `requires_human_review: true` with
   a `reason` that names the open skill question.

6. Write the updated array back to `data/jobs.json` (preserve every existing
   field and job; atomic-safe — just edit the file).
7. Run `python -m app.main requeue` and report its summary plus a short list of
   the newly `QUEUED` jobs (id, title, company, score), and a short list of the
   jobs you asked the human about with the outcome.

Do **not** open a browser or prepare any application here.
