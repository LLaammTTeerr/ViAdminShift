# Datasheet for ViAdminShift

This datasheet follows *Datasheets for Datasets* (Gebru et al., 2021). Facts are taken from the repository
documentation: `docs/SPEC.md`, `docs/data_report.md`, `docs/wiki_report.md`, `docs/benchmark_report.md`,
`docs/gold_audit.md` and the paper. The coverage numbers in section 2.4 were computed from
`data/processed/ward_mapping.jsonl` and `data/benchmark/items.jsonl`.

Data version: **2025-07-01**, the administrative structure in force on 1 July 2025.

---

## 1. Motivation

**For what purpose was the dataset created?**
On 1 July 2025 Vietnam reduced its provinces from 63 to 34, abolished the district level (696 units), and merged its
10,035 communes into 3,321. ViAdminShift was created to measure:

- whether large language models know the post-reform structure;
- whether they know only the *surface* facts ("34 provinces", "Bình Dương merged into Ho Chi Minh City") or also the
  entailed ward-level facts;
- whether they *use* the new map when a question does not state which map it refers to;
- which document they follow when given both old and new documents;
- whether simple mitigations help (dated passages, a current date in the prompt).

The design isolates outdated knowledge from missing geographic knowledge through a 2x2 control (province changed ×
ward changed).

**Who created the dataset, and on behalf of which entity?** Phan Binh Nguyen Lam (Faculty of Information Technology,
University of Science, Vietnam National University, Ho Chi Minh City) and Nguyen Thai Anh (Faculty of Information
Technology, Van Lang School of Technology, Van Lang University, Ho Chi Minh City), as academic research.

**Who funded the creation of the dataset?** No external funding.

**Any other comments?**
Per the paper's ethics statement, Claude (Anthropic) was used to help write the data-processing, generation and
evaluation code, and to run an automated audit of the items. The authors designed the study and checked the data and
the results.

## 2. Composition

### 2.1 What do the instances represent?

The release has four layers.

| Layer | File(s) | Instances |
|---|---|---|
| Canonical tables (rebuilt locally, not shipped) | `data/processed/provinces_old.jsonl` | 63 pre-reform provinces (57 tỉnh, 6 thành phố) |
| | `data/processed/districts_old.jsonl` | 696 pre-reform districts |
| | `data/processed/wards_old.jsonl` | 10,035 pre-reform communes (7,691 xã, 1,727 phường, 617 thị trấn) |
| | `data/processed/provinces_new.jsonl` | 34 post-reform provinces (28 tỉnh, 6 thành phố) with their components |
| | `data/processed/wards_new.jsonl` | 3,321 post-reform communes (2,621 xã, 687 phường, 13 đặc khu) |
| | `data/processed/ward_mapping.jsonl` | 10,566 (old ward, new ward) pairs covering all 10,035 old wards |
| Passages | `data/wiki/passages.jsonl` | 1,584 Vietnamese Wikipedia passages: one per (province or district, era old/new) |
| | `data/benchmark/template_passages.jsonl` | 2,281 retrieval passages: 1,002 Wikipedia excerpts + 1,279 template passages generated from the tables |
| Benchmark | `data/benchmark/items.jsonl` | 7,995 questions (5,320 MCQ, 2,675 short answer) |
| | `data/benchmark/contexts.jsonl` | 23,985 rows: the passage ids shown for each item under the `none`, `new` and `mixed` conditions |
| Evaluation sets | `data/eval_sets/*.jsonl` | The paired short-answer item sets of the paper's probing experiments, plus the 1,262-item benchmark subset (see `data/eval_sets/README.md`) |

There are 23,985 context rows because there are 3 conditions for each of the 7,995 items.

**Benchmark items by type:**

| Type | Items |
|---|---:|
| T0 headline | 12 |
| T6 old province → new province | 378 (63 provinces × MCQ/short × 3 cues) |
| T2 composition of a new province | 34 |
| T1 ward → province | 2,781 (927 old wards × 3 cues) |
| T1 new-name → province | 720 (240 new wards × 3 cues) |
| T3 existence | 308 |
| T4 address conversion | 1,200 (800 addresses + 400 diacritic-free twins) |
| T5 old ward → new ward | 2,562 (427 old wards × MCQ/short × 3 cues) |

