# Pending activities

What is not finished or not tested yet, as of 2026-11-25.

## For the team (cannot be done by code)
- **Screenshots:** capture every UI step (Upload, Confirm, Review, Results, Export) and the evaluation output into `docs/screenshots/`.
- **Sample PDF:** open `data/sample/sample_paper.docx` in Word, save it as `sample_paper.pdf` in `data/sample/`, and run it through the app once (the text-PDF path was tested only with unit tests and an image-only "scanned" PDF; see test_cases.md TC6).
- **README placeholders:** Review 1 feedback and individual contributions.
- **Manual browser check:** the full flow was verified with Streamlit's AppTest runner and a live server health check, not by clicking through in a browser. Please click through once before the demo.

## Known limitations
- **Free-tier Gemini quota.** gemini-3.5-flash allowed only 20 requests per day on our key, which is less than one 10-question paper needs (~25–30 calls). Development and evaluation therefore used `gemini-3.5-flash-lite` (see `data/eval/results.md` for the model actually used). For the demo, either use the cache (questions already reviewed are instant), use flash-lite, or use a paid key.
- **Browser reload.** Streamlit keeps data in session state across interactions, but a full browser reload (F5) starts a new session and returns to Upload. Re-running the same paper is fast because all Gemini replies are cached.
- **Similarity on single technical words.** MiniLM gives low similarity to some good distractors (e.g. "Stigma" vs "Stamen" = 0.14), so the similarity layer alone can raise a false "implausible" finding. The UI shows "detected by: similarity" only in that case. Tuning `SIM_TOO_FAR` on more data is pending.
- **LLM judge strictness.** flash-lite still rates many acceptable SciQ distractors as unlikely to be chosen. After tuning (plausibility 1 → MEDIUM, 2 → LOW), implausible precision is 0.26 for the findings that trigger a replacement (recall 1.00). Further tuning (a stronger model, few-shot examples in prompts/judge.md) is pending.
- **Evaluation model.** `data/eval/results.md` was produced with gemini-3.5-flash-lite because of the free-tier daily limit; rerun with gemini-3.5-flash (or a paid key) for the final report.
- **Parser formats.** Roman-numeral options (i, ii, iii) and answers written as "iii" are not handled by the regex; such papers go to the Gemini fallback, and the answer is left for the teacher to pick.
- **Questions with more than 4 options** are cut to A–D in the Confirm table.

## Not tested
- Very large papers (100+ questions) in one session.
- DOCX files with images or equations inside options.
- Non-English papers.
