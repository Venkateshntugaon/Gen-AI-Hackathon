# IMPLEMENTATION.md — PS 84: Scientific MCQ Distractor Reviewer

> **For Claude Code.** This file is the single source of truth for building this project.
> Repo: https://github.com/basavarajbillur000/GEN-AI-HACKATHON
> Team: Anika Ramya Shetty · Basavaraj Babasab Billur · Mahesh · Venkatesh Tugaon (AI/ML-F, VII Sem, Alliance University)

---

## 0. Operating rules for Claude Code (read first, follow always)

1. **Build only what this file describes.** Do not add features, pages, files, dependencies, abstractions, Docker, CI, databases, authentication, logging frameworks or "nice-to-haves" that are not listed here.
2. **Work one phase at a time.** At the end of every phase: stop, summarise what you built in plain English, show the exact command to verify it, and wait for the team to say "continue". Never start the next phase on your own.
3. **Ask before deviating.** If a step is unclear, a package is missing, or an API has changed, ask the team instead of guessing or improvising a workaround.
4. **No new packages** beyond §3 without asking first.
5. **Secrets:** the Gemini API key lives only in `.env`. Never print it, log it, hard-code it, paste it into any other file, or commit it. Create `.gitignore` (with `.env` in it) **before the first commit**. Commit only `.env.example`, which contains placeholder values.
6. **The verified correct answer is never modified by code.** Not by the LLM, not by suggestions, not by "cleaning". It can only be *flagged* for the teacher.
7. **Explainability:** every Python file starts with a short plain-English docstring that says *what this file does and why it exists*. Every phase ends with an entry in `docs/IMPLEMENTATION_LOG.md` (format in §8).
8. **Keep code simple and readable for students:** small functions, clear names, comments only where the *why* is not obvious. Use Pydantic models for data; avoid class hierarchies.
9. **Git:** make one commit per phase with the message given in that phase. **Never `git push`** unless the team says so.
10. Do not refactor or "improve" code from an earlier phase unless the current phase requires it.

> **Phase 0 task:** copy this section (§0) into a `CLAUDE.md` file in the repository root, so the rules load automatically in every Claude Code session.

---

## 1. What we are building (problem statement, as given)

> *Develop a GenAI application that processes existing science questions and answer options. The system should produce ambiguity findings and improved distractor suggestions. The prototype must preserve the verified correct answer.*
> *Expected solution: LLM + question evaluation.*

**In plain words:** a teacher uploads a question paper (PDF, Word or text). The app extracts the MCQs and lets the teacher confirm the answer key. It then finds flawed wrong options (distractors), explains each flaw, and suggests better, misconception-based distractors. The teacher accepts or rejects each suggestion and downloads a revised question paper and a review report. **The correct answer is locked throughout.**

**Input:** the question, the verified correct answer and the distractors. **No support passage is used.** The LLM relies on its own science knowledge.

---

## 2. Final repository structure (create exactly this; nothing extra)

