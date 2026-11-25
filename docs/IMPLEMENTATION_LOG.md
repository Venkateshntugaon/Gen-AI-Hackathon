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

## Phase 2: Document ingestion (PDF, DOCX, TXT, CSV)  (2026-11-25)
**What we built:** Readers that turn PDF (pdfplumber, with page markers), DOCX (paragraphs and table cells, in document order), TXT and SciQ-style CSV into text or MCQs. A regex parser that understands the common numbering, option and answer formats, including an answer-key block at the end of the paper. A Gemini fallback extractor used when the PDF is scanned (PDF bytes sent directly) or the parser result looks unreliable (0 questions, or more than 30% with fewer than 3 options).
**Why:** Teachers upload papers as they already have them. The regex is free, fast and predictable; Gemini only handles messy or scanned layouts. Answers are never guessed: a question without a marked answer gets `None` and the teacher picks it in the UI.
**Files:** src/reviewer/ingest/readers.py, src/reviewer/ingest/parser.py, src/reviewer/ingest/llm_extract.py, prompts/extract.md, tests/test_parser.py
**How to verify:** `pytest tests/test_parser.py` → 35 passed. `python -c "from pathlib import Path; from src.reviewer.ingest.llm_extract import extract_questions; q,llm=extract_questions('sample_paper.docx', Path('data/sample/sample_paper.docx').read_bytes()); print(len(q), all(x.answer for x in q), llm)"` → `10 True False`.
**Notes / issues:** `extract_questions()` (the read → parse → maybe-fallback decision) lives in llm_extract.py, because putting it in parser.py would create a circular import. The Gemini extractor calls the SDK directly; caching and retry come with llm.py in Phase 4. Extraction uses temperature 0 because it must copy text, not be creative.
