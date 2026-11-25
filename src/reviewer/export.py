"""Builds the downloads: revised question paper (DOCX), review report (DOCX, CSV) and full results (JSON).

Why this file exists: teachers work in Word, so the two main downloads are Word
documents (the revised paper and a plain-English review report). The CSV and
JSON are kept for analysis and as evidence for our evaluation. The revised paper applies ONLY accepted
suggestions to distractors; the correct answer is copied unchanged, in its
original position, and listed again in the answer key at the end.
"""

import io
import json

import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor

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


ISSUE_LABELS = {
    "also_correct": "Also correct",
    "ambiguous_question": "Ambiguous question",
    "implausible": "Implausible option",
    "answer_cue": "Answer give-away",
    "duplicate": "Duplicate option",
    "possible_wrong_answer_key": "Answer key may be wrong",
}
LAYER_LABELS = {"rules": "rule check", "similarity": "similarity scan", "llm": "AI judge"}
SEVERITY_COLOURS = {"high": RGBColor(0x8E, 0x0A, 0x13), "medium": RGBColor(0x9A, 0x5B, 0x00),
                    "low": RGBColor(0x5B, 0x64, 0x72)}
OK_COLOUR = RGBColor(0x1E, 0x7B, 0x4F)


def _target_label(target: str, answer_position: int) -> str:
    if target.startswith("distractor:"):
        index = int(target.split(":")[1])
        return f"Option {LETTERS[index if index < answer_position else index + 1]}"
    return {"question": "Question", "answer_key": "Answer key"}.get(target, target)


def _coloured(paragraph, text: str, colour: RGBColor, bold: bool = True) -> None:
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.color.rgb = colour


def review_report_docx(results: list[ReviewResult], answer_positions: dict[str, int]) -> bytes:
    """A teacher-friendly review report in Word: summary, then every question with its findings."""
    findings = [f for r in results for f in r.findings]
    preserved = sum(r.answer_preserved for r in results)
    accepted = sum(s.status == "accepted" for r in results for s in r.suggestions)

    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading("MCQ Review Report", level=1)
    doc.add_paragraph("This report lists the problems the reviewer found in each question and the "
                      "replacement options it suggested. Correct answers were never changed.")

    doc.add_heading("Summary", level=2)
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    for label, value in [
        ("Questions reviewed", len(results)),
        ("Questions with problems", sum(1 for r in results if r.findings)),
        ("High-severity problems", sum(f.severity == "high" for f in findings)),
        ("Medium-severity problems", sum(f.severity == "medium" for f in findings)),
        ("Low-severity problems", sum(f.severity == "low" for f in findings)),
        ("Replacement options suggested", sum(len(r.suggestions) for r in results)),
        ("Suggestions you accepted", accepted),
        ("Correct answers preserved", f"{preserved} of {len(results)}"),
    ]:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = str(value)

    doc.add_heading("How to read this report", level=2)
    doc.add_paragraph("HIGH: must fix (for example, a second correct option). "
                      "MEDIUM: should fix (for example, an option no student would choose). "
                      "LOW: minor (for example, two options that say the same thing).")

    doc.add_heading("Question by question", level=2)
    for number, result in enumerate(results, start=1):
        _report_question(doc, number, result, answer_positions[result.mcq.id])

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _report_question(doc, number: int, result: ReviewResult, answer_position: int) -> None:
    mcq = result.mcq
    doc.add_heading(f"{number}. {mcq.question}", level=3)

    options = list(mcq.distractors)
    options.insert(answer_position, mcq.correct_answer)
    for letter, text in zip(LETTERS, options):
        line = doc.add_paragraph(f"{letter}) {text}", style="List Paragraph")
        if text == mcq.correct_answer and LETTERS.index(letter) == answer_position:
            _coloured(line, "   ✔ correct answer (unchanged)", OK_COLOUR)

    if not result.answer_preserved:
        _coloured(doc.add_paragraph(), "Warning: a change to the correct answer was detected and "
                  "blocked; suggestions for this question were discarded.", SEVERITY_COLOURS["high"])
    if not result.findings:
        _coloured(doc.add_paragraph(), "No problems found.", OK_COLOUR)

    for finding in result.findings:
        p = doc.add_paragraph(style="List Bullet")
        _coloured(p, f"{finding.severity.upper()}  ", SEVERITY_COLOURS[finding.severity])
        p.add_run(f"{_target_label(finding.target, answer_position)} – "
                  f"{ISSUE_LABELS[finding.issue_type]}: ").bold = True
        p.add_run(finding.reason)
        found_by = ", ".join(LAYER_LABELS[layer] for layer in finding.detected_by)
        note = p.add_run(f"  (found by: {found_by})")
        note.italic = True
        note.font.color.rgb = SEVERITY_COLOURS["low"]

    if any(f.issue_type == "possible_wrong_answer_key" for f in result.findings):
        _coloured(doc.add_paragraph(), "Resolve the answer key first. Replacement options are suggested "
                  "only after the correct answer is confirmed.", SEVERITY_COLOURS["high"], bold=False)

    for suggestion in result.suggestions:
        letter = _target_label(f"distractor:{suggestion.distractor_index}", answer_position)
        p = doc.add_paragraph()
        p.add_run(f"Suggested replacement for {letter}: ").bold = True
        p.add_run(f"“{suggestion.original}” → “{suggestion.new_text}”")
        status = {"accepted": "Accepted", "rejected": "Rejected", "pending": "Not decided"}[suggestion.status]
        _coloured(p, f"   [{status}]", OK_COLOUR if suggestion.status == "accepted" else SEVERITY_COLOURS["low"])
        why = doc.add_paragraph()
        run = why.add_run(f"Why it is a good wrong option: {suggestion.misconception}")
        run.italic = True


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
