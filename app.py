"""Streamlit entry point: the 4-step teacher flow (Upload → Confirm → Review → Results).

Why this file exists: teachers are the users, so the whole review must work
without technical knowledge. The teacher uploads a paper, confirms the answer
key (so the "verified" answer really is verified by a human), watches the review
run, then accepts or rejects suggestions and downloads the results.
From the moment questions are confirmed, the correct answers are locked.

Run with:  streamlit run app.py
"""

import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from src.reviewer import export
from src.reviewer.ingest.llm_extract import extract_questions
from src.reviewer.ingest.parser import ParsedMCQ
from src.reviewer.ingest.readers import read_csv
from src.reviewer.llm import GeminiBusyError
from src.reviewer.models import MCQ
from src.reviewer.pipeline import similarity
from src.reviewer.pipeline.runner import review_one
from ui import components as ui

SAMPLE_PAPER = Path(__file__).resolve().parent / "data" / "sample" / "sample_paper.docx"
LETTERS = "ABCD"
STEP_INDEX = {"upload": 0, "confirm": 1, "review": 2, "results": 3}
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

st.set_page_config(page_title="MCQ Distractor Reviewer", page_icon="🔬", layout="wide")


@st.cache_resource(show_spinner="Loading the similarity model…")
def load_similarity_model():
    return similarity.get_model()


def init_state() -> None:
    defaults = {"step": "upload", "rows": None, "mcqs": [], "answer_positions": {},
                "results": [], "file_note": "", "processed_file": None}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ---------------------------------------------------------------- Step 1: Upload

def parsed_to_rows(parsed: list[ParsedMCQ]) -> pd.DataFrame:
    rows = []
    for q in parsed:
        options = (q.options + [""] * 4)[:4]
        rows.append({"No.": q.number, "Question": q.question, "A": options[0], "B": options[1],
                     "C": options[2], "D": options[3], "Answer": q.answer, "Source": q.source})
    return pd.DataFrame(rows)


def csv_to_rows(mcqs: list[MCQ]) -> pd.DataFrame:
    """CSV rows already have the answer; place it at a stable position derived from the id."""
    rows = []
    for number, mcq in enumerate(mcqs, start=1):
        position = int(hashlib.sha256(mcq.id.encode()).hexdigest(), 16) % (len(mcq.distractors) + 1)
        options = list(mcq.distractors[:3])
        options.insert(position, mcq.correct_answer)
        options = (options + [""] * 4)[:4]
        rows.append({"No.": number, "Question": mcq.question, "A": options[0], "B": options[1],
                     "C": options[2], "D": options[3], "Answer": LETTERS[position], "Source": mcq.source})
    return pd.DataFrame(rows)


def load_file(name: str, data: bytes) -> None:
    """Read the file, find the questions and move to the Confirm step."""
    with st.status("Reading file…", expanded=True) as status:
        try:
            if name.lower().endswith(".csv"):
                st.write("Reading CSV rows…")
                rows = csv_to_rows(read_csv(data))
                used_llm = False
            else:
                st.write("Reading file…")
                st.write("Finding questions…")
                parsed, used_llm = extract_questions(name, data)
                rows = parsed_to_rows(parsed)
        except GeminiBusyError as error:
            status.update(label=str(error), state="error")
            return
        except Exception as error:   # show a friendly message instead of a stack trace
            status.update(label=f"Could not read this file: {error}", state="error")
            return

        if rows.empty:
            status.update(label="No questions were found in this file.", state="error")
            return
        if used_llm:
            st.write("The layout was unusual, so Gemini was used to extract the questions.")
        status.update(label=f"Done ({len(rows)} questions found)", state="complete")

    st.session_state.rows = rows
    st.session_state.file_note = (f"**{name}** · {len(rows)} questions found"
                                  + (" · extracted with Gemini" if used_llm else ""))
    st.session_state.step = "confirm"
    st.rerun()


