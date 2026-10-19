# ViAdminShift: data report for the canonical administrative-unit tables

Built by `uv run python -m viadmin.data.build` (code in `src/viadmin/data/`). Tested by
`uv run pytest tests/test_data_build.py` (21 tests).
All counts below come from `data/processed/build_stats.json`. Every disagreement and every data fix
is listed in `data/processed/crosscheck_issues.jsonl`.

## 1. Summary

- **Tables.** 63 old provinces, 696 old districts, 10,035 old wards, 34 new provinces, 3,321 new
  wards (2,621 xã, 687 phường, 13 đặc khu) and 10,566 (old ward, new ward) mapping rows.
  - The ward counts match the official totals: 10,035 → 3,321.
  - The province counts match NQ 202/2025/QH15: 28 tỉnh and 6 thành phố.
- **The backbone is official.** It is the National Statistics Office (NSO) conversion table
  *Bảng chuyển đổi ĐVHC mới – cũ*, downloaded directly from danhmuchanhchinh.nso.gov.vn.
- **The two independent lineages agree on 10,564 of the 10,565 NSO pairs.**
  - Lineage A is the NSO table. Lineage B is vietnamadminunits, which is built from the scrape of
    sapnhap.bando.com.vn.
  - At the old-ward level, 10,003 of 10,035 old wards get *identical* sets of new wards from both.
  - The remaining disagreements were checked against the UBTVQH resolutions (section 6.1): the
    Đồng Tháp and Cần Thơ namesake cases, the Thủ Thừa case and the two NSO-only/lineage-B-only
    pairs were read clause by clause; five namesake cases elsewhere were confirmed only by the
    namesake check and the automated clause comparison, not read clause by clause. NSO
    was right in all but two respects: wrong *codes* in 3 rows, and **one missing pair**
    (Xã Hòa Thắng → Xã Hồng Thái, NQ 1671 k.46), which lineage B had and which is now added from the
    resolution (`sources[0]="resolution"`). The other 32 lineage-B-only pairs are B's errors.
- **All 34 ward-level resolutions were parsed** (`src/viadmin/data/resolutions.py`, texts in
  `data/raw/ubtvqh_resolutions_hoatieu/`). Every one of the 3,321 new wards is matched to its
  forming clause, and every mapping row's old ward is named in that clause except 7 explained cases
  (section 6.1, item 6). The parse is a check, not a source; only hand-verified pairs carry
  `"resolution"` in `sources`.
- **Manual spot check: 30/30 rows are correct**, checked against the per-province UBTVQH
  resolutions. This covers 30 different new provinces, drawn with seed 13. A further 11 targeted
  checks of disagreements were also correct after the fixes.
- **2x2 cells (mapping rows):**

  | | ward_changed=False | ward_changed=True |
  |---|---:|---:|
  | province_changed=False | **43** (pure control) | 3,043 |
  | province_changed=True | 84 | 7,396 |

  The pure-control cell is small: only 127 of the 10,035 old wards survived unchanged.
- **The "changed" cells contain rows whose surface answer did not change.** `province_changed` is
  True for every ward of a merged province, including the component whose name the new province kept
  (old Tuyên Quang → new Tuyên Quang), and `ward_changed` is True for a merged ward that keeps its
  name. 1,147 rows outside the control cell have `surface_answer_changed=false`, i.e. the
  "ward, province" answer is literally the same before and after (old_answer = gold):

  | province_changed, ward_changed | surface_answer_changed=False | True |
  |---|---:|---:|
  | False, False (control) | 43 | 0 |
  | False, True | 493 | 2,550 |
  | True, False | 36 | 48 |
  | True, True | 618 | 6,778 |

  **The generator must stratify on, or exclude, `surface_answer_changed=false` rows in the three
  changed cells** (for questions whose answer is the ward + province name); otherwise they inflate
  accuracy and deflate the outdated rate there.

## 2. Sources and lineage

| id (`sources`) | raw dir | what | lineage | used as |
|---|---|---|---|---|
| `nso` | `data/raw/nso_conversion/` | Official NSO xlsx `BangChuyendoiĐVHCmoi_cu_final.xlsx` (Last-Modified 2025-10-23). Sheet "không merge", 10,571 rows, with a per-row note "Nhập toàn bộ / Nhập một phần / Giữ nguyên …" | **A** | backbone (all pairs, codes, new names) |
| `vietnamadminunits` | `data/raw/vietnamadminunits/` | tranngocminhhieu/vietnamadminunits `convert_legacy_2025_with_location_and_default_ward.csv` (10,602 rows, MIT), built from the sapnhap.bando.com.vn composition texts plus GSO lists plus GIS heuristics | **B** | independent vote |
| `undertheseanlp` | `data/raw/undertheseanlp_address/` | HF `undertheseanlp/address` `data/mapping.json` (10,602 records, Apache-2.0) | B (copy of vietnamadminunits 1.0.4, per its own metadata and `build_mapping.py`) | non-independent vote, reported only |
| `vietaddr` | `data/raw/vietaddr/` | WordPress plugin `legacy-map.json` (GPL-3.0+), from provinces.open-api.vn `to-legacies`, which is generated from the NSO table | A (derivative) | non-independent vote, reported only |
| — | `data/raw/vietnam_provinces_nso/` | VietnamProvinces copy of the NSO table (CSV) and the GSO list as of 2025-01-04 | A (copy) | consistency check only |
| — | `vietnamadminunits/data/raw/danhmuchanhchinh.gso.gov.vn_*_2025-07-18.csv` | GSO pre-reform registry: 696 districts, 10,035 communes | registry | `wards_old`, `districts_old`, `provinces_old` |
| — | `vietnamadminunits/data/raw/production.cas.so_3221_wards_2025-08-05.json` | 3,321 new communes with resolution numbers | — | new-ward name/code check, `resolution` |
| — | `vietnamadminunits/data/raw/sapnhap.bando.com.vn_ward_2025-07-17.csv` | Ministry merger site: free-text composition per new ward | B's upstream | `bando_mentions_old_ward` (weak aid only) |
| `resolution` | `data/raw/ubtvqh_resolutions_hoatieu/` | The 34 UBTVQH15 ward-level resolutions NQ 1654–1687 (16/6/2025), HTML reproductions from hoatieu.vn (not the official scanned PDFs) | **R** (the legal text itself) | decides old-name spelling; whole-table composition check; `sources` tag only for hand-checked pairs |

