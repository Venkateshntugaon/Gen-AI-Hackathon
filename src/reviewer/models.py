"""Data models (Pydantic) shared by every part of the reviewer.

Why this file exists: one clear definition of what a question, a finding and a
suggestion look like. Pydantic checks every value, including every LLM reply.
MCQ is frozen (immutable), so code that tries to change the verified correct
answer raises an error. This is the first layer of the answer lock.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class MCQ(BaseModel):
    model_config = ConfigDict(frozen=True)   # immutable → answer cannot be edited in place
    id: str
    question: str
    correct_answer: str                      # VERIFIED, LOCKED
    distractors: list[str]                   # 2–4 items
    source: str                              # e.g. "paper.pdf p.2 Q5" or "SciQ #123"


IssueType = Literal["also_correct", "ambiguous_question", "implausible",
                    "answer_cue", "duplicate", "possible_wrong_answer_key"]
Severity = Literal["high", "medium", "low"]


class Finding(BaseModel):
    target: str            # "question", "answer_key", or "distractor:<index>"
    issue_type: IssueType
    severity: Severity
    reason: str            # one plain-English sentence
    detected_by: list[Literal["rules", "similarity", "llm"]]


class Suggestion(BaseModel):
    distractor_index: int  # which distractor it replaces
    original: str
    new_text: str
    misconception: str     # the student mistake that makes it tempting
    status: Literal["pending", "accepted", "rejected"] = "pending"


class ReviewResult(BaseModel):
    mcq: MCQ
    findings: list[Finding]
    suggestions: list[Suggestion]
    answer_preserved: bool
