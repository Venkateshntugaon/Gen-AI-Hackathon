"""Regex parser that finds MCQs in the plain text of a question paper.

Why this file exists: a regex is free, fast and predictable, so it runs before
any LLM. It understands the common school formats:
  - numbering:   1.   1)   Q1.   Q.1   Question 1:
  - options:     A)   A.   (A)   a)   (a)   on separate lines or on one line
  - answers:     Answer: B   Ans: B   Ans. (b)   Correct answer: B   Key: B
                 or an answer-key block at the end ("1-B, 2-C ...")
If no answer is written in the paper, the answer stays None. We never guess.
"""

import re

from pydantic import BaseModel

LETTERS = "ABCD"


class ParsedMCQ(BaseModel):
    number: int
    question: str
    options: list[str]          # in A, B, C, D order
    answer: str | None = None   # option letter, or None if the paper does not say
    source: str                 # e.g. "paper.pdf p.2 Q5"


QUESTION_RE = re.compile(
    r"^\s*(?:(?:Q|Question)\s*\.?\s*(\d{1,3})\s*[.):\-]?|(\d{1,3})\s*[.)])\s*(.*?)\s*$",
    re.IGNORECASE,
)
# One option marker: "A)", "A.", "(A)" (upper case) or "a)", "(a)" (lower case).
# Lower-case "a." is not accepted because it is common inside normal sentences.
OPTION_MARKER_RE = re.compile(r"(?:^|(?<=\s))(?:\(([A-Da-d])\)|([A-D])[.)]|([a-d])\))\s*")
ANSWER_RE = re.compile(
    r"^\s*(?:correct\s+answer|answer|ans|key)\s*[:.\-]?\s*[:.\-]?\s*\(?([A-Da-d])\)?(?![A-Za-z])",
    re.IGNORECASE,
)
ANSWER_KEY_HEADING_RE = re.compile(r"^\s*(?:answer\s*key|answers|key)\s*:?\s*$", re.IGNORECASE)
KEY_PAIR_RE = re.compile(r"(\d{1,3})\s*[-.):=]\s*\(?([A-Da-d])\)?(?![A-Za-z])")
PAGE_RE = re.compile(r"^--- Page (\d+) ---$")


def parse(text: str, filename: str = "paper") -> list[ParsedMCQ]:
    """Find every MCQ in the text. Answers come only from the text itself."""
    questions: list[dict] = []
    answer_key: dict[int, str] = {}
    current: dict | None = None
    page: int | None = None
    in_key_block = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        page_match = PAGE_RE.match(line)
        if page_match:
            page = int(page_match.group(1))
            continue

        if ANSWER_KEY_HEADING_RE.match(line):
            in_key_block = True
            continue
        if in_key_block or _is_answer_key_line(line):
            answer_key.update(_key_pairs(line))
            continue

        answer_match = ANSWER_RE.match(line)
        if answer_match and current is not None:
            current["answer"] = answer_match.group(1).upper()
            continue

        options = _split_options(line, start=len(current["options"])) if current else []
        if options:
            current["options"].extend(options)
            continue

        question_match = QUESTION_RE.match(line)
        if question_match:
            number = int(question_match.group(1) or question_match.group(2))
            current = {"number": number, "question": question_match.group(3),
                       "options": [], "answer": None, "page": page}
            questions.append(current)
            continue

        # A line that is none of the above continues the question or the last option.
        if current is not None:
            if current["options"]:
                current["options"][-1] += " " + line
            else:
                current["question"] = (current["question"] + " " + line).strip()

    return [_to_parsed(q, answer_key, filename) for q in questions]


def needs_llm_fallback(parsed: list[ParsedMCQ]) -> bool:
    """True if the regex result looks unreliable: no questions, or >30% with <3 options."""
    if not parsed:
        return True
    too_few_options = sum(1 for q in parsed if len(q.options) < 3)
    return too_few_options / len(parsed) > 0.30


def _split_options(line: str, start: int = 0) -> list[str]:
    """Split a line that starts with an option marker into its options.

    `start` is how many options this question already has, so the next marker
    must be LETTERS[start] (e.g. "B)" when "A)" was on the line before).
    Markers must come in order (A, B, C, D) so that text like "vitamin C." inside
    an option is not mistaken for a new option.
    """
    markers = []
    for match in OPTION_MARKER_RE.finditer(line):
        expected = start + len(markers)
        if expected >= len(LETTERS):
            break
        letter = next(group for group in match.groups() if group).upper()
        if letter == LETTERS[expected]:
            markers.append(match)
    if not markers or markers[0].start() != 0:
        return []
    options = []
    for i, match in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(line)
        options.append(line[match.end():end].strip())
    return options


def _is_answer_key_line(line: str) -> bool:
    """A line made only of pairs like "1-B, 2-C, 3-A" (at least two pairs)."""
    pairs = KEY_PAIR_RE.findall(line)
    leftover = KEY_PAIR_RE.sub("", line)
    return len(pairs) >= 2 and not re.search(r"[A-Za-z0-9]", leftover)


def _key_pairs(line: str) -> dict[int, str]:
    return {int(number): letter.upper() for number, letter in KEY_PAIR_RE.findall(line)}


def _to_parsed(q: dict, answer_key: dict[int, str], filename: str) -> ParsedMCQ:
    answer = q["answer"] or answer_key.get(q["number"])
    if answer is not None and LETTERS.index(answer) >= len(q["options"]):
        answer = None   # the letter points to an option that does not exist
    page = f" p.{q['page']}" if q["page"] else ""
    return ParsedMCQ(
        number=q["number"],
        question=q["question"],
        options=q["options"],
        answer=answer,
        source=f"{filename}{page} Q{q['number']}",
    )
