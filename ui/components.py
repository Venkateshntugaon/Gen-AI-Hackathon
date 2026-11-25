"""Small UI helpers: CSS loading, header stepper, severity badges and question cards.

Why this file exists: app.py stays readable when the HTML snippets for badges,
the stepper and the question card live here. All text from questions is escaped
before it is put into HTML.
"""

from html import escape
from pathlib import Path

import streamlit as st

from src.reviewer.models import ReviewResult

CSS_FILE = Path(__file__).resolve().parent / "styles.css"
STEPS = ["Upload", "Confirm", "Review", "Results"]
LETTERS = "ABCD"
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
ISSUE_LABELS = {
    "also_correct": "Also correct",
    "ambiguous_question": "Ambiguous question",
    "implausible": "Implausible",
    "answer_cue": "Answer cue",
    "duplicate": "Duplicate",
    "possible_wrong_answer_key": "Possible wrong answer key",
}
LAYER_LABELS = {"rules": "rules", "similarity": "similarity", "llm": "LLM"}


def load_css() -> None:
    st.markdown(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def header(current_step: int) -> None:
    """App title, subtitle and the 4-step stepper (current_step is 0..3)."""
    steps = []
    for i, name in enumerate(STEPS):
        state = "current" if i == current_step else "done" if i < current_step else ""
        steps.append(f'<div class="step {state}"><span class="num">{i + 1}</span>{name}</div>')
    st.markdown(
        '<div class="app-header"><div>'
        '<div class="app-title">MCQ Distractor Reviewer</div>'
        '<div class="app-subtitle">PS 84 · Alliance University</div></div>'
        f'<div class="stepper">{"".join(steps)}</div></div>',
        unsafe_allow_html=True,
    )


def badge(severity: str | None) -> str:
    label = (severity or "ok").upper()
    return f'<span class="badge {escape((severity or "ok").lower())}">{label}</span>'


def chips(layers: list[str]) -> str:
    return "detected by: " + "".join(f'<span class="chip">{LAYER_LABELS[l]}</span>' for l in layers)


def worst_severity(result: ReviewResult, target: str) -> str | None:
    severities = [f.severity for f in result.findings if f.target == target]
    return max(severities, key=SEVERITY_RANK.get) if severities else None


def card_body(result: ReviewResult, answer_position: int) -> str:
    """HTML for the question text and its options with badges (correct answer locked)."""
    mcq = result.mcq
    rows = []
    distractor_index = 0
    n_options = len(mcq.distractors) + 1
    for slot in range(n_options):
        letter = LETTERS[slot]
        if slot == answer_position:
            rows.append(f'<div class="opt answer"><span class="letter">{letter}</span>'
                        f'<span>{escape(mcq.correct_answer)}</span>'
                        f'<span class="lock">🔒 Verified answer (locked)</span></div>')
            continue
        text = mcq.distractors[distractor_index]
        severity = worst_severity(result, f"distractor:{distractor_index}")
        rows.append(f'<div class="opt"><span class="letter">{letter}</span>'
                    f'<span>{escape(text)}</span>{badge(severity)}</div>')
        distractor_index += 1

    return (f'<div class="q-head"><div class="q-title">{escape(mcq.id)}. {escape(mcq.question)}</div>'
            f'<div class="q-source">{escape(mcq.source)}</div></div>'
            f'<div class="options">{"".join(rows)}</div>')


def option_letter(distractor_index: int, answer_position: int) -> str:
    """Letter shown on the paper for a distractor index (the answer slot is skipped)."""
    slot = distractor_index if distractor_index < answer_position else distractor_index + 1
    return LETTERS[slot]


def target_label(target: str, answer_position: int) -> str:
    if target.startswith("distractor:"):
        return f"Option {option_letter(int(target.split(':')[1]), answer_position)}"
    return {"question": "Question", "answer_key": "Answer key"}.get(target, target)


def finding_row(finding, answer_position: int) -> str:
    return (f'<div class="finding">{badge(finding.severity)}<div>'
            f'<span class="what">{escape(target_label(finding.target, answer_position))} · '
            f'{ISSUE_LABELS[finding.issue_type]}</span> — '
            f'<span class="why">{escape(finding.reason)}</span><br>'
            f'<span class="muted">{chips(finding.detected_by)}</span></div></div>')


def wrong_key_banner() -> str:
    return ('<div class="banner">The reviewer thinks the answer key may be wrong. Please check. '
            '(The answer has NOT been changed.)</div>')


def suggestion_html(suggestion, answer_position: int) -> str:
    letter = option_letter(suggestion.distractor_index, answer_position)
    status = ""
    if suggestion.status != "pending":
        status = f' <span class="status {suggestion.status}">· {suggestion.status.upper()}</span>'
    return (f'<div class="suggestion"><b>Suggestion for option {letter}</b>{status}<br>'
            f'<span class="old">{escape(suggestion.original)}</span> → '
            f'<span class="new">{escape(suggestion.new_text)}</span><br>'
            f'<span class="why">Misconception: {escape(suggestion.misconception)}</span></div>')
