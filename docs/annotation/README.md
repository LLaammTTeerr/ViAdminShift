# Scorer validation: instructions for the two annotators

Each sheet (`sheet_A.csv` for annotator A, `sheet_B.csv` for annotator B) has the same 200 model answers in a different
order. The filled-in sheets are `sheet_A_labeled.csv` and `sheet_B_labeled.csv`. Every question asks which province an old ward belongs to now; the province changed in the 2025 reform.

Columns: `question`, `new_answer` (the correct post-reform province), `old_answer` (the pre-reform province),
`model_output`. Fill in `label` with exactly one of the five labels below; use `note` for anything unclear. Do not
look at the other sheet, at `key.jsonl`, or at the model names, and do not discuss rows with the other annotator
until both sheets are done.

| label | when |
|---|---|
| `correct` | The answer names only the new province (spelling variants, missing "Tỉnh"/"Thành phố" or a short note are fine). |
| `outdated` | The answer names only the old province. |
| `both_new` | Both provinces are named and the answer commits to the new one (e.g. "Tỉnh Tuyên Quang (trước đây là Hà Giang)"). |
| `both_old` | Both are named and the answer commits to the old one (e.g. "Tỉnh Hà Giang (từ 1/7/2025 sáp nhập vào Tuyên Quang)"). |
| `other` | Neither province, a different province, an empty answer, or a refusal. |

When both are named and it is unclear which one the answer commits to, choose the one that a reader who wants a
current address would take from the answer, and write a note.

When both sheets are done, run:

```bash
python3 scripts/make_annotation.py score docs/annotation/sheet_A_labeled.csv docs/annotation/sheet_B_labeled.csv
```

It prints Cohen's kappa between the annotators and between each annotator and the automatic scorer, on the five
labels and on the paper's summary metrics (new-first / old-only / rest). The kappa values are reported in the
"Scoring" paragraph of the paper's Discussion.

Licence: CC BY-SA 4.0 (see `../../data/LICENSE.md`, which also states the licence of the model outputs).
