# Resumes

Drop your PDF resumes in this folder. The agent picks one per application and
records the exact filename used in `applications.json`.

Expected files (referenced by `resume_service.py` defaults):

| File | Use for |
|------|---------|
| `master_resume.pdf` | Source of truth; also the fallback if nothing else matches |
| `software_engineering.pdf` | Backend / full-stack / general SWE roles |
| `machine_learning.pdf` | ML / MLE / research roles |
| `data_science.pdf` | Data science / analytics roles |

You can add more; edit the `RESUME_ROUTES` table in
`app/services/resume_service.py` to map keywords to new files.

These PDFs are **not** committed (they are personal). Keep them out of any public repo.
