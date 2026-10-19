# Gold-label audit — ViAdminShift benchmark

Automated audit with Claude, as disclosed in the paper (Quality control (iii)). Scope: `data/benchmark/items.jsonl` (7,995 items),
`data/benchmark/contexts.jsonl` (23,985 rows), scorer in `src/viadmin/eval/`. Nothing under `data/` or
`src/viadmin/gen/` was modified; audit scripts lived in a scratch directory only.

**Bottom line.** No wrong gold answer was found. Every item whose gold can be derived from the processed
tables (7,983 of 7,995) re-derives exactly. The 12 T0 items were checked by hand. All 5,320 MCQ items pass the
structural checks, and the mixed contexts pass the must_contain check. The remaining risks are not wrong labels:
(i) the benchmark's correctness rests on `ward_mapping.jsonl`, and the web spot check confirmed 14/14 mappings (section 2);
(ii) 849 changed-answer T4/T5 items have the gold ward name inside the question;
(iii) the scorer labels 121 T4 items' stale 3-level answers `other_wrong`, not `outdated`.

## 0. Method

Independent re-derivation code (`derive.py`, scratch) reads only `provinces_old/new`, `wards_old/new`,
`districts_old` and `ward_mapping` and takes unit codes from the item **id**, never from `meta`.
- old→new province = inverse of `provinces_new.merged_from`.
- T6 gold = new province of the old province. old_answer = old name if it differs.
- T1 gold = `new_province_code` of every mapping row of the old ward (all rows must agree). The derivation also asserts that this equals the province-level merge.
- T1_newname gold = `wards_new[code].province_code`. It also asserts that the bare name is unique nationwide.
- T5 / T4 gold = the single non-partial mapping row's new ward (+ new province for T4). It cross-checks `wards_new` name and province.
- T3: province exists iff its bare name is a new province; district → "Không"; new ward → "cấp xã"; old/kept ward exists iff a same-name ward exists in its new province. Also confirmed: all 60 `T3-keepw` wards have mapping `change_type=unchanged`, and all 65 `T3-oldw` wards are `merged`.
- T2: the set of old provinces named in the gold choice must equal `merged_from`.

## 1. Re-derivation of gold and old_answer

| qtype | items re-derived | gold mismatches | old_answer differences (all explained, see below) |
|---|---:|---:|---:|
| T1_membership | 2,781 (all) | 0 | 0 |
| T1_newname | 720 (all) | 0 | 0 (old namesake province re-derived separately: 240/240 `__none` agree) |
| T5_ward_successor | 2,562 (all) | 0 | 0 |
| T4_address | 1,200 (all) | 0 | 121 (design convention) |
| T6_reverse | 378 (all) | 0 | 0 |
| T3_existence | 308 (all) | 0 | 53 (34 convention + 19 debatable) |
| T2_composition | 34 (all) | 0 | 0 |
| T0_headline | 12 (by hand) | 0 | 0 |
| **Total** | **7,995** | **0** | 174 |

The full run was over every item, not only a sample. In addition, a **stratified sample of 60 (seed 4242:
8 T1, 8 T1N, 8 T4, 8 T5, 7 T6, 7 T3, 7 T2, 7 T0)** was printed side by side (question / gold / old / derived) and
read by hand: 0 errors. The sample ids are listed in section 1.1 below.

Other consistency checks over all 6,543 T1/T4/T5 items:
- The ward, district and province named in the question match `wards_old` / `districts_old` / `provinces_old` for the id's ward code: 0 failures.
- Each T4 `-nd` twin has the same gold as its diacritised base: 0 failures.
- No T1/T4/T5 item uses a ward that changes province independently of its province merge. `ward_mapping` has 0 such rows, and the Kim Đông / Biên Sơn non-ward areas (SPEC l.129–131) have no rows and no items.

