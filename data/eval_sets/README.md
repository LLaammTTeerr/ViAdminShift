# Evaluation item sets used in the paper

This directory holds byte-identical copies of the item files behind the paper's experiments. The originals stay where
the scripts expect them: `results/minitest/items/`, `data/benchmark/` and `results/mech/`. The scripts hard-code those
paths and must be run from the repository root. Both copies are kept so that the released data directory is
self-contained. The `sha256` column below verifies that a copy matches its original.

Licence: CC BY-SA 4.0 (see `../LICENSE.md`).

## Two tracks: why most results are not on the 7,995-item file

The paper has two kinds of experiments. Both draw their gold answers from the same canonical tables
(`data/processed/ward_mapping.jsonl` and `provinces_*.jsonl`).

1. **Closed-book probing experiments.** These are the cue ladder, T1np, date placement, frame, prefix and agent
   settings. They use the small, paired item sets in this directory. They are built by `scripts/minitest.py build-cue3`
   (seed 31), `scripts/build_review_items.py`, `scripts/build_sysdate_items.py` and `scripts/mech/build_items.py`, and use a simple short-answer schema.
   Every question exists in several versions that differ only in a prefix, a system prompt or one dropped component.
   This pairing is what allows within-unit comparisons. Scoring uses `minitest.label` / `analyze_cue.label2`: strict =
   new name only; outdated = old name only.
2. **Benchmark conditions** (closed, `rag_new`, `rag_mixed`, `rag_mixed+date`; question types; the 2x2 cells). These
   use the benchmark items in `data/benchmark/items.jsonl` (all 7,995) or the stratified 1,262-item subset
   `items_sub1k.jsonl`, with `viadmin.eval.runner` and the label scheme in `docs/SPEC.md`.

## Files

| File | Items | Feeds (paper) | Original path | Built by |
|---|---:|---|---|---|
| `cue3_items.jsonl` | 549 | Cue ladder base set and knowledge gate (Table *cue*, left), lineage table, model list. The 80 absorbed T1 units at cue *reform* are the gate items. Repeats and Muse-Glimmer chat-template ablation (Table *template*) | `results/minitest/items/` | `python3 scripts/minitest.py build-cue3 --out …` (defaults: 80 absorbed + 40 kept T1 units) |
| `cue3np_items.jsonl` | 360 | T1np: the same 120 wards without the province (Table *cue*, right; Table *template*) | `results/minitest/items/` | `python3 scripts/minitest.py build-cue3 --no-province --out …` |
| `cue3sub_items.jsonl` | 2,589 | Stratified extension for models that pass the gate: depth (Table *depth*), quantization ladder (Table *quant*) | `results/minitest/items/` | All T6 rows of `cue3full_items.jsonl`, plus the first 300 absorbed / 100 kept T1 bases and the first 300 renamed / 100 unchanged T5 bases, in file order |
| `cue3full_items.jsonl` | 6,789 | Superset of `cue3sub`. Some models (e.g. DeepSeek-V4.1-Flash, some local runs) answered all of it. `analyze_cue.py` pools all `preds_cue3*` predictions of a model by item id | `results/minitest/items/` | `python3 scripts/minitest.py build-cue3 --n-absorbed 1000 --n-kept 300 --n-successor 600 --out …` |
| `sysdate_items.jsonl` | 303 | Date placement (Tables *sys*, *sysctrl*). Asked under the conditions sys0 (plain system prompt), sys1 (system prompt + "Hôm nay là ngày 13/10/2026."), sysasof (system prompt + "Hãy trả lời theo thông tin tính đến tháng 10/2026.") and sys2025 (system prompt + "Hôm nay là ngày 01/01/2025.") | `results/minitest/items/` | The cue = *none* rows of `cue3_items` + `cue3np_items` (identical rows; `python3 scripts/build_sysdate_items.py`) |
| `sysdate_q_items.jsonl` | 303 | Date placement, condition sys0q: "Tính đến tháng 10/2026, " in the question, plain system prompt | `results/minitest/items/` | The cue = *date* rows of `cue3_items` + `cue3np_items` (identical rows; `python3 scripts/build_sysdate_items.py`) |
| `sysdate_qm_items.jsonl` | 303 | Date placement, condition sys0qm: "Hôm nay là ngày 13/10/2026. " in the question (same sentence as sys1, moved to the user turn) | `results/minitest/items/` | `python3 scripts/build_sysdate_items.py` (the `sysdate_items` rows with the sentence in front; cue label `datem`) |
| `sysdate_q2025_items.jsonl` | 303 | Date-placement control, condition q2025: pre-reform date "Tính đến tháng 1/2025, " in the question, no system prompt (Table *sysctrl*) | `results/minitest/items/` | `python3 scripts/build_sysdate_items.py` (the `sysdate_q_items` rows with the date replaced; cue label `d2025`) |
| `prefix_items.jsonl` | 480 | Wording controls (§ "Is the default an artefact of the question wording?"): prefix "Hiện nay, " (now) and a content-free filler "Cho tôi hỏi một câu, " on the 120 T1 and 120 T1np bases | `results/minitest/items/` | `scripts/build_review_items.py` |
| `newname_items.jsonl` | 720 | Frame control (Table *frame*): province of 240 wards asked by their **post-reform** name, no district, three cues. 120 bases have a defined old answer (`absorbed=true`, "renamed-old" stratum) and 120 do not ("new-only") | `results/minitest/items/` | `scripts/build_review_items.py` (from the cue = *none* `T1_newname` items of `data/benchmark/items.jsonl`) |
| `items_sub1k.jsonl` | 1,262 | Benchmark conditions on the stratified subset (Table *rag*), results by question type (Table *qtype*, appendix) | `data/benchmark/` | `uv run python scripts/make_sub1k.py` (question groups per (`qtype`, `format`) stratum, `random.Random(13)`; see the main README, *Evaluation subsets*). Exact subset of `data/benchmark/items.jsonl` (rows identical); its complement is `data/benchmark/items_rest.jsonl` (6,733) |
| `sysdate_nosuffix_items.jsonl` | 120 | Brevity-suffix control (reviewer request; scored by `scripts/score_nosuffix.py`): the 120 T1np cue = *none* questions without " Chỉ trả lời ngắn gọn bằng tên, không giải thích.", asked under sys0 / sys1 (`scripts/nosuffix.sh`, absorbed units only) | `results/minitest/items/` | `python3 scripts/build_sysdate_items.py` (the cue = *none* rows of `cue3np_items` with the answer-format suffix removed) |
| `agent_items.jsonl` | 7,998 | Agent settings (Table *agent*), via `scripts/agent_date.py`. Only the 1,333 rows with `cue == "sys0"` are read. These are the paper's 80 absorbed + 40 kept T1np units (`paper80 = true`) plus a seeded sample (`random.Random(11)`) of 280 absorbed + 80 kept others. Built by the item builder in `scripts/mech/` | `results/mech/items.jsonl` | `python3 scripts/mech/build_items.py` |

