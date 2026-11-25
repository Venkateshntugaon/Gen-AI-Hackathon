"""Builds data/sample/sample_paper.docx, a realistic teacher question paper for demos.

It takes 10 questions from data/sample/sciq_sample.csv and writes them in the
common school format (numbered question, options A-D on one line, "Answer: B").
Three questions get a deliberate flaw so the demo shows findings:
  - a duplicate option ("Protein" next to "proteins")
  - an implausible option ("A bicycle" for a flower part)
  - an option that is also correct ("Steam" next to "Water vapor")
The team exports this DOCX to PDF in Word to get a sample PDF.
"""

from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "sample" / "sciq_sample.csv"
OUTPUT = ROOT / "data" / "sample" / "sample_paper.docx"

# (SciQ id, position of the correct answer A-D)
CHOSEN = [
    ("SciQ #3657", "C"), ("SciQ #8279", "A"), ("SciQ #9674", "D"), ("SciQ #4557", "B"),
    ("SciQ #9195", "A"), ("SciQ #3257", "D"), ("SciQ #5574", "C"), ("SciQ #2547", "B"),
    ("SciQ #5514", "A"), ("SciQ #434", "C"),
]

# Planted flaws: SciQ id -> (distractor index to replace, new text, flaw type)
PLANTED_FLAWS = {
    "SciQ #8279": (2, "Protein", "duplicate"),       # duplicates "proteins"
    "SciQ #4557": (0, "A bicycle", "implausible"),   # not a flower part at all
    "SciQ #5574": (0, "Steam", "also_correct"),      # steam is water vapor
}

LETTERS = "ABCD"


def capitalise(text: str) -> str:
    return text[:1].upper() + text[1:]


def build_options(row: pd.Series, answer_letter: str) -> list[str]:
    """Return the 4 options in A-D order with the answer at answer_letter."""
    distractors = [str(row["distractor1"]), str(row["distractor2"]), str(row["distractor3"])]
    if row["id"] in PLANTED_FLAWS:
        index, new_text, _ = PLANTED_FLAWS[row["id"]]
        distractors[index] = new_text
    options = distractors[:]
    options.insert(LETTERS.index(answer_letter), str(row["correct_answer"]))
    return [capitalise(option) for option in options]


def main() -> None:
    df = pd.read_csv(SAMPLE_CSV).set_index("id", drop=False)

    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading("Green Valley Public School", level=1)
    doc.add_paragraph("Class VIII · Science · Unit Test 2")
    doc.add_paragraph("Time: 30 minutes        Maximum marks: 10")
    doc.add_paragraph("Instructions: Choose the correct option for each question. Each question carries 1 mark.")

    for number, (sciq_id, answer_letter) in enumerate(CHOSEN, start=1):
        row = df.loc[sciq_id]
        options = build_options(row, answer_letter)
        doc.add_paragraph(f"{number}. {row['question']}")
        doc.add_paragraph("   ".join(f"{LETTERS[i]}) {text}" for i, text in enumerate(options)))
        doc.add_paragraph(f"Answer: {answer_letter}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"Saved {len(CHOSEN)} questions ({len(PLANTED_FLAWS)} with planted flaws) to {OUTPUT}")


if __name__ == "__main__":
    main()