def step_upload() -> None:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("### Upload a question paper")
        st.markdown('<p class="muted">PDF, Word (.docx) or text file, in the format you already use. '
                    'The reviewer finds the multiple-choice questions for you.</p>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Question paper", type=["pdf", "docx", "txt"],
                                    label_visibility="collapsed")
        st.markdown('<p class="muted" style="margin:0.4rem 0">No paper at hand?</p>', unsafe_allow_html=True)
        use_sample = st.button("Try a sample paper", icon=":material/description:")
        with st.expander("Advanced: upload a SciQ-style CSV"):
            st.caption("Columns: id, question, correct_answer, distractor1, distractor2, distractor3")
            uploaded_csv = st.file_uploader("CSV file", type=["csv"], key="csv_upload")
    with right:
        st.markdown(ui.how_it_works(), unsafe_allow_html=True)

    if use_sample:
        load_file(SAMPLE_PAPER.name, SAMPLE_PAPER.read_bytes())
        return
    for file in (uploaded, uploaded_csv):
        if file is not None and st.session_state.processed_file != file.file_id:
            st.session_state.processed_file = file.file_id
            load_file(file.name, file.getvalue())
            return


# ---------------------------------------------------------------- Step 2: Confirm

def cell(value) -> str:
    """Text of a table cell; empty for blank cells (None / NaN in new rows)."""
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()


def row_problem(row: pd.Series) -> str | None:
    """Why a row cannot be reviewed yet, or None if it is ready."""
    if not cell(row["Question"]):
        return "question text is empty"
    options = [cell(row[letter]) for letter in LETTERS]
    if sum(1 for o in options if o) < 3:
        return "needs at least 3 options"
    answer = row["Answer"]
    if not isinstance(answer, str) or answer not in LETTERS:
        return "no answer selected"
    if not options[LETTERS.index(answer)]:
        return f"answer {answer} points to an empty option"
    return None


def rows_to_mcqs(rows: pd.DataFrame) -> tuple[list[MCQ], dict[str, int]]:
    """Convert confirmed rows to frozen MCQs. From here on the answer is locked."""
    mcqs, positions, used_ids = [], {}, set()
    for index, row in rows.reset_index(drop=True).iterrows():
        filled = [(letter, cell(row[letter])) for letter in LETTERS if cell(row[letter])]
        answer_letter = row["Answer"]
        answer = cell(row[answer_letter])
        distractors = [text for letter, text in filled if letter != answer_letter]
        position = [letter for letter, _ in filled].index(answer_letter)

        mcq_id = f"Q{int(row['No.'])}" if pd.notna(row["No."]) else f"Q{index + 1}"
        if mcq_id in used_ids:
            mcq_id = f"Q{index + 1}"
        used_ids.add(mcq_id)

        mcqs.append(MCQ(id=mcq_id, question=cell(row["Question"]), correct_answer=answer,
                        distractors=distractors, source=cell(row["Source"]) or mcq_id))
        positions[mcq_id] = position
    return mcqs, positions


def step_confirm() -> None:
    st.markdown("### Confirm the questions and answer key")
    st.markdown(st.session_state.file_note)
    st.markdown('<p class="muted">Check the extracted text and choose the correct answer for every '
                'question. You can fix typos or delete rows that are not questions.</p>',
                unsafe_allow_html=True)

    edited = st.data_editor(
        st.session_state.rows,
        key="confirm_editor",
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "No.": st.column_config.NumberColumn("No.", width="small", disabled=True),
            "Question": st.column_config.TextColumn("Question", width="large"),
            "Answer": st.column_config.SelectboxColumn("Answer", options=list(LETTERS), width="small"),
            "Source": None,   # hidden; kept for the report
        },
    )

    problems = {int(i): p for i, row in edited.iterrows() if (p := row_problem(row))}
    if problems:
        missing = [str(edited.loc[i, "No."]) for i, p in problems.items() if p == "no answer selected"]
        if missing:
            st.warning("Select the correct answer for these questions. The reviewer never guesses answers.  \n"
                       f"Questions without an answer: **{', '.join(missing)}**")
        other = [f"Q{edited.loc[i, 'No.']}: {p}" for i, p in problems.items() if p != "no answer selected"]
        if other:
            st.warning("Please fix: " + "; ".join(other))

    back, _, start = st.columns([1, 2, 1])
    if back.button("← Upload another file", width="stretch"):
        reset()
        st.rerun()
    if start.button("Start review", type="primary", disabled=bool(problems) or edited.empty,
                    width="stretch"):
        st.session_state.rows = edited
        st.session_state.mcqs, st.session_state.answer_positions = rows_to_mcqs(edited)
        st.session_state.results = []
        st.session_state.step = "review"
        st.rerun()


