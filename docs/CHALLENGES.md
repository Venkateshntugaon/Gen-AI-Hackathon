# Challenges and Solutions

## Phase 0
- **Python 3.11 not available.** The plan asks for Python 3.11, but the dev machine has only 3.13 and 3.14. We used Python 3.13 for the venv, because CPU PyTorch and all listed packages publish wheels for it. If the team prefers 3.11, install it and recreate `.venv`.
- **Gemini model retired.** `check_setup.py` failed with 404: *"models/gemini-2.5-flash is no longer available to new users. Please use models/gemini-3.8-flash."* The script's model-list fallback showed the options; the team chose `gemini-3.8-flash` and we updated `.env`, `.env.example`, the config default and the README.
- **`.env.example` renamed instead of copied.** During setup `.env.example` was renamed to `.env`, which removed the example file from the repo. We recreated it with placeholder values only. Use `cp`, not `mv`.

## Phase 2
- **Options split across lines.** The first parser version only recognised an option line if it started with "A)", so "B) …" on its own line was glued onto the previous option. Fix: the parser remembers how many options the current question already has and expects the next letter (B after A). Caught by the unit tests.
- **Letters inside option text.** "Vitamin C." could look like a new option "C.". Fix: option markers must appear in order (A, B, C, D) and lower-case "a." is not accepted as a marker.
- **Merged DOCX table cells** are returned by python-docx once per grid column; we skip repeated neighbouring cell text.
- **gemini-3.8-flash temporarily unavailable (503 "high demand").** The fallback was verified with `gemini-3.5-flash` for one run. On a messy paper using roman-numeral options (i, ii, iii), Gemini kept the numerals in the option text (as told: copy verbatim) and an answer written as "iii" was dropped because it is not a letter A–D, so the teacher picks it. Safe behaviour; noted in case the prompt needs refining later.
