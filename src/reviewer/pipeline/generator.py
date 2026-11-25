"""Pipeline step 5: ask Gemini for better distractors.

Why this file exists: when a distractor has a high or medium finding, the teacher
needs a better one. We make ONE Gemini call per question covering all weak
distractors, and ask for 3 candidates each. Every candidate must be wrong and
must come from a real student misconception, so it tests understanding.
The correct answer is sent as read-only context; it is never part of the output.
"""

from pydantic import BaseModel

from src.reviewer import llm
from src.reviewer.models import MCQ


class Candidate(BaseModel):
    text: str
    misconception: str


class Replacement(BaseModel):
    distractor_index: int
    candidates: list[Candidate]


class GenerateOutput(BaseModel):
    replacements: list[Replacement]


def generate(mcq: MCQ, weak: dict[int, str], rejected: list[str] | None = None) -> dict[int, list[Candidate]]:
    """Return candidates per weak distractor index.

    weak maps distractor index -> the problem found (e.g. "also_correct: ...").
    rejected lists earlier unsafe candidates, so a retry asks for different ones.
    """
    kept = [d for i, d in enumerate(mcq.distractors) if i not in weak]
    payload = {
        "question": mcq.question,
        "correct_answer": mcq.correct_answer,
        "kept_options": kept or "none",
        "weak_distractors": {str(i): f"{mcq.distractors[i]} ({problem})" for i, problem in weak.items()},
        "rejected": rejected or "none",
    }
    output = llm.call_json("generate", payload, GenerateOutput, temperature=0.7)
    candidates: dict[int, list[Candidate]] = {i: [] for i in weak}
    for replacement in output.replacements:
        if replacement.distractor_index in candidates:
            candidates[replacement.distractor_index].extend(replacement.candidates)
    return candidates
