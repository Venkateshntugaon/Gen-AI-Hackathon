"""Pipeline step 3: embedding similarity between the options of one MCQ.

Why this file exists: meaning-level checks that plain text rules miss. We turn each
option into a vector with the small all-MiniLM-L6-v2 model (runs on CPU) and
compare them with cosine similarity:
  - distractor very close to the answer  → might also be correct
  - distractor very far from the answer  → implausible (unrelated)
  - two distractors very close           → duplicate
The scores are also passed to the LLM judge as hints.
"""

import re

from sentence_transformers import SentenceTransformer, util

from src.reviewer import config
from src.reviewer.models import MCQ, Finding

MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None

NUMBER_RE = re.compile(r"^[-+±~≈]?\s*\d[\d.,]*(?:\s*[×x*]\s*10\^?[-−]?\d+)?")
NUMBER_WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "eleven", "twelve", "twenty", "hundred", "thousand", "million", "half", "none"}


def is_mainly_number(text: str) -> bool:
    """True for "100 °C", "29", "3.5 m/s", "6 × 10^23", "Two": numbers with or without units.

    Embeddings cannot compare numbers ("50 °C" and "100 °C" score 0.91), so the
    too-close / too-far checks are skipped for them.
    """
    text = text.strip()
    if text.lower() in NUMBER_WORDS:
        return True
    match = NUMBER_RE.match(text)
    if not match:
        return False
    unit = text[match.end():].strip()
    return len(unit.split()) <= 3 and len(re.sub(r"[^A-Za-z]", "", unit)) <= 15


def get_model() -> SentenceTransformer:
    """Load the embedding model once and reuse it (loading takes a few seconds)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def similarity_scores(texts_a: list[str], texts_b: list[str]) -> list[list[float]]:
    """Cosine similarity of every text in texts_a against every text in texts_b."""
    model = get_model()
    emb_a = model.encode(texts_a, convert_to_tensor=True)
    emb_b = model.encode(texts_b, convert_to_tensor=True)
    return util.cos_sim(emb_a, emb_b).tolist()


def check_similarity(mcq: MCQ) -> tuple[list[Finding], dict]:
    """Return (findings, scores) for one MCQ."""
    distractors = mcq.distractors
    to_answer = [row[0] for row in similarity_scores(distractors, [mcq.correct_answer])]
    pairwise = similarity_scores(distractors, distractors)

    findings = []
    for i, score in enumerate(to_answer):
        if is_mainly_number(mcq.correct_answer) or is_mainly_number(distractors[i]):
            continue   # meaning-similarity is not meaningful for numbers
        if score > config.SIM_TOO_CLOSE:
            findings.append(_finding(i, "also_correct", "medium",
                                     f'"{distractors[i]}" means almost the same as the correct answer (similarity {score:.2f}).'))
        elif score < config.SIM_TOO_FAR:
            findings.append(_finding(i, "implausible", "medium",
                                     f'"{distractors[i]}" is unrelated to the correct answer (similarity {score:.2f}).'))

    pair_scores = {}
    for i in range(len(distractors)):
        for j in range(i + 1, len(distractors)):
            pair_scores[f"{i}-{j}"] = round(pairwise[i][j], 2)
            if pairwise[i][j] > config.SIM_DUPLICATE:
                findings.append(_finding(j, "duplicate", "low",
                                         f'"{distractors[j]}" is nearly the same as "{distractors[i]}" (similarity {pairwise[i][j]:.2f}).'))

    scores = {
        "distractor_vs_answer": {str(i): round(s, 2) for i, s in enumerate(to_answer)},
        "distractor_vs_distractor": pair_scores,
    }
    return findings, scores


def _finding(index: int, issue_type: str, severity: str, reason: str) -> Finding:
    return Finding(target=f"distractor:{index}", issue_type=issue_type, severity=severity,
                   reason=reason, detected_by=["similarity"])