- **Why `confidence` counts lineages, not files.** "≥2 sources agree" must mean ≥2 *lineages*.
  Otherwise the undertheseanlp copy would confirm vietnamadminunits, and vietaddr would confirm NSO.
  So `confidence="high"` means that at least two of {A = `nso`, B = `vietnamadminunits`,
  R = `resolution` (hand-checked)} contain the pair. All 10,566 rows are currently high: 10,564 have
  A+B, Văn Khê → Ô Diên has A+R, Hòa Thắng → Hồng Thái has B+R.
- **The NSO table and its CSV copy are identical.** They match on all 10,605 rows, except that 342
  codes lost their leading zeros in the xlsx; the build zero-pads every code.

## 3. Province level: verification against NQ 202/2025/QH15

- **What the resolution says.** NQ 202/2025/QH15 (12/6/2025), Điều 1, sets out 23 merged units.
  The text was read in the reproductions on baolaocai.vn and on the Cần Thơ PBGDPL portal; vbpl.vn and
  thuvienphapluat returned 403. The resolution lists the units that are not rearranged verbatim:
  *"11 tỉnh, thành phố không thực hiện sắp xếp là các tỉnh: Cao Bằng, Điện Biên, Hà Tĩnh, Lai Châu,
  Lạng Sơn, Nghệ An, Quảng Ninh, Thanh Hóa, Sơn La và thành phố Hà Nội, thành phố Huế."*
  **The list in SPEC.md is correct.**
- **The resolution was transcribed by hand into `build.py` (`NQ202`).** The build then checks it
  three ways:
  - (a) the `merged_from` sets derived from the NSO table must equal it exactly, or the build aborts;
  - (b) a test checks all 34 names and components against a second, independently typed copy in
    `tests/test_data_build.py`;
  - (c) a test checks `merged_from` against `ward_mapping`.
- **The 23 merged units.** Tuyên Quang (Hà Giang + Tuyên Quang); Lào Cai (Yên Bái + Lào Cai); Thái
  Nguyên (Bắc Kạn + Thái Nguyên); Phú Thọ (Vĩnh Phúc + Hòa Bình + Phú Thọ); Bắc Ninh (Bắc Giang + Bắc
  Ninh); Hưng Yên (Thái Bình + Hưng Yên); TP Hải Phòng (Hải Phòng + Hải Dương); Ninh Bình (Hà Nam +
  Nam Định + Ninh Bình); Quảng Trị (Quảng Bình + Quảng Trị); TP Đà Nẵng (Đà Nẵng + Quảng Nam); Quảng
  Ngãi (Kon Tum + Quảng Ngãi); Gia Lai (Bình Định + Gia Lai); Khánh Hòa (Ninh Thuận + Khánh Hòa); Lâm
  Đồng (Đắk Nông + Bình Thuận + Lâm Đồng); Đắk Lắk (Phú Yên + Đắk Lắk); TP HCM (HCM + BR-VT + Bình
  Dương); Đồng Nai (Bình Phước + Đồng Nai); Tây Ninh (Long An + Tây Ninh); TP Cần Thơ (Cần Thơ + Sóc
  Trăng + Hậu Giang); Vĩnh Long (Bến Tre + Trà Vinh + Vĩnh Long); Đồng Tháp (Tiền Giang + Đồng Tháp);
  Cà Mau (Bạc Liêu + Cà Mau); An Giang (Kiên Giang + An Giang).
- **New province codes.** A new province keeps the GSO code of one of its parts, and that part is not
  always the one whose name it takes. New Bắc Ninh is 24 (Bắc Giang's code), Tây Ninh is 80 (Long
  An), Lào Cai is 15 (Yên Bái), Gia Lai is 52 (Bình Định), Đồng Tháp is 82 (Tiền Giang), An Giang is
  91 (Kiên Giang), Quảng Trị is 44 (Quảng Bình), Vĩnh Long is 86 and Ninh Bình is 37.
  `province_changed` is therefore computed as `len(merged_from) > 1`, never from code or name.
