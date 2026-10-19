# ViAdminShift: benchmark report (items + RAG contexts)

Built by `uv run python -m viadmin.gen.generate` (code in `src/viadmin/gen/`), validated by
`uv run python -m viadmin.gen.validate` (0 problems) and the eval linter
`uv run python -m viadmin.eval.validate data/benchmark/items.jsonl` (0 problems), tested by
`uv run pytest tests/test_gen_benchmark.py tests/test_gen_components.py` (20 tests; full suite 275 passed).
Count tables below are printed by `uv run python -m viadmin.gen.report`.

## 1. Outputs

| file | content |
|---|---|
| `data/benchmark/items.jsonl` | 7,995 items (SPEC schema + meta extensions, see SPEC "Benchmark items — details fixed by the generator") |
| `data/benchmark/contexts.jsonl` | 23,985 rows = 3 conditions (none/new/mixed) × every item |
| `data/benchmark/template_passages.jsonl` | 2,281 passages: 1,002 wiki excerpts (`wikix_…`, `source="wiki_excerpt"`) + 1,279 templates (`tpl_…`, `source="template"`) |
| `data/benchmark/build_stats.json` | counts + sha256 of the three files |

Re-runs are byte-identical (seed 13; every random choice uses `random.Random(f"13:{key}")`;
`test_deterministic_rebuild` builds twice and compares with the committed files).
sha256: items `475032a8…`, template_passages `310702e8…`, contexts `ede5186c…` (full values in build_stats.json).

## 2. Design summary

- **Gold labels** come only from `data/processed/ward_mapping.jsonl` rows with `confidence == "high"` (all 10,566 rows
  are high), `provinces_new.merged_from` (NQ 202/2025/QH15, checked in `docs/data_report.md` §3) and, for T0, the counts in
  `data/processed` plus NQ 202/203/2025/QH15 (same facts as the verified `headline_probe.jsonl`).
  The validator re-derives every ward-level gold from the mapping.
- **Question types** (all cue=none wording obeys the SPEC rule: no "trước đây / cũ / mới / nay / sắp xếp" outside the
  entity names; date/reform variants add only the SPEC prefixes):
  - `T0_headline` (surface): 12 items (7 MCQ, 5 numeric short): 34 vs 63 provinces, 2 vs 3 levels, district level
    abolished, 3,321 vs 10,035 communes, commune types (xã/phường/đặc khu vs …/thị trấn), 13 đặc khu.
  - `T6_reverse` (surface): all 63 old provinces × {MCQ, short} × 3 cues. Old answer = the old province when its name
    disappeared (29 absorbed provinces); 34 kept/namesake provinces are controls (old_answer null).
  - `T2_composition` (surface): 34 MCQ "Tỉnh Y hiện nay được hình thành từ (những) đơn vị hành chính cấp tỉnh nào trước
    đây?"; old answer (23 merged) = "Chỉ có tỉnh Y (giữ nguyên…)"; other distractors swap/add/drop a neighbouring old
    province.
  - `T1_membership` (compose): 927 old wards × 3 cues, MCQ. Old ward named with district + old province (always, so no
    ambiguity). Choices: new province (gold), the old province (when its name changed = old_answer), nearest other new
    provinces.
  - `T1_newname` (deep): 240 new wards × 3 cues, MCQ; bare name unique among new wards; 120 with an identifiable outdated
    answer (the name existed before as a ward/district of an absorbed component province).
  - `T5_ward_successor` (deep): 427 old wards × {MCQ, short} × 3 cues: "Địa bàn xã X, huyện D, tỉnh P thuộc đơn vị hành
    chính cấp xã nào?" Gold = new ward; old answer = X itself when its bare name changed.
  - `T4_address` (deep): 800 old addresses (fake but plausible house number + thôn/ấp/tổ dân phố/khu phố) → gold
    "Xã/Phường W, Tỉnh/Thành phố G"; `meta.gold_ward`/`gold_province` for component scoring; 400 no-diacritic twins.
  - `T3_existence`: 308 4-way MCQ (exists as cấp tỉnh / cấp huyện / cấp xã / no longer exists), 154 exist / 154 not.
