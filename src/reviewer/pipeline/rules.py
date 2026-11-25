"""Pipeline step 2: cheap rule checks on one MCQ (no AI needed).

Why this file exists: some flaws can be caught with simple text rules, for free
and instantly: duplicate options, a distractor equal to the answer, answer cues
(the answer is much longer, or "a"/"an" gives it away) and "all/none of the above".
Every finding here has detected_by=["rules"].
"""

import re

from src.reviewer.models import MCQ, Finding

ARTICLES = {"a", "an", "the"}
ABOVE_PHRASES = ("all of the above", "none of the above")
VOWELS = "aeiou"
LENGTH_CUE_RATIO = 1.8


def normalise(text: str) -> str:
    """Lowercase, drop punctuation and articles, and singularise simple plurals.

    "The Proteins." and "protein" both become "protein".
    """
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return " ".join(_singular(word) for word in words if word not in ARTICLES)


def _singular(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def check_rules(mcq: MCQ) -> list[Finding]:
    """Run all rule checks on one MCQ and return the findings."""
    return (_duplicates_and_answer_copies(mcq) + _length_cue(mcq)
            + _article_cue(mcq) + _above_options(mcq))


def _finding(target: str, issue_type: str, severity: str, reason: str) -> Finding:
    return Finding(target=target, issue_type=issue_type, severity=severity,
                   reason=reason, detected_by=["rules"])


def _duplicates_and_answer_copies(mcq: MCQ) -> list[Finding]:
    findings = []
    answer = normalise(mcq.correct_answer)
    seen: dict[str, int] = {}
    for i, distractor in enumerate(mcq.distractors):
        text = normalise(distractor)
        if text == answer:
            findings.append(_finding(f"distractor:{i}", "also_correct", "high",
                                     f'"{distractor}" is the same as the correct answer.'))
        elif text in seen:
            other = mcq.distractors[seen[text]]
            findings.append(_finding(f"distractor:{i}", "duplicate", "low",
                                     f'"{distractor}" repeats the option "{other}".'))
        else:
            seen[text] = i
    return findings


def _length_cue(mcq: MCQ) -> list[Finding]:
    answer_len = len(mcq.correct_answer.strip())
    if mcq.distractors and all(answer_len > LENGTH_CUE_RATIO * len(d.strip()) for d in mcq.distractors):
        return [_finding("question", "answer_cue", "medium",
                         "The correct answer is much longer than every other option, which gives it away.")]
    return []


def _article_cue(mcq: MCQ) -> list[Finding]:
    """The question ends with "an" (or "a") and only the answer fits that article."""
    words = re.sub(r"[^\w\s]", " ", mcq.question.lower()).split()
    if not words or words[-1] not in ("a", "an"):
        return []
    wants_vowel = words[-1] == "an"

    def fits(option: str) -> bool:
        first = option.strip().lower()[:1]
        return bool(first) and (first in VOWELS) == wants_vowel

    if fits(mcq.correct_answer) and not any(fits(d) for d in mcq.distractors):
        return [_finding("question", "answer_cue", "medium",
                         f'The question ends with "{words[-1]}", and only the correct answer fits it grammatically.')]
    return []


def _above_options(mcq: MCQ) -> list[Finding]:
    findings = []
    options = [("question", mcq.correct_answer)] + [(f"distractor:{i}", d) for i, d in enumerate(mcq.distractors)]
    for target, text in options:
        if any(phrase in text.lower() for phrase in ABOVE_PHRASES):
            findings.append(_finding(target, "ambiguous_question", "low",
                                     f'"{text}" makes the question harder to mark fairly; prefer specific options.'))
    return findings