- **Capital.** `capital` is null in every row. The seat ward of each provincial People's Committee
  was not verified.
  - Instead, the extra field `seat_old_province_code` records which old province hosts the new
    political-administrative centre, per NQ 60-NQ/TW. Sources are the SGGP list and
    sapnhap.bando.com.vn "trungtamhc"; the two agree for all 23.
  - Centres that are not in the namesake province: Lào Cai → Yên Bái, Bắc Ninh → Bắc Giang, Quảng
    Trị → Quảng Bình, Gia Lai → Bình Định, Tây Ninh → Long An, Đồng Tháp → Tiền Giang, An Giang →
    Kiên Giang.
- **Date scope.** The tables describe the state on 1/7/2025. Later changes are not represented, for
  example 2026 upgrades of some provinces to centrally-run cities, which `docs/wiki_report.md` notes for
  Đồng Nai, Quảng Ninh and Bắc Ninh.

## 4. Definitions (also in SPEC.md, "Canonical tables — details")

For each mapping row with old ward *o* and new ward *n*:

- `n_new_targets(o)` is the number of distinct new wards *o* maps to.
- `n_old_sources(n)` is the number of distinct old wards that form *n*.
- `change_type` is the first rule that applies, in this order:
  1. **divided** if `n_new_targets(o) > 1`. *o* was split, and all of its rows are `divided`, even
     the row whose new ward keeps *o*'s name. Resolution wording: "một phần diện tích tự nhiên, quy mô
     dân số của …" / "phần còn lại của …".
  2. **merged** if `n_old_sources(n) > 1`. *o* went wholly into a new ward formed from several old
     wards. This includes the 1,641 rows where *n* keeps *o*'s name (e.g. Xã Bàu Hàm → Xã Bàu Hàm
     with 3 other xã). Use `name_changed` / `surface_answer_changed` when the question is about the
     surface name.
  3. **unchanged** if 1:1 and the same name, or 1:1 with the NSO note "Giữ nguyên" and the same unit
     type. In the second case `spelling_variant=true` when old and new are spelt differently. Since old
     names now follow the resolution's spelling (6.1, item 6), no such row remains; the six former
     cases (Tà Si Láng/Tà Xi Láng, Lưỡng Minh/Lượng Minh, Đắk Long/Đăk Long, Rơ Kơi/Rờ Kơi, Đak Ơ/Đăk Ơ,
     Dak Lua/Đak Lua) now have the new spelling as old name and the registry's in `old_ward_name_alt`.
  4. **renamed** otherwise: 1:1 but a different name or unit type. There are 5 rows:
     - Thị trấn Mường Lát → Xã Mường Lát
     - Thị trấn Thạnh Mỹ → Xã Thạnh Mỹ
     - Xã Krông Na → Xã Buôn Đôn
     - Xã Bà Gia → Xã Đạ Huoai 3
     - Xã Thổ Châu → Đặc khu Thổ Châu
- **Combined cases.** An old ward that is split, where one part also merges with other wards, is
  `divided`. Divided takes precedence because the answer to "which new ward is *o* in now?" is no
  longer unique.
- `is_partial` = `n_new_targets > 1`.
  - This agrees with the NSO note in 10,564 of 10,566 rows.
  - Exception 1: Xã Kỳ Lợi → Phường Vũng Áng, noted "Nhập toàn bộ diện tích". The resolution (NQ
    1665, khoản 62–64) moves *all the area* of Kỳ Lợi to one ward but splits its *population* across
    three. So the ward is partial in population, and the flag is correct.
  - Exception 2: Xã Hòa Thắng → Xã Hòa Thắng, noted "Nhập toàn bộ". NQ 1671 k.51 says "phần còn lại
    của xã Hòa Thắng"; the NSO note is wrong (see 6.1, item 2).
- `ward_changed` = `change_type != "unchanged"`. `province_changed` = the new province has more than
  one old component; it is False exactly for the 11 provinces.
- `name_changed`: the old (canonical, resolution-spelt) and new full names differ under `name_key`,
  which ignores tone placement, case and apostrophes. `province_name_changed`: the same for the old
  and new province names. `surface_answer_changed` = `name_changed or province_name_changed`.

## 5. Counts

**Tables.**

| table | rows | notes |
|---|---:|---|
| provinces_old | 63 | 57 tỉnh, 6 thành phố |
| districts_old | 696 | 5 have no communes (Bạch Long Vĩ, Cồn Cỏ, Hoàng Sa, Lý Sơn, Côn Đảo) |
| wards_old | 10,035 | xã 7,691, phường 1,727, thị trấn 617 (unit type from the name prefix) |
| provinces_new | 34 | 28 tỉnh, 6 thành phố |
| wards_new | 3,321 | xã 2,621, phường 687, đặc khu 13 |
| ward_mapping | 10,566 | 10,035 old wards |

**change_type.**

| change_type | mapping rows | old wards |
|---|---:|---:|
| merged | 9,462 | 9,462 |
| divided | 972 | 441 |
| unchanged | 127 | 127 |
| renamed | 5 | 5 |

**2x2 cells.**