- **2x2 cells.** Control cells used in full (pc0_wc0 43, pc1_wc0 84 old wards). In the changed cells an old ward is
  eligible only if the asked surface changed (province name changed for pc1; the BARE ward name changed for wc1 — a
  unit-type-only change "Thị trấn X → Xã X" is not a change for the scorer). Eligible old wards: pc0_wc1 2,163 of 2,745;
  pc1_wc1 3,098 of 7,163. The 36 namesake rows of pc1_wc0 (e.g. an unchanged ward of old Tuyên Quang, now in new Tuyên
  Quang) have `surface_answer_changed=false`, `cell_pure=false`, `old_answer=null`: filter them for a pure pc1_wc0 cell.
- **Exclusions (documented):** divided wards (441 old wards) from T4/T5 and T3 ward items (no unique new ward; T1 keeps
  them, the province is unique); for T5 the 264 old wards whose bare name is the name of another current ward of the
  same new province; T3 districts whose territory became a đặc khu; T3 "abolished" names that still exist anywhere among
  the 3,321 new wards; T1_newname names whose old namesakes lie in several old provinces or outside the gold's
  components; island đặc khu without mapping rows.
- **Leakage.** A changed gold component never occurs (with its unit prefix, as a whole segment) in the question; checked
  for every item. Not counted as leakage: a gold that is the beginning of a longer old name ("Xã Định Thành" vs old "xã
  Định Thành A"), and the gold ward's bare name occurring as the old DISTRICT name (new ward named after the district,
  e.g. "xã Dân Quyền, huyện Triệu Sơn" → "Xã Triệu Sơn"). The latter is a real-world regularity, kept and flagged
  `meta.gold_name_in_question` (rates in section 3); analyses can split on it.

## 3. Counts
### Items per qtype x format x cue

| qtype | format | cue | items |
|---|---:|---:|---:|
| T0_headline | mcq | - | 7 |
| T0_headline | short | - | 5 |
| T1_membership | mcq | date | 927 |
| T1_membership | mcq | none | 927 |
| T1_membership | mcq | reform | 927 |
| T1_newname | mcq | date | 240 |
| T1_newname | mcq | none | 240 |
| T1_newname | mcq | reform | 240 |
| T2_composition | mcq | - | 34 |
| T3_existence | mcq | - | 308 |
| T4_address | short | - | 1200 |
| T5_ward_successor | mcq | date | 427 |
| T5_ward_successor | mcq | none | 427 |
| T5_ward_successor | mcq | reform | 427 |
| T5_ward_successor | short | date | 427 |
| T5_ward_successor | short | none | 427 |
| T5_ward_successor | short | reform | 427 |
| T6_reverse | mcq | date | 63 |
| T6_reverse | mcq | none | 63 |
| T6_reverse | mcq | reform | 63 |
| T6_reverse | short | date | 63 |
| T6_reverse | short | none | 63 |
| T6_reverse | short | reform | 63 | 

Total items: 7995

### Items per qtype x 2x2 cell x format (all cues and twins counted)

| qtype | format | pc0_wc0 | pc0_wc1 | pc1_wc0 | pc1_wc1 | na |
|---|---:|---:|---:|---:|---:|---:|
| T0_headline | mcq | 0 | 0 | 0 | 0 | 7 |
| T0_headline | short | 0 | 0 | 0 | 0 | 5 |
| T1_membership | mcq | 129 | 1200 | 252 | 1200 | 0 |
| T1_newname | mcq | 9 | 171 | 12 | 528 | 0 |
| T2_composition | mcq | 0 | 0 | 0 | 0 | 34 |
| T3_existence | mcq | 30 | 51 | 31 | 73 | 123 |
| T4_address | short | 65 | 505 | 126 | 504 | 0 |
| T5_ward_successor | mcq | 129 | 450 | 252 | 450 | 0 |
| T5_ward_successor | short | 129 | 450 | 252 | 450 | 0 |
| T6_reverse | mcq | 0 | 0 | 0 | 0 | 189 |
| T6_reverse | short | 0 | 0 | 0 | 0 | 189 | 