Explained old_answer differences (not errors):
- **T4, 121 items** (60 wards + twins, e.g. `T4-23788`, `T4-16816`, `T4-26377`, `T4-02305`) have `old_answer=null`. These are wards whose ward and province names are unchanged. The old 3-level address still exists ("Xã Ia Chia, Huyện Ia Grai, Tỉnh Gia Lai"), but the generator nulls it. This is a design choice; the scorer reads the stale address from `meta.old_address` (section 5, issue S1, resolved).
- **T3 province, 34 items** (`T3-prov-20`, `-37`, `-87`, …) have `old_answer=null` where the province name survives. The old answer would equal the gold, so null is correct by the "old == gold → null" convention.
- **T3 new ward, 19 items** have old = "Không": `T3-neww-31411, 01936, 07462, 31858, 13579, 28159, 29227, 23332, 25399, 07381, 28444, 25267, 00889, 29194, 12454, 27889, 31993, 00982, 04828`. A same-name commune existed before 1/7/2025, but in a *different* component province, and sometimes under another type. Examples: Xã Bảo Đài was in Bắc Giang, not Bắc Ninh; Thị trấn Nà Phặc is now Xã Nà Phặc. The generator's rule is applied consistently to all 60 T3-neww items: "no same-name unit in the same-named old province → old answer Không". That rule is defensible because the question names the new province. Still, a stale model that knows the commune may answer "Có, cấp xã" and be scored `correct`, so these 19 items do not separate stale from updated models. Several are the *same* commune with only its province changed (`00982` Minh Sơn, `31858` Vĩnh Lộc, `25399` Đak Nhau, `29227` Thạnh Phong).

### 1.1 Sample ids (seed 4242)
T0-10 T0-09 T0-04 T0-07 T0-08 T0-02 T0-06 · T1-26677__date T1-01304__reform T1-17245__reform T1-23383__reform
T1-03263__date T1-12625__reform T1-17287__reform T1-01951__date · T1N-14167__date T1N-20971__date T1N-01843__reform
T1N-20900__none T1N-04441__none T1N-07822__date T1N-20669__date T1N-04849__date · T2-80 T2-42 T2-12 T2-15 T2-91 T2-20
T2-31 · T3-neww-04828 T3-oldw-19249 T3-neww-20669 T3-neww-10441 T3-keepw-00919 T3-keepw-07663 T3-oldw-30640 ·
T4-31362-nd T4-31609-nd T4-09826 T4-15127 T4-26539 T4-14857-nd T4-14864 T4-06022 · T5-03514-short__none
T5-03451-mcq__none T5-29305-mcq__none T5-25225-mcq__none T5-22105-short__none T5-13444-mcq__none
T5-03250-short__reform T5-24985-short__date · T6-48-short__date T6-15-mcq__date T6-35-mcq__date T6-60-mcq__reform
T6-86-short__date T6-20-mcq__none T6-84-mcq__none

T0 by hand: 34 provinces / 63 old; 3,321 communes / 10,035 old; 13 đặc khu / 0; 2 levels / 3; no cấp huyện;
no thị trấn — all correct. Minor: `T0-06` distractor "705" is probably also a pre-reform figure (the district count before the
2023–24 mergers; this is from memory and cannot be derived from `districts_old`, which has 696), but only "696" is marked old. It is harmless for accuracy but slightly under-counts `outdated`.

## 2. Web verification

14 items were checked against the text of the UBTVQH commune-level resolutions and NQ 202/2025/QH15, Điều 1
(6 T5, 5 T4, 1 T1, 2 T6). Each item's clause was located, and the new name, type (xã/phường), full composition and province were compared.
The two highest-risk T5 mappings from `crosscheck_issues` were deliberately included.
**Result: 14/14 CONFIRMED, 0 contradicted, 0 unverified.**