| province_changed, ward_changed | rows | old wards |
|---|---:|---:|
| False, False (pure control) | 43 | 43 |
| False, True | 3,043 | 2,745 |
| True, False | 84 | 84 |
| True, True | 7,396 | 7,163 |

**change_type × province_changed (rows).**

| change_type | province_changed=False | province_changed=True |
|---|---:|---:|
| divided | 523 | 449 |
| merged | 2,519 | 6,943 |
| unchanged | 43 | 84 |
| renamed | 1 | 4 |

**Name changes.**

- 8,728 rows have `name_changed=true` (8,771 before old names followed the resolution). 1,641
  `merged` rows keep the old ward's name. 4,009 rows have `province_name_changed=true`.
- The ward_changed=False cells contain 6 rows where the literal strings still differ, all of them
  tone-placement or capitalisation differences such as "Xã Thuận Hoà" vs "Xã Thuận Hòa" or "Xã KRong"
  vs "Xã Krong"; `name_key` treats tone placement as equal and is case-insensitive.
- 2 merged rows have the registry spelling equal to the new name but the resolution spells the old
  ward differently (Pờ Y → Bờ Y, Chơ GLong → Chơ Long); they keep `name_changed=true` because the
  resolution treats them as different names. The control cell contains one row whose
  `old_ward_name_alt` differs (Lượng Minh, registry "Lưỡng Minh").
- **Recommendation for the generator:** have the scorer compare names with tone-placement
  normalisation; `viadmin.data.normalize.name_key` does this.

## 6. Cross-source agreement

**Pair level (old_code, new_code).**

| | pairs |
|---|---:|
| NSO | 10,565 |
| vietnamadminunits | 10,597 |
| both lineages | **10,564** |
| only in vietnamadminunits | 33: 1 emitted after checking the resolution (Hòa Thắng → Hồng Thái), 32 rejected |
| only in NSO | 1 (Văn Khê → Ô Diên; confirmed by NQ 1656 k.107, so `sources` has "resolution" and `confidence="high"`) |
| emitted (`ward_mapping`) | 10,566 |
| NSO ∩ undertheseanlp | 10,479 of 10,512 matched (90 of the 10,602 HF records could not be matched by name, 45 of them because the HF record has an empty `new_ward`, a defect of that file) |
| NSO ∩ vietaddr | 10,551 of 10,554 (the 3 vietaddr-only pairs are the 3 NSO code errors below, inherited by vietaddr; 14 NSO pairs are absent from vietaddr, mostly HCMC and Mộc Châu wards for which vietaddr has no entry) |

**Old-ward level.** This compares the full set of new wards for each old ward, NSO against
vietnamadminunits:

- identical: 10,003;
- vietnamadminunits has an extra target: 31;
- vietnamadminunits is missing a target: 1 (Văn Khê);
- disjoint: 0.

Rows of the 32 differing old wards have `target_set_agrees=false`.

**New-province level.** The two lineages give the same new province for every old ward: 0
disagreements.

### 6.1 Disagreements and their adjudication

1. **32 of the 33 vietnamadminunits-only pairs are vietnamadminunits errors** (the 33rd is item 2).
   31 are same-name collisions: wards with identical names in different districts of the merged
   province; vietnamadminunits keeps the correct target *and* adds the namesake's target (a script
   check confirms that for each of the 31 the namesake does map to that target in NSO). The 32nd is
   Thị trấn Thủ Thừa → Xã Nhựt Tảo: bando's text for Nhựt Tảo ends "Xã Nhị Thành, Thủ Thừa", meaning
   the remainder of Nhị Thành *of huyện Thủ Thừa* (NQ 1682 k.52); the town Thủ Thừa goes wholly to xã
   Thủ Thừa (k.20). Verified against the resolutions:
   - **Đồng Tháp (NQ 1663).** Phường 4 (TP Mỹ Tho) → only Phường Đạo Thạnh (khoản 84), not Phường
     Cao Lãnh. Khoản 95 forms Cao Lãnh from Phường 1, 3, 4 and 6 *of TP Cao Lãnh*. The same pattern
     holds for Phường 6 (Mỹ Tho) → Thới Sơn (k.86), Phường 3 (Cai Lậy) → Mỹ Phước Tây (k.99),
     Phường 4 (Cai Lậy) → Cai Lậy (k.101) and Phường 3/4 (Sa Đéc) → Sa Đéc (k.98).
   - **Cần Thơ (NQ 1668).** Phú Tân (Châu Thành, Hậu Giang) → Phú Hữu (k.57) and Phú Tân (Châu
     Thành, Sóc Trăng) → Thuận Hòa (k.80); vietnamadminunits cross-links the two. The same applies
     to four more pairs of namesakes, each pair being two different old communes in two clauses:
     xã Tân Long (Phụng Hiệp, Hậu Giang) → xã Thạnh Hòa (k.64) and xã Tân Long (Ngã Năm, Sóc Trăng)
     → xã Tân Long (k.85); xã Long Phú (Long Mỹ, Hậu Giang) → phường Long Phú 1 (k.20) and xã Long
     Phú (Long Phú, Sóc Trăng) → xã Long Phú (k.72); Thạnh Quới (k.43/k.66); Tân Thạnh (k.36/k.71).
     The new xã Tân Long is formed by k.85 and the new xã Long Phú by k.72.
   - **Elsewhere (same pattern, confirmed by the namesake check above, not read clause by clause).**
     Phường 4 TP Tây Ninh vs Phường 4 TP Tân An; Hòa Bình (Kim Thành) vs Hoà Bình (Vĩnh Bảo); Hòa Lộc
     (Mỏ Cày Bắc) vs Hoà Lộc (Tam Bình); Hồng Phong (Bình Gia) vs Hồng Phong (Cao Lộc); Mỹ An (Mang
     Thít) vs Mỹ An (Thạnh Phú).