```
GEN-AI-HACKATHON/
├── CLAUDE.md                    # §0 rules (copied in Phase 0)
├── IMPLEMENTATION.md            # this file
├── README.md                    # how to install and run
├── requirements.txt
├── .env.example                 # GEMINI_API_KEY=your_key_here, GEMINI_MODEL=...
├── .gitignore
├── .streamlit/config.toml       # UI theme (Alliance colours)
├── app.py                       # Streamlit entry point: the 4-step UI
├── src/reviewer/
│   ├── __init__.py
│   ├── config.py                # loads .env and thresholds
│   ├── models.py                # Pydantic data models
│   ├── llm.py                   # Gemini client + retry + disk cache
│   ├── ingest/
│   │   ├── readers.py           # PDF / DOCX / TXT / CSV → raw text or rows
│   │   ├── parser.py            # regex MCQ parser for common formats
│   │   └── llm_extract.py       # Gemini fallback extractor (incl. scanned PDFs)
│   ├── pipeline/
│   │   ├── rules.py             # step 2: rule checks
│   │   ├── similarity.py        # step 3: embedding similarity
│   │   ├── judge.py             # step 4: LLM judge
│   │   ├── generator.py         # step 5: distractor generation
│   │   ├── validator.py         # step 6: validation
│   │   ├── answer_lock.py       # step 7: answer lock
│   │   └── runner.py            # runs steps 1–7 for a list of MCQs
│   └── export.py                # CSV / JSON report + revised DOCX
├── ui/
│   ├── styles.css               # custom CSS injected into Streamlit
│   └── components.py            # small helpers: badges, question card, stepper
├── prompts/
│   ├── extract.md
│   ├── judge.md
│   ├── generate.md
│   └── verify.md
├── scripts/
│   ├── check_setup.py           # verifies .env + Gemini key with one tiny call
│   ├── make_sciq_sample.py      # downloads SciQ, saves 100-question sample
│   ├── make_sample_docx.py      # builds a sample question paper DOCX for demos
│   ├── capture_prompt_samples.py# saves real prompts + responses for the report
│   └── evaluate.py              # planted-flaw evaluation (precision / recall)
├── data/
│   ├── sample/                  # sciq_sample.csv, sample_paper.docx (committed)
│   ├── eval/                    # planted.json, results (committed)
│   └── cache/                   # LLM cache (git-ignored)
├── tests/
│   ├── test_parser.py
│   ├── test_rules.py
│   ├── test_validator.py
│   └── test_answer_lock.py
└── docs/
    ├── IMPLEMENTATION_LOG.md    # one entry per phase (what / why / verify)
    ├── architecture.md          # Mermaid diagram of implemented components
    ├── workflow.md              # step-by-step functioning
    ├── prompt_samples.md        # generated by scripts/capture_prompt_samples.py
    ├── test_cases.md            # initial testing: inputs, outputs, observations
    ├── CHALLENGES.md            # real problems hit during build + fixes
    ├── PENDING.md               # what remains (written in final phase)
    └── screenshots/             # team adds UI screenshots here
```

---

## 3. Tech stack and dependencies

| Package | Why we need it |
|---|---|
| `streamlit` | Web UI in Python; fast to build, easy to demo |
| `pandas` | Holds questions as tables; CSV export |
| `pydantic` (v2) | Strict data models; validates every LLM reply |
| `google-genai` | Official Gemini SDK; supports JSON output with a schema |
| `python-dotenv` | Loads the API key from `.env` |
| `sentence-transformers` | `all-MiniLM-L6-v2` embeddings for similarity (CPU) |
| `pdfplumber` | Extracts text from PDFs |
| `python-docx` | Reads uploaded Word files and writes the revised paper |
| `datasets` | Only in `scripts/make_sciq_sample.py` to fetch SciQ |
| `scikit-learn` | Precision / recall in `scripts/evaluate.py` |
| `pytest` | Unit tests |

**CPU-only PyTorch (important, our laptops have no GPU):** install torch from the CPU index *before* `sentence-transformers`; otherwise pip downloads ~2 GB of CUDA libraries:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```
Python 3.11. Use a virtual environment `.venv`. Development happens on WSL Ubuntu.

---

## 4. Data models (`src/reviewer/models.py`)

```python
class MCQ(BaseModel):
    model_config = ConfigDict(frozen=True)   # immutable → answer cannot be edited in place
    id: str
    question: str
    correct_answer: str                      # VERIFIED, LOCKED
    distractors: list[str]                   # 2–4 items
    source: str                              # e.g. "paper.pdf p.2 Q5" or "SciQ #123"

IssueType = Literal["also_correct", "ambiguous_question", "implausible",
                    "answer_cue", "duplicate", "possible_wrong_answer_key"]
Severity  = Literal["high", "medium", "low"]

class Finding(BaseModel):
    target: str            # "question", "answer_key", or "distractor:<index>"
    issue_type: IssueType
    severity: Severity
    reason: str            # one plain-English sentence
    detected_by: list[Literal["rules", "similarity", "llm"]]

class Suggestion(BaseModel):
    distractor_index: int  # which distractor it replaces
    original: str
    new_text: str
    misconception: str     # the student mistake that makes it tempting
    status: Literal["pending", "accepted", "rejected"] = "pending"

class ReviewResult(BaseModel):
    mcq: MCQ
    findings: list[Finding]
    suggestions: list[Suggestion]
    answer_preserved: bool
