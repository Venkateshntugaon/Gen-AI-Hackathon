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
