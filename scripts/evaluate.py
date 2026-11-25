"""Planted-flaw evaluation: how well does the reviewer find flaws we put in on purpose?

How it works:
  1. Take 30 SciQ questions from data/sample/sciq_sample.csv (seed 42).
  2. Plant one known flaw in 24 of them (8 of each type) and leave 6 clean:
       also_correct - a distractor is replaced by a paraphrase of the answer
                      (paraphrases are made once with Gemini and stored in
                      data/eval/planted.json, so every run uses the same data)
       implausible  - a distractor is replaced by an everyday object ("a teacup")
       duplicate    - a distractor is replaced by a case/plural variant of another one
  3. Run the full pipeline and compare findings with the planted labels per
     (question, distractor index, issue type).
  4. Print and save precision / recall / F1 per flaw type and overall, the share of
     weak distractors that got a validated suggestion, and "answer preserved: n/n"
     to data/eval/results.md (raw results go to data/eval/results.json).

Re-running is cheap: all Gemini replies are cached in data/cache/.
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from pydantic import BaseModel
from sklearn.metrics import precision_recall_fscore_support

from src.reviewer import config, llm
from src.reviewer.models import MCQ
from src.reviewer.pipeline.runner import review, weak_distractors

SAMPLE_CSV = ROOT / "data" / "sample" / "sciq_sample.csv"
EVAL_DIR = ROOT / "data" / "eval"
PLANTED_FILE = EVAL_DIR / "planted.json"
SEED = 42
FLAW_TYPES = ["also_correct", "implausible", "duplicate"]
PER_TYPE = 8
N_CLEAN = 6
EVERYDAY_OBJECTS = ["a bicycle", "a teacup", "an umbrella", "a pencil sharpener",
                    "a football", "a toothbrush", "a wristwatch", "a frying pan"]


class Paraphrase(BaseModel):
    index: int
    paraphrase: str


# ------------------------------------------------------------ planting

def paraphrase_answers(items: list[dict]) -> list[str]:
    """One Gemini call: a short paraphrase (same meaning) of each correct answer."""
    lines = "\n".join(f"{i}: question: {it['question']} | answer: {it['correct_answer']}"
                      for i, it in enumerate(items))
    prompt = ("For each item, write a short paraphrase of the answer that a science teacher "
              "would ALSO mark correct (a synonym or equivalent wording, not the same words).\n"
              f"{lines}\nReturn JSON: a list of {{index, paraphrase}}.")
    raw = llm.generate_text(prompt, list[Paraphrase], temperature=0.0)
    by_index = {p.index: p.paraphrase for p in
                [Paraphrase.model_validate(x) for x in json.loads(raw)]}
    return [by_index[i] for i in range(len(items))]


def plural_or_case_variant(text: str) -> str:
    """'Proteins' -> 'protein', 'cell' -> 'Cells': same option, different surface form."""
    if text.lower().endswith("s") and not text.lower().endswith("ss"):
        variant = text[:-1]
    else:
        variant = text + "s"
    return variant.lower() if variant[:1].isupper() else variant.capitalize()


def build_planted() -> list[dict]:
    """Choose 30 questions and plant flaws; saved to planted.json and reused afterwards."""
    df = pd.read_csv(SAMPLE_CSV)
    rng = random.Random(SEED)
    chosen = rng.sample(range(len(df)), PER_TYPE * len(FLAW_TYPES) + N_CLEAN)
    items = []
    for n, row_index in enumerate(chosen):
        row = df.iloc[row_index]
        flaw = FLAW_TYPES[n // PER_TYPE] if n < PER_TYPE * len(FLAW_TYPES) else None
        items.append({
            "id": row["id"], "question": row["question"], "correct_answer": str(row["correct_answer"]),
            "distractors": [str(row["distractor1"]), str(row["distractor2"]), str(row["distractor3"])],
            "planted_type": flaw, "planted_index": None, "planted_text": None,
        })

    also = [it for it in items if it["planted_type"] == "also_correct"]
    for item, paraphrase in zip(also, paraphrase_answers(also)):
        _plant(item, rng.randrange(3), paraphrase)
    for k, item in enumerate(it for it in items if it["planted_type"] == "implausible"):
        _plant(item, rng.randrange(3), EVERYDAY_OBJECTS[k])
    for item in (it for it in items if it["planted_type"] == "duplicate"):
        # Copy distractor 0 into a later slot, so the copy is the one flagged as the duplicate.
        _plant(item, rng.choice([1, 2]), plural_or_case_variant(item["distractors"][0]))

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    PLANTED_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return items


def _plant(item: dict, index: int, text: str) -> None:
    item["planted_index"] = index
    item["planted_text"] = text
    item["distractors"][index] = text


def load_planted() -> list[dict]:
    if PLANTED_FILE.exists():
        return json.loads(PLANTED_FILE.read_text(encoding="utf-8"))
    return build_planted()


# ------------------------------------------------------------ scoring

def score(items: list[dict], results, severities=("high", "medium", "low")) -> dict:
    """Binary labels per (question, distractor index, flaw type) → precision/recall/F1.

    Only findings with a severity in `severities` count as flagged.
    """
    y_true = {t: [] for t in FLAW_TYPES}
    y_pred = {t: [] for t in FLAW_TYPES}
    for item, result in zip(items, results):
        for index in range(len(item["distractors"])):
            target = f"distractor:{index}"
            found = {f.issue_type for f in result.findings if f.target == target and f.severity in severities}
            for flaw in FLAW_TYPES:
                y_true[flaw].append(item["planted_type"] == flaw and item["planted_index"] == index)
                y_pred[flaw].append(flaw in found)

    table = {}
    for flaw in FLAW_TYPES:
        p, r, f, _ = precision_recall_fscore_support(y_true[flaw], y_pred[flaw], average="binary", zero_division=0)
        table[flaw] = (p, r, f, sum(y_true[flaw]), sum(y_pred[flaw]))
    all_true = [v for t in FLAW_TYPES for v in y_true[t]]
    all_pred = [v for t in FLAW_TYPES for v in y_pred[t]]
    p, r, f, _ = precision_recall_fscore_support(all_true, all_pred, average="binary", zero_division=0)
    table["overall"] = (p, r, f, sum(all_true), sum(all_pred))
    return table


def _recompute_overall(table: dict, items: list[dict], results) -> dict:
    """Overall row for the actionable table: HIGH/MEDIUM findings plus all duplicates."""
    y_true, y_pred = [], []
    for item, result in zip(items, results):
        for index in range(len(item["distractors"])):
            target = f"distractor:{index}"
            found = {f.issue_type for f in result.findings if f.target == target
                     and (f.severity in ("high", "medium") or f.issue_type == "duplicate")}
            for flaw in FLAW_TYPES:
                y_true.append(item["planted_type"] == flaw and item["planted_index"] == index)
                y_pred.append(flaw in found)
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    table["overall"] = (p, r, f, sum(y_true), sum(y_pred))
    return table


def metrics_table(table: dict) -> list[str]:
    lines = ["| Flaw type | Precision | Recall | F1 | Planted | Flagged |", "|---|---|---|---|---|---|"]
    for name, (p, r, f, planted, flagged) in table.items():
        lines.append(f"| {name} | {p:.2f} | {r:.2f} | {f:.2f} | {planted} | {flagged} |")
    return lines


def report(all_findings: dict, actionable: dict, results) -> str:
    weak = sum(len(weak_distractors(r.findings)) for r in results)
    suggested = sum(len(r.suggestions) for r in results)
    preserved = sum(r.answer_preserved for r in results)

    lines = [
        "# Planted-flaw evaluation results",
        "",
        f"Model: `{config.GEMINI_MODEL}` · 30 SciQ questions (seed {SEED}): "
        f"{PER_TYPE} per flaw type planted, {N_CLEAN} left clean.",
        "",
        "## Findings of any severity (everything the teacher sees)",
        "",
        *metrics_table(all_findings),
        "",
        "## HIGH and MEDIUM findings only (these trigger a replacement suggestion)",
        "",
        "Duplicates are LOW by design but always get a replacement, so they are counted here too.",
        "",
        *metrics_table(actionable),
        "",
        f"- Weak distractors with a validated suggestion: {suggested}/{weak} "
        f"({suggested / weak:.0%})" if weak else "- No weak distractors found.",
        f"- **Answer preserved: {preserved}/{len(results)}**",
        "",
        "Note: the \"clean\" SciQ items and the other distractors can contain real flaws "
        "(for example a genuinely implausible SciQ distractor). The reviewer flags those too, "
        "and they count as false positives here, which lowers measured precision. This is expected.",
    ]
    return "\n".join(lines)


def main() -> None:
    items = load_planted()
    mcqs = [MCQ(id=it["id"], question=it["question"], correct_answer=it["correct_answer"],
                distractors=it["distractors"], source=it["id"]) for it in items]

    results = review(mcqs, lambda i, n: print(f"  reviewed {i}/{n}", flush=True))
    all_findings = score(items, results)
    actionable = score(items, results, severities=("high", "medium"))
    # Duplicates are LOW but always replaced, so count them as actionable as well.
    actionable["duplicate"] = all_findings["duplicate"]
    actionable = _recompute_overall(actionable, items, results)
    text = report(all_findings, actionable, results)

    (EVAL_DIR / "results.md").write_text(text + "\n", encoding="utf-8")
    (EVAL_DIR / "results.json").write_text(
        json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(text)


if __name__ == "__main__":
    main()