```

**Why frozen?** Code that tries to change `correct_answer` raises an error. This is the first layer of the answer lock.

---

## 5. Phases

Each phase lists its **goal**, **what to build**, **why** (for explanations to the judges), **done when** (verification), and the **commit message**.

---

### Phase 0: Project setup

**Goal:** a clean, runnable skeleton with the secret key protected.

Build:
1. `CLAUDE.md` (copy of §0).
2. `.gitignore` containing at least:
   ```
   .env
   .venv/
   __pycache__/
   *.pyc
   data/cache/
   .pytest_cache/
   ```
3. `.env.example`:
   ```
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```
4. `requirements.txt` (§3, without torch; README explains the torch line).
5. `src/reviewer/config.py`: loads `.env` with python-dotenv. Exposes `GEMINI_API_KEY`, `GEMINI_MODEL` and the thresholds below. If the key is missing, fail with the clear message: *"GEMINI_API_KEY not found. Copy .env.example to .env and paste your key."*
   ```python
   SIM_TOO_CLOSE = 0.85   # distractor vs answer: might also be correct
   SIM_TOO_FAR   = 0.20   # distractor vs answer: implausible
   SIM_DUPLICATE = 0.90   # distractor vs distractor: duplicate
   ```
6. `scripts/check_setup.py`: sends one tiny prompt to Gemini and prints "Gemini OK: <model>". If the call fails because the model name is wrong, print the available model names, so the team can update `GEMINI_MODEL` in `.env`.
7. `README.md`: setup steps (venv, CPU torch, requirements, copy `.env.example` → `.env`, run `check_setup.py`, run `streamlit run app.py`).
8. `docs/IMPLEMENTATION_LOG.md` with the Phase 0 entry.

**Why:** a working foundation. `.env` is git-ignored because the repository is on GitHub. A pushed key can be found by bots within minutes and misused on our quota, and Google may revoke it automatically.

**Done when:** `git status` does **not** show `.env`, and `python scripts/check_setup.py` prints "Gemini OK".

**Commit:** `phase 0: project setup, config, secret handling`

---

### Phase 1: Data models and sample data

Build:
1. `models.py` exactly as in §4.
2. `scripts/make_sciq_sample.py`: loads `allenai/sciq` (train split) with `datasets` and saves 100 random questions (fixed seed 42) to `data/sample/sciq_sample.csv` with columns `id, question, correct_answer, distractor1, distractor2, distractor3`. The support column is **not** saved.
3. `scripts/make_sample_docx.py`: writes `data/sample/sample_paper.docx`, a realistic teacher question paper with 10 SciQ questions in the common format:
   ```
   1. What do plants absorb from the air for photosynthesis?
   A) Oxygen   B) Carbon dioxide   C) Nitrogen   D) Hydrogen
   Answer: B
   ```
   Deliberately include 3 flawed questions (one duplicate option, one implausible option, one option that is also correct), so the demo shows findings. The team will export this DOCX to PDF in Word to get a sample PDF. Do not add a PDF library for that.

**Why:** SciQ gives us real, verified science MCQs. The sample paper mimics what teachers actually upload.

**Done when:** both files exist and `python -c "from src.reviewer.models import MCQ"` works.

**Commit:** `phase 1: data models and sample data`

---

### Phase 2: Document ingestion (PDF, DOCX, TXT, CSV)

Teachers should **not** need to prepare a CSV. They upload the question paper as they already have it.

Build:
1. `ingest/readers.py`
   - `read_pdf(bytes) -> str`: pdfplumber, page text joined with page markers.
   - `read_docx(bytes) -> str`: python-docx paragraphs **and** table cells (many papers put options in tables).
   - `read_txt(bytes) -> str`
   - `read_csv(bytes) -> list[MCQ]`: for the SciQ-style CSV only (an optional power-user path).
2. `ingest/parser.py`: regex parser for common formats:
   - Question numbering: `1.`, `1)`, `Q1.`, `Q.1`, `Question 1:`
   - Options: `A)`, `A.`, `(A)`, `a)`, `(a)`, on separate lines **or** on one line
   - Answer key: `Answer: B`, `Ans: B`, `Ans. (b)`, `Correct answer: B`, `Key: B`, or an answer-key block at the end of the paper (`1-B, 2-C …`)
   - Returns `list[ParsedMCQ]` where the answer may be `None` if not found. **Never guess an answer.**
3. `ingest/llm_extract.py`: Gemini fallback used when:
   - the parser finds 0 questions, **or** more than 30% of the parsed questions have fewer than 3 options, **or**
   - the PDF has no selectable text (a scanned paper). In that case, send the PDF bytes directly to Gemini as a document part (Gemini reads PDFs natively, so no OCR library is needed).
   - Uses `prompts/extract.md` and a Pydantic response schema. Rules in the prompt: copy text **verbatim**, do not correct or rephrase anything, and set the answer to `null` unless the document explicitly marks it.
4. Convert parsed items to `MCQ` only **after** the teacher confirms answers in the UI (Phase 5).

**Why:** a regex runs first because it is free, fast and predictable. The LLM handles messy or scanned layouts. The teacher always confirms the answer key, so the "verified answer" really is verified by a human.

**Done when:** `pytest tests/test_parser.py` passes (cover each numbering, option and answer format above), and running the readers on `sample_paper.docx` yields 10 questions with answers.

**Commit:** `phase 2: PDF/DOCX/TXT/CSV ingestion with regex parser and LLM fallback`

---

### Phase 3: Detection (pipeline steps 2–4)

Build:
1. `pipeline/rules.py` → `list[Finding]` with `detected_by=["rules"]`:
   - **duplicate:** two options are equal after lowercasing, stripping punctuation and articles (a/an/the) and singularising simple plurals → `low`
   - **distractor equals answer** after the same normalisation → `also_correct`, `high`
   - **answer_cue (length):** the answer is more than 1.8× longer than every distractor → `medium`, target `question`
   - **answer_cue (grammar):** the question ends with "an" and only the answer starts with a vowel (or the reverse with "a") → `medium`
   - **"all of the above" / "none of the above"** present → `low`, `ambiguous_question`
2. `pipeline/similarity.py`: loads `all-MiniLM-L6-v2` **once** (cached with `st.cache_resource` from the UI; a plain module-level cache elsewhere). Computes cosine similarity with `util.cos_sim`:
   - distractor vs answer > `SIM_TOO_CLOSE` → `also_correct`, `medium` (the LLM may raise it to high)
   - distractor vs answer < `SIM_TOO_FAR` → `implausible`, `medium`
   - distractor vs distractor > `SIM_DUPLICATE` → `duplicate`, `low`
   - Returns the scores as well; they are passed to the judge as hints.
3. `pipeline/judge.py`: **one Gemini call per question** (saves free-tier quota), using `prompts/judge.md`, temperature 0.2, JSON output with this schema:
   ```python
   class OptionVerdict(BaseModel):
       option_index: int
       is_also_correct: Literal["yes", "partly", "no"]
       plausibility: int            # 1 (absurd) .. 5 (very tempting)
       issue_type: IssueType | None
       reason: str                  # ≤ 25 words
   class JudgeOutput(BaseModel):
       question_ambiguous: bool
       question_reason: str
       options: list[OptionVerdict]
       answer_key_agrees: bool       # does the LLM agree the given answer is correct?
       answer_key_reason: str
   ```
   Severity mapping:

   | LLM verdict | Finding |
   |---|---|
   | `is_also_correct = yes` | also_correct, **high** |
   | `is_also_correct = partly` | also_correct, **medium** |
   | `question_ambiguous = true` | ambiguous_question, **high** |
   | `plausibility ≤ 2` | implausible, **medium** |
   | `answer_key_agrees = false` | possible_wrong_answer_key, **high** (flag only, **never change the answer**) |

4. **Merge** rule, similarity and LLM findings per target: keep one finding per (target, issue_type), use the highest severity, combine `detected_by`, and prefer the LLM's reason text.

**Why:** cheap checks first, then embeddings, then the LLM, the most expensive and most capable. Layering makes each finding explainable (the UI shows *which* layer caught it).

**Done when:** `pytest tests/test_rules.py` passes, and running detection on the 10 sample-paper questions flags all 3 planted flaws.

**Commit:** `phase 3: rule checks, similarity scan and LLM judge`

---

### Phase 4: Improvement and guard (pipeline steps 5–7)

Build:
1. `pipeline/generator.py`: for each distractor with a **high or medium** finding, ask Gemini (`prompts/generate.md`, **one call per question** covering all weak distractors) for 3 candidates, each with `text` and `misconception`.
2. `pipeline/validator.py`: reject a candidate if **any** of these hold:
   - it equals the answer after normalisation, or has similarity > `SIM_TOO_CLOSE` to the answer
   - it duplicates an existing option (similarity > `SIM_DUPLICATE`)
   - its length is more than 2.5× or less than 0.4× the answer's length (an answer cue)
   - it contains "all of the above" / "none of the above"
   - the verify call (`prompts/verify.md`, one batched Gemini call per question) says it **is** a correct answer

   Keep the first valid candidate per distractor. If none are valid, retry generation **once**; if still none, record no suggestion and add the reason "No safe replacement found", and keep the finding.
3. `pipeline/answer_lock.py`:
   - `fingerprint(mcq)`: SHA-256 of `correct_answer`, taken at load time.
   - `verify(original, result) -> bool`: the answer string must be identical character for character and the fingerprint must match. On mismatch: discard the result, set `answer_preserved=False`, and record it in the UI and the report.
4. `pipeline/runner.py`: `review(mcqs, progress_callback) -> list[ReviewResult]`, which runs steps 2–7 for each MCQ and calls `progress_callback(i, n)` for the UI progress bar.
5. `llm.py` (used by all LLM steps):
   - `call_json(prompt_name, payload, schema)`: loads the prompt file, calls Gemini with `response_mime_type="application/json"` and `response_schema=schema`, and returns the parsed Pydantic object.
   - **Disk cache** in `data/cache/llm_cache.json`, keyed by the SHA-256 of model + prompt + payload. This saves free-tier quota and makes the live demo instant and repeatable.
   - **Retry:** on rate-limit or server errors, wait 2 s, 4 s, then 8 s; then raise a clear error that the UI shows as *"Gemini is busy (free-tier limit). Wait a minute and press Retry."*
   - If the installed `google-genai` version uses different call names than expected, **stop and ask**; do not write workarounds.

**Why:** generation without validation is unsafe, because the LLM can accidentally produce a second correct answer. The validator plus the answer lock guarantee the hard rule.

**Done when:** `pytest tests/test_validator.py tests/test_answer_lock.py` passes. The answer-lock test proves that a tampered result is caught, and the validator test proves that a candidate equal to the answer is rejected. Running the full pipeline on the sample paper gives suggestions for every flawed distractor.

**Commit:** `phase 4: distractor generation, validation and answer lock`

---

### Phase 5: User interface (`app.py`, `ui/`)

**The UI must look polished and professional, not like a default Streamlit app.** It has one page with a 4-step flow, plus a header stepper.

**Theme** (`.streamlit/config.toml` + `ui/styles.css`), Alliance University colours:
- Primary maroon `#8E0A13`, navy `#012258`, ink `#061F39`, light blue `#E9EEF6`, light pink `#F8ECED`, background `#F7F8FA`
- Headings in Poppins (Google Fonts `@import` in `styles.css`), body in the system sans-serif
- Cards: white, 10 px radius, soft shadow; buttons in maroon; hide Streamlit's default menu and footer with CSS
- Severity badges always show **text + colour**: `HIGH` maroon, `MEDIUM` amber `#9A5B00`, `LOW` grey, `OK` green `#1E7B4F`