2. **Hòa Thắng → Hồng Thái: a pair missing from NSO (found by review, now added).** NQ 1671 k.46:
   "Sắp xếp toàn bộ diện tích tự nhiên, quy mô dân số của xã Phan Thanh, xã Hồng Thái và một phần
   diện tích tự nhiên của xã Hòa Thắng thành xã mới có tên gọi là xã Hồng Thái"; k.51 sends "phần còn
   lại của xã Hòa Thắng sau khi sắp xếp theo quy định tại khoản 46" to xã Hòa Thắng. NSO has only
   Hòa Thắng → Hòa Thắng with "Nhập toàn bộ"; vietnamadminunits and bando list Hòa Thắng in Hồng
   Thái's composition. The pair is added by `RESOLUTION_ADDED_PAIRS` in build.py with
   `sources=["resolution","vietnamadminunits","undertheseanlp"]`; both Hòa Thắng rows are now
   `divided`, `is_partial=true`. Like Văn Khê → Ô Diên it moves area only. An earlier version of this
   report said that every checked lineage-B addition was wrong; that was wrong for this pair.
3. **Văn Khê → Ô Diên (NSO only, partial).** NQ 1656, Điều 1, khoản 107 forms xã Ô Diên from "…một
   phần diện tích tự nhiên của xã Văn Khê…". **NSO is right**: vietnamadminunits misses this target,
   and bando's text for Ô Diên omits it too. Kept; `sources` gains "resolution" (hand-checked), so
   `confidence="high"`. Văn Khê is split four ways: Ô Diên, Mê Linh, Yên Lãng and Tiến Thắng
   (k.107, 118–120).
- **Whole-table composition check.** Every clause of the 34 resolutions was parsed and compared with
  the mapping (old names by name, both spellings). Apart from the pair in item 2, the non-ward areas
  in 6.2 and the 4 Kiên Hải communes (the resolution merges "huyện Kiên Hải" as a whole), all
  remaining differences were parser artefacts (glued words in the reproduction, "phần còn lại"
  scoping), checked by eye. An independent clause-by-clause comparison by the reviewer (3,193
  clauses) reached the same result.
4. **Wrong old-ward codes in the NSO table (3 rows), fixed by name lookup within the district.**
   - "Xã Đặng Xá" was coded 00553, which is Cổ Bi's code; corrected to 00556.
   - "Xã Mỹ Hưng" was coded 01615 (Hồng Quang); corrected to 01651.
   - "Xã Phú Thịnh" was coded 02485 (Công Đa); corrected to 02482.

   Verified in NQ 1684 k.27–28 (Phú Thịnh → Thái Bình, Công Đa → Trung Sơn), NQ 1657 k.38–39 (Mỹ
   Hưng → Phục Hòa, Hồng Quang → Bế Văn Đàn) and NQ 1656 k.110 and k.112 (Đặng Xá → Thuận An, k.110, and its remainder → Phù Đổng, k.112). Without
   the fix, three wards would have received wrong extra targets. vietaddr inherits these errors.
5. **NSO new-ward name typo.** "Xa Ea Kly" was replaced by the cas.so name "Xã Ea Kly". New-ward
   names otherwise agree across NSO, cas.so, vietnamadminunits, vietaddr and VietnamProvinces for all
   3,321 codes. Seventeen differ only in tone-mark placement.
