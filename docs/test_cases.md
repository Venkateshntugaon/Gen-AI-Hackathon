# Initial testing: test cases

All cases were run on 2026-11-25 with model `gemini-3.5-flash-lite` through the real pipeline (`review_one` / `extract_questions`), not mocks. "Actual result" is copied from the run output. In every review case the answer lock reported `answer_preserved=True`, and the answer after review was identical to the input.

| # | Test case | Input | Expected result | Actual result | Observation |
|---|---|---|---|---|---|
| TC1 | Clean question | "Which organ pumps blood around the human body?" Answer: Heart; distractors: Lungs, Liver, Kidneys | No findings, no suggestions, answer preserved | No findings, no suggestions; answer "Heart" preserved | Correct. Plausible same-category distractors (organs) are not flagged. |
| TC2 | Duplicate option | "Which planet is closest to the Sun?" Answer: Mercury; distractors: Venus, Mars, **venus** | Duplicate finding on the copy; replacement suggested | LOW duplicate on "venus", detected by rules + similarity + LLM; suggestion "venus" → "Earth" | All three layers agree. The copy (later option) is the one flagged. |
| TC3 | Implausible option | "What is the chemical symbol for sodium?" Answer: Na; distractors: S, So, **A teacup** | Implausible finding on "A teacup"; replacement suggested | MEDIUM implausible on "A teacup" (similarity + LLM: "completely unrelated to chemical symbols"); suggestion "A teacup" → "N" | Correct. "N" is a classic confusion (nitrogen vs sodium). |
| TC4 | Option that is also correct | "What is the SI unit of force?" Answer: Newton; distractors: Joule, **kg m/s^2**, Watt | also_correct HIGH on "kg m/s^2"; replacement suggested | HIGH also_correct on "kg m/s^2" ("equivalent to Newtons"); suggestion → "Pascal". Also HIGH possible_wrong_answer_key | Caught by the LLM only (embeddings cannot know that the units are equivalent). The extra answer-key flag is over-cautious, but harmless: the answer was not changed. |
| TC5 | Wrong answer key | "What is the boiling point of water at sea level?" **Answer: 50 °C**; distractors: 100 °C, 0 °C, 212 °C | possible_wrong_answer_key flagged; answer NOT changed | HIGH possible_wrong_answer_key ("water boils at 100 °C"); HIGH also_correct on "100 °C" and "212 °C"; answer after review still "50 °C" | The hard rule holds: the key is only flagged, and the UI shows the maroon banner. First run gave the same suggestion ("10 °C") for two options; fixed (the retry now skips texts already suggested), and the rerun shows one suggestion plus "No safe replacement found" for the other. |
| TC6 | Scanned PDF (no text layer) | Image-only PDF with 2 questions and "Answer: A/C" lines | Detected as scanned; Gemini reads the PDF directly; 2 questions with answers A and C | `pdf_has_text = False`; Gemini fallback used; 2 questions extracted with options and answers A, C | First run: Gemini copied the "A) " labels into the option text, and a 503 crashed the extractor (no retry). Both fixed: labels are stripped, and the extractor now uses the shared retry. |
| TC7 | DOCX with a table layout | Word file: "Q.1 …" paragraph, options "(a) …(d)" in a 2×2 table, "Ans. (a)"; Q.2 with a 1×4 table, "Ans. (b)" | Regex parser handles it (no LLM); 2 questions, answers A and B | 2 questions, options in the right order, answers A and B; LLM not used | Table cells are read row by row in document order, so the free regex path is enough. |
| TC8 | Paper without an answer key | TXT, numbering "1)", options "A." on separate lines, no answers | 2 questions found, answers left empty (never guessed) | 2 questions, 4 options each, `answer=None` for both; LLM not used | In the UI, "Start review" stays disabled and the teacher sees "Select the correct answer for these questions. The reviewer never guesses answers." |
| TC9 | Sample paper, full app flow | `data/sample/sample_paper.docx` via "Try a sample paper" (Streamlit AppTest) | 10 questions; planted flaws in Q2, Q4, Q7 flagged; downloads work | 10 found; Q2 duplicate, Q4 "A bicycle" implausible, Q7 "Steam" also_correct HIGH; 10/10 answers preserved; revised DOCX answer key equals the original paper's key | End-to-end check of Upload → Confirm → Review → Results → Export. |
| TC10 | Tampered result (unit test) | ReviewResult whose answer was changed to "carbon dioxide", "Carbon dioxide " (trailing space), "Oxygen", … | Caught, discarded, `answer_preserved=False` | All tampered variants caught; original answer kept, suggestions dropped | `tests/test_answer_lock.py`. Even a case or whitespace change is caught. |