**Header:** app title "MCQ Distractor Reviewer", subtitle "PS 84 · Alliance University", and a 4-step stepper (Upload → Confirm → Review → Results) that highlights the current step. Use `st.session_state` to hold the current step and data.

**Step 1: Upload**
- A large drag-and-drop area accepting **PDF, DOCX, TXT** (and CSV, shown as a small "Advanced" option).
- A "Try a sample paper" button that loads `data/sample/sample_paper.docx`.
- After upload: `st.status` showing "Reading file → Finding questions → Done (N questions found)". If the LLM fallback was used, say so in one line.

**Step 2: Confirm questions and answer key**
- An editable table (`st.data_editor`): question, options A–D, answer (a dropdown A–D).
- Rows without an answer are highlighted with the message *"Select the correct answer for these questions. The reviewer never guesses answers."*
- The "Start review" button stays disabled until every row has an answer. After confirmation, convert rows to frozen `MCQ` objects. From this point the answer is locked.

**Step 3: Review running**
- A progress bar with "Reviewing question i of n", and a live count of findings so far.

**Step 4: Results**
- **Summary row** (`st.metric` cards): questions reviewed · high / medium / low findings · suggestions made · **Answers preserved: n/n (100%)**.
- **Filters:** severity (multiselect), issue type, and "show only questions with issues".
- **Question card** for each question:
  - The question text, then the options as rows: letter · text · badge. The correct answer is marked "🔒 Verified answer (locked)".
  - A findings list: badge + issue type + reason + small "detected by: rules / similarity / LLM" chips.
  - If `possible_wrong_answer_key`: a maroon banner, *"The reviewer thinks the answer key may be wrong. Please check. (The answer has NOT been changed.)"*
  - A suggestion block for each weak distractor: original → new text, the misconception in italics, and **Accept** / **Reject** buttons. Accepting replaces that distractor in the *revised* set only.
