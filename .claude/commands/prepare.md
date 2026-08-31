---
description: Draft truthful answers for a prepared application's open questions
---

Argument: a job id (`$ARGUMENTS`).

## Steps

1. Read `data/profile.json` and `CLAUDE.md`.
2. Read `data/answers/$ARGUMENTS.json`. If it does not exist, tell me to run
   `python -m app.main prepare --job-id $ARGUMENTS` first (that generates the
   stub of questions the form asked).
3. For each entry whose `answer` is empty:
   - Answer using **only** facts in `data/profile.json`.
   - Never fabricate experience, numbers, education, or credentials.
   - Short fields → one line. Essays → 3-5 sentences, first person, plain and
     professional, no preamble.
   - Tailor "why this company / why interested" to the specific job using the
     `job_context` field and the matching job in `data/jobs.json`, staying
     truthful.
   - If the profile genuinely lacks the information, set the answer to
     `"NEEDS_HUMAN"` and note it for me.
4. Optionally, if a resume clearly fits better than the current pick, set
   `resume_hint` on this job in `data/jobs.json`.
5. Write `data/answers/$ARGUMENTS.json` back with the filled answers.
6. Tell me to re-run `python -m app.main prepare --job-id $ARGUMENTS` to apply
   them, and list any `NEEDS_HUMAN` questions.

Do **not** submit the application.