## Automated tests

`pytest -q` → **62 passed**:
- `test_parser.py`: every numbering, option and answer format, answer-key blocks, never-guess, fallback decision, extractor clean-up.
- `test_rules.py`: normalisation, duplicates, answer equals distractor, length and a/an cues, all-of-the-above, merge.
- `test_validator.py`: candidate equal to the answer is rejected, duplicates, length cue, all-of-the-above, LLM verify.
- `test_answer_lock.py`: frozen MCQ, tampered results caught.

## Evaluation

See [`data/eval/results.md`](../data/eval/results.md): 30 SciQ questions with 24 planted flaws. Recall 0.96; precision 0.46 for the findings that trigger a replacement (duplicate 1.00, also_correct 0.64, implausible 0.26); 100% of weak distractors got a validated suggestion; **answer preserved 30/30**.

## Review of the 10-question test paper: before / after the fixes

Input: `PS84_test_paper_10_flawed_MCQs.pdf` (10 questions, text PDF, answer under each question). "Before" is the team's `review_report.docx` from the app; "After" is a re-run through the same path as the app (PDF → `extract_questions` → `review_one` with each answer's paper position → Word review report), model `gemini-3.5-flash-lite`. Answers preserved: **10/10 before and after**.

| Q | Planted / real issue | Before | After | Fix |
|---|---|---|---|---|
| 1 | D "O2" is also correct (same as Oxygen) | D: HIGH also_correct **and** LOW duplicate (same reason twice); A "Carbon dioxide": MEDIUM "Answer give-away" from the LLM | D: one finding, HIGH also_correct → suggestion "Hydrogen"; A no longer flagged | 5, 6 |
| 2 | D "Joules" duplicates A "Joule" | LOW duplicate (rules + LLM) → "Pascal" | LOW duplicate (rules) → "Pascal" | 5 (LLM no longer labels duplicates) |
| 3 | B "A football" implausible | MEDIUM implausible → "Brain" | MEDIUM implausible → "Brain" | unchanged ✔ |
| 4 | Answer much longer than the others | MEDIUM answer give-away + 3 implausible, 3 suggestions | MEDIUM answer give-away; C, D MEDIUM implausible (2 suggestions); A now LOW | unchanged ✔ |
| 5 | "…called an ________." only "atom" fits "an" | **No problems found** (cue missed) | MEDIUM answer give-away: "The question ends with "an", and only the correct answer fits it grammatically." | 1 |
| 6 | Answer is "All of the above" | 6 findings: 2× similarity "unrelated to the answer", 3× HIGH "also correct", "No safe replacement found" on every option | Only LOW "All of the above makes the question harder to mark fairly" | 2 |
| 7 | B "Iron" is also a body mineral | Answer-key flag says "**option 0** (Iron)"; 3 suggestions generated anyway | Reasons say "Option B"; no suggestions, shows "Resolve the answer key first" | 4, 7 |
| 8 | Wrong key: "Ag" for gold (Au is B) | Answer-key flag + suggestion replacing **"Au" (the real answer!)** with "Gl" | Answer-key flag (HIGH), B also correct; no suggestions, shows "Resolve the answer key first"; answer still "Ag" (only flagged) | 4 |
| 9 | Clean | LOW implausible on D | No problems found | (LLM run-to-run variation) |
| 10 | Numeric options (°C) | A "50 °C", D "150 °C": MEDIUM "**also correct** (similarity 0.91 / 0.90)" + suggestions "212 °C", "373 °C" | A, D: LOW implausible from the LLM only; no similarity flags, no suggestions | 3, 6 |

Summary counts: high 8 → 5, medium 12 → 7, low 8 → 9, suggestions 13 → 5. All the removed findings were false alarms or duplicates; every planted flaw is still reported. Unit tests for the fixes: `tests/test_rules.py` (blank grammar cue, number detection, no LLM answer cue/duplicate, one finding per option, letters instead of indices). `pytest -q` → 67 passed.