- An **Export** section at the bottom (Phase 6).

**Why:** teachers are the users, so the flow must need zero technical knowledge. The confirm step ensures the answer really is verified, and accept/reject keeps the teacher in control.

**Done when:** the full flow works with the sample DOCX and with a PDF exported from it, and nothing breaks on a refresh mid-flow (session state holds the data). The team takes screenshots of every step for `docs/screenshots/`.

**Commit:** `phase 5: streamlit UI with upload, confirm, review and results`

---

### Phase 6: Export (`src/reviewer/export.py`)

Build three downloads (`st.download_button`):
1. **Revised question paper (.docx):** questions with accepted suggestions applied; answers unchanged; an answer key at the end.
2. **Review report (.csv):** one row per finding (question id, target, issue type, severity, reason, detected by, suggestion, status).
3. **Full results (.json):** a dump of all `ReviewResult` objects.

**Why:** teachers work in Word, the CSV is for analysis, and the JSON is our evidence for evaluation and the report.

**Done when:** all three files download and open correctly, and the answers in the DOCX match the confirmed answers.

**Commit:** `phase 6: export revised paper, CSV report and JSON`

---

### Phase 7: Evaluation and tests

Build `scripts/evaluate.py`:
1. Take 30 SciQ questions from the sample (seed 42).
2. Plant one known flaw in 24 of them (8 of each type) and leave 6 clean:
   - **also_correct:** replace a distractor with a paraphrase of the answer (generate the paraphrases once with Gemini and store them in `data/eval/planted.json`, so runs are repeatable)
   - **implausible:** replace a distractor with an unrelated everyday object ("a bicycle", "a teacup", …)
   - **duplicate:** replace a distractor with a case/plural variant of another distractor