### Composition details

- **`cue3_items`**: 63 T6 bases (29 absorbed, 34 kept) + 120 T1 bases (80 absorbed, 40 kept) × 3 cues
  (`none`, `date` = "Tính đến tháng 10/2026, ", `reform` = "Sau đợt sắp xếp đơn vị hành chính năm 2025, ").
- **`cue3np_items`**: the same 120 T1 wards with the old province removed ("Xã X, Huyện D thuộc tỉnh/thành phố nào?").
  All 120 (ward, district) pairs are unique nationwide.
- **`cue3sub_items`**: 63 T6 + 400 T1 (300 absorbed / 100 kept) + 400 T5 (300 renamed / 100 kept name) bases × 3 cues.
  T5 drops wards whose new name occurs in the old ward, district or province name.
- **`cue3full_items`**: 63 T6 + 1,300 T1 (1,000 / 300) + 900 T5 (600 / 300) bases × 3 cues.
- **`sysdate*_items`**: 63 T6 (29 absorbed / 34 kept) + 120 T1 (80 / 40) + 120 T1np (80 / 40) = 303 per file.
- **`prefix_items`**: 120 T1 + 120 T1np bases × {`now`, `filler`}.
- **`items_sub1k`**: T1_membership 348, T5_ward_successor 318, T6_reverse 240, T4_address 150 (47 without
  diacritics), T1_newname 120, T3_existence 40, T2_composition 34, T0_headline 12. Formats: 828 MCQ, 434 short.
  Cells: pc0_wc0 72, pc0_wc1 315, pc1_wc0 100, pc1_wc1 475, no cell 300.
- **`agent_items`**: 1,333 T1np bases × 6 date conditions (`sys0`, `sys1`, `sysasof`, `sys0qm`, `sys0q`, `sys2025`).
  `split` is `derive` (200 absorbed + 100 kept) or `eval`. `agent_date.py` builds the agent conditions (earlier turn,
  tool result, tool offer, tool + instruction) itself from the `sys0` rows.

## Fields

**Probing sets** (all files except `items_sub1k` and `agent_items`):

