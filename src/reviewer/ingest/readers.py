"""Turns an uploaded file (PDF, DOCX, TXT or CSV) into plain text or question rows.

Why this file exists: teachers upload question papers in the format they already
have. Each reader turns one format into plain text that the regex parser can read.
The CSV reader is an optional "power user" path for SciQ-style files, which
already contain the answer, so it returns MCQ objects directly.
"""

import csv
import io

import pdfplumber
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.reviewer.models import MCQ

PAGE_MARKER = "--- Page {} ---"


def read_pdf(data: bytes) -> str:
    """Return the text of every page, each page preceded by a page marker.

    A scanned PDF (only images) gives back markers but no real text; see pdf_has_text().
    """
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            pages.append(PAGE_MARKER.format(number))
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def pdf_has_text(pdf_text: str) -> bool:
    """True if the PDF text contains more than just our page markers."""
    lines = [line for line in pdf_text.splitlines() if line.strip()]
    return any(not line.startswith("--- Page ") for line in lines)


def read_docx(data: bytes) -> str:
    """Return paragraphs and table cells in document order.

    Many papers put options in a table, so tables are read too. Each table row
    becomes one line (cells separated by spaces), which the parser handles like
    options written on one line.
    """
    doc = Document(io.BytesIO(data))
    lines = []
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(block, doc).text)
        elif tag == "tbl":
            lines.extend(_table_lines(Table(block, doc)))
    return "\n".join(lines)


def _table_lines(table: Table) -> list[str]:
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = cell.text.strip()
            # Merged cells are returned once per grid column; keep only one copy.
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        lines.append("   ".join(cells))
    return lines


def read_txt(data: bytes) -> str:
    """Decode a text file (UTF-8, falling back to Latin-1 for old Windows files)."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_csv(data: bytes) -> list[MCQ]:
    """Read a SciQ-style CSV: id, question, correct_answer, distractor1..3."""
    rows = csv.DictReader(io.StringIO(read_txt(data)))
    mcqs = []
    for number, row in enumerate(rows, start=1):
        distractors = [row.get(f"distractor{i}", "").strip() for i in (1, 2, 3, 4)]
        mcq_id = (row.get("id") or f"Q{number}").strip()
        mcqs.append(MCQ(
            id=mcq_id,
            question=row["question"].strip(),
            correct_answer=row["correct_answer"].strip(),
            distractors=[d for d in distractors if d],
            source=mcq_id,
        ))
    return mcqs
