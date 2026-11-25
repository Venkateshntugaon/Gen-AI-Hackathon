"""Tests for the answer lock (src/reviewer/pipeline/answer_lock.py).

They prove that (1) the MCQ answer cannot be edited in place, and (2) a tampered
result is caught, discarded and marked answer_preserved=False.
"""

import pytest
from pydantic import ValidationError

from src.reviewer.models import MCQ, ReviewResult, Suggestion
from src.reviewer.pipeline import answer_lock

ORIGINAL = MCQ(id="q1", question="What do plants absorb for photosynthesis?",
               correct_answer="Carbon dioxide", distractors=["Oxygen", "Nitrogen", "Hydrogen"],
               source="test")
SUGGESTION = Suggestion(distractor_index=0, original="Oxygen", new_text="Water vapour",
                        misconception="plants breathe in water")


def result_for(mcq: MCQ) -> ReviewResult:
    return ReviewResult(mcq=mcq, findings=[], suggestions=[SUGGESTION], answer_preserved=True)


def test_answer_cannot_be_edited_in_place():
    with pytest.raises(ValidationError):
        ORIGINAL.correct_answer = "Oxygen"


def test_untouched_result_passes():
    lock = answer_lock.fingerprint(ORIGINAL)
    result = answer_lock.enforce(ORIGINAL, result_for(ORIGINAL), lock)
    assert result.answer_preserved is True
    assert result.suggestions == [SUGGESTION]


@pytest.mark.parametrize("tampered_answer", ["Oxygen", "carbon dioxide", "Carbon dioxide ", "Carbon Dioxide"])
def test_tampered_result_is_caught_and_discarded(tampered_answer):
    lock = answer_lock.fingerprint(ORIGINAL)
    tampered = ORIGINAL.model_copy(update={"correct_answer": tampered_answer})
    assert answer_lock.verify(ORIGINAL, result_for(tampered), lock) is False

    result = answer_lock.enforce(ORIGINAL, result_for(tampered), lock)
    assert result.answer_preserved is False
    assert result.mcq.correct_answer == "Carbon dioxide"   # original kept
    assert result.suggestions == []                        # tampered output discarded


def test_fingerprint_is_sha256_of_answer():
    import hashlib
    assert answer_lock.fingerprint(ORIGINAL) == hashlib.sha256(b"Carbon dioxide").hexdigest()