### 2.2 How many instances per cell?

The 2x2 cells of the mapping, as old wards per cell / benchmark items per cell (all cue variants and twins):

| | ward kept (wc=0) | ward changed (wc=1) |
|---|---:|---:|
| province kept (pc=0, 11 provinces) | 43 / 491 | 2,745 / 2,827 |
| province merged (pc=1, 52 old provinces) | 84 / 925 | 7,163 / 3,205 |

547 province-level and headline items have no cell.

### 2.3 Is it a sample?

**Tables.** The tables are complete: every unit and every pair of the 1/7/2025 reform. The only exceptions are listed
under "missing information" in 2.6.

**Benchmark items.** The items are a stratified, seeded sample (seed 13, deterministic):

- The control cells pc0_wc0 (43 old wards) and pc1_wc0 (84) are used in full.
- In the changed cells, old wards are drawn round-robin over old provinces. T1 draws 400 per changed cell, T5 draws
  150, and T4 splits ~336 per cell (800 addresses in total).
- In a changed cell, an old ward is eligible only if the *asked* answer changed:
  - for pc=1, the province *name* changed (`province_name_changed`);
  - for wc=1, the bare ward name changed for every successor.
- Divided wards (441 old wards) are excluded from T4 and T5 (no unique answer) but kept in T1.
- For T5, the 264 old wards whose name is the name of another current ward in the same new province are excluded.

**Probing sets.** These are separate seeded samples (seed 31) from the same table. The base set has 80 absorbed + 40
kept T1 wards; the extension has 300 + 100 T1 and 300 + 100 T5 wards.

### 2.4 Geographic coverage of ward-level items

These numbers were computed from `data/processed/ward_mapping.jsonl` and `data/benchmark/items.jsonl`. The headline
figures count the items that name an *old* ward as the asked unit (T1_membership, T4_address, T5_ward_successor);
T1_newname and the ward items of T3_existence are reported separately below, and the paper's figure, which counts all
ward-level types (T1, T3-T5) together, is given at the end of the list.

**Old wards named in a question (T1, T4, T5).**

- **1,659 of the 10,035 old wards (16.5%)** are the asked ward of at least one item:
  - T1: 927 distinct old wards;
  - T5: 427;
  - T4: 800.
  The three sets overlap.
- Per cell:

  | Cell | Old wards named / old wards in cell | Share |
  |---|---:|---:|
  | pc0_wc0 | 43 / 43 | all |
  | pc1_wc0 | 84 / 84 | all |
  | pc0_wc1 | 735 / 2,745 | 26.8% |
  | pc1_wc1 | 797 / 7,163 | 11.1% |

**Old provinces.**

- **53 of the 63 old provinces** have at least one old ward named in a T1, T4 or T5 item. Each of the three types on
  its own also covers the same 53.
- A covered province has between 1 and 100 named old wards (median 29).

**T1_newname.**

- These items name a *post-reform* ward, not an old one, so they are not counted above.
- Their 240 new wards were formed from 764 old wards in 61 old provinces. Only old Ninh Bình and old Đà Nẵng contribute
  none.
- Counting these old wards as well, 2,274 old wards (22.7%) and 61 old provinces are touched.

