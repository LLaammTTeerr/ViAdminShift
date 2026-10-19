# ViAdminShift

**ViAdminShift: A Vietnamese Benchmark for Event-Level Knowledge Updates Built from the 2025 Administrative Reform**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23473403.svg)](https://doi.org/10.5281/zenodo.23473403)

On 1 July 2025 Vietnam reorganised its administrative map:

- 63 provinces and centrally-run cities became **34**.
- The district level (696 units) was **abolished**, leaving a two-level structure.
- 10,035 communes (*xã, phường, thị trấn*) were merged into **3,321** (*xã, phường, đặc khu*).

ViAdminShift is a Vietnamese benchmark and toolkit. It measures whether large language models know the new map,
whether they *use* it when a question does not say which map it refers to, and whether they follow new or old
documents when both are given. This repository holds the data, the item generator, the evaluation code, the item sets
and predictions behind every result in the paper, and the scripts that rebuild every table.

- Data version: **2025-07-01**, the administrative structure in force on 1 July 2025 (see [Data version and
  updates](#data-version-and-updates)).
- Licences: data, model outputs (`results/`) and annotations (`docs/annotation/`) CC BY-SA 4.0, except the Tiny Aya
  outputs, CC BY-NC-SA 4.0 ([`data/LICENSE.md`](data/LICENSE.md)); code MIT ([`LICENSE`](LICENSE)).
- Datasheet: [`docs/datasheet.md`](docs/datasheet.md).

## Contents

1. [What is in the benchmark](#what-is-in-the-benchmark)
2. [Two evaluation tracks](#two-evaluation-tracks)
3. [Repository layout](#repository-layout)
4. [Installation](#installation)
5. [Regenerating the data](#regenerating-the-data)
6. [Running the evaluations from the paper](#running-the-evaluations-from-the-paper)
7. [Evaluation subsets](#evaluation-subsets)
8. [Data version and updates](#data-version-and-updates)
9. [Licences](#licences)
10. [Citation](#citation)

## What is in the benchmark

### Sources and canonical tables

- **Backbone.** The backbone is the official old-to-new conversion table of the National Statistics Office (NSO,
  *Bảng chuyển đổi ĐVHC mới – cũ*, danhmuchanhchinh.nso.gov.vn).
- **Province level.** Province groupings were transcribed from Resolution 202/2025/QH15. The build aborts unless the
  groupings implied by the NSO table match them exactly.
- **Cross-check.** An independently built mapping, vietnamadminunits (built from the composition texts of
  sapnhap.bando.com.vn), agrees on 10,564 of the 10,565 NSO pairs.
- **Adjudication.** Every disagreement was settled against the 34 ward-level resolutions of the National Assembly
  Standing Committee (NQ 1654–1687/NQ-UBTVQH15 of 16/6/2025). Details: [`docs/data_report.md`](docs/data_report.md).

| Table (`data/processed/`) | Rows | Breakdown |
|---|---:|---|
| `provinces_old.jsonl` | 63 | 57 tỉnh, 6 thành phố |
| `districts_old.jsonl` | 696 | abolished on 1/7/2025 |
| `wards_old.jsonl` | 10,035 | 7,691 xã, 1,727 phường, 617 thị trấn |
| `provinces_new.jsonl` | 34 | 28 tỉnh, 6 thành phố |
| `wards_new.jsonl` | 3,321 | 2,621 xã, 687 phường, 13 đặc khu |
| `ward_mapping.jsonl` | 10,566 | one row per (old ward, new ward) pair; covers all 10,035 old wards |

Each mapping row has exactly one `change_type`:

| `change_type` | Mapping rows | Old wards |
|---|---:|---:|
| merged | 9,462 | 9,462 |
| divided | 972 | 441 |
| unchanged | 127 | 127 |
| renamed | 5 | 5 |

All 10,566 rows have `confidence = "high"`, meaning at least two independent lineages attest them.

### The 2x2 design

Every ward-level item carries two flags:

- `province_changed` (**pc**): the old province was merged with another one. It is false only for the 11 provinces
  kept by NQ 202/2025/QH15: Cao Bằng, Điện Biên, Hà Tĩnh, Lai Châu, Lạng Sơn, Nghệ An, Quảng Ninh, Thanh Hóa, Sơn La,
  Hà Nội and Huế.
- `ward_changed` (**wc**): the ward was merged, divided or renamed.

The cell pc=0, wc=0 is the **pure control**: the correct answer is the same before and after the reform, so errors
there reflect missing geographic knowledge rather than outdated knowledge.

| Old wards per cell (full mapping) / benchmark items per cell | wc = 0 (ward kept) | wc = 1 (ward changed) |
|---|---:|---:|
| **pc = 0** (11 kept provinces) | 43 / 491 | 2,745 / 2,827 |
| **pc = 1** (52 merged provinces) | 84 / 925 | 7,163 / 3,205 |

The control cells are used in full. In the changed cells, sampling is stratified (round-robin over old provinces).
An old ward is eligible only if the *asked* answer actually changed:

- for pc=1, the province name changed;
- for wc=1, the bare ward name changed for every successor.

547 province-level and headline items have no cell.

### Item types (`data/benchmark/items.jsonl`, 7,995 items)

| Type | Depth | What is asked | Format | Items |
|---|---|---|---|---:|
| `T0_headline` | surface | headline facts (34 vs 63 provinces, 2 vs 3 levels, 3,321 communes, 13 đặc khu, …) | 7 MCQ + 5 short | 12 |
| `T6_reverse` | surface | which new province the area of old province *P* belongs to (all 63 old provinces) | MCQ + short, × 3 cues | 378 |
| `T2_composition` | surface | which old provinces form new province *Y* | MCQ | 34 |
| `T1_membership` | compose | province of old ward *X*, district *D*, old province *P* (927 old wards) | MCQ × 3 cues | 2,781 |
| `T1_newname` | deep | province of a ward given by its **post-reform** name (240 new wards) | MCQ × 3 cues | 720 |
| `T3_existence` | surface / deep | does a province, district or ward still exist, and at which level (154 yes / 154 no) | 4-way MCQ | 308 |
| `T4_address` | deep | rewrite an old 3-level address in the 2-level system (800 addresses + 400 diacritic-free twins) | short | 1,200 |
| `T5_ward_successor` | deep | which new ward the area of old ward *X* is in now (427 old wards) | MCQ + short, × 3 cues | 2,562 |
| **Total** | | | 5,320 MCQ, 2,675 short | **7,995** |

Every item stores:

- the gold answer;
- `old_answer`, the answer that was correct under the old structure, so that a wrong answer can be labelled
  *outdated* rather than merely wrong. It is `null` for the 2,989 items whose asked answer is the same in both
  structures (e.g. the province of a ward in one of the 11 kept provinces, or the pure-control cell); these are scored
  *correct* or wrong, and *outdated* only for a pre-reform legacy name (e.g. "Thừa Thiên Huế" for Huế);
- the 2x2 flags and a `meta.depth` tag.

**Cues.** T1, T1_newname, T5 and T6 come in three cue variants that differ only in a prefix:

- `none`: no temporal or change marker;
- `date`: "Tính đến tháng 10/2026, …";
- `reform`: "Sau đợt sắp xếp đơn vị hành chính năm 2025, …".

**Retrieval contexts.** Every item has three context conditions (`none`, `new`, `mixed`) in
`data/benchmark/contexts.jsonl` (23,985 rows). The passages are Vietnamese Wikipedia revisions from before
12/6/2025 (old) and from 15/7/2025 to 31/12/2025 (new), or template passages generated from the tables when no suitable
article exists. They are stored in `data/wiki/passages.jsonl` (1,584) and `data/benchmark/template_passages.jsonl`
(2,281).

Generation is deterministic: seed 13, byte-identical re-runs, sha256 values in `data/benchmark/build_stats.json`.
Full specification: [`docs/SPEC.md`](docs/SPEC.md). Counts and examples:
[`docs/benchmark_report.md`](docs/benchmark_report.md). Gold audit: [`docs/gold_audit.md`](docs/gold_audit.md).

## Two evaluation tracks

Most results in the paper are **not** computed on the 7,995-item file. The paper uses two tracks, and both draw their
gold answers from the same canonical tables.

1. **Closed-book probing experiments** (cue ladder, T1np, date placement, frame, prefix and agent settings, chat
   template, quantization).
   - They use small, *paired* short-answer item sets: every question is asked in several versions that differ only in
     a prefix, a system prompt or one dropped component, so all comparisons are within-unit.
   - They are built from `data/processed/` by `scripts/minitest.py build-cue3`, `scripts/build_review_items.py`,
     `scripts/build_sysdate_items.py` and `scripts/mech/build_items.py`, run with `scripts/minitest.py run` /
     `scripts/agent_date.py`, and scored by `scripts/analyze_*.py`.
2. **Benchmark conditions** (closed-book, `rag_new`, `rag_mixed`, `rag_mixed+date`; per question type; 2x2 cells).
   - They run `viadmin.eval.runner` on `data/benchmark/items.jsonl` (all 7,995 items for the small models) or on its
     stratified 1,262-item subset `data/benchmark/items_sub1k.jsonl`, drawn by `scripts/make_sub1k.py` (see
     [Evaluation subsets](#evaluation-subsets)).

The exact item files of both tracks are collected, with descriptions and checksums, in
[`data/eval_sets/`](data/eval_sets/README.md).

## Repository layout

```
data/
  raw/<source>/              SOURCE.md (URL, licence, sha256) and licence texts; the files themselves are fetched by scripts/fetch_sources.sh
  processed/                 canonical tables: rebuilt locally (scripts/fetch_sources.sh, then viadmin.data.build)
  wiki/                      Wikipedia passages (CC BY-SA), fetch log, quality flags
  benchmark/                 items.jsonl (7,995), contexts.jsonl, template_passages.jsonl, items_sub1k / items_rest
  probe/                     headline probe items (pilot; not used for the paper's results)
  eval_sets/                 copies of the item sets used for the paper's results (README inside)
  LICENSE.md                 data licence
src/viadmin/
  data/                      canonical-table build and cross-checks (NSO xlsx reader, resolution parser)
  wiki/                      Wikipedia revision fetcher and passage builder
  gen/                       item generator, RAG context builder, validator, count report
  eval/                      normalisation, prompts, backends (hf / vllm / openai), scorer, metrics, runner, linter
  probe/                     headline probe
scripts/                     probing-experiment runners and the analysis scripts that write results/analysis/*.tex
results/
  minitest/<source>/         predictions of the probing experiments, one directory per endpoint
  minitest/items/            item files of the probing experiments (originals of data/eval_sets/)
  bench/                     benchmark-condition predictions (viadmin.eval.runner output)
  review/, mech/             reviewer controls; the agent item file (`mech/items.jsonl`, built by scripts/mech/build_items.py)
  descriptive/omni/          cue3 predictions of five further reseller-served models; three are reported descriptively in
                             the paper, none is counted among the evaluated models; tables in analysis/descriptive/
  excluded/orouter/          cue3 and cue3np predictions of one OpenRouter model not counted among the evaluated models
  minitest/*.log, *.out      driver logs of the run scripts in scripts/ (progress lines and the per-run markers that
                             the scripts read when they resume)
  probe_deepseek-*/          headline-probe pilot runs (viadmin.eval.runner on data/probe/probe_all.jsonl; not used in the paper)
  analysis/                  JSON summaries and LaTeX tables used by the paper (analysis/descriptive/: the same for
                             descriptive/omni/)
tests/                       pytest suite
docs/                        SPEC, data / wiki / benchmark / probe reports, gold audit, manual checks, datasheet
CHANGELOG.md                 data versions, confirmed corrections, known later changes
```

## Installation

Python 3.12 with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                    # core dependencies (torch 2.13, transformers <5.18, openai, rapidfuzz, ...)
uv sync --extra vllm       # optional, on a GPU server only
uv run pytest -q           # test suite
```

`scripts/minitest.py` (except its `run-hf` subcommand, which needs torch), `scripts/analyze_*.py` and
`scripts/agent_date.py` use only the standard library; `scripts/clustered_ci.py` also needs numpy (installed by
`uv sync`). Run them
with `python3` from the repository root, because they use relative paths. API keys are read from environment variables
whose names are passed on the command line (e.g. `--api-key-env DS_TOKEN`). The shell wrappers in `scripts/*.sh`
source them from a git-ignored `.env`.

## Regenerating the data

The released files are the reference. Every step below is deterministic, and the generator re-runs byte for byte.

```bash
# 1. canonical tables from data/raw/ (NSO table, vietnamadminunits, resolutions, ...)
#    No source file with NSO data or data from a government portal is redistributed: fetch them first
bash scripts/fetch_sources.sh                  # downloads + SHA-256 check of every such file
uv run python -m viadmin.data.build            # -> data/processed/*.jsonl, build_stats.json, crosscheck_issues.jsonl
uv run pytest tests/test_data_build.py

# 2. Wikipedia passages (needs network unless data/raw/wiki_cache/ is present; the cache is git-ignored)
uv run python -m viadmin.wiki.build            # add --offline to rebuild from the cache
uv run python -m viadmin.wiki.report --write-quality

# 3. benchmark items, contexts and template passages (seed 13)
uv run python -m viadmin.gen.generate
uv run python -m viadmin.gen.validate                          # 0 problems expected
uv run python -m viadmin.eval.validate data/benchmark/items.jsonl  # items linter, 0 problems expected
uv run python -m viadmin.gen.report                            # count tables of docs/benchmark_report.md

# 4. probing item sets (closed-book track); write to a scratch path, then compare with data/eval_sets/
python3 scripts/minitest.py build-cue3 --out cue3_items.jsonl                    # 549 items
python3 scripts/minitest.py build-cue3 --no-province --out cue3np_items.jsonl    # 360 items
python3 scripts/minitest.py build-cue3 --n-absorbed 1000 --n-kept 300 --n-successor 600 --out cue3full_items.jsonl
python3 scripts/build_review_items.py          # newname + prefix sets (writes into results/minitest/items/)
python3 scripts/build_sysdate_items.py --check  # sysdate, sysdate_q, sysdate_qm, sysdate_q2025, sysdate_nosuffix
python3 scripts/mech/build_items.py            # agent items (writes results/mech/items.jsonl)
```

Notes:

- `data/processed/*.jsonl` (the canonical tables) is not in the repository, because it is derived from the NSO
  table, whose redistribution terms are not stated. Step 1 rebuilds it byte for byte; every
  later step and most analysis scripts need it.
- No source file that contains NSO data or data from a government portal is in the repository. Besides the NSO table
  (and its VietnamProvinces copy), `scripts/fetch_sources.sh` downloads the vietnamadminunits data files (GSO lists,
  scrapes of sapnhap.bando.com.vn and cas.so, tables built from them), their copy in undertheseanlp/address,
  vietaddr's data files (generated from the NSO table) and the hoatieu.vn resolution pages. Only their `SOURCE.md`
  notes, licence texts and READMEs are tracked.
- How `cue3sub`, `sysdate*` and `items_sub1k` are derived from the files above is described in
  [`data/eval_sets/README.md`](data/eval_sets/README.md).

## Running the evaluations from the paper

### Probing experiments (closed-book)

Run an item set against any OpenAI-compatible endpoint, such as llama.cpp's `llama-server`, an API or OpenRouter.
Runs are resumable.

```bash
python3 scripts/minitest.py run --items results/minitest/items/cue3_items.jsonl \
  --url http://127.0.0.1:8080 --model NAME --out results/minitest/<source>/preds_cue3_NAME.jsonl \
  [--api-key-env VAR] [--extra '{"thinking": {"type": "disabled"}}'] [--system "Bạn là một trợ lý hữu ích."] \
  [--max-tokens 1024] [--par 8] [--only T1_ward_province:absorbed]

python3 scripts/minitest.py knows results/minitest/<source>/preds_cue3_NAME.jsonl   # knowledge gate: exit 0 iff
                                                    # strict accuracy on absorbed T1 units at cue=reform >= 0.50
python3 scripts/minitest.py score preds1.jsonl preds2.jsonl ...
python3 scripts/api_sweep.py --items X.jsonl --url URL --api-key-env VAR --outdir DIR --tag cue3 model1 model2 ...
```

- **Date placement.** Run `sysdate_items` with the four system prompts (sys0, sys1, sysasof, sys2025), and
  `sysdate_q`, `sysdate_qm` and `sysdate_q2025` with the plain system prompt or none. The exact system prompts and
  output names are in `scripts/openrouter_controls.sh`, `scripts/review_controls.sh` and
  `scripts/review2_controls.sh`. The item files are derived from the cue sets by `scripts/build_sysdate_items.py`.
- **Claude Fable 5.1 at `reasoning_effort=none`.** `scripts/claude_fable51_none.sh` repeats every Fable 5.1 probing
  run at the lowest reasoning setting, the run counted in the paper; outputs go to `results/minitest/claude_none/`,
  `results/minitest/sysprompt/*__claude_none.jsonl` and `results/review/*__claude_none.jsonl`.
- **Generation limits.** API probing runs use `--max-tokens 1024` (2,048 for the Claude ablations), with these
  exceptions: 4,096 for Grok-4.7 and Gemini-4-Argon through OpenRouter, whose reasoning cannot be turned off
  (`scripts/orouter_screen.sh`, `scripts/orouter_more.sh`); 256 for the reasoning-off agent conditions
  (`scripts/agent_date.py`); 8,192 for reasoning-on runs. No answer in these runs ends at the limit.
- **Agent settings.** `scripts/agent_date.py` asks the T1np units with the date given in the system prompt, in the
  question, in an earlier turn, as a `get_current_date` tool result, or through an offered tool (with or without an
  instruction to call it):

```bash
python3 scripts/agent_date.py run deepseek-flash [--paper | --ext] [--conds a,b] [--think] [--rpm N]
python3 scripts/agent_date.py score      # -> results/analysis/agent_date.json, agent_date_table.tex
```

### Benchmark conditions (7,995 items or the 1,262-item subset)

```bash
uv run python -m viadmin.eval.runner --backend openai --base-url http://host:8000/v1 --model NAME \
  --items data/benchmark/items_sub1k.jsonl --contexts data/benchmark/contexts.jsonl \
  --passages data/wiki/passages.jsonl,data/benchmark/template_passages.jsonl \
  --conditions closed,rag_new,rag_mixed,rag_mixed+date --out results/bench/NAME
# other backends: --backend hf (transformers, --quant 4bit) or --backend vllm; see docs/eval_README.md
uv run python -m viadmin.eval.runner --items data/benchmark/items.jsonl --rescore --out results/bench/NAME
```

### Rebuilding the tables

Every table in the paper is written by these scripts from the released predictions under `results/`:

```bash
python3 scripts/analyze_cue.py        # cue ladder, depth, lineage, quantization, model list
python3 scripts/analyze_cue.py --root results/descriptive --out results/analysis/descriptive/cue   # descriptive/omni/
python3 scripts/analyze_sys.py        # date placement (main and control tables)
python3 scripts/analyze_review.py     # frame / prefix / repeat controls
python3 scripts/agent_date.py score   # agent settings
python3 scripts/analyze_template.py   # Muse-Glimmer chat-template ablation
python3 -c "import sys; sys.path.insert(0,'scripts'); import analyze_rag as r; r.main(); r.tex()"  # retrieval table
python3 scripts/analyze_bench_extra.py  # 2x2 cells and per-question-type tables (run after analyze_rag)
python3 scripts/clustered_ci.py       # province-clustered intervals and wild cluster tests (run after the above)
```

**Intervals.** The scripts above give unit-level paired bootstrap intervals (B=2,000), on which the prespecified
criteria were evaluated. Absorbed wards of one old province share their answer, so `scripts/clustered_ci.py` adds, for
the same paired differences, a cluster bootstrap over old provinces (B=10,000) and a Rademacher wild cluster bootstrap
test (B=10,000); an effect counts as established when the cluster interval excludes zero and p < 0.05. Per-model
results with both kinds of interval are in `results/analysis/clustered.md` (and `.json`).

**Scoring.**

- *Probing track.* Answers are NFC-normalised and lower-cased, tone placement and dashes are unified (*Hoà* = *Hòa*,
  *–* = *-*), and punctuation and unit-type prefixes (*tỉnh, thành phố, phường, xã, …*) are removed. An answer is then:
  - *correct* if it names only the new unit;
  - *outdated* if it names only the old unit;
  - *both* if it names both;
  - *other* otherwise.
  The headline metric is strict accuracy (correct only).
- *Benchmark track.* Rule-based labels `correct / outdated / other_wrong / invalid`, defined in
  [`docs/eval_README.md`](docs/eval_README.md).

## Evaluation subsets

[`data/eval_sets/`](data/eval_sets/README.md) holds byte-identical copies of the item files behind the paper's results:

| File | Items | Used for |
|---|---:|---|
| `cue3_items.jsonl` | 549 | cue ladder base set (63 T6 + 120 T1 units × 3 cues), knowledge gate |
| `cue3np_items.jsonl` | 360 | T1np: the same wards without the old province |
| `cue3sub_items.jsonl` | 2,589 | stratified extension (T6, 400 T1, 400 T5 units × 3 cues): depth, quantization |
| `cue3full_items.jsonl` | 6,789 | superset of `cue3sub`, answered in full by some models |
| `sysdate_items.jsonl`, `sysdate_q_items.jsonl`, `sysdate_qm_items.jsonl`, `sysdate_q2025_items.jsonl` | 303 each | date placement (system prompt vs question) and its controls |
| `prefix_items.jsonl` | 480 | wording controls ("Hiện nay," and a content-free filler) |
| `newname_items.jsonl` | 720 | frame control (post-reform ward names) |
| `items_sub1k.jsonl` | 1,262 | benchmark conditions and per-type results (subset of `items.jsonl`, see below) |
| `agent_items.jsonl` | 7,998 | agent settings (T1np units; 1,333 `sys0` rows used) |
| `sysdate_nosuffix_items.jsonl` | 120 | brevity-suffix reviewer control |

**The 1,262-item subset** (`data/benchmark/items_sub1k.jsonl`, complement `items_rest.jsonl`) is drawn by
`scripts/make_sub1k.py` (`--check` verifies the released files byte for byte):

- sampling unit: a question group, all items whose `id` has the same part before `__` (so the cue and diacritic variants
  of one question stay together);
- strata: (`qtype`, `format`), visited in sorted order with one `random.Random(13)`;
- a stratum with at most 40 groups is taken whole; a larger one contributes `max(40, round(0.125 × groups))` groups,
  drawn with `rng.sample` from its sorted group keys;
- rows keep the order and the exact lines of `items.jsonl`.

## Data version and updates

**Version 2025-07-01.** The tables, items and gold answers describe the structure in force on **1 July 2025**:

- Resolution 202/2025/QH15 of the National Assembly (12/6/2025) on the province-level arrangement;
- the 34 Standing Committee resolutions NQ 1654–1687/NQ-UBTVQH15 of 16/6/2025 on the commune-level arrangement of each
  new province;
- the NSO conversion table that implements them.

"Old" means the structure on 30 June 2025.

**Changes after 1 July 2025.** The later changes we know of concern unit type only. Between 30 April and 20 September
2026, Đồng Nai, Quảng Ninh and Bắc Ninh became centrally-run cities (*thành phố*) with the same name and territory
(Resolutions 30, 36 and 39/2026/QH16), and 10 *xã* of Đồng Nai and 12 of Bắc Ninh became *phường* under the same names
(Resolutions 237 and 388/NQ-UBTVQH16). The release does not reflect this. Because the scorers strip unit-type words
and MCQ options differ by name, only T3 items, which name the unit type, are affected: four of them (`T3-prov-22`,
`T3-prov-27`, `T3-prov-75` and `T3-dist-256`) are correct only at the version date, and no ward-level item names one
of the 22 communes that became *phường*.

- Both scorers ignore the "Tỉnh" / "Thành phố" prefix, so "Tỉnh Đồng Nai" and "Thành phố Đồng Nai" are scored the
  same; such an answer is correct only because of this normalisation. The probing track has no MCQs.
- The number of provincial-level units (34) is unchanged. Items that ask about the present (*hiện nay*, "now") refer
  to version 2025-07-01, so later users should check the `T0` totals against the version date.
- In the benchmark's MCQ items, the choices differ by name. Choices still print the 1/7/2025 prefix ("Tỉnh Đồng Nai"),
  which a model aware of the 2026 changes may read as outdated (see `docs/benchmark_report.md`, section 7).
- The scorers also ignore the *xã* / *phường* prefix. Later reclassifications of communes as wards therefore do not
  change ward-level gold answers either.
- Retrieval passages use Wikipedia revisions from before 1 January 2026, which match the 1/7/2025 counts.

**Update plan.** The administrative map will keep changing, so the data is released in **versions named after the
date of the structure they describe**.

- When the map changes in a way that alters names, membership or boundaries, we plan a new version with:
  - rebuilt tables from the then-current official conversion table and resolutions;
  - regenerated items, with the previous version as the "old" structure;
  - a changelog.
- Earlier versions stay available unchanged, so published results remain reproducible.
- Confirmed corrections and known later changes are listed in [`CHANGELOG.md`](CHANGELOG.md); report errors on the
  issue tracker.
- Changes that alter neither names nor boundaries, such as the 2026 city upgrades above, are documented in this README
  without a new version.

## Licences

- **Code** (`src/`, `scripts/`, `tests/`): MIT, see [`LICENSE`](LICENSE).
- **Data released by the authors** (everything under `data/` except `data/raw/`; the canonical tables are rebuilt,
  not shipped), **model predictions and analysis outputs** (`results/`) and **scorer-validation annotations**
  (`docs/annotation/`): CC BY-SA 4.0, see [`data/LICENSE.md`](data/LICENSE.md) (exception: the Tiny Aya outputs, below).
  - Share-alike is required for the Wikipedia-derived passages (`data/wiki/passages.jsonl`, the `wiki_excerpt` rows of
    `data/benchmark/template_passages.jsonl`). It is used for all data files for simplicity, in line with the
    paper's Ethics and Data Statement.
  - Each Wikipedia passage carries its page title and revision id for attribution.
- **Third-party source files in `data/raw/`** keep their own terms, listed in each `SOURCE.md`:
  - no source file that contains NSO data or data from a government portal is redistributed; all are downloaded by
    `scripts/fetch_sources.sh`: the NSO table (official statistical classification, no explicit licence) and its
    VietnamProvinces copy (GPL-3.0-or-later), the vietnamadminunits data files (MIT), their copy in
    undertheseanlp/address (Apache-2.0), vietaddr's data files (GPL-3.0-or-later) and the hoatieu.vn resolution pages;
  - resolutions: legal texts, not copyrighted.
- **Model weights and outputs.** The models are used under their own licences.
  Model outputs in `results/` and the annotations in `docs/annotation/` are released under CC BY-SA 4.0, except the
  Tiny Aya outputs (`results/bench/tiny-aya-global-q8_0/`, `results/minitest/gpu/preds_*_tiny-aya-global.jsonl`), which
  are released under CC BY-NC-SA 4.0 because the model's licence (CC BY-NC 4.0) restricts commercial use. Outputs of
  hosted models are also released under CC BY-SA 4.0; users must still follow each provider's terms.

The benchmark measures model knowledge. It is not an authoritative address converter; consult official sources for
administrative use.

## Citation

```bibtex
@misc{viadminshift2026,
  title  = {{ViAdminShift}: A {Vietnamese} Benchmark for Event-Level Knowledge Updates Built from the 2025 Administrative Reform},
  author = {Phan, Binh Nguyen Lam and Nguyen, Thai Anh},
  year   = {2026},
  note   = {Data version 2025-07-01},
  doi    = {10.5281/zenodo.23473403},
  url    = {https://doi.org/10.5281/zenodo.23473403}
}
```

Contact: questions and error reports go to the issue tracker of this repository.
