# Challenges and Solutions

## Phase 0
- **Python 3.11 not available.** The plan asks for Python 3.11, but the dev machine has only 3.13 and 3.14. We used Python 3.13 for the venv, because CPU PyTorch and all listed packages publish wheels for it. If the team prefers 3.11, install it and recreate `.venv`.
- **Gemini model retired.** `check_setup.py` failed with 404: *"models/gemini-2.5-flash is no longer available to new users. Please use models/gemini-3.8-flash."* The script's model-list fallback showed the options; the team chose `gemini-3.8-flash` and we updated `.env`, `.env.example`, the config default and the README.
- **`.env.example` renamed instead of copied.** During setup `.env.example` was renamed to `.env`, which removed the example file from the repo. We recreated it with placeholder values only. Use `cp`, not `mv`.