# ---------------------------------------------------------------- Step 3: Review

def step_review() -> None:
    mcqs = st.session_state.mcqs
    results = st.session_state.results
    n = len(mcqs)
    st.markdown("### Reviewing your questions")
    st.markdown('<p class="muted">Each question goes through rule checks, a similarity scan and the '
                'Gemini judge; weak distractors get safer replacements. Correct answers stay locked.</p>',
                unsafe_allow_html=True)

    progress = st.progress(len(results) / n, text=f"Reviewing question {min(len(results) + 1, n)} of {n}")
    counter = st.empty()
    load_similarity_model()

    for i in range(len(results), n):
        progress.progress(i / n, text=f"Reviewing question {i + 1} of {n}")
        counter.markdown(ui.review_status(mcqs[i].question, sum(len(r.findings) for r in results)),
                         unsafe_allow_html=True)
        try:
            results.append(review_one(mcqs[i]))
        except GeminiBusyError as error:
            st.error(f"{error}  \n{len(results)} of {n} questions are done and kept.")
            st.button("Retry", type="primary")
            return
        except Exception as error:
            st.error(f"The review stopped at question {i + 1}: {error}")
            st.button("Retry", type="primary")
            return

    progress.progress(1.0, text=f"Reviewed {n} of {n} questions")
    st.session_state.step = "results"
    st.rerun()


# ---------------------------------------------------------------- Step 4: Results

def set_status(result_index: int, distractor_index: int, status: str) -> None:
    result = st.session_state.results[result_index]
    suggestions = [s.model_copy(update={"status": status}) if s.distractor_index == distractor_index else s
                   for s in result.suggestions]
    st.session_state.results[result_index] = result.model_copy(update={"suggestions": suggestions})


def set_all_pending(status: str) -> None:
    """Accept or reject every suggestion the teacher has not decided on yet."""
    st.session_state.results = [
        r.model_copy(update={"suggestions": [s.model_copy(update={"status": status}) if s.status == "pending"
                                             else s for s in r.suggestions]})
        for r in st.session_state.results
    ]


def summary(results) -> None:
    findings = [f for r in results for f in r.findings]
    preserved = sum(r.answer_preserved for r in results)
    st.markdown(ui.stat_tiles([
        ("Questions reviewed", len(results), ""),
        ("High", sum(f.severity == "high" for f in findings), "high"),
        ("Medium", sum(f.severity == "medium" for f in findings), "medium"),
        ("Low", sum(f.severity == "low" for f in findings), "low"),
        ("Suggestions made", sum(len(r.suggestions) for r in results), ""),
        ("Answers preserved", f"{preserved}/{len(results)} ({preserved / len(results):.0%})", "ok"),
    ]), unsafe_allow_html=True)


