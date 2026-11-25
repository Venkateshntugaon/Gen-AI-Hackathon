# GEN-AI-HACKATHON — PS 84: Scientific MCQ Distractor Reviewer

A GenAI app that reviews science multiple-choice questions: it finds flawed wrong
options (distractors), explains each flaw, and suggests better, misconception-based
distractors. **The verified correct answer is never changed.**

Team: Anika Ramya Shetty · Basavaraj Babasab Billur · Mahesh · Venkatesh Tugaon
(AI/ML-F, VII Sem, Alliance University)

The full build plan is in [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Setup (WSL Ubuntu)

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install CPU-only PyTorch FIRST (otherwise pip downloads ~2 GB of CUDA libraries)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. Install the rest
pip install -r requirements.txt

# 4. Add your Gemini API key
cp .env.example .env
#    then open .env and paste your key after GEMINI_API_KEY=

# 5. Check that the key and model work
python scripts/check_setup.py      # expected: "Gemini OK: gemini-3.5-flash"

# 6. Run the app
streamlit run app.py
```

`.env` is git-ignored. Never commit it or paste the key anywhere else.

## Review 1 feedback

_Placeholder: the team writes the judges' comments and the actions taken here._
