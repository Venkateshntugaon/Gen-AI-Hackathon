# Planted-flaw evaluation results

Model: `gemini-3.5-flash-lite` · 30 SciQ questions (seed 42): 8 per flaw type planted, 6 left clean.

## Findings of any severity (everything the teacher sees)

| Flaw type | Precision | Recall | F1 | Planted | Flagged |
|---|---|---|---|---|---|
| also_correct | 0.64 | 0.88 | 0.74 | 8 | 11 |
| implausible | 0.14 | 1.00 | 0.24 | 8 | 58 |
| duplicate | 1.00 | 1.00 | 1.00 | 8 | 8 |
| overall | 0.30 | 0.96 | 0.46 | 24 | 77 |

## HIGH and MEDIUM findings only (these trigger a replacement suggestion)

Duplicates are LOW by design but always get a replacement, so they are counted here too.

| Flaw type | Precision | Recall | F1 | Planted | Flagged |
|---|---|---|---|---|---|
| also_correct | 0.64 | 0.88 | 0.74 | 8 | 11 |
| implausible | 0.26 | 1.00 | 0.41 | 8 | 31 |
| duplicate | 1.00 | 1.00 | 1.00 | 8 | 8 |
| overall | 0.46 | 0.96 | 0.62 | 24 | 50 |

- Weak distractors with a validated suggestion: 45/45 (100%)
- **Answer preserved: 30/30**

Note: the "clean" SciQ items and the other distractors can contain real flaws (for example a genuinely implausible SciQ distractor). The reviewer flags those too, and they count as false positives here, which lowers measured precision. This is expected.
