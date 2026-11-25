# Implementation Log

## Phase 0: Project setup  (2026-11-25)
**What we built:** The project skeleton: CLAUDE.md with the build rules, a .gitignore that hides .env and the LLM cache, a .env.example with placeholder values, requirements.txt, a config module that loads the key and thresholds, and a setup-check script that makes one tiny Gemini call.
**Why:** A working foundation where the secret key is protected from the start. The repo is public on GitHub, so a committed key could be found by bots and misused.
**Files:** CLAUDE.md, IMPLEMENTATION.md, .gitignore, .env.example, requirements.txt, README.md, src/reviewer/__init__.py, src/reviewer/config.py, scripts/check_setup.py, docs/IMPLEMENTATION_LOG.md
**How to verify:** `git status` does not list `.env`; `python scripts/check_setup.py` prints `Gemini OK: gemini-3.8-flash`.
**Notes / issues:** Python 3.11 is not installed on this machine; the venv was created with Python 3.13 (see CHALLENGES.md).

## Phase 1: Data models and sample data  (2026-11-25)
**What we built:** Pydantic models for a question (MCQ), a finding, a suggestion and a review result. A script that saves 100 random SciQ questions (seed 42, no support passage) to a CSV, and a script that writes a 10-question teacher-style question paper (DOCX) with 3 deliberately flawed questions.
**Why:** SciQ gives real, verified science MCQs. The sample paper mimics what teachers actually upload, and the planted flaws (Q2 duplicate option, Q4 implausible option, Q7 also-correct option) let the demo show findings. MCQ is frozen, so code cannot change the verified answer in place.
**Files:** src/reviewer/models.py, scripts/make_sciq_sample.py, scripts/make_sample_docx.py, data/sample/sciq_sample.csv, data/sample/sample_paper.docx
**How to verify:** `python scripts/make_sciq_sample.py` → "Saved 100 questions …"; `python scripts/make_sample_docx.py` → "Saved 10 questions (3 with planted flaws) …"; `python -c "from src.reviewer.models import MCQ"` runs without error.
**Notes / issues:** Each CSV id keeps the original SciQ train-row number (e.g. "SciQ #8279"), so every question can be traced back to the dataset. Option text in the paper is capitalised for realism; the question text is copied as-is, including SciQ's own typos.