### Base items (cue=none, diacritised) per cell, with old_answer set / surface changed

| qtype | cell | base items | old_answer set | surface_answer_changed |
|---|---:|---:|---:|---:|
| T0_headline | na | 12 | 12 | 0 |
| T1_membership | pc0_wc0 | 43 | 0 | 0 |
| T1_membership | pc0_wc1 | 400 | 0 | 0 |
| T1_membership | pc1_wc0 | 84 | 48 | 48 |
| T1_membership | pc1_wc1 | 400 | 400 | 400 |
| T1_newname | pc0_wc0 | 3 | 0 | 0 |
| T1_newname | pc0_wc1 | 57 | 0 | 0 |
| T1_newname | pc1_wc0 | 4 | 3 | 3 |
| T1_newname | pc1_wc1 | 176 | 117 | 117 |
| T2_composition | na | 34 | 23 | 0 |
| T3_existence | pc0_wc0 | 30 | 0 | 0 |
| T3_existence | pc0_wc1 | 51 | 51 | 32 |
| T3_existence | pc1_wc0 | 31 | 1 | 16 |
| T3_existence | pc1_wc1 | 73 | 73 | 33 |
| T3_existence | na | 123 | 89 | 0 |
| T4_address | pc0_wc0 | 43 | 0 | 0 |
| T4_address | pc0_wc1 | 337 | 337 | 337 |
| T4_address | pc1_wc0 | 84 | 48 | 48 |
| T4_address | pc1_wc1 | 336 | 336 | 336 |
| T5_ward_successor | pc0_wc0 | 86 | 0 | 0 |
| T5_ward_successor | pc0_wc1 | 300 | 300 | 300 |
| T5_ward_successor | pc1_wc0 | 168 | 0 | 0 |
| T5_ward_successor | pc1_wc1 | 300 | 300 | 300 |
| T6_reverse | na | 126 | 58 | 58 | 

### T3_existence by entity kind and gold

| entity_kind | gold (P/D/W=exists at level, N=no) | old_answer set | n |
|---|---:|---:|---:|
| abolished_ward | N | True | 65 |
| district | N | True | 60 |
| new_ward | W | True | 60 |
| province | N | True | 29 |
| province | P | False | 34 |
| unchanged_ward | W | False | 60 | 

T3 exists / not: 154 / 154

### T1_newname categories (base items)

| category | cell | n |
|---|---:|---:|
| new name | pc0_wc1 | 6 |
| new name | pc1_wc1 | 23 |
| reused, old answer identifiable | pc1_wc0 | 3 |
| reused, old answer identifiable | pc1_wc1 | 117 |
| reused, same province name | pc0_wc0 | 3 |
| reused, same province name | pc0_wc1 | 51 |
| reused, same province name | pc1_wc0 | 1 |
| reused, same province name | pc1_wc1 | 36 | 

### T4 twins (no-diacritic copies) per cell

| cell | twins |
|---|---:|
| pc0_wc0 | 22 |
| pc0_wc1 | 168 |
| pc1_wc0 | 42 |
| pc1_wc1 | 168 | 

### Gold ward name occurs in the question (new ward named after the old district etc.)

| qtype | cell | base items | gold name in question | rate |
|---|---:|---:|---:|---:|
| T4_address | pc0_wc0 | 43 | 43 | 100.0% |
| T4_address | pc0_wc1 | 337 | 75 | 22.3% |
| T4_address | pc1_wc0 | 84 | 84 | 100.0% |
| T4_address | pc1_wc1 | 336 | 110 | 32.7% |
| T5_ward_successor | pc0_wc0 | 43 | 43 | 100.0% |
| T5_ward_successor | pc0_wc1 | 150 | 45 | 30.0% |
| T5_ward_successor | pc1_wc0 | 84 | 84 | 100.0% |
| T5_ward_successor | pc1_wc1 | 150 | 38 | 25.3% | 