**All ward-level types together (the paper's count).**

- T3_existence has 125 items about an old ward (65 abolished, 60 unchanged). Added to the T1, T4 and T5 items above,
  ward-level items (T1, T3-T5) cover **1,708 old wards and 57 of the 63 old provinces**; this is the figure in the paper.
- The six provinces without any ward-level item are Ninh Bình, Quảng Trị, Khánh Hòa, Tây Ninh, Vĩnh Long and Đồng Tháp.

**Old provinces with no T1, T4 or T5 item naming one of their wards (10).**

Bắc Ninh, Hải Phòng, Hưng Yên, Ninh Bình, Quảng Trị, Đà Nẵng, Khánh Hòa, Tây Ninh, Vĩnh Long and Đồng Tháp. Four of them
(Bắc Ninh, Hải Phòng, Hưng Yên, Đà Nẵng) still have T3_existence items about their wards; the other six have no
ward-level item of any type.

**Why these 10 are missing.** The cause is the sampling rule in `src/viadmin/gen/items.py`:

- **Namesakes.** All ten are *namesake components* of merged provinces: the new province kept their name (e.g. old
  Bắc Ninh + Bắc Giang → new Bắc Ninh). There are 23 such namesake components.
- **Their wards fail the eligibility rule.** For their wards `province_changed = True` but
  `province_name_changed = False`, so the "province" part of the answer is literally the same before and after.
  - In the changed cell pc1_wc1, `Ctx.surface_ok` admits a ward only if its province name changed. `build_t1`,
    `build_t4` and `build_t5` sample the changed cells only from `surface_ok` wards.
  - So no namesake ward can be drawn from pc1_wc1. This is deliberate: such items could not tell an outdated model
    from an updated one (see `docs/data_report.md`, "surface_answer_changed").
- **Only the control cell remains.** A namesake ward can enter only through the control cell pc1_wc0, which is used in
  full.
  - 13 of the 23 namesake components have such unchanged wards (36 rows, flagged `cell_pure = false`).
  - The ten listed above have none: all their wards are in pc1_wc1.
- **The 11 kept provinces are covered.** They fall into pc=0, where the province rule does not apply.

The province-level types still cover these ten provinces:

- T6 and T3 cover all 63 old provinces;
- T2 covers all 34 new provinces;
- the probing extension `cue3sub_items` (400 T1 + 400 T5 wards) covers all 63 old provinces, because its kept stratum
  includes namesake components.

### 2.5 What data does each instance consist of? Is there a label?

Each benchmark item has the following fields:

- `question`, in Vietnamese and self-contained;
- `format` (mcq/short) and `choices`;
- the gold `answer` and `answer_aliases`;
- `old_answer`, the answer that would be correct under the pre-reform structure, or null when it did not change;
- `meta`: 2x2 flags, change type, codes, depth (surface/compose/deep), cue (none/date/reform), consistency group, twin
  id, diacritics flag, and context source.

Gold answers are derived from `ward_mapping.jsonl` (all rows two-lineage `high` confidence) and from
`provinces_new.merged_from` (NQ 202/2025/QH15). The T0 golds come from the official counts.

The probing sets use a simpler schema: `id, base, qtype, depth, absorbed, cue, question, gold[], old[]`.

### 2.6 Is any information missing?

- `provinces_new.capital` is null for every row, because the seat ward was not verified. `seat_old_province_code`
  records which old province hosts the new provincial centre.
- **Island districts.** The 5 island districts without a commune level became đặc khu and have no mapping row. They
  are Bạch Long Vĩ, Cồn Cỏ, Hoàng Sa, Lý Sơn and Côn Đảo (đặc khu codes 11948, 19742, 20333, 21548, 26732).
- **Non-ward areas.** Two non-ward areas merged into new wards have no row: the Kim Sơn coastal mudflat → Xã Kim Đông,
  and Trường bắn TB1 → Xã Biên Sơn.
- Pages not edited between 15/7/2025 and 1/1/2026 have no new-era Wikipedia passage. Template passages fill that gap.
- No short-answer format exists for T1, T1_newname, T2 or T3. T4 has no cue variants.

### 2.7 Relationships between instances

These links are explicit in the data:

- `meta.cue_group` links the three cue variants of an item;
- `meta.twin_id` links a T4 item to its diacritic-free twin;
- `meta.consistency_group` (the old province code) links a T6 item to the T1, T4 and T5 items of wards in that
  province;
- `base` links the variants of an item in the probing sets.

### 2.8 Recommended splits

ViAdminShift is an evaluation set with no training split.

- **Full benchmark.** Use the full 7,995 items, or the stratified 1,262-item subset `items_sub1k.jsonl` (its
  complement is `items_rest.jsonl`), drawn by `scripts/make_sub1k.py`: question groups (the cue and diacritic variants
  of one question) sampled per (`qtype`, `format`) stratum with `random.Random(13)`, whole strata of at most 40 groups,
  otherwise `max(40, round(0.125 × groups))` groups.
- **Probing experiments.** Use the sets in `data/eval_sets/`.
- **Agent items.** `agent_items.jsonl` has a `derive` / `eval` split (300 / 1,033 bases); `scripts/agent_date.py`
  reads its `sys0` rows and reports the 120 `paper80` units separately.

### 2.9 Errors, noise and redundancies

- **Gold labels.** An automated audit re-derived the gold and old answers of all 7,995 items from the tables with
  independently written code (the 12 T0 items were checked by hand) and found no wrong gold label. A sample of 60
  items was also read by hand, and 14 items were checked against the resolution texts. See `docs/gold_audit.md`.
- **Tables.**
  - 30 of 30 randomly drawn mapping rows (one per new province) were confirmed by hand against the resolutions, as were
    11 targeted checks.
  - Three wrong old-ward codes and one missing pair in the NSO table were corrected from the resolutions.
  - The resolution texts used are hoatieu.vn HTML reproductions, not the official scanned PDFs.
- **Known item issues** (`docs/benchmark_report.md`, `docs/gold_audit.md`):
  - In 22–33% of changed-cell T4/T5 items, the gold ward's bare name occurs in the question, usually as the old
    district name. This is flagged as `meta.gold_name_in_question`.
  - 19 T3 new-ward items do not separate stale from updated models.
  - Template passages carry synthetic timestamps (old 2025-06-01, new 2025-10-01).
  - Wikipedia excerpts are quoted as is, including small imprecisions.
- **Probing sets.** These exist in paired versions by design. The same base appears under several cues, prefixes or
  system prompts.

### 2.10 Is the dataset self-contained?

Yes. All passages, items and contexts are included; the canonical tables are rebuilt locally. `data/raw/<source>/` holds
each source's `SOURCE.md` (URL, licence, SHA-256 checksum) and licence texts; the source files themselves are not
redistributed but downloaded by `scripts/fetch_sources.sh`. The raw Wikipedia API cache (`data/raw/wiki_cache/`) is not
tracked in git.
Third-party raw files keep their own licences (see section 6).

### 2.11 Confidential data, offensive content, people

The data contains no confidential data and no offensive content.

The data contains names of administrative units, which are public, and encyclopedic text about provinces and
districts. It does not identify individuals. T4 addresses combine real unit names with a *synthetic* house number and
hamlet, so they refer to no real person. No sub-populations of people are identified.

## 3. Collection process

**How was the data acquired?** All data was downloaded from public sources. The sources
are:

- the NSO conversion table (xlsx, Last-Modified 2025-10-23);
- the pre-reform GSO registry lists and the post-reform commune list with resolution numbers, both through the
  vietnamadminunits repository at a pinned commit;
- the sapnhap.bando.com.vn composition texts, used for adjudication only;
- HTML reproductions of the 34 Standing Committee resolutions;
- two derivative mappings, used for agreement statistics only;
- Vietnamese Wikipedia revisions through the MediaWiki Action API.

Each source's URL, revision or commit, licence and checksum is in `data/raw/<source>/SOURCE.md`.

**What mechanisms were used?**

- Raw files were saved untouched and parsed as data only. No downloaded code was executed.
- Wikipedia was fetched with an identifying user agent, at most about 2 requests per second, with `maxlag=5`.
- Revisions were selected by date:
  - *old* = the last revision before 2025-06-12 (the date of NQ 202), stepping back past revisions that already show
    the post-reform state;
  - *new* = the last revision before 2026-01-01, kept only if it postdates 2025-07-15.

**Who was involved?** The two authors. No crowd workers were employed. The manual checks and the scorer-validation labels were done by the two authors; the manual-check list was prepared with an AI assistant.

**Over what timeframe?**

- The data describes the structure on 30 June 2025 (old) and 1 July 2025 (new).
- Wikipedia revisions range from 2023-05 (old era) to 2025-12 (new era).
- All sources were retrieved, and all API model calls made, after the reform took effect.

**Were ethical review processes conducted?** No; none was required. The data contains no personal data and no human
subjects, and the only annotators were the two authors.

## 4. Preprocessing, cleaning and labelling

These steps are documented in `docs/data_report.md` and `docs/SPEC.md`:

- **Text normalisation.** Unicode NFC. Apostrophes are normalised. Names are compared with `name_key`, which ignores
  tone-mark placement, case and apostrophes. Codes are zero-padded GSO/NSO strings.
- **Old ward spelling.** Where the GSO registry and the NSO table spell an old ward differently, the forming clause of
  the resolution decides. 176 old wards take the resolution/NSO spelling, and the other spelling is kept as
  `name_alt`. Two registry entries that were verified wrong were corrected.
- **Corrections.** Three wrong old-ward codes in the NSO table were fixed. One pair missing from the NSO table
  (Xã Hòa Thắng → Xã Hồng Thái, NQ 1671 k.46) was added from the resolution.
- **Labels.**
  - `change_type` (divided > merged > unchanged > renamed);
  - `province_changed` = the new province has more than one component;
  - `ward_changed` = `change_type` is not `unchanged`;
  - `surface_answer_changed`, `confidence` (lineages attesting the pair), and the remaining fields defined in SPEC.
- **Scoring.** Two schemes are used; both are released.
  - *Benchmark scorer* (`src/viadmin/eval/scorer.py`; every result under `results/bench/`, the retrieval, 2x2 and
    per-type tables). Labels: `correct` (gold, `answer_aliases` or alias table), `outdated` (the stored `old_answer`,
    or a legacy name of the gold such as Thừa Thiên Huế for Huế, and not the gold), `other_wrong`, `invalid` (no
    letter for MCQ; empty or abstention for short answers). Rules for short answers, in order: (1) the whole answer
    line equals a gold, old or legacy name (unit-type prefixes stripped, NFC, case-insensitive); (2) numeric golds
    (T0) match integers stated as the current value, with dates, resolution numbers and numbers in past clauses
    removed; (3) addresses (multi-segment golds) are matched segment by segment after past parentheticals are
    dropped and "X nay là Y" is resolved to Y, and a pre-reform three-level address is `outdated`, also on the T4
    items whose two-level address is unchanged (their `old_answer` is null; the scorer uses `meta.old_address`);
    (4) past-tense clauses and parentheticals ("(cũ)", "(trước đây là X)", ", trước đây thuộc X") are dropped, and
    the destination of a present-tense relation clause ("nay là", "đã sáp nhập vào", "thuộc", "sắp xếp/hợp nhất ...
    thành", "được đổi thành") is the answer, so "Tỉnh Hà Giang (từ 1/7/2025 sáp nhập vào tỉnh Tuyên Quang)" is
    `correct`; a negated clause ("không còn thuộc X") names nothing; a subject echoed before such a clause is not
    credited when the clause names another unit; (5) otherwise the first segment of the answer line decides, and
    the other name elsewhere in it makes the answer ambiguous (`other_wrong`); (6) a name found only inside a
    longer explanation is accepted when the other name is absent (`contained`), never when the output abstains.
    The answer line is the first line, except that an output which reasons first and then gives a bare name or
    address alone on its last line ("... Tuy nhiên, tôi không chắc chắn.\n\n**Xã Thạch Hà**") is scored on that
    last line, as an MCQ letter alone on the last line is; a first sentence that is a bare name or address is
    likewise scored alone, so a disclaimer after it ("Lưu ý: tôi không chắc chắn") does not void it. An
    abstention is a clause that says the model does not know ("tôi không chắc chắn", "không có thông tin",
    "không thể xác nhận", also after "Tuy nhiên," or ", nên"); a hedged commitment ("Không chắc, nhưng có lẽ là X")
    is scored as X. An unresolved co-mention ("X, Y", "X hoặc Y") is `other_wrong`; there is no "both" label.
    MCQ: the letter is read (bare, keyword, leading, trailing, or alone on the last line after an explanation),
    else the unique choice text the answer names (aliases expanded, relation clauses read, negated ones skipped);
    the `old_answer` letter or a legacy-name distractor is `outdated`. Items with `meta.has_diacritics == False` (the T4
    twins) take the diacritic-insensitive label as their main label; `label_nodiac` and `label_strict` are stored
    for every item. `match_detail` records which rule fired.
  - *Cue-ladder scorer* (`scripts/minitest.py label`, `scripts/analyze_cue.py label2`; every result under
    `results/minitest/` and `results/review/`). Labels: `correct` (new name only), `outdated` (old name only),
    `both` (both names, split post hoc into `both_new` / `both_old` by which name comes first in the output),
    `other`. Strict accuracy counts `correct` only; new-first = `correct` + `both_new`; old-only = `outdated`. The
    same dual answer is therefore `both_old` here and `correct` under the benchmark scorer. The two authors'
    blind labels of 200 cue-ladder answers (`docs/annotation/`) agree with this scorer at kappa 0.89-0.91 (0.88-0.89 on new-first / old-only / rest); most
    disagreements are `both_old` answers that the annotators read as committing to the new name (13 and 15 of 40).
- **Passages.**
  - Wikipedia leads were converted to plain text and cut at a sentence boundary at no more than 1,500 characters
    (`data/wiki/passages.jsonl`). The administrative section was extracted separately.
  - The benchmark contexts do not use these leads whole: each `wiki_excerpt` row of
    `data/benchmark/template_passages.jsonl` keeps the first sentence of the lead plus the sentence that states the
    merger (provinces, at most 600 characters) or the administrative-table line that lists the ward (at most 1,250
    characters), 254 characters on average. These excerpts are what the models saw in the retrieval conditions.
  - Passages whose lead does not name the entity were dropped.
  - New-era passages that still state the old structure are never used.
- **Raw data.** The source files are fetched into `data/raw/` by `scripts/fetch_sources.sh` (checksums in `SOURCE.md`;
  wiki cache git-ignored). The tables rebuild from them with
  `uv run python -m viadmin.data.build`, and the items with `uv run python -m viadmin.gen.generate` (byte-identical).
- **Software.** All processing code is in `src/viadmin/` (MIT).

## 5. Uses

**What has the dataset been used for?** The accompanying paper uses it for:

- a pre-specified cue ladder (no cue / date / reform) over 63 old provinces and sampled wards, run on local and API
  models;
- date-placement experiments: system prompt vs question, earlier turn, tool result, tool offer;
- frame and wording controls;
- a chat-template ablation and a quantization ladder;
- closed-book and retrieval conditions on the benchmark items: new-only and mixed old and new passages, dated
  passages.

**Other possible uses.**

- temporal knowledge and knowledge-update evaluation of language models;
- conflict resolution in retrieval-augmented generation;
- research on Vietnamese address normalisation (the mapping table).

**Is there anything about the composition or collection that might affect future uses?**

- **Fixed date.** The data is fixed to 1 July 2025.
  - Between 30 April and 20 September 2026, Đồng Nai, Quảng Ninh and Bắc Ninh became centrally-run cities with the
    same name and territory (Resolutions 30, 36 and 39/2026/QH16), and 10 xã of Đồng Nai and 12 of Bắc Ninh became
    phường under the same names (Resolutions 237 and 388/NQ-UBTVQH16).
  - The scorers ignore the "Tỉnh" / "Thành phố" (and "xã" / "phường") prefixes and MCQ options differ by name, so only
    T3 items, which name the unit type, are affected: `T3-prov-22`, `T3-prov-27`, `T3-prov-75` and `T3-dist-256` are
    correct only at the version date. No ward-level item names one of the 22 communes that became phường. MCQ choices
    still print the 1/7/2025 prefix.
  - Further changes to names or boundaries would make some gold answers stale; check the data version.
- **Cue = date.** The cue says "Tính đến tháng 10/2026" while the gold describes 1/7/2025.
- **Biased coverage.** Ward-level coverage is stratified, not uniform (section 2.4). Ten old provinces have no T1, T4
  or T5 item naming one of their wards, and six have no ward-level item of any type.

**Tasks for which the dataset should not be used.**
ViAdminShift is not an authoritative address converter and must not be used for administrative or legal purposes.
Consult official sources instead.

## 6. Distribution

**How will the dataset be distributed?**
In this repository: https://github.com/LLaammTTeerr/ViAdminShift, with a versioned release per data version. Each release is archived on Zenodo:
v1.0 has DOI [10.5281/zenodo.23473404](https://doi.org/10.5281/zenodo.23473404); the DOI [10.5281/zenodo.23473403](https://doi.org/10.5281/zenodo.23473403) always resolves to the latest version.

**When?** Release v1.0, with the paper.

**Licence.**

- **Data:** CC BY-SA 4.0. Share-alike is required by the Wikipedia-derived passages and applied to all data files,
  to the model predictions and analysis outputs in `results/` and to the annotations in `docs/annotation/` (see
  `data/LICENSE.md`). Model outputs in `results/` and the annotations in `docs/annotation/` are released under CC BY-SA 4.0, except the
  Tiny Aya outputs (`results/bench/tiny-aya-global-q8_0/`, `results/minitest/gpu/preds_*_tiny-aya-global.jsonl`), which
  are released under CC BY-NC-SA 4.0 because the model's licence (CC BY-NC 4.0) restricts commercial use. Outputs of
  hosted models are also released under CC BY-SA 4.0; users must still follow each provider's terms.
- **Code:** MIT (see `LICENSE`).

**Third-party restrictions.** The files in `data/raw/` keep their own terms. No source file that contains NSO data or data
from a government portal is redistributed; `scripts/fetch_sources.sh` downloads each of them:

| Source | Terms |
|---|---|
| NSO table | official statistical classification, no explicit licence; not redistributed (with its VietnamProvinces copy and the derived canonical tables); `scripts/fetch_sources.sh` downloads it and the build recreates the tables byte for byte |
| resolutions | legal texts, not copyrighted; the HTML reproductions are from hoatieu.vn |
| vietnamadminunits | MIT; its data files (official lists, portal scrapes, tables built from them) are not redistributed (downloaded by `scripts/fetch_sources.sh`) |
| undertheseanlp/address | Apache-2.0; `mapping.json` copies the vietnamadminunits tables, so not redistributed (downloaded by `scripts/fetch_sources.sh`) |
| vietaddr | GPL-3.0-or-later; its data files are generated from the NSO table, so not redistributed (downloaded by `scripts/fetch_sources.sh`) |
| VietnamProvinces | GPL-3.0-or-later; a copy of the NSO table, not redistributed |

**Export controls or regulatory restrictions?** None known. [authors to confirm]

## 7. Maintenance

**Who maintains the dataset? How can they be contacted?** The authors, Phan Binh Nguyen Lam and Nguyen Thai Anh, through the issue tracker of
the repository.

**Is there an erratum?** Data corrections made during construction are logged in
`data/processed/crosscheck_issues.jsonl` (written by the build) and `docs/data_report.md`. Public errata channel: the issue tracker of the
repository.

**Will the dataset be updated?** Yes, through versioned releases named after the date of the structure they describe.

- **When the map changes.** If the administrative map changes in names, membership or boundaries, the plan is a new
  version with:
  - rebuilt tables from the then-current official conversion table and resolutions;
  - regenerated items, with the previous version as the "old" structure;
  - a changelog.
- **Changes that touch neither names nor boundaries** (such as the 2026 city upgrades) are documented without a new
  version.

**Will older versions remain available?** Yes. Released versions stay available unchanged, so published results
remain reproducible. Hosted model outputs can change behind a fixed identifier, so the released prediction files,
not new API calls, are the reference for the paper's numbers.

**Can others contribute?** Yes. Corrections and additions are welcome as issues or pull requests in the
repository; accepted data changes go into the next versioned release, with a changelog entry.