6. **Old-ward name and type issues.**
   - **180 old wards (182 rows)** are spelt differently in NSO and in the GSO registry, for example
     Phó Bảng vs Phố Bảng, Xà Phìn vs Sà Phìn, Kim Chung vs Kim Trung and Hưng Yên vs Hưng Yên Nam.
     Some are orthographic (Đắk/Đăk, Quí/Quý), others are different names where the registry is
     stale or wrong ("Xã Hưng Yên" for Hưng Yên Nam, whose sibling 18008 is Hưng Yên Bắc).
     **Rule (since the review): the resolution decides.** For each such ward the build looks up the
     clause(s) forming its new ward(s) and checks which spelling the clause names (exact item match,
     whole-word fallback; a unit-type change only if the clause states the type). Result: **176 take
     the resolution/NSO spelling** (e.g. Kim Trung, Hưng Yên Nam, Mù Cang Chải, Măng Bút, Cư Yang,
     Pờ Y, Thạnh An, Hua Bum, Tung Qua Lìn, Quan Triều, Vinh Kim, Cổ Đạm, An Qui), **3 keep the
     registry's because the resolution uses it** (Trang Hạ, Đắk Wil, and Xã Hòa Tân Đông where NSO
     says "Phường"), and **1 keeps the registry's by manual exception** (code 19780 "Phường Phường
     Đúc": the ward is named "Phường Đúc", NQ 1675 k.15; NSO drops the doubled prefix). The other
     spelling is stored in `wards_old.name_alt` / `old_ward_name_alt` as an alias. Each decision is in
     `crosscheck_issues.jsonl` (`old_ward_name_from_resolution` / `old_ward_name_registry_kept`, with
     the khoản). 4 registry names had a capitalised prefix "Thị Trấn"; normalised to "Thị trấn".
   - **Canonical old name not found in the forming clause (7):** Đăk Trôi (resolution "Đak Trôi"),
     Đắk Kơ Ning ("Đăk Kơ Ning"), Đạ K' Nàng ("Đạ K'Nàng") — registry and NSO agree here, so kept —
     and the 4 communes of huyện Kiên Hải (merged as a district).
   - **Two registry entries were corrected after checking the resolutions:**
     - Code 03244 is listed as "Xã Sáng Nhè", but that is the code's *new* name. NQ 1661 k.20 merges
       "xã Xá Nhè, Mường Đun và Phình Sáng" into the new xã Sáng Nhè, so the old name is set to
       "Xã Xá Nhè".
     - Code 13369 is listed as "Xã Tiên Sơn", but NQ 1674 k.102 says "phường Tiên Sơn". The old name
       is set to "Phường Tiên Sơn".
     These two registry values are verified wrong and are NOT kept as aliases (`name_alt` null).
   - The opposite case was not changed. For code 22267, NSO says "Phường Hòa Tân Đông", but NQ 1660
     k.94 says "xã Hòa Tân Đông", so the registry's "Xã" is kept.
   - "Thị trấn NT …" and "Thị trấn N.T …" were expanded to "Thị trấn Nông trường …" (6 wards).
7. **sapnhap.bando.com.vn texts.** Matching is now done item by item on a key without spaces,
   hyphens or unit-type prefix, with both spellings of the old ward ("Xã EaBar" ~ "Xã Ea Bar",
   "Văn Miếu - Quốc Tử Giám" ~ "Văn Miếu Quốc Tử Giám"); bando's "Không sáp nhập" counts as a mention
   for 1:1 rows. The text names the old ward in 10,546 rows, does not in 10, and is unavailable in 10.
   The 10: Văn Khê → Ô Diên (bando omits it), Thượng Bình → Đồng Tâm and Trung Môn → Minh Xuân
   (bando's lists are incomplete; NQ 1684 k.79/k.106 confirm the pairs), Xím Vàng (bando typo "Xí m
   Vàng"), Đăk Trôi, Đắk Kơ Ning and the 4 Kiên Hải communes. (The earlier figure of 329 was mostly
   matching artefacts.) The text is a weak aid and does not affect `confidence`.

### 6.2 Data notes

- **Rows with no old ward.** Six NSO rows have no old commune, and they are not in `ward_mapping`:
  - the 5 đặc khu formed from island districts that had no commune level (Bạch Long Vĩ, Cồn Cỏ,
    Hoàng Sa, Lý Sơn, Côn Đảo);
  - "Khu vực bãi bồi ven biển do huyện Kim Sơn quản lý", a coastal mudflat area that went into Xã
    Kim Đông (NQ 1674 k.97).
- **Non-ward area without an NSO row:** NQ 1658 k.34 also merges "Trường bắn TB1" (a firing range)
  into Xã Biên Sơn (Bắc Ninh). So the T2 composition of **Xã Kim Đông** and **Xã Biên Sơn** in
  `ward_mapping` is not the complete legal composition: the generator should exclude these two from
  T2 composition questions or state that non-ward areas are not counted.
- **Registry entries whose "Cấp" contradicts the name prefix.** There are 4; the name prefix is used.
  - Code 15061, "Thị trấn Ngọc Lặc".
  - Codes 27046 and 27076: two wards named "Phường …" in the registry.
  - Code 13369 (Tiên Sơn), which was fixed as described in 6.1.

## 7. Manual spot check: 30 rows, seed 13, one per new province

- **Sampling.** `random.Random(13).shuffle` over the mapping rows, keeping the first row for each
  new province until 30 rows were drawn. The sample was drawn before the pair Xã Hòa Thắng → Xã Hồng
  Thái (NQ 1671 k.46, section 6.1) was added, i.e. over 10,565 rows; on the released 10,566-row file the
  same procedure gives a different sample in 8 of the 30 positions. All 30 rows below are in the released
  mapping.
- **Source.** Each row was checked against the Điều 1 text of the province's UBTVQH resolution of
  16/6/2025, as reproduced on luatvietnam.vn. The official signed PDFs on vanban.chinhphu.vn are
  scanned images with no OCR available here, so they were not used.
- **What was checked.** For each row, the khoản forming the new ward, plus every khoản
  mentioning the old ward, with the row and with the full composition in our table.