| Field | Meaning |
|---|---|
| `id` | `<base>__<cue>`. Base prefixes: `P_<old province code>` (T6), `W_<old ward code>` (T1), `N_<old ward code>` (T1np), `S_<old ward code>` (T5), `T1N-<new ward code>` (new-name frame) |
| `base` | Unit id shared by all cue/prefix variants of one question (the pairing unit for bootstrap CIs) |
| `qtype` | `<type>/<cue>`, e.g. `T1_ward_province/reform`, `T1np_ward_province/none`, `T6_province/date`, `T5_ward_successor/none`, `T1new_ward_province/none` |
| `depth` | `surface` (T6), `compose` (T1, T1np), `deep` (T5), `newname` (frame control) |
| `absorbed` | T6/T1/T1np: the old province was merged into a differently named province (the test; `false` = control). T5: the ward was renamed. Frame set: an old answer is defined |
| `cue` | `none`, `date`, `reform`; `datem`, `d2025` (sysdate variants); `now`, `filler` (prefix set) |
| `question` | Full Vietnamese prompt, including the answer-format suffix " Chỉ trả lời ngắn gọn bằng tên, không giải thích." |
| `gold` | List of accepted current names (full official names with unit prefix) |
| `old` | List of pre-reform names that mark an answer as outdated (empty for controls) |

**`agent_items`** adds `system` (the system prompt of the condition), `split` (`derive`/`eval`), `paper80` (one of the
paper's 120 units), `old_province`, `new_province`.

**`items_sub1k`** uses the benchmark schema (`docs/SPEC.md`, "Benchmark items"): `id, qtype, question, format, choices,
answer, answer_aliases, old_answer, meta{…}`. RAG passages for these items come from `data/benchmark/contexts.jsonl`,
`data/wiki/passages.jsonl` and `data/benchmark/template_passages.jsonl`.

## Checksums (sha256)

```
029f90f18a1ec3a5a9dd974f74d157e784bb5c2d89b5ab5bb066919ac5476a2e  cue3_items.jsonl
da955809b697c46e9248905363b9876f619005125a7048e504074c400f139f8b  cue3np_items.jsonl
23fc659fac7664400789879ce57fad95aadc047695223a9f4cdbe251b061d50c  cue3sub_items.jsonl
62705a3fd71e2750e9415e14190c6c0a40754b5eaa8826a806bdab3fedd159b8  cue3full_items.jsonl
3ee44d84901d5b000139852915683b6aa1872e9099f04ffff07f8552eb0a0b78  sysdate_items.jsonl
5e2866dd468eb55909b757596134b110efcc620d5b5906938b0c8952bb5c2564  sysdate_q_items.jsonl
eee48ccc79d5330053ce60483593470c590881c08fa7aa42c3fd69760d9f4c62  sysdate_qm_items.jsonl
7710d643aaa998b38e221c3415e1d079083ee3dfe6708e47742e09682c6da2ae  sysdate_q2025_items.jsonl
4b8e08f11965fa8ca3a85b1a06b541e5d0c154f6ffedffa285b4574117501fa7  sysdate_nosuffix_items.jsonl
2bdb3665b75ecb626b0898d25bf52e6d16f39b4ed0887c6b8d8889dc8e78b6c8  prefix_items.jsonl
34d7c4eae7eecdf00b3236361d4da9b93cb9313628e3864d27473d80d8acfd40  newname_items.jsonl
daf664e91c5a8458426b41eb63aa23b13906497b8c73d1af4cf11250b6ffc2c2  items_sub1k.jsonl
1c7f1d373e54b5fa221580cfe1ff5bca565f18a77ff6e113327edaadc463195d  agent_items.jsonl
```

## Reproducing the sets

`cue3`, `cue3np`, `cue3full`, `newname` and `prefix` were rebuilt from `data/processed/` and checked byte for byte
against these files. `cue3sub` was re-derived from them by the rule above. The five `sysdate*` sets are derived from
`cue3` and `cue3np` by `scripts/build_sysdate_items.py`; `python3 scripts/build_sysdate_items.py --check` rebuilds
them in memory and compares them with `results/minitest/items/` and this directory. The builders write into
`results/minitest/items/` (`build_review_items.py` overwrites `newname_items.jsonl` and `prefix_items.jsonl` there),
so pass a scratch `--out` path where the CLI allows it.

## Item files not included here

These files are in `results/minitest/items/` but feed no table or reported number in the paper:
- `minitest_items_v1.jsonl`, `minitest_items_v2.jsonl`: early pilot sets.
- `rag_items.jsonl`: a pilot retrieval set with inline template passages (`minitest.py build-rag`). The paper's
  retrieval results use `items_sub1k.jsonl` and the full benchmark.

Some runs over `cue3sub_items` also wrote their predictions to files named `preds_cue3full_*`. This is a naming quirk
of the run scripts, not a different item set: check the item ids.
