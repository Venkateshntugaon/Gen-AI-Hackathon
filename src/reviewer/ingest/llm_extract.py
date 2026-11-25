"""Gemini fallback extractor, plus the function that decides when to use it.

Why this file exists: the regex parser handles common layouts, but some papers
are messy, and scanned PDFs contain no text at all. In those cases we ask Gemini
to extract the questions. For a scanned PDF we send the PDF bytes directly,
because Gemini reads PDFs natively (no OCR library needed).
The prompt (prompts/extract.md) tells Gemini to copy text verbatim and to leave
the answer empty unless the paper marks it. The teacher confirms answers later.
"""

import re
from pathlib import Path

from google.genai import types
from pydantic import BaseModel

from src.reviewer import llm
from src.reviewer.ingest import readers
from src.reviewer.ingest.parser import LETTERS, ParsedMCQ, needs_llm_fallback, parse

PROMPT_FILE = Path(__file__).resolve().parents[3] / "prompts" / "extract.md"


class ExtractedQuestion(BaseModel):
    number: int
    question: str
    options: list[str]
    answer: str | None


class ExtractOutput(BaseModel):
    questions: list[ExtractedQuestion]


def extract_questions(filename: str, data: bytes) -> tuple[list[ParsedMCQ], bool]:
    """Read a PDF / DOCX / TXT paper and return (questions, used_llm).

    The regex parser runs first. Gemini is used only when the PDF has no
    selectable text (scanned) or the parser result looks unreliable.
    """
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        text = readers.read_pdf(data)
        if not readers.pdf_has_text(text):
            return extract_with_llm(filename, pdf_bytes=data), True
    elif suffix == ".docx":
        text = readers.read_docx(data)
    elif suffix == ".txt":
        text = readers.read_txt(data)
    else:
        raise ValueError(f"Unsupported file type: {suffix or filename}. Use PDF, DOCX or TXT.")

    parsed = parse(text, filename)
    if needs_llm_fallback(parsed):
        return extract_with_llm(filename, text=text), True
    return parsed, False


def extract_with_llm(filename: str, text: str | None = None,
                     pdf_bytes: bytes | None = None) -> list[ParsedMCQ]:
    """Ask Gemini to extract the MCQs from the document text or the PDF bytes."""
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    if pdf_bytes is not None:
        contents = [prompt, types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")]
    else:
        contents = [f"{prompt}\n\nDocument:\n{text}"]

    raw = llm.generate_text(contents, ExtractOutput, temperature=0.0)   # literal copy, not creative
    output = ExtractOutput.model_validate_json(raw)
    return [_to_parsed(q, filename) for q in output.questions]


def _to_parsed(q: ExtractedQuestion, filename: str) -> ParsedMCQ:
    answer = (q.answer or "").strip().strip("()").upper() or None
    # Keep the answer only if it is a real option letter; otherwise the teacher picks it.
    if answer not in tuple(LETTERS) or LETTERS.index(answer) >= len(q.options):
        answer = None
    return ParsedMCQ(number=q.number, question=q.question, options=strip_option_letters(q.options),
                     answer=answer, source=f"{filename} Q{q.number} (extracted by Gemini)")


def strip_option_letters(options: list[str]) -> list[str]:
    """Remove a leading "A) " / "(b) " / "C. " label that Gemini sometimes copies into the option.

    Only the label matching the option's own position is removed, so text such as
    "A bicycle" in position A is kept (no bracket or dot after the letter).
    """
    cleaned = []
    for position, option in enumerate(options):
        letter = LETTERS[position] if position < len(LETTERS) else ""
        pattern = rf"^\s*\(?[{letter}{letter.lower()}][.)]\s*" if letter else r"(?!)"
        cleaned.append(re.sub(pattern, "", option, count=1).strip() or option.strip())
    return cleaned
