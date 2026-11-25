"""Builds the three downloads: revised question paper (DOCX), review report (CSV), full results (JSON).

Why this file exists: teachers work in Word, the CSV is for analysis, and the
JSON is our evidence for evaluation. The revised paper applies ONLY accepted
suggestions to distractors; the correct answer is copied unchanged, in its
original position, and listed again in the answer key at the end.
"""

import io
import json

import pandas as pd
from docx import Document
from docx.shared import Pt

from src.reviewer.models import ReviewResult

LETTERS = "ABCD"


def revised_options(result: ReviewResult, answer_position: int) -> list[str]:
    """All options in paper order, with accepted suggestions applied to distractors only."""
    distractors = list(result.mcq.distractors)
    for suggestion in result.suggestions:
        if suggestion.status == "accepted":
            distractors[suggestion.distractor_index] = suggestion.new_text
    options = distractors[:]
    options.insert(answer_position, result.mcq.correct_answer)   # answer untouched
    return options


def revised_docx(results: list[ReviewResult], answer_positions: dict[str, int]) -> bytes:
    """Revised question paper with an answer key at the end."""
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading("Revised Question Paper", level=1)
    doc.add_paragraph("Reviewed with the MCQ Distractor Reviewer. Correct answers are unchanged.")

    for number, result in enumerate(results, start=1):
        options = revised_options(result, answer_positions[result.mcq.id])
        doc.add_paragraph(f"{number}. {result.mcq.question}")
        for letter, text in zip(LETTERS, options):
            doc.add_paragraph(f"{letter}) {text}", style="List Paragraph")

    doc.add_page_break()
    doc.add_heading("Answer Key", level=2)
    for number, result in enumerate(results, start=1):
        letter = LETTERS[answer_positions[result.mcq.id]]
        doc.add_paragraph(f"{number}. {letter}) {result.mcq.correct_answer}")

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def report_csv(results: list[ReviewResult]) -> bytes:
    """One row per finding, with the suggestion for that distractor (if any) and its status."""
    rows = []
    for result in results:
        by_target = {f"distractor:{s.distractor_index}": s for s in result.suggestions}
        for finding in result.findings:
            suggestion = by_target.get(finding.target)
            rows.append({
                "question_id": result.mcq.id,
                "target": finding.target,
                "issue_type": finding.issue_type,
                "severity": finding.severity,
                "reason": finding.reason,
                "detected_by": ", ".join(finding.detected_by),
                "suggestion": suggestion.new_text if suggestion else "",
                "status": suggestion.status if suggestion else "",
                "answer_preserved": result.answer_preserved,
            })
    columns = ["question_id", "target", "issue_type", "severity", "reason",
               "detected_by", "suggestion", "status", "answer_preserved"]
    return pd.DataFrame(rows, columns=columns).to_csv(index=False).encode("utf-8")


def results_json(results: list[ReviewResult]) -> bytes:
    """Dump of all ReviewResult objects."""
    data = [result.model_dump() for result in results]
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