| item | mapping checked | source clause |
|---|---|---|
| T5-28270-* | Phường 6 (TP Mỹ Tho, Tiền Giang) + xã Thới Sơn → **phường** Thới Sơn, Đồng Tháp | NQ 1663 Đ1 k.86 |
| T5-31582-* | xã Thuận Hòa (h. Châu Thành) + xã Phú Tân → xã Thuận Hòa, Cần Thơ | NQ 1668 Đ1 k.80 (note: k.50/k.57 involve *different* Thuận Hòa / Phú Tân, so the namesake trap is handled correctly) |
| T5-03514-* | TT Sìn Hồ + Sà Dề Phìn + Phăng Sô Lin + Tả Phìn → xã Sìn Hồ, Lai Châu | NQ 1670 Đ1 k.19 |
| T5-29305-* | Đại Phước + Đức Mỹ + Nhị Long → xã Nhị Long, Vĩnh Long | NQ 1687 Đ1 k.32 |
| T5-22105-* | TT La Hai + Xuân Sơn Nam/Bắc + Xuân Long + Xuân Quang 2 → xã Đồng Xuân, Đắk Lắk | NQ 1660 Đ1 k.81 |
| T5-13444-* | P. Tân Liêm + Đinh Xá + Trịnh Xá → phường Liêm Tuyền, Ninh Bình | NQ 1674 Đ1 k.113 |
| T4-31362 | TT Cái Tắc + Đông Thạnh + Đông Phước A → xã Đông Phước, Cần Thơ | NQ 1668 Đ1 k.56 (verbatim from the signed PDF) |
| T4-31609 | TT Huỳnh Hữu Nghĩa + Mỹ Thuận + Mỹ Tú → xã Mỹ Tú, Cần Thơ | NQ 1668 Đ1 k.82 |
| T4-09826 | TT Phùng + Đồng Tháp + Song Phượng + Thượng Mỗ + Đan Phượng → xã Đan Phượng, Hà Nội | NQ 1656 Đ1 k.106 |
| T4-26539 | Phường 11 + Phường 12 (TP Vũng Tàu) → phường Phước Thắng, TP HCM | NQ 1685 Đ1 k.105 |
| T4-06022 | Tân Yên + Kim Đồng + Tân Tiến → xã Tân Tiến, Lạng Sơn | NQ 1672 Đ1 k.3 |
| T1-12625-* | Quang Trung (h. Hưng Hà) + Văn Cẩm + Duyên Hải → xã Diên Hà, **Hưng Yên** | NQ 1666 Đ1 k.76 |
| T6-60-* | Đắk Nông + Bình Thuận + Lâm Đồng → tỉnh Lâm Đồng | NQ 202/2025/QH15 Đ1 k.14 |
| T6-84-* | Bến Tre + Trà Vinh + Vĩnh Long → tỉnh Vĩnh Long | NQ 202/2025/QH15 Đ1 k.20 |

Sources:
- NQ 1668: the signed text on cdn.thuvienphapluat.vn.
- The other resolutions: hoatieu.vn copies, with NQ 202 also on thuvienphapluat.vn. The hoatieu.vn quotes were read through a summarising fetch tool, so they are near-verbatim.
- For the paper, cite vbpl.vn / vanban.chinhphu.vn.

With 14/14 confirmed, the external error rate of the mapping is bounded only weakly: 95 % upper bound ≈ 21 % (rule of 3).
Together with the 4-lineage agreement in `ward_mapping` (10,464/10,566 rows have 4 sources), no evidence of mapping errors was found.

## 3. MCQ integrity (all 5,320 MCQ items)