| # | resolution (khoản) | old ward (district, old province) | → new ward (new province) | type | result |
|---|---|---|---|---|---|
| 1 | 1664 (k.122) | Phường Yên Đỗ (TP Pleiku, Gia Lai) | Phường Diên Hồng (Gia Lai) | merged | ✔ composition {Yên Đỗ, Ia Kring, Diên Hồng, Diên Phú} matches |
| 2 | 1686 (k.90) | Xã Lương Ngoại (Bá Thước, Thanh Hóa) | Xã Quý Lương (Thanh Hóa) | merged | ✔ {Lương Nội, Lương Trung, Lương Ngoại} |
| 3 | 1671 (k.105) | Xã ĐamBri (TP Bảo Lộc, Lâm Đồng) | Phường 2 Bảo Lộc (Lâm Đồng) | merged | ✔ the resolution spells it "ĐamBri" (now the canonical name; registry "Đạm Bri" is the alias) |
| 4 | 1662 (k.12) | Xã Bàu Hàm (Trảng Bom, Đồng Nai) | Xã Bàu Hàm (Đồng Nai) | merged | ✔ {Thanh Bình, Cây Gáo, Sông Thao, Bàu Hàm} |
| 5 | 1677 (k.43) | Xã Ba Tô (Ba Tơ, Quảng Ngãi) | Xã Ba Tô (Quảng Ngãi) | merged | ✔ |
| 6 | 1674 (k.101, k.109) | Phường Hoàng Đông (TX Duy Tiên, Hà Nam) | Phường Hà Nam (Ninh Bình) | divided | ✔ part → Duy Hà (k.101), remainder → Hà Nam (k.109); our targets {Duy Hà, Hà Nam} |
| 7 | 1655 (k.57) | Xã Hiệp Thành (TP Bạc Liêu) | Phường Hiệp Thành (Cà Mau) | merged | ✔ |
| 8 | 1669 (k.86) | Xã Tân Việt (Bình Giang, Hải Dương) | Xã Bình Giang (Hải Phòng) | merged | ✔ the namesake Tân Việt (Thanh Hà) → Hà Bắc (k.78) is a different ward and is correctly separate |
| 9 | 1668 (k.15) | Phường Thuận An (Q. Thốt Nốt, Cần Thơ) | Phường Thốt Nốt (Cần Thơ) | merged | ✔ |
| 10 | 1656 (k.112) | Xã Yên Viên (Gia Lâm, Hà Nội) | Xã Phù Đổng (Hà Nội) | merged | ✔ full composition, including remainders of Cổ Bi and Đặng Xá, matches |
| 11 | 1687 (k.104) | Phường 4 (TP Vĩnh Long) | Phường Phước Hậu (Vĩnh Long) | merged | ✔ |
| 12 | 1660 (k.41) | Xã Cư KTy (Krông Bông, Đắk Lắk) | Xã Dang Kang (Đắk Lắk) | merged | ✔ |
| 13 | 1676 (k.43) | Xã Văn Miếu (Thanh Sơn, Phú Thọ) | Xã Văn Miếu (Phú Thọ) | merged | ✔ |
| 14 | 1666 (k.98) | Xã Ngọc Lâm (TX Mỹ Hào, Hưng Yên) | Phường Đường Hào (Hưng Yên) | merged | ✔ k.66 creates a *new* xã Ngọc Lâm from Quỳnh Hoàng / Quỳnh Lâm / Quỳnh Ngọc, which is not this ward |
| 15 | 1680 (k.72) | Xã Quảng Hải (TX Ba Đồn, Quảng Bình) | Phường Ba Đồn (Quảng Trị) | merged | ✔ |
| 16 | 1679 (k.12) | Xã Tân Bình (Đầm Hà, Quảng Ninh) | Xã Đầm Hà (Quảng Ninh) | merged | ✔ |
| 17 | 1678 (k.3) | Xã Tam Đỉnh (huyện Anh Sơn, Nghệ An) | Xã Nhân Hòa (Nghệ An) | merged | ✔ not to be confused with Tam Đình (Tương Dương, k.97). The clause names no district; "huyện Anh Sơn" (the old district) is from the NSO table and GSO registry (all four sources agree), and the two communes merged with it in k.3, Cẩm Sơn and Hùng Sơn (code 17347; not the new xã Hùng Sơn of Đà Nẵng, NQ 1659 k.83), are also in huyện Anh Sơn. Not the new xã Anh Sơn, which k.1 forms from thị trấn Kim Nhan, xã Đức Sơn and xã Phúc Sơn |
| 18 | 1659 (k.17) | Phường Điện Phương (TX Điện Bàn, Quảng Nam) | Phường Điện Bàn (Đà Nẵng) | merged | ✔ |
| 19 | 1663 (k.79) | Xã Tân Tây (Gò Công Đông, Tiền Giang) | Xã Tân Đông (Đồng Tháp) | merged | ✔ |
| 20 | 1670 (k.1) | Xã Pha Mu (Than Uyên, Lai Châu) | Xã Mường Kim (Lai Châu) | merged | ✔ |
| 21 | 1665 (k.37) | Xã Tân Dân (Đức Thọ, Hà Tĩnh) | Xã Đức Thọ (Hà Tĩnh) | merged | ✔ |
| 22 | 1681 (k.39) | Xã Tú Nang (Yên Châu, Sơn La) | Xã Chiềng Hặc (Sơn La) | merged | ✔ |
| 23 | 1683 (k.77) | Xã Huống Thượng (TP Thái Nguyên) | Phường Linh Sơn (Thái Nguyên) | merged | ✔ |
| 24 | 1667 (k.52) | Phường Phước Long (TP Nha Trang) | Phường Nam Nha Trang (Khánh Hòa) | merged | ✔ |
| 25 | 1685 (k.3) | Phường Bến Thành (Quận 1, HCM) | Phường Bến Thành (HCM) | merged | ✔ including the parts of Cầu Ông Lãnh and Nguyễn Thái Bình |
| 26 | 1658 (k.79) | Phường Hà Mãn (TX Thuận Thành, Bắc Ninh) | Phường Song Liễu (Bắc Ninh) | merged | ✔ |
| 27 | 1657 (k.49) | Xã Phong Nặm (Trùng Khánh, Cao Bằng) | Xã Đình Phong (Cao Bằng) | merged | ✔ the resolution spells it "Phong Nặm" (now canonical; registry "Phong Nậm" is the alias) |
| 28 | 1682 (k.49) | Xã Tân Tập (Cần Giuộc, Long An) | Xã Tân Tập (Tây Ninh) | merged | ✔ |
| 29 | 1673 (k.55) | Xã Khánh Yên Thượng (Văn Bàn, Lào Cai) | Xã Văn Bàn (Lào Cai) | merged | ✔ |
| 30 | 1654 (k.75) | Xã Mỹ Hiệp Sơn (Hòn Đất, Kiên Giang) | Xã Mỹ Thuận (An Giang) | merged | ✔ k.75: "thị trấn Sóc Sơn và các xã Mỹ Hiệp Sơn, Mỹ Phước, Mỹ Thuận thành xã mới có tên gọi là xã Mỹ Thuận" (parsed text of NQ 1654) |

