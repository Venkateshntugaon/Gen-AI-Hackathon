# Implementation Log

## Phase 0: Project setup  (2026-11-25)
**What we built:** The project skeleton: CLAUDE.md with the build rules, a .gitignore that hides .env and the LLM cache, a .env.example with placeholder values, requirements.txt, a config module that loads the key and thresholds, and a setup-check script that makes one tiny Gemini call.
**Why:** A working foundation where the secret key is protected from the start. The repo is public on GitHub, so a committed key could be found by bots and misused.
**Files:** CLAUDE.md, IMPLEMENTATION.md, .gitignore, .env.example, requirements.txt, README.md, src/reviewer/__init__.py, src/reviewer/config.py, scripts/check_setup.py, docs/IMPLEMENTATION_LOG.md
**How to verify:** `git status` does not list `.env`; `python scripts/check_setup.py` prints `Gemini OK: gemini-3.8-flash`.
**Notes / issues:** Python 3.11 is not installed on this machine; the venv was created with Python 3.13 (see CHALLENGES.md).