3. Run the pipeline and compare the findings with the planted labels per (question, distractor index, issue type).
4. Print and save to `data/eval/results.md`: precision, recall and F1 per flaw type and overall (scikit-learn); the % of suggestions passing validation; and **answer preserved: n/n**.
5. Note in the output that clean SciQ items can contain real flaws, which lowers measured precision. This is expected.

Make sure all 4 test files pass: `pytest -q`.

**Done when:** `python scripts/evaluate.py` prints the metrics table, and `pytest -q` is green.

**Commit:** `phase 7: planted-flaw evaluation and unit tests`

---

### Phase 8: Documentation for Review 2

Build:
1. `docs/architecture.md`: a Mermaid diagram of the **implemented** components (Streamlit UI → ingest → pipeline steps 2–7 → export; services: Gemini API, MiniLM, LLM cache), plus one paragraph per component.
2. `docs/workflow.md`: the step-by-step flow from upload to export, in plain English.
3. `scripts/capture_prompt_samples.py`: runs extract, judge, generate and verify on 2 sample questions and writes `docs/prompt_samples.md` with the exact prompt, input and raw JSON response for each.
4. `docs/test_cases.md`: a table of at least 8 test cases (clean question, duplicate, implausible, also-correct, wrong answer key, scanned PDF, DOCX with a table layout, paper without an answer key), each with input, expected result, actual result and observation. Fill it by actually running them.
5. `docs/CHALLENGES.md`: real issues met during phases 0–7 and how each was solved. Add to it as you go, not at the end from imagination.
6. `docs/PENDING.md`: anything not finished or not tested.
7. Update `README.md` with run instructions and a "How it works" summary.

**Commit:** `phase 8: documentation for review 2`

---

## 6. Prompt drafts (put these in `prompts/`, refine only if tests show problems)

