"""Pipeline step 4: the LLM judge, and merging of all detection findings.

Why this file exists: rules and embeddings cannot understand science. The judge
asks Gemini (one call per question, temperature 0.2, JSON schema output) whether
each distractor is also correct, how tempting it is, whether the question is
ambiguous, and whether it agrees with the answer key. The answer key is only
ever FLAGGED, never changed.

merge_findings() then combines rule, similarity and LLM findings, keeping one
finding per (target, issue_type), so the UI can show which layers caught it.
"""

from typing import Literal

from pydantic import BaseModel

from src.reviewer import llm
from src.reviewer.models import MCQ, Finding, IssueType

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
LAYER_ORDER = ["rules", "similarity", "llm"]


class OptionVerdict(BaseModel):
    option_index: int
    is_also_correct: Literal["yes", "partly", "no"]
    plausibility: int            # 1 (absurd) .. 5 (very tempting)
    issue_type: IssueType | None
    reason: str                  # ≤ 25 words


class JudgeOutput(BaseModel):
    question_ambiguous: bool
    question_reason: str
    options: list[OptionVerdict]
    answer_key_agrees: bool       # does the LLM agree the given answer is correct?
    answer_key_reason: str


def judge(mcq: MCQ, rule_findings: list[Finding], similarity_scores: dict) -> list[Finding]:
    """Ask Gemini to review one MCQ and turn its verdict into findings."""
    payload = {
        "question": mcq.question,
        "correct_answer": mcq.correct_answer,
        "distractors": {str(i): d for i, d in enumerate(mcq.distractors)},
        "rule_flags": [f"{f.target}: {f.issue_type}" for f in rule_findings] or "none",
        "similarity_scores": similarity_scores,
    }
    output = llm.call_json("judge", payload, JudgeOutput, temperature=0.2)
    return verdict_to_findings(output, len(mcq.distractors))


def verdict_to_findings(output: JudgeOutput, n_distractors: int) -> list[Finding]:
    """Apply the severity mapping table from IMPLEMENTATION.md §5 Phase 3."""
    findings = []
    if output.question_ambiguous:
        findings.append(_finding("question", "ambiguous_question", "high", output.question_reason))
    if not output.answer_key_agrees:
        # Flag only. The verified answer is never changed by code.
        findings.append(_finding("answer_key", "possible_wrong_answer_key", "high", output.answer_key_reason))

    for verdict in output.options:
        if not 0 <= verdict.option_index < n_distractors:
            continue   # ignore an index that does not exist
        target = f"distractor:{verdict.option_index}"
        if verdict.is_also_correct == "yes":
            findings.append(_finding(target, "also_correct", "high", verdict.reason))
        elif verdict.is_also_correct == "partly":
            findings.append(_finding(target, "also_correct", "medium", verdict.reason))
        if verdict.plausibility <= 2:
            findings.append(_finding(target, "implausible", "medium", verdict.reason))
        # The table has no row for duplicate / answer_cue; keep them at the rule-layer severity.
        if verdict.issue_type == "duplicate":
            findings.append(_finding(target, "duplicate", "low", verdict.reason))
        elif verdict.issue_type == "answer_cue":
            findings.append(_finding(target, "answer_cue", "medium", verdict.reason))
    return findings


def merge_findings(findings: list[Finding]) -> list[Finding]:
    """Keep one finding per (target, issue_type): highest severity, all layers, LLM reason preferred."""
    merged: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.target, finding.issue_type)
        if key not in merged:
            merged[key] = finding
            continue
        old = merged[key]
        layers = set(old.detected_by) | set(finding.detected_by)
        severity = max(old.severity, finding.severity, key=SEVERITY_RANK.get)
        reason = finding.reason if "llm" in finding.detected_by else old.reason
        merged[key] = Finding(target=old.target, issue_type=old.issue_type, severity=severity,
                              reason=reason, detected_by=[l for l in LAYER_ORDER if l in layers])
    return list(merged.values())


def _finding(target: str, issue_type: str, severity: str, reason: str) -> Finding:
    return Finding(target=target, issue_type=issue_type, severity=severity,
                   reason=reason, detected_by=["llm"])