### Context sources (passage of the `new` condition; old passage of `mixed`)

| qtype | new: wiki | new: template | mixed old: wiki | mixed old: template |
|---|---:|---:|---:|---:|
| T0_headline | 0 | 12 | 0 | 12 |
| T1_membership | 690 | 2091 | 2364 | 417 |
| T1_newname | 717 | 3 | 660 | 60 |
| T2_composition | 5 | 29 | 34 | 0 |
| T3_existence | 190 | 118 | 283 | 25 |
| T4_address | 0 | 1200 | 1027 | 173 |
| T5_ward_successor | 0 | 2562 | 2136 | 426 |
| T6_reverse | 90 | 288 | 378 | 0 | 

| passage source | era | entity_set | n |
|---|---:|---:|---:|
| template | new | new_province | 29 |
| template | new | new_ward | 919 |
| template | new | old_district | 5 |
| template | new | old_province | 48 |
| template | new | None | 1 |
| template | old | old_district | 10 |
| template | old | old_ward | 266 |
| template | old | None | 1 |
| wiki_excerpt | new | new_province | 357 |
| wiki_excerpt | new | old_district | 55 |
| wiki_excerpt | new | old_province | 15 |
| wiki_excerpt | old | new_province | 34 |
| wiki_excerpt | old | old_district | 478 |
| wiki_excerpt | old | old_province | 63 | 

Context length (chars): new mean 368 max 1142; mixed mean 652 max 1495

Mixed order: old passage first in 4093, new first in 3902 rows

### MCQ answer letters per qtype

| qtype | A | B | C | D |
|---|---:|---:|---:|---:|
| T0_headline | 1 | 2 | 2 | 2 |
| T1_membership | 741 | 666 | 660 | 714 |
| T1_newname | 198 | 165 | 183 | 174 |
| T2_composition | 7 | 8 | 8 | 11 |
| T3_existence | 80 | 81 | 80 | 67 |
| T5_ward_successor | 372 | 291 | 348 | 270 |
| T6_reverse | 33 | 45 | 63 | 48 | 

consistency groups: 63 (with T6: 63, with T6 and >=1 other item: 53)


## 4. Examples (cue = none unless stated)

**T0_headline (MCQ).** "Chính quyền địa phương ở Việt Nam hiện nay gồm những cấp nào?" A. Cấp tỉnh và cấp xã (gold)
· B. Cấp huyện và cấp xã · C. Cấp tỉnh, cấp huyện và cấp xã (old) · D. Cấp tỉnh và cấp huyện.

**T0_headline (short).** "Cả nước hiện có tổng cộng bao nhiêu tỉnh và thành phố trực thuộc trung ương?" gold `34`, old `63`.

**T6_reverse (MCQ, 3 cues).**
- none: "Địa bàn tỉnh Bà Rịa - Vũng Tàu thuộc đơn vị hành chính cấp tỉnh nào?"
- date: "Tính đến tháng 10/2026, địa bàn tỉnh Bà Rịa - Vũng Tàu thuộc đơn vị hành chính cấp tỉnh nào?"
- reform: "Sau đợt sắp xếp đơn vị hành chính năm 2025, địa bàn tỉnh Bà Rịa - Vũng Tàu thuộc đơn vị hành chính cấp tỉnh nào?"
- A. Tỉnh Đồng Nai · B. Thành phố Hồ Chí Minh (gold) · C. Tỉnh Bà Rịa - Vũng Tàu (old) · D. Tỉnh Vĩnh Long.

