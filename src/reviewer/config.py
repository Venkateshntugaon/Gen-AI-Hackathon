"""Project settings: the Gemini key, the model name and the similarity thresholds.

Why this file exists: every other module reads its settings from one place.
The API key is loaded from the git-ignored .env file, never from source code,
so it is never committed to GitHub.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Similarity thresholds (cosine similarity, 0..1) used by the embedding checks.
SIM_TOO_CLOSE = 0.85   # distractor vs answer: might also be correct
SIM_TOO_FAR   = 0.20   # distractor vs answer: implausible
SIM_DUPLICATE = 0.90   # distractor vs distractor: duplicate

MISSING_KEY_MESSAGE = "GEMINI_API_KEY not found. Copy .env.example to .env and paste your key."


def get_api_key() -> str:
    """Return the Gemini API key, or stop with a clear message if it is missing."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key == "your_key_here":
        raise RuntimeError(MISSING_KEY_MESSAGE)
    return key


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