| check | failures |
|---|---:|
| exactly 4 non-empty choices, `answer` ∈ A–D | 0 |
| exactly one choice equals the (re-derived) gold | 0 |
| duplicate choices after `normalize_name` | 0 |
| duplicate choices after `normalize_name_nodiac` | 0 |
| a distractor is alias-/legacy-equivalent to the gold (scorer's `expand_key` + `LEGACY` + `answer_aliases`) | 0 |
| `old_answer` letter ≠ `answer` and ∈ A–D | 0 |
| `surface_answer_changed=True` but `old_answer` null / `False` but set (T1, T1N, T5, T6, T2) | 0 / 0 |
| derived old answer present among choices when it differs from gold (T1, T5, T6) | 0 |
| T2: no distractor names exactly the `merged_from` set (all 34 × 3 distractors); every "Chỉ có X" old answer names the new province itself | 0 / 0 |
| old-letter text equals derived old answer | 0 (19 T3-neww differences explained in section 1) |

## 4. Leak checks (all items)

**Gold in question text** (`normalize_text`, word-boundary match; T4 compares only the ward part; `-nd` twins are
compared without diacritics):

| qtype | gold in question, surface answer unchanged (expected by design) | gold in question, **answer changed** |
|---|---:|---:|
| T1_membership | 1,437 / 1,437 | **3** (`T1-25414__none/__date/__reform`: "Xã Đồng Nai, huyện Bù Đăng, tỉnh Bình Phước" → Tỉnh Đồng Nai; not flagged in meta) |
| T5_ward_successor | 762 / 762 | **498 / 1,800 (27.7 %)** |
| T4_address | 121 / 121 | **351 / 1,079 (32.5 %)** |
| T6_reverse | 204 / 204 | 0 / 174 |
| T1_newname | 0 / 720 | 0 |

The T4/T5 changed-answer leaks are new wards named after the old district: "xã X, huyện Mỹ Tú" → "Xã Mỹ Tú". Every one of
them is correctly flagged by `meta.gold_name_in_question`. An independent computation disagrees with the flag on 0 of 3,762
T4/T5 items. So this is a known design property, not a labelling error. But it is large: a model that copies the
district name scores on about 30 % of the "changed" T4/T5 cells. The headline T4/T5 numbers should be reported with
`gold_name_in_question=False`, or at least split by it.

**Temporal / change markers in cue=none items** (2,147 items, `meta.cue=='none'`). Markers checked: trước đây, cũ, sau sắp
xếp, sắp xếp, sáp nhập, mới, 2025, 2026, hiện nay, hiện tại, hiện, bây giờ, từ ngày, 1/7. Result: **0 real hits**. There is one
false positive, `T1-02125__none` "huyện Chợ Mới" (a place name). T3/T4/T0 items contain "Hiện nay" by design and have
`cue=null`, not `'none'`.

## 5. Scorer spot check (17 short items + 1 MCQ × 4 inputs, plus legacy-name probes)

Items: `T5-23164-short__date, T5-03124-short__reform, T5-09061-short__reform, T5-23383-short__none` (list old_answer),
`T5-02425-short__none` (unchanged), `T6-84-short__date, T6-84-short__none, T6-46-short__reform, T6-77-short__none,
T6-80-short__none, T6-15-short__none, T4-03191, T4-01359, T4-21844-nd, T4-16819` (unchanged), `T0-12, T0-11`. No item in
the file has `meta.old_answer_dropped`, so that path is untested.

| input | result |
|---|---|
| (a) gold | `correct` for all 18 items (exact / address / nodiac:address) |
| (b) old answer | `outdated` for all changed items. Unchanged T5/T6: `correct`, or `invalid` when old is null (fine). Legacy "Tỉnh Thừa Thiên Huế" for Huế → `outdated` (legacy_name), good. **Exception S1** below. |
| (c) "Không phải <old> mà là <gold>" | `correct` (relation) for all T4/T5/T6. **Exception S2**: T0 numeric → `other_wrong` (ambiguous). |
| (d) gold without diacritics | diacritised items: `label=other_wrong`, `label_nodiac=correct` (by design: main label is diacritic-strict for has_diacritics items). `-nd` T4 twin: `correct`. T0 numeric: `correct`. |

- **S1 (resolved).** On T4 items with unchanged ward and province names (121 items, `old_answer=null`), the stale 3-level answer "Xã Bắc Lý, Huyện Kỳ Sơn, Tỉnh Nghệ An" was labelled `other_wrong` (`extra_district`), not `outdated` (`T4-16819`). The scorer now takes `meta.old_address` as the old answer for these items, so the pre-reform three-level address is `outdated`; all benchmark runs were rescored.
- **S2 (low).** The T0 short numeric "Không phải 63 mà là 34" → `other_wrong`/`ambiguous`. The relation rule only covers names. This affects 5 T0 short items.
- **S3 (low, MCQ).** A bare-text answer without diacritics on an MCQ ("Tinh Dong Nai", `T1-25414__none`) → `invalid` (no_letter). Diacritised choice text is matched (`choice_text`). It matters only for models that ignore the letter instruction.

## 6. Mixed-condition contexts

- 30 random `mixed` rows (seed 4242) were checked by hand. The `new`-era passage contains **all** `must_contain` strings in 30/30. The old passage contains a `must_contain_old` string in 30/30.
- Extended to **all 7,995 mixed rows**:
  - All passage ids resolve in `data/wiki/passages.jsonl` + `template_passages.jsonl`.
  - Every row has exactly 2 passages with eras {new, old} (asserted for all 7,995 rows).
  - Every `must_contain` string is present in the new passage: 7,995/7,995.
  - `must_contain_old` is satisfied: 7,995/7,995.
  - 12 rows (T0) have an empty `must_contain` list.
  - For T1/T1N/T4/T5/T6 the gold name itself occurs in the new passage in every row. The 185 rows where it does not are T3/T2/T0, whose gold is an answer phrase, which is expected.

## 7. Estimated error rate per qtype (gold `answer`)

| qtype | n | observed wrong golds | internal error rate | 95 % upper bound (rule of 3) | external (web) check |
|---|---:|---:|---:|---:|---|
| T1_membership | 2,781 | 0 | 0 % | 0.11 % | 1/1 confirmed |
| T1_newname | 720 | 0 | 0 % | 0.42 % | — (province of a uniquely named new ward) |
| T5_ward_successor | 2,562 | 0 | 0 % | 0.12 % | 6/6 confirmed (incl. 2 highest-risk rows) |
| T4_address | 1,200 | 0 | 0 % | 0.25 % | 5/5 confirmed |
| T6_reverse | 378 | 0 | 0 % | 0.79 % | 2/2 confirmed |
| T3_existence | 308 | 0 | 0 % | 0.97 % | — |
| T2_composition | 34 | 0 | 0 % | 8.8 % | — (all 34 equal NQ 202/2025/QH15 merged_from) |
| T0_headline | 12 | 0 | 0 % | — | checked by hand |

"Internal" means agreement with the processed tables. Ward-level golds (T4/T5, T3 ward kinds) can only be as
good as `ward_mapping.jsonl`. Higher-risk mapping rows are the ones with `target_set_agrees=false` or a pair seen in
only one lineage (`crosscheck_issues.jsonl`). These touch only 2 old wards used in T5: 12 items, `T5-28270-*` and
`T5-31582-*`, both web-checked in section 2. T1 has 9 such items, but T1 golds are province-level and unaffected.

## 8. Prioritised fixes

No gold `answer` needs changing. The following are the fixes, in priority order. All except F5 can be done at scoring/analysis time, without regenerating
items, by passing a corrected label or filter to the offline rescoring.

1. **F1 (high, analysis): report T4/T5 with and without `meta.gold_name_in_question`.** 498/1,800 changed T5 items (27.7 %) and 351/1,079
   changed T4 items (32.5 %) contain the gold ward name in the question, because the new ward was named after the old district. Copying the district name
   then inflates "updated" accuracy. Add the 3 `T1-25414__*` items (Xã Đồng Nai → Tỉnh Đồng Nai) to the same exclusion; they are not flagged in meta.
2. **F2 (done, scorer): S1.** For T4 items with `old_answer=null` (121 items), a 3-level answer that adds the abolished district is scored
   `outdated`, not `other_wrong`: the scorer uses `meta.old_address` as the old answer for these items (regression-tested; all runs rescored).
3. **F3 (medium, analysis): T3 ambiguity.**
   - 52 of the 60 `T3-dist-*` items have a same-name commune today (`name_survives_as_ward=True`). A "Có, cấp xã" answer there is a plausible confusion, not a stale answer. Report T3-district accuracy split by that flag.
   - The 19 `T3-neww-*` items listed in section 1 have an old namesake in another component province. They do not separate stale from updated models (a stale model can be right), so drop them from outdated-rate denominators or mark `surface_answer_changed=False` in the rescoring.
4. **F4 (low, scorer):** handle numeric relation phrasing for T0 short items ("Không phải 63 mà là 34" → correct) (S2). Optionally match diacritic-free choice text for MCQ (S3).
5. **F5 (low, data, next regeneration only):** add "705" to `T0-06` as a second old-answer letter, or replace that distractor. Add an `old_answer_dropped` test item: the path is unused in this build.