**`prompts/judge.md`**
```
You are an experienced school science teacher reviewing one multiple-choice question.

The VERIFIED correct answer is given. Do not rewrite it. You may only report whether you
agree with it in answer_key_agrees.

For EACH distractor (wrong option), decide using accepted science knowledge:
- is_also_correct: "yes" if it is also a correct answer, "partly" if a reasonable student
  could defend it, otherwise "no".
- plausibility: 1 = absurd or unrelated, 5 = very tempting for a student who has a
  misconception.
- issue_type: one of also_correct, implausible, duplicate, answer_cue, or null if fine.
- reason: one sentence, max 25 words, a teacher-friendly explanation.

Also decide whether the question itself is ambiguous (more than one defensible answer
because of its wording).

Hints from earlier checks (may be wrong, use your judgement): {rule_flags}, {similarity_scores}

Question: {question}
Verified answer: {correct_answer}
Distractors (index: text): {distractors}

Return JSON only, matching the schema.
```

**`prompts/generate.md`**
```
You write wrong options (distractors) for a science MCQ.

Question: {question}
Verified correct answer (do not change, do not paraphrase): {correct_answer}
Other options that stay: {kept_options}
Distractors to replace (index: text, problem): {weak_distractors}

For each distractor to replace, give 3 candidates. Each candidate must:
- be scientifically WRONG for this question
- reflect a real, common student misconception (state it in "misconception")
- match the answer's type and format (number for number, organ for organ…)
- be of similar length to the answer
- not be a synonym or paraphrase of the answer, and not repeat an existing option
- not be "all of the above" or "none of the above"

Return JSON only, matching the schema.
```

**`prompts/verify.md`**
```
Question: {question}
For each candidate below, answer strictly: could it be marked correct by a science teacher?
Candidates (index: text): {candidates}
Return JSON only: [{index, is_correct: true|false}].
```

**`prompts/extract.md`**
```
Extract every multiple-choice question from this document.
Rules:
- Copy question and option text EXACTLY as written. Do not fix spelling or rephrase.
- Set "answer" to the option letter ONLY if the document explicitly marks it
  (e.g. "Answer: B", an answer key table). Otherwise set it to null. Never guess.
- Ignore instructions, headers, marks and page numbers.
Return JSON only, matching the schema.
```

---

## 7. Review 2 checklist: where each required section comes from

| # | Review 2 section | Source in this repo |
|---|---|---|
| 1 | Team and problem details | README + §1 |
| 2 | Review 1 feedback | **Team writes** the judges' comments and the actions taken (Claude Code: leave a placeholder in README) |
| 3 | Data preparation | Phase 1 (SciQ sample) + Phase 2 (document ingestion) + `IMPLEMENTATION_LOG.md` |
| 4 | GenAI implementation | `llm.py`, `config.py`, prompts: model name, temperature 0.2, JSON schema output, cache, retry |
| 5 | System architecture | `docs/architecture.md` (Mermaid) |
| 6 | Workflow implementation | `docs/workflow.md` |
| 7 | Core functional prototype | The running app (phases 2–6) |
| 8 | Initial prompt design | `prompts/` + `docs/prompt_samples.md` |
| 9 | Initial testing | `docs/test_cases.md` + `data/eval/results.md` + `pytest` |
| 10 | Screenshots | `docs/screenshots/` (team captures each UI step + eval output) |
| 11 | Challenges and solutions | `docs/CHALLENGES.md` |
| 12 | Individual contribution | Team fills in (suggested split below) |
| 13 | Pending activities | `docs/PENDING.md` |
| + | Deliverables | Working prototype, repo link, sample inputs (`data/sample/`), generated outputs (exports + `data/eval/`) |

**Suggested split** (the team may change it):
- **Basavaraj:** repo setup, ingestion (Phase 0–2)
- **Mahesh:** LLM judge, generator, prompts (Phase 3–4 LLM parts)
- **Venkatesh:** rules, similarity, validator, answer lock, evaluation (Phase 3–4 non-LLM parts, Phase 7)
- **Anika:** UI and export (Phase 5–6), screenshots

Each person should be able to explain their own modules using the docstrings and `IMPLEMENTATION_LOG.md`.

---

## 8. Format of `docs/IMPLEMENTATION_LOG.md` entries

```
## Phase N: <name>  (date)
**What we built:** 2–4 sentences.
**Why:** 1–3 sentences, the design reason.
**Files:** list of files created or changed.
**How to verify:** exact command(s) and expected output.
**Notes / issues:** anything surprising (also add it to CHALLENGES.md).
```
