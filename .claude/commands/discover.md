---
description: Refresh data/jobs.json from the configured job sources (deterministic, no AI)
---

Run the discovery pipeline and report the result:

```
python -m app.main discover
```

Then run `python -m app.main status` and tell me:
- how many new jobs were added
- how many jobs now await scoring

If jobs await scoring, remind me to run `/analyze` next.
