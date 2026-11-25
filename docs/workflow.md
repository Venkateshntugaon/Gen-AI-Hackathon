# Workflow: from upload to export

## 1. Upload
1. The teacher drops a question paper (PDF, DOCX or TXT) on the Upload step, or presses **Try a sample paper**. A SciQ-style CSV can be uploaded under "Advanced".
2. The matching reader turns the file into plain text. PDFs keep page markers so each question's source can say "p.2". DOCX tables are read too, because many papers put options in a table.
3. The regex parser looks for numbered questions, A–D options and answer lines (or an answer-key block at the end).
4. If the PDF has no selectable text (a scanned paper), or the parser finds no questions, or more than 30% of the questions have fewer than 3 options, the file is sent to Gemini with `prompts/extract.md` instead. The status box says so in one line.
5. The status box shows "Done (N questions found)" and the app moves to Confirm.

## 2. Confirm questions and answer key
1. All questions appear in an editable table: question, options A–D and an answer dropdown.
2. The teacher fixes any extraction mistakes, deletes rows that are not questions, and picks the answer wherever the paper did not mark one. The reviewer never guesses answers.
3. **Start review** stays disabled until every row has a question, at least 3 options and a valid answer.
4. On **Start review** every row becomes a frozen `MCQ`. From this point the correct answer cannot be edited.

## 3. Review (pipeline steps 2–7, per question)
1. **Fingerprint:** a SHA-256 hash of the correct answer is stored.
2. **Rules:** duplicate options, a distractor equal to the answer, answer cues (length, "a"/"an"), "all/none of the above".
3. **Similarity:** MiniLM embeddings compare every distractor with the answer and with each other.
4. **LLM judge:** one Gemini call returns, for every distractor, whether it is also correct and how tempting it is; it also says whether the question is ambiguous and whether Gemini agrees with the answer key. Findings from all three layers are merged.
5. **Generate:** for every weak distractor (high or medium finding, or duplicate), one Gemini call asks for 3 candidates, each based on a named student misconception.
6. **Validate:** candidates that resemble the answer, duplicate an option, give the answer away by length, or use "all/none of the above" are dropped; one Gemini verify call drops any candidate a teacher could mark correct. The first safe candidate becomes the suggestion. If none is safe, generation is retried once; if still none, the finding says "No safe replacement found."
7. **Answer lock:** the answer must still be identical and match its fingerprint. If not, the result is discarded and marked as not preserved.

The progress bar shows "Reviewing question i of n" and a live count of findings. If Gemini's free-tier limit is hit, finished questions are kept and the teacher presses **Retry**. Cached replies make the retry instant for everything already answered.

## 4. Results
1. Summary cards: questions reviewed, high / medium / low findings, suggestions made, and **Answers preserved n/n**.
2. Filters: severity, issue type, and "show only questions with issues".
3. One card per question: the options with severity badges and the locked verified answer; each finding with its reason and the layers that detected it; a maroon banner if the answer key may be wrong (it is never changed); and each suggestion (original → new, plus the misconception) with **Accept** / **Reject**.

## 5. Export
1. **Revised question paper (.docx):** accepted suggestions replace their distractors; each correct answer stays exactly as confirmed, in its original letter position; an answer key is added at the end.
2. **Review report (.csv):** one row per finding, with the suggestion and its accept/reject status.
3. **Full results (.json):** every `ReviewResult`, for evaluation and the report.
