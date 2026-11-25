"""Pipeline step 7: the answer lock. Proves the verified answer was never changed.

Why this file exists: the hard rule of the project is that the verified correct
answer is preserved. MCQ objects are already frozen (layer 1). This file adds
layer 2: a SHA-256 fingerprint of the answer taken when the question is loaded,
and a check after the review that the answer is identical character for character
and the fingerprint still matches. If not, the result is discarded.
"""

import hashlib

from src.reviewer.models import MCQ, ReviewResult


def fingerprint(mcq: MCQ) -> str:
    """SHA-256 of the correct answer, taken at load time."""
    return hashlib.sha256(mcq.correct_answer.encode("utf-8")).hexdigest()


def verify(original: MCQ, result: ReviewResult, original_fingerprint: str | None = None) -> bool:
    """True only if the result's answer is exactly the original answer."""
    expected = original_fingerprint or fingerprint(original)
    return (result.mcq.correct_answer == original.correct_answer
            and fingerprint(result.mcq) == expected)


def enforce(original: MCQ, result: ReviewResult, original_fingerprint: str) -> ReviewResult:
    """Return the result if the answer is intact; otherwise discard it.

    A discarded result keeps the ORIGINAL question, drops all suggestions and
    sets answer_preserved=False so the UI and the report show the problem.
    """
    if verify(original, result, original_fingerprint):
        return result.model_copy(update={"answer_preserved": True})
    return ReviewResult(mcq=original, findings=result.findings, suggestions=[], answer_preserved=False)
