"""Tests for the regex MCQ parser (src/reviewer/ingest/parser.py).

Each supported numbering, option and answer format has a test, plus the
"never guess an answer" rule and the decision to fall back to Gemini.
"""

import pytest

from src.reviewer.ingest.parser import ParsedMCQ, needs_llm_fallback, parse


def only(text: str) -> ParsedMCQ:
    parsed = parse(text)
    assert len(parsed) == 1
    return parsed[0]


# ---------- question numbering ----------

@pytest.mark.parametrize("prefix", ["1.", "1)", "Q1.", "Q.1", "Question 1:"])
def test_numbering_formats(prefix):
    q = only(f"{prefix} What do plants absorb?\nA) Oxygen\nB) Carbon dioxide\nC) Nitrogen\nD) Hydrogen\nAnswer: B")
    assert q.number == 1
    assert q.question == "What do plants absorb?"
    assert q.options == ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"]
    assert q.answer == "B"


def test_question_text_on_next_line():
    q = only("Question 3:\nWhat is H2O?\nA) Water\nB) Salt\nC) Sugar")
    assert q.number == 3
    assert q.question == "What is H2O?"


def test_multiline_question_text():
    q = only("1. Which gas do plants\nabsorb from the air?\nA) Oxygen\nB) Carbon dioxide\nC) Nitrogen")
    assert q.question == "Which gas do plants absorb from the air?"


# ---------- option formats ----------

@pytest.mark.parametrize("markers", [
    ("A)", "B)", "C)", "D)"),
    ("A.", "B.", "C.", "D."),
    ("(A)", "(B)", "(C)", "(D)"),
    ("a)", "b)", "c)", "d)"),
    ("(a)", "(b)", "(c)", "(d)"),
])
def test_option_formats_on_separate_lines(markers):
    lines = "\n".join(f"{m} Option {i}" for i, m in enumerate(markers))
    q = only(f"1. Question?\n{lines}")
    assert q.options == ["Option 0", "Option 1", "Option 2", "Option 3"]


@pytest.mark.parametrize("markers", [
    ("A)", "B)", "C)", "D)"),
    ("A.", "B.", "C.", "D."),
    ("(A)", "(B)", "(C)", "(D)"),
    ("a)", "b)", "c)", "d)"),
    ("(a)", "(b)", "(c)", "(d)"),
])
def test_option_formats_on_one_line(markers):
    line = "   ".join(f"{m} Option {i}" for i, m in enumerate(markers))
    q = only(f"1. Question?\n{line}")
    assert q.options == ["Option 0", "Option 1", "Option 2", "Option 3"]


def test_options_on_two_lines():
    q = only("1. Question?\nA) Oxygen   B) Carbon dioxide\nC) Nitrogen   D) Hydrogen")
    assert q.options == ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"]


def test_letter_inside_option_text_is_not_a_new_option():
    q = only("1. Which vitamin is in oranges?\nA) Vitamin C.   B) Vitamin D.   C) Iron   D) Zinc")
    assert q.options == ["Vitamin C.", "Vitamin D.", "Iron", "Zinc"]


# ---------- answer formats ----------

@pytest.mark.parametrize("answer_line", [
    "Answer: B", "Ans: B", "Ans. (b)", "Correct answer: B", "Key: B", "Answer - b", "ANSWER: (B)",
])
def test_answer_formats(answer_line):
    q = only(f"1. Question?\nA) One\nB) Two\nC) Three\n{answer_line}")
    assert q.answer == "B"


def test_answer_key_block_at_end():
    text = (
        "1. First?\nA) a1\nB) b1\nC) c1\n"
        "2. Second?\nA) a2\nB) b2\nC) c2\n"
        "3. Third?\nA) a3\nB) b3\nC) c3\n"
        "Answer Key\n1-B, 2-C\n3-A"
    )
    assert [q.answer for q in parse(text)] == ["B", "C", "A"]


def test_answer_key_line_without_heading():
    text = "1. First?\nA) a1\nB) b1\nC) c1\n2. Second?\nA) a2\nB) b2\nC) c2\n1-C, 2-A"
    assert [q.answer for q in parse(text)] == ["C", "A"]


def test_missing_answer_is_none_never_guessed():
    q = only("1. Question?\nA) One\nB) Two\nC) Three")
    assert q.answer is None


def test_answer_letter_outside_options_is_dropped():
    q = only("1. Question?\nA) One\nB) Two\nC) Three\nAnswer: D")
    assert q.answer is None


# ---------- pages, sources and fallback decision ----------

def test_page_markers_go_into_source():
    text = "--- Page 1 ---\nIntro text\n--- Page 2 ---\n5. Question?\nA) x\nB) y\nC) z"
    q = only(text)
    assert q.source == "paper p.2 Q5"


def test_header_text_before_first_question_is_ignored():
    parsed = parse("Green Valley School\nClass VIII Science\n1. Question?\nA) x\nB) y\nC) z")
    assert len(parsed) == 1


def test_fallback_when_no_questions():
    assert needs_llm_fallback([]) is True


def test_fallback_when_too_many_questions_lack_options():
    text = "1. A?\nA) x\n2. B?\nA) x\n3. C?\nA) x\nB) y\nC) z"
    assert needs_llm_fallback(parse(text)) is True


def test_no_fallback_for_clean_paper():
    text = "1. A?\nA) x\nB) y\nC) z\n2. B?\nA) x\nB) y\nC) z"
    assert needs_llm_fallback(parse(text)) is False
