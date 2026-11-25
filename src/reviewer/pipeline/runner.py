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
from src.reviewer.pipeline.rules import check_rules, is_above_option, normalise
from src.reviewer.pipeline.similarity import check_similarity
from src.reviewer.pipeline.validator import choose_valid

NO_SAFE_REPLACEMENT = "No safe replacement found."
RESOLVE_KEY_FIRST = "Resolve the answer key first"


def review(mcqs: list[MCQ], progress_callback: Callable[[int, int], None] | None = None,
           answer_positions: dict[str, int] | None = None) -> list[ReviewResult]:
    """Review every MCQ; call progress_callback(i, n) after question i of n.

    answer_positions (MCQ id -> slot of the answer on the paper) lets reasons name
    options by their real letter; without it the answer is assumed to come last.
    """
    results = []
    for i, mcq in enumerate(mcqs, start=1):
        results.append(review_one(mcq, (answer_positions or {}).get(mcq.id)))
        if progress_callback:
            progress_callback(i, len(mcqs))
    return results


def review_one(mcq: MCQ, answer_position: int | None = None) -> ReviewResult:
    """Run steps 2–7 for one MCQ."""
    locked = answer_lock.fingerprint(mcq)
    above_answer = is_above_option(mcq.correct_answer)

    rule_findings = check_rules(mcq)
    if above_answer:
        # "All/None of the above" is correct BECAUSE the other options are correct (or not),
        # so similarity to the answer and "also correct" verdicts are meaningless here.
        sim_findings, scores = [], {}
    else:
        sim_findings, scores = check_similarity(mcq)
    llm_findings = judge(mcq, rule_findings, scores, answer_position)
    if above_answer:
        llm_findings = [f for f in llm_findings
                        if not (f.issue_type == "also_correct" and f.target.startswith("distractor:"))]
    findings = merge_findings(rule_findings + sim_findings + llm_findings)

    if has_wrong_key_flag(findings):
        # New distractors are built around the answer; if the key itself is doubtful,
        # suggestions could replace the real answer. The teacher resolves the key first.
        suggestions = []
    else:
        suggestions, findings = improve(mcq, weak_distractors(findings), findings)

    result = ReviewResult(mcq=mcq, findings=findings, suggestions=suggestions, answer_preserved=True)
    return answer_lock.enforce(mcq, result, locked)


def has_wrong_key_flag(findings: list[Finding]) -> bool:
    return any(f.issue_type == "possible_wrong_answer_key" for f in findings)


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
        for index, candidate in retry_chosen.items():
            # The retry does not know the first round's picks; never suggest the same text twice.
            if all(normalise(candidate.text) != normalise(c.text) for c in chosen.values()):
                chosen[index] = candidate

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
