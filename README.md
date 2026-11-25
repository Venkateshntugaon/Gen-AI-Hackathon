# GEN-AI-HACKATHON — PS 84: Scientific MCQ Distractor Reviewer

> *Develop a GenAI application that processes existing science questions and answer options. The system should produce ambiguity findings and improved distractor suggestions. The prototype must preserve the verified correct answer.*

A teacher uploads a question paper (PDF, Word or text). The app extracts the MCQs and lets the teacher confirm the answer key. It then finds flawed wrong options (distractors), explains each flaw, and suggests better, misconception-based distractors. The teacher accepts or rejects each suggestion and downloads a revised paper and a review report. **The verified correct answer is locked throughout.**

Team: Anika Ramya Shetty · Basavaraj Babasab Billur · Mahesh · Venkatesh Tugaon
(AI/ML-F, VII Sem, Alliance University)

The full build plan is in [IMPLEMENTATION.md](IMPLEMENTATION.md); the per-phase log is in [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md).

## Setup (WSL Ubuntu)

```bash
# 1. Create and activate a virtual environment (Python 3.11+; we use 3.13)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install everything (requirements.txt pins CPU-only PyTorch, so no ~2 GB CUDA download)
pip install -r requirements.txt

# 3. Add your Gemini API key (copy, do not rename, the example file)
cp .env.example .env
#    then open .env and paste your key after GEMINI_API_KEY=

# 4. Check that the key and model work
python scripts/check_setup.py      # expected: "Gemini OK: gemini-3.5-flash"
```

`.env` is git-ignored. Never commit it or paste the key anywhere else.

**Free-tier limits.** A free Gemini key allows only a few requests per minute and a small number per day for each model (we measured 20 per day for gemini-3.5-flash). Reviewing one question takes about 3 calls. If the daily limit is reached, the app says so; set another model in `GEMINI_MODEL` in `.env` (e.g. `gemini-3.5-flash-lite`). `check_setup.py` lists the models your key can use. All replies are cached in `data/cache/`, so nothing is asked twice.

## Run

```bash
source .venv/bin/activate
streamlit run app.py               # opens http://localhost:8501
```

Press **Try a sample paper** to review `data/sample/sample_paper.docx` (10 questions, 3 with planted flaws).

Other commands:

```bash
pytest -q                                   # unit tests
python scripts/evaluate.py                  # planted-flaw evaluation → data/eval/results.md
python scripts/capture_prompt_samples.py    # real prompts + replies → docs/prompt_samples.md
python scripts/make_sciq_sample.py          # rebuild data/sample/sciq_sample.csv
python scripts/make_sample_docx.py          # rebuild data/sample/sample_paper.docx
```

## Deploy (Streamlit Community Cloud, from this GitHub repo)

1. Go to https://share.streamlit.io and sign in with the GitHub account that owns this repo.
2. **Create app** → "Deploy a public app from GitHub" → repository `basavarajbillur000/GEN-AI-HACKATHON`, branch `main`, main file `app.py`.
3. **Advanced settings** → Python version **3.13**, and paste the secrets (TOML):
   ```toml
   GEMINI_API_KEY = "your_key_here"
   GEMINI_MODEL = "gemini-3.5-flash-lite"
   ```
   Root-level secrets become environment variables, which `src/reviewer/config.py` already reads, so no code change is needed. Never put the key in the repository.
4. **Deploy**. The first build takes a few minutes (it installs CPU PyTorch and downloads the MiniLM model). Every push to `main` redeploys automatically.

The deployed app uses the team's Gemini key and its free-tier quota for every visitor. To limit who can use it, set the app to private under **Settings → Sharing** and invite the team and judges by email.

## How it works

1. **Upload:** PDF, DOCX or TXT is read into text, and a regex parser finds the questions, options and answers. Scanned PDFs or messy layouts are extracted by Gemini instead, which copies text verbatim and never guesses answers.
2. **Confirm:** the teacher checks the table and selects any missing answers. Then every question becomes an immutable `MCQ`, and the answer is locked.
3. **Review:** each question goes through
   - rule checks (duplicates, answer cues, "all of the above"),
   - an embedding similarity scan (all-MiniLM-L6-v2, CPU),
   - a Gemini judge (one JSON call per question, temperature 0.2),
   - distractor generation (3 misconception-based candidates per weak distractor),
   - validation (similarity and length checks plus a Gemini verify call),
   - an answer lock (SHA-256 fingerprint check).
4. **Results:** findings with severity badges and the layers that detected them, a banner if the answer key may be wrong (it is never changed), and suggestions with Accept/Reject.
5. **Export:** the revised paper (.docx, answers unchanged and an answer key), the review report (.csv) and the full results (.json).

More detail: [docs/architecture.md](docs/architecture.md) · [docs/workflow.md](docs/workflow.md) · [docs/prompt_samples.md](docs/prompt_samples.md) · [docs/test_cases.md](docs/test_cases.md) · [data/eval/results.md](data/eval/results.md) · [docs/CHALLENGES.md](docs/CHALLENGES.md) · [docs/PENDING.md](docs/PENDING.md)

## Review 1 feedback

_Placeholder: the team writes the judges' comments and the actions taken here._

## Individual contribution

_Placeholder: the team fills this in (suggested split in IMPLEMENTATION.md §7)._
