"""Runs pipeline steps 2–7 for a list of MCQs.

Why this file exists: one simple entry point for the UI and the scripts.
For each question: fingerprint the answer → rules → similarity → LLM judge →
merge findings → generate replacements for weak distractors → validate them
(retry generation once if needed) → answer lock.
"""

from typing import Callable

from src.reviewer.models import MCQ, Finding, ReviewResult, Suggestion
from src.reviewer.pipeline import answer_lock
from src.reviewer.pipeline.generator import generate
from src.reviewer.pipeline.judge import judge, merge_findings
from src.reviewer.pipeline.rules import check_rules
from src.reviewer.pipeline.similarity import check_similarity
from src.reviewer.pipeline.validator import choose_valid

NO_SAFE_REPLACEMENT = "No safe replacement found."


def review(mcqs: list[MCQ], progress_callback: Callable[[int, int], None] | None = None) -> list[ReviewResult]:
    """Review every MCQ; call progress_callback(i, n) after question i of n."""
    results = []
    for i, mcq in enumerate(mcqs, start=1):
        results.append(review_one(mcq))
        if progress_callback:
            progress_callback(i, len(mcqs))
    return results


def review_one(mcq: MCQ) -> ReviewResult:
    """Run steps 2–7 for one MCQ."""
    locked = answer_lock.fingerprint(mcq)

    rule_findings = check_rules(mcq)
    sim_findings, scores = check_similarity(mcq)
    llm_findings = judge(mcq, rule_findings, scores)
    findings = merge_findings(rule_findings + sim_findings + llm_findings)

    weak = weak_distractors(findings)
    suggestions, findings = improve(mcq, weak, findings)

    result = ReviewResult(mcq=mcq, findings=findings, suggestions=suggestions, answer_preserved=True)
    return answer_lock.enforce(mcq, result, locked)


def weak_distractors(findings: list[Finding]) -> dict[int, str]:
    """Distractor index -> problem text, for distractors with a high or medium finding.

    Duplicates are low severity but still need a replacement (two identical options
    are a real flaw on the paper), so they are included too.
    """
    weak: dict[int, str] = {}
    for f in findings:
        needs_replacement = f.severity in ("high", "medium") or f.issue_type == "duplicate"
        if f.target.startswith("distractor:") and needs_replacement:
            index = int(f.target.split(":")[1])
            problem = f"{f.issue_type}: {f.reason}"
            weak[index] = f"{weak[index]}; {problem}" if index in weak else problem
    return weak


def improve(mcq: MCQ, weak: dict[int, str], findings: list[Finding]) -> tuple[list[Suggestion], list[Finding]]:
    """Generate and validate replacements; retry generation once for distractors left without one."""
    if not weak:
        return [], findings

    chosen, rejected = choose_valid(mcq, generate(mcq, weak))
    missing = {i: p for i, p in weak.items() if i not in chosen}
    if missing:
        retry_chosen, _ = choose_valid(mcq, generate(mcq, missing, rejected=rejected))
        chosen.update(retry_chosen)

    suggestions = [
        Suggestion(distractor_index=i, original=mcq.distractors[i],
                   new_text=c.text, misconception=c.misconception)
        for i, c in sorted(chosen.items())
    ]
    unresolved = {f"distractor:{i}" for i in weak if i not in chosen}
    findings = [
        f.model_copy(update={"reason": f"{f.reason} {NO_SAFE_REPLACEMENT}"})
        if f.target in unresolved else f
        for f in findings
    ]
    return suggestions, findings
