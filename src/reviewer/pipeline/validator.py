"""Pipeline step 6: reject unsafe distractor candidates.

Why this file exists: an LLM can accidentally write a second correct answer or a
copy of an existing option. Every candidate must pass ALL of these checks:
  - not equal to the answer (after normalisation) and not too similar to it
  - not a duplicate of an existing option
  - length between 0.4x and 2.5x the answer's length (otherwise it is an answer cue)
  - no "all of the above" / "none of the above"
  - a separate Gemini verify call (one per question) says it is NOT a correct answer
"""

from pydantic import BaseModel

from src.reviewer import config, llm
from src.reviewer.models import MCQ
from src.reviewer.pipeline.generator import Candidate
from src.reviewer.pipeline.rules import ABOVE_PHRASES, normalise
from src.reviewer.pipeline.similarity import similarity_scores

MAX_LENGTH_RATIO = 2.5
MIN_LENGTH_RATIO = 0.4


class VerifyItem(BaseModel):
    index: int
    is_correct: bool


def local_reject_reason(text: str, mcq: MCQ, other_options: list[str]) -> str | None:
    """Return why a candidate is unsafe (checks without the LLM), or None if it passes."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in ABOVE_PHRASES):
        return "uses all/none of the above"
    if normalise(text) == normalise(mcq.correct_answer):
        return "same as the correct answer"
    if any(normalise(text) == normalise(option) for option in other_options):
        return "repeats an existing option"

    ratio = len(text.strip()) / max(len(mcq.correct_answer.strip()), 1)
    if ratio > MAX_LENGTH_RATIO or ratio < MIN_LENGTH_RATIO:
        return "length gives away the answer"

    [to_answer] = similarity_scores([text], [mcq.correct_answer])
    if to_answer[0] > config.SIM_TOO_CLOSE:
        return "too similar to the correct answer"
    if other_options:
        [to_others] = similarity_scores([text], other_options)
        if max(to_others) > config.SIM_DUPLICATE:
            return "too similar to an existing option"
    return None


def verify_with_llm(mcq: MCQ, texts: list[str]) -> list[bool]:
    """One Gemini call: for each text, could a teacher mark it correct?"""
    if not texts:
        return []
    payload = {"question": mcq.question, "candidates": {str(i): t for i, t in enumerate(texts)}}
    items = llm.call_json("verify", payload, list[VerifyItem], temperature=0.0)
    correct = {item.index: item.is_correct for item in items}
    # A missing verdict counts as "could be correct": unsafe by default.
    return [correct.get(i, True) for i in range(len(texts))]


def choose_valid(mcq: MCQ, candidates: dict[int, list[Candidate]]) -> tuple[dict[int, Candidate], list[str]]:
    """Pick the first safe candidate per distractor index.

    Returns (chosen, rejected_texts). Options already chosen for other distractors
    count as existing options, so two replacements never duplicate each other.
    """
    locally_ok: dict[int, list[Candidate]] = {}
    rejected: list[str] = []
    for index, options in candidates.items():
        others = [mcq.correct_answer] + [d for i, d in enumerate(mcq.distractors) if i != index]
        locally_ok[index] = []
        for candidate in options:
            if local_reject_reason(candidate.text, mcq, others) is None:
                locally_ok[index].append(candidate)
            else:
                rejected.append(candidate.text)

    flat = [c for options in locally_ok.values() for c in options]
    verdicts = dict(zip([id(c) for c in flat], verify_with_llm(mcq, [c.text for c in flat])))

    chosen: dict[int, Candidate] = {}
    for index, options in locally_ok.items():
        taken = [c.text for c in chosen.values()]
        for candidate in options:
            if verdicts[id(candidate)]:
                rejected.append(candidate.text)
            elif all(normalise(candidate.text) != normalise(t) for t in taken):
                chosen[index] = candidate
                break
    return chosen, rejected