**T6_reverse (short).** "Địa bàn tỉnh Long An thuộc đơn vị hành chính cấp tỉnh nào?" gold `Tỉnh Tây Ninh`, old `Tỉnh Long An`.

**T2_composition.** "Tỉnh Khánh Hòa hiện nay được hình thành từ (những) đơn vị hành chính cấp tỉnh nào trước đây?"
A. Tỉnh Khánh Hòa và tỉnh Ninh Thuận (gold) · B. Chỉ có tỉnh Khánh Hòa (giữ nguyên, không sáp nhập với tỉnh, thành phố
nào) (old) · C. Tỉnh Khánh Hòa và tỉnh Phú Yên · D. Tỉnh Khánh Hòa, tỉnh Ninh Thuận và tỉnh Đắk Lắk.

**T1_membership.** "Xã Tân Tú, huyện Bạch Thông, tỉnh Bắc Kạn thuộc tỉnh/thành phố nào?" A. Tỉnh Tuyên Quang · B. Tỉnh
Bắc Kạn (old) · C. Tỉnh Thái Nguyên (gold) · D. Tỉnh Cao Bằng.

**T1_newname.** "Phường Gò Công thuộc tỉnh/thành phố nào?" A. Tỉnh Vĩnh Long · B. Tỉnh Tiền Giang (old: thị xã Gò Công
was in Tiền Giang) · C. Tỉnh Đồng Tháp (gold) · D. Tỉnh Tây Ninh.

**T5_ward_successor (MCQ).** "Địa bàn phường Na Lay, thị xã Mường Lay, tỉnh Điện Biên thuộc đơn vị hành chính cấp xã
nào?" A. Phường Mường Lay (gold) · B. Phường Na Lay (old) · C. Xã Mường Tùng · D. Xã Pa Ham.

**T5_ward_successor (short).** "Địa bàn xã Dân Quyền, huyện Triệu Sơn, tỉnh Thanh Hóa thuộc đơn vị hành chính cấp xã
nào?" gold `Xã Triệu Sơn`, old `Xã Dân Quyền` (`gold_name_in_question=true`: the new commune is named after the district).

**T4_address.** "Địa chỉ cũ: Số 125, thôn 7, xã Đông Yên, huyện Quốc Oai, thành phố Hà Nội. Địa chỉ này hiện nay được
viết theo đơn vị hành chính hai cấp (cấp xã, cấp tỉnh) như thế nào?" gold `Xã Phú Cát, Thành phố Hà Nội`, old
`Xã Đông Yên, Huyện Quốc Oai, Thành phố Hà Nội`. Twin `T4-09952-nd`: "Địa chỉ cũ: So 125, thon 7, xa Dong Yen, huyen
Quoc Oai, thanh pho Ha Noi. …" (same gold).

**T3_existence.** "Hiện nay, xã Tạ An Khương Nam (huyện Đầm Dơi, tỉnh Cà Mau) có phải là một đơn vị hành chính đang tồn
tại không? Nếu có, đó là đơn vị hành chính cấp nào?" A. Không, hiện không còn (hoặc không phải) là một đơn vị hành
chính (gold) · B. Có, là đơn vị hành chính cấp xã (old) · C. … cấp tỉnh · D. … cấp huyện.

**Contexts (rag_mixed of T5-15706-short).**
- [new, template] "Xã Triệu Sơn là một xã thuộc tỉnh Thanh Hóa, Việt Nam. Theo Nghị quyết số 1686/NQ-UBTVQH15 ngày 16
  tháng 6 năm 2025 của Ủy ban Thường vụ Quốc hội, xã Triệu Sơn được thành lập trên cơ sở sắp xếp toàn bộ diện tích tự
  nhiên, quy mô dân số của thị trấn Triệu Sơn, xã Minh Sơn, xã Dân Lực, xã Dân Lý và xã Dân Quyền (thuộc huyện Triệu
  Sơn, tỉnh Thanh Hóa). Xã Triệu Sơn chính thức hoạt động từ ngày 1 tháng 7 năm 2025."