**Result: 30/30 correct.** All 30 old→new pairs and all 30 full compositions of the new wards
match the resolutions.

- **Caveat on the sample.** It contains only one `divided` row (#6) and no `unchanged` or `renamed`
  rows, because merges dominate the population.
- **Targeted checks.** Eleven further checks (section 6.1) cover the divided, conflicting and fixed
  rows:
  - Văn Khê
  - Kỳ Lợi
  - Đặng Xá / Cổ Bi
  - Mỹ Hưng / Hồng Quang
  - Phú Thịnh / Công Đa
  - the 5 Đồng Tháp collisions
  - the Cần Thơ collisions
  - Xá Nhè
  - Tiên Sơn
  - Hòa Tân Đông
  - after review: Hòa Thắng → Hồng Thái / Hòa Thắng (NQ 1671 k.46, k.51), Thủ Thừa / Nhị Thành
    (NQ 1682 k.20, k.52), Kim Trung (NQ 1666 k.71), Hưng Yên Nam (NQ 1678 k.27), Pờ Y (NQ 1677 k.64),
    Phường Đúc (NQ 1675 k.15)
- **Errors found and their causes.**
  - Three code-copy errors and one typo in the NSO table (fixed).
  - Same-name collisions in vietnamadminunits (excluded).
  - One stale registry name (Xá Nhè) and one stale registry type (Tiên Sơn), both fixed.

## 8. Known issues and uncertainties

- **NSO backbone with one addition.** NSO determines every emitted pair except Hòa Thắng → Hồng
  Thái, which NSO missed and which was added from the resolution after review. The automatic
  clause-by-clause comparison against all 34 resolutions found no other missing pair, but that
  comparison depends on a parser of reproduced (not official) text; a missing pair in a clause the
  parser mangled cannot be fully excluded.
- **The source of divided wards is only partly verified.** The fine structure of the 441 divided
  wards (which new wards receive part of an old ward) agrees across both lineages for all but 32 old
  wards. Only 4 divided wards were checked by hand (Hoàng Đông, Văn Khê, Kỳ Lợi, Hòa Thắng). Divided wards have
  no unique answer to "which new ward is *o* in now?"; generators should treat them as multi-answer
  or skip them.
- **Spelling.** The registries mix tone placements and contain variant spellings (S/X, Đắk/Đăk/Dak).
  Always compare names with `name_key` and accept `old_ward_name_alt`. All 180 registry/NSO spelling
  conflicts were decided automatically against the resolution clause (6.1, item 6); the decision
  list was read through by eye, but only the cases named in section 7 were read clause by clause.
  The resolution texts are hoatieu.vn reproductions; where the reproduction has a typo, NSO and the
  reproduction would have to share it for the build to adopt it.
- **Capitals.** `capital` is null; only `seat_old_province_code` is provided.
- **The pure-control cell is small:** 43 rows / 43 old wards (one, Lượng Minh, has a registry
  alias "Lưỡng Minh"). Use per-old-ward stratification.
- **Surface-unchanged rows in the changed cells** (1,147 rows, section 1): stratify or exclude.
- **Post-reform changes are not represented.** VietnamProvinces and provinces.open-api.vn data
  version 2026-09-20, and therefore vietaddr, mention later 2026 adjustments in Quảng Ninh and Bắc
  Ninh. These are deliberately not used, since the benchmark targets 1/7/2025.