def question_card(index: int, result, severities: list[str], issue_types: list[str]) -> None:
    position = st.session_state.answer_positions[result.mcq.id]
    findings = [f for f in result.findings if f.severity in severities and f.issue_type in issue_types]
    with st.container(border=True):
        st.markdown(ui.card_body(result, position), unsafe_allow_html=True)
        if not result.answer_preserved:
            st.error("The answer lock caught a change to the correct answer; this result was discarded.")
        if any(f.issue_type == "possible_wrong_answer_key" for f in result.findings):
            st.markdown(ui.wrong_key_banner(), unsafe_allow_html=True)
        if findings:
            st.markdown('<div class="section-label">Findings</div>'
                        + "".join(ui.finding_row(f, position) for f in findings), unsafe_allow_html=True)
        elif not result.findings:
            st.markdown(f'{ui.badge(None)} <span class="muted">No issues found.</span>', unsafe_allow_html=True)

        if result.suggestions:
            st.markdown('<div class="section-label">Suggested replacements</div>', unsafe_allow_html=True)
        for suggestion in result.suggestions:
            text_col, accept, reject = st.columns([6, 1.2, 1.2], vertical_alignment="center")
            text_col.markdown(ui.suggestion_html(suggestion, position), unsafe_allow_html=True)
            key = f"{result.mcq.id}-{suggestion.distractor_index}"
            accept.button("Accept", key=f"acc-{key}", type="primary", width="stretch", icon=":material/check:",
                          disabled=suggestion.status == "accepted",
                          on_click=set_status, args=(index, suggestion.distractor_index, "accepted"))
            reject.button("Reject", key=f"rej-{key}", width="stretch", icon=":material/close:",
                          disabled=suggestion.status == "rejected",
                          on_click=set_status, args=(index, suggestion.distractor_index, "rejected"))


def step_results() -> None:
    results = st.session_state.results
    st.markdown("### Review results")
    summary(results)

    pending = sum(s.status == "pending" for r in results for s in r.suggestions)
    with st.container(border=True):
        f1, f2, f3 = st.columns([2, 3, 2], vertical_alignment="bottom")
        severities = f1.multiselect("Severity", ["high", "medium", "low"], default=["high", "medium", "low"],
                                    format_func=str.upper)
        issue_types = f2.multiselect("Issue type", list(ui.ISSUE_LABELS), default=list(ui.ISSUE_LABELS),
                                     format_func=ui.ISSUE_LABELS.get)
        only_issues = f3.toggle("Only questions with issues", value=False)
        if pending:
            b1, b2, _ = st.columns([2, 2, 3])
            b1.button(f"Accept all {pending} undecided", on_click=set_all_pending, args=("accepted",),
                      width="stretch")
            b2.button("Reject all undecided", on_click=set_all_pending, args=("rejected",), width="stretch")

    shown = 0
    for index, result in enumerate(results):
        matching = [f for f in result.findings if f.severity in severities and f.issue_type in issue_types]
        if only_issues and not matching:
            continue
        question_card(index, result, severities, issue_types)
        shown += 1
    if shown == 0:
        st.info("No questions match these filters.")

    st.markdown("### Download")
    positions = st.session_state.answer_positions
    with st.container(border=True):
        st.markdown('<p class="muted">Both files open in Microsoft Word (use <b>File → Save as PDF</b> '
                    'if you need a PDF). The revised paper applies only the suggestions you accepted; '
                    'correct answers are never changed.</p>', unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        d1.download_button("Revised question paper", export.revised_docx(results, positions),
                           file_name="revised_question_paper.docx", type="primary", width="stretch",
                           icon=":material/edit_document:", mime=DOCX_MIME)
        d2.download_button("Review report", export.review_report_docx(results, positions),
                           file_name="review_report.docx", type="primary", width="stretch",
                           icon=":material/summarize:", mime=DOCX_MIME)
        with st.expander("For analysis (spreadsheet and raw data)"):
            a1, a2 = st.columns(2)
            a1.download_button("Findings table (.csv)", export.report_csv(results),
                               file_name="review_report.csv", mime="text/csv", width="stretch")
            a2.download_button("Full results (.json)", export.results_json(results),
                               file_name="review_results.json", mime="application/json", width="stretch")

    st.divider()
    if st.button("Start a new review", icon=":material/restart_alt:"):
        reset()
        st.rerun()


# ---------------------------------------------------------------- main

def main() -> None:
    init_state()
    ui.load_css()
    ui.header(STEP_INDEX[st.session_state.step])
    {"upload": step_upload, "confirm": step_confirm,
     "review": step_review, "results": step_results}[st.session_state.step]()


main()
