"""Pipeline step 4: the LLM judge, and merging of all detection findings.

Why this file exists: rules and embeddings cannot understand science. The judge
asks Gemini (one call per question, temperature 0.2, JSON schema output) whether
each distractor is also correct, how tempting it is, whether the question is
ambiguous, and whether it agrees with the answer key. The answer key is only
ever FLAGGED, never changed.

merge_findings() then combines rule, similarity and LLM findings, keeping one
finding per (target, issue_type), so the UI can show which layers caught it.
"""

import re
from typing import Literal

from pydantic import BaseModel

from src.reviewer import llm
from src.reviewer.models import MCQ, Finding, IssueType

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
LETTERS = "ABCD"
# Tie-break when one option has several findings of the same severity (most serious first).
ISSUE_PRIORITY = ["also_correct", "duplicate", "implausible", "answer_cue", "ambiguous_question",
                  "possible_wrong_answer_key"]
INDEX_RE = re.compile(r"\b(option|distractor|index|choice)\s*#?\s*(\d)\b", re.IGNORECASE)
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


def option_letters(n_distractors: int, answer_position: int | None) -> list[str]:
    """Paper letter (A-D) of each distractor index; the answer's slot is skipped.

    Without a known answer position the answer is assumed to come last.
    """
    position = n_distractors if answer_position is None else answer_position
    return [LETTERS[i if i < position else i + 1] for i in range(n_distractors)]


def judge(mcq: MCQ, rule_findings: list[Finding], similarity_scores: dict,
          answer_position: int | None = None) -> list[Finding]:
    """Ask Gemini to review one MCQ and turn its verdict into findings."""
    letters = option_letters(len(mcq.distractors), answer_position)
    payload = judge_payload(mcq, rule_findings, similarity_scores, letters)
    output = llm.call_json("judge", payload, JudgeOutput, temperature=0.2)
    return verdict_to_findings(output, len(mcq.distractors), letters)


def judge_payload(mcq: MCQ, rule_findings: list[Finding], similarity_scores: dict, letters: list[str]) -> dict:
    """The data that fills prompts/judge.md (options are shown with their paper letters)."""
    return {
        "question": mcq.question,
        "correct_answer": mcq.correct_answer,
        "distractors": [{"index": i, "letter": letters[i], "text": d} for i, d in enumerate(mcq.distractors)],
        "rule_flags": [f"{_letter_target(f.target, letters)}: {f.issue_type}" for f in rule_findings] or "none",
        "similarity_scores": _letter_scores(similarity_scores, letters),
    }


def _letter_target(target: str, letters: list[str]) -> str:
    if target.startswith("distractor:"):
        return f"option {letters[int(target.split(':')[1])]}"
    return target


def _letter_scores(scores: dict, letters: list[str]) -> dict:
    """Similarity hints keyed by paper letters ("B", "B-D") instead of 0-based indices."""
    if not scores:
        return {}
    return {
        "option_vs_answer": {letters[int(i)]: v for i, v in scores["distractor_vs_answer"].items()},
        "option_vs_option": {"-".join(letters[int(i)] for i in pair.split("-")): v
                             for pair, v in scores["distractor_vs_distractor"].items()},
    }


def letters_in_reason(reason: str, letters: list[str]) -> str:
    """Replace "option 0" / "distractor 2" / "index 1" in an LLM reason with the paper letter."""
    def to_letter(match: re.Match) -> str:
        index = int(match.group(2))
        return f"option {letters[index]}" if index < len(letters) else match.group(0)
    return INDEX_RE.sub(to_letter, reason)


def verdict_to_findings(output: JudgeOutput, n_distractors: int,
                        letters: list[str] | None = None) -> list[Finding]:
    """Apply the severity mapping table from IMPLEMENTATION.md §5 Phase 3 (implausible tuned, see below).

    Option findings come only from is_also_correct (yes/partly) and plausibility (<= 2).
    The LLM's own issue_type label is not turned into findings: answer cues come from
    the rules only, and duplicates from the rules and similarity layers.
    """
    letters = letters or option_letters(n_distractors, None)
    findings = []
    if output.question_ambiguous:
        findings.append(_finding("question", "ambiguous_question", "high",
                                 letters_in_reason(output.question_reason, letters)))
    if not output.answer_key_agrees:
        # Flag only. The verified answer is never changed by code.
        findings.append(_finding("answer_key", "possible_wrong_answer_key", "high",
                                 letters_in_reason(output.answer_key_reason, letters)))

    for verdict in output.options:
        if not 0 <= verdict.option_index < n_distractors:
            continue   # ignore an index that does not exist
        target = f"distractor:{verdict.option_index}"
        reason = letters_in_reason(verdict.reason, letters)
        if verdict.is_also_correct == "yes":
            findings.append(_finding(target, "also_correct", "high", reason))
        elif verdict.is_also_correct == "partly":
            findings.append(_finding(target, "also_correct", "medium", reason))
        # The plan maps plausibility <= 2 to MEDIUM. Our evaluation showed that this
        # over-flags (precision 0.14); using 1 -> MEDIUM and 2 -> LOW doubled precision
        # with no loss of recall (see docs/CHALLENGES.md, Phase 7).
        if verdict.plausibility <= 1:
            findings.append(_finding(target, "implausible", "medium", reason))
        elif verdict.plausibility == 2:
            findings.append(_finding(target, "implausible", "low", reason))
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
    return one_per_option(list(merged.values()))


def one_per_option(findings: list[Finding]) -> list[Finding]:
    """Each option shows at most one finding: the highest severity wins.

    On equal severity the more serious issue type wins (ISSUE_PRIORITY). Findings on
    the question and the answer key are kept as they are.
    """
    best: dict[str, Finding] = {}
    others = []
    for finding in findings:
        if not finding.target.startswith("distractor:"):
            others.append(finding)
            continue
        current = best.get(finding.target)
        if current is None or _rank(finding) > _rank(current):
            best[finding.target] = finding
    return others + sorted(best.values(), key=lambda f: int(f.target.split(":")[1]))


def _rank(finding: Finding) -> tuple[int, int]:
    return SEVERITY_RANK[finding.severity], -ISSUE_PRIORITY.index(finding.issue_type)


def _finding(target: str, issue_type: str, severity: str, reason: str) -> Finding:
    return Finding(target=target, issue_type=issue_type, severity=severity,
                   reason=reason, detected_by=["llm"])
