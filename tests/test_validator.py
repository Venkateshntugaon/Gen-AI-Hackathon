"""Tests for the distractor validator (src/reviewer/pipeline/validator.py).

The Gemini verify call is replaced by a fake, so these tests run offline.
The embedding model (MiniLM) runs locally.
"""

from src.reviewer.models import MCQ
from src.reviewer.pipeline import validator
from src.reviewer.pipeline.generator import Candidate
from src.reviewer.pipeline.validator import choose_valid, local_reject_reason

MCQ_ = MCQ(id="t", question="What is the part of the flower that produces pollen?",
           correct_answer="Stamen", distractors=["A bicycle", "Stigma", "Leaves"], source="test")
OTHERS = ["Stamen", "Stigma", "Leaves"]


def test_candidate_equal_to_answer_is_rejected():
    assert local_reject_reason("the stamen.", MCQ_, OTHERS) == "same as the correct answer"


def test_candidate_repeating_an_option_is_rejected():
    assert local_reject_reason("Stigmas", MCQ_, OTHERS) == "repeats an existing option"


def test_all_of_the_above_is_rejected():
    assert local_reject_reason("All of the above", MCQ_, OTHERS) == "uses all/none of the above"


def test_length_cue_is_rejected():
    assert local_reject_reason("The green leaves around the base of the flower", MCQ_, OTHERS) == \
        "length gives away the answer"
    assert local_reject_reason("Ox", MCQ_, OTHERS) == "length gives away the answer"


def test_good_candidate_passes_local_checks():
    assert local_reject_reason("Petal", MCQ_, OTHERS) is None


def test_choose_valid_skips_candidates_the_llm_calls_correct(monkeypatch):
    # Fake verify: "Anther" (part of the stamen) could be marked correct.
    monkeypatch.setattr(validator, "verify_with_llm",
                        lambda mcq, texts: [t == "Anther" for t in texts])
    candidates = {0: [Candidate(text="stamen", misconception="x"),
                      Candidate(text="Anther", misconception="x"),
                      Candidate(text="Ovary", misconception="female part")]}
    chosen, rejected = choose_valid(MCQ_, candidates)
    assert chosen[0].text == "Ovary"
    assert "stamen" in rejected and "Anther" in rejected


def test_choose_valid_returns_nothing_when_all_unsafe(monkeypatch):
    monkeypatch.setattr(validator, "verify_with_llm", lambda mcq, texts: [True] * len(texts))
    chosen, _ = choose_valid(MCQ_, {0: [Candidate(text="Petal", misconception="x")]})
    assert chosen == {}
