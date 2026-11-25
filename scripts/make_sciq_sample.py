"""Builds our sample dataset: 100 random science MCQs from SciQ.

SciQ (allenai/sciq) is a public set of real, verified science questions, each with
one correct answer and three distractors. We save 100 of them (fixed seed 42, so
everyone on the team gets the same sample) to data/sample/sciq_sample.csv.
The "support" passage is NOT saved, because our reviewer does not use one.
"""

import random
from pathlib import Path

from datasets import load_dataset

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "sample" / "sciq_sample.csv"
SAMPLE_SIZE = 100
SEED = 42


def main() -> None:
    train = load_dataset("allenai/sciq", split="train")
    row_numbers = random.Random(SEED).sample(range(len(train)), SAMPLE_SIZE)

    df = train.select(row_numbers).to_pandas()
    df["id"] = [f"SciQ #{n}" for n in row_numbers]   # keeps the original SciQ row number
    df = df[["id", "question", "correct_answer", "distractor1", "distractor2", "distractor3"]]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Saved {len(df)} questions to {OUTPUT}")


if __name__ == "__main__":
    main()