- [old, wiki excerpt of "Triệu Sơn" rev. before 2025-06-12] "Triệu Sơn là một huyện thuộc tỉnh Thanh Hóa, Việt Nam. /
  Huyện Triệu Sơn có 32 đơn vị hành chính cấp xã trực thuộc, bao gồm 2 thị trấn: Triệu Sơn (huyện lỵ), Nưa và 30 xã: …,
  Dân Quyền, …"

## 5. RAG contexts

- **Per item:** `none` → no passage; `new` → one era-new passage that contains the gold names (string match,
  re-verified by the validator; numbered wards matched with their prefix "Phường 4"); `mixed` → one era-old passage +
  the same new passage, order shuffled per cue group (old first in 4,093 rows, new first in 3,902). The old passage
  contains the old answer (old province / old ward) whenever it changed. Every old passage is older than its partner
  (`+recency`). Max context 1,495 chars (mixed), mean 652.
- **Wiki first, template otherwise.** Which passage is used per qtype:
  - T6 / T3 province / T1 (absorbed province): the new-era lead of the OLD province, excerpted to its first sentence + the
    sentence that names the gold province together with a 2025 merger verb (sáp nhập / hợp nhất / giải thể). 15 of the
    29 absorbed provinces have such a sentence; all 15 (plus 5 new-province composition sentences used by T2) were read
    by hand and state the right merger. One false positive of an earlier, looser rule (Bạc Liêu "nằm trên bán đảo Cà
    Mau") was found in review and the rule was tightened; now the Bạc Liêu excerpt carries the actual merger sentence.
    Kept/namesake provinces always use a template (their new-era leads do not state the (non-)merger).
  - T1_newname / T3 new & unchanged wards: the new-province admin table (end-2025 revision): summary line, table title,
    header, section line ("Phường (20)") + the ward's row; the section's unit type must equal `wards_new.type`.
    717/720 T1_newname items use wiki.
  - T4 / T5 / T3 abolished ward "new": **always template** — no Wikipedia text states the old-ward → new-ward
    composition (new-province tables list only new names, new-era district pages still list the old communes). The
    template is generated from the mapping rows (full/partial parts, grouped by old district, resolution number from
    `wards_new.resolution`; the extra non-ward areas of Xã Kim Đông and Xã Biên Sơn are mentioned).
  - Old passages for ward items: the old-era district page excerpt (lead sentence naming the province + the admin line
    listing the ward), only from pages with `stated_count_matches_gold != false`, no stale names
    (`admin_names_not_in_gold` empty) and no reform mention; numbered wards (Phường 1, Phường IV) always use templates.
  - T3 districts "new": the new-era district lead when it calls the district former ("là một huyện cũ…") and names its
    province (55 pages), otherwise a template citing NQ 203/2025/QH15.
  - T0: one national template per era.

## 6. Changes outside src/viadmin/gen (for the eval owner)

- `src/viadmin/eval/validate.py`: `QTYPES` += `T1_newname`, `T5_ward_successor` (SPEC depth addendum).
- `src/viadmin/eval/scorer.py`: new `score_address_components(item, raw)`; `ScoreResult.components` (new last field,
  default None, so existing constructors are unaffected) set by `score_short` for items with `meta.gold_ward` +
  `meta.gold_province` (all T4 items). Labels per component: correct / outdated / other_wrong / invalid.
- `src/viadmin/eval/runner.py` (`score_row`): copies `components` into prediction rows when present.
- `src/viadmin/eval/metrics.py` (`stats`): adds a `components` block (ward / province accuracy, outdated rate, labels,
  `both_correct_rate`) to any stats block whose rows carry `components`; nothing changes for other rows.
- Tests: `tests/test_gen_components.py` (component scoring + metrics), `tests/test_gen_benchmark.py`. All 255 pre-existing
  tests still pass.

## 7. Known issues and uncertainties

- **Correctness rests on `data/processed`.** Golds are copied from the mapping (30/30 hand-checked rows, see `docs/data_report.md` §7;
  all rows two-lineage "high"); individual T1/T4/T5 golds were not re-verified against the resolutions in this step. Template
  passages restate the same table facts, so a table error would appear consistently in gold and context.
- **Template wording asserts legal details** (NQ 202/2025/QH15 of 12/6/2025; ward resolutions NQ 1654–1687/NQ-UBTVQH15 of
  16/6/2025 by number from `wards_new.resolution`; NQ 203/2025/QH15 amending the Constitution for the two-level model;
  "toàn bộ / một phần diện tích tự nhiên, quy mô dân số" from `is_partial`). The resolution titles are not quoted
  verbatim, and the effective date is stated as 1/7/2025 for all units.
- **Template timestamps are synthetic** (old 2025-06-01, new 2025-10-01); `+date` shows them to the model.
- **Wiki excerpts quote Wikipedia as is**, including imprecisions (Đắk Lắk / Lâm Đồng leads say the merger happened
  "kể từ ngày 12 tháng 6 năm 2025", the resolution date, not the 1/7/2025 effective date).
- **`cue=date` says "Tính đến tháng 10/2026"** while the gold is the 1/7/2025 structure. Between 30 April and 20
  September 2026 Đồng Nai, Quảng Ninh and Bắc Ninh became centrally-run cities with the same name and territory
  (Resolutions 30, 36 and 39/2026/QH16), and 10 xã of Đồng Nai and 12 of Bắc Ninh became phường under the same names
  (Resolutions 237 and 388/NQ-UBTVQH16). Names do not change, MCQ choices differ by name, and the scorer ignores the
  tỉnh/thành phố and xã/phường prefixes, so only T3 items, which name the unit type, are affected: `T3-prov-22`,
  `T3-prov-27`, `T3-prov-75` and `T3-dist-256` are correct only at the version date. A model answering "Thành phố
  Đồng Nai" is scored correct, and "Tỉnh Đồng Nai" in a choice may look outdated to a 2026-aware model.
- **Hint in the question.** In the changed cells 22–33% of T4/T5 golds share the bare name of the old district in the
  question (`meta.gold_name_in_question`); 100% in the control cells (the ward is unchanged). Report results split on it.
- **T3 districts with a namesake ward.** For 52 of the 60 T3 district items a current ward carries the district's name
  (`meta.name_survives_as_ward`), e.g. "huyện Tứ Kỳ (tỉnh Hải Dương)" is gone but "xã Tứ Kỳ" exists. A model answering
  "Có, là đơn vị hành chính cấp xã" is labelled `other_wrong`, not `outdated`; split on the flag in the analysis.
- **Consistency metric.** `metrics.consistency` pools all cue variants and both T6 formats into "surface" (a group is
  surface-correct only if all 6 T6 items are right) and counts T1/T5/T4 items of every cue as "deep". Filter rows by
  `meta.cue` (and T6 format) before calling it, or extend the metric. 10 of the 63 groups (namesake provinces) have no
  deep items with an identifiable change.
- **Control cell size.** T1_newname has only 3 pc0_wc0 and 4 pc1_wc0 base items (few unchanged wards have a unique name);
  use T1_membership / T5 / T4 for control-cell comparisons.
- **T1_membership "new" context is province-level** (the merger statement), not the ward-level template: the model must
  compose "ward in old province P" (given in the question) with "P → G" (passage). This is intended (compose level) but
  differs from T4/T5, whose new context states the ward-level fact.
- **T0 distractor numbers** (28, 45, 705, 4.528, 6.714) are arbitrary plausible values; 28 is the post-reform number of
  *tỉnh* (without the 6 cities), so it is a deliberate near-miss.
- **Not done:** no short-format T1_membership / T1_newname items (MCQ only, as specified "MCQ primary"); T4 has no cue
  variants (SPEC lists cues only for T6/T1/T1_newname/T5).
