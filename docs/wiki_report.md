# Wikipedia passages: coverage report

Built by `uv run python -m viadmin.wiki.build`; revised in a fixer pass
(review findings: the new era now uses end-2025 revisions, old-era revisions that already show the
post-reform state are stepped back, stale new-era copies are flagged). Numbers come from
`uv run python -m viadmin.wiki.report`. Outputs:

- `data/wiki/passages.jsonl`: 1,584 passages (schema in SPEC.md, "Wikipedia passages")
- `data/wiki/fetch_log.jsonl`: one line per (entity, era) attempt: status, validation problems,
  warnings, the first 200 chars of the lead; plus one line per old-era step-back
- `data/wiki/quality.jsonl`: per-passage checks against `data/processed` (ward-name recall,
  stated vs. gold commune count, listed names not in gold, reform mention, staleness of new-era
  text). Written by `uv run python -m viadmin.wiki.report --write-quality`.
- raw API responses: `data/raw/wiki_cache/` (7,675 gzip files, 75 MB, see SOURCE.md). Reruns are
  offline (`--offline`) and reproduce passages.jsonl and fetch_log.jsonl byte for byte.

## 1. Entities and revision choice

| entity set | source of the list | n |
|---|---|---|
| old_province | "Đơn vị hành chính cấp tỉnh (Việt Nam)" rev 73531195 (2025-05-23) | 63 |
| new_province | same page rev 75581808 (2026-09-23), names only | 34 |
| old_district | "Danh sách đơn vị hành chính cấp huyện của Việt Nam" rev 73518904 (2025-05-18) | 696 |

- **era "old"** is the last revision strictly before 2025-06-12T00:00:00Z of the page that held
  the entity's article at that time (range 2023-05-19 … 2025-06-11). A new province's "old"
  passage is the old revision of its own page. Every one of the 34 new provinces has a page that
  existed before the reform under the same name: Tuyên Quang, Gia Lai and so on.
- **Old-era step-back.** Some pages were edited to the post-reform state *before* the cut-off.
  If the cut-off revision's first sentence calls the entity former ("là một huyện cũ", "trước
  đây là", "nay là/thuộc"), or (districts) fewer than 50% of the gold old wards are named in
  admin_text AND the stated commune count differs from gold, up to 10 earlier revisions of the
  same page (not before 2025-01-01) are tried. The newest clean one is used; if none is clean, the
  passage is dropped. This fired twice, and both were repaired:

  | entity | cut-off revision | problem | used instead |
  |---|---|---|---|
  | Hoài Nhơn (TX, Bình Định) | 73537879 (2025-05-25) | admin_text "7 phường: … Hoài Nhơn Bắc/Đông/Nam/Tây" (post-reform list re-applied by an anonymous IP after a bot revert); 2/17 gold named | 73528069 (2025-05-22, bot revert): 17/17 named, stated 17 |
  | Quỳnh Lưu (Nghệ An) | 73505390 (2025-05-13) | lead "là một huyện cũ" | 72301118 (2025-03-14): same 25/25 commune list, no "cũ" |

- **era "new"** is the last revision of the same page id **before 2026-01-01T00:00:00Z** (range
  2025-09-03 … 2025-12-31), kept only if after 2025-07-15 and not a redirect. The first build
  used the latest revision, which carries 2026 changes that contradict the
  1/7/2025 gold:
  - Bắc Ninh and Đồng Nai list 22 wards as phường that are xã in `wards_new` (infobox "45 phường,
    54 xã" vs gold 33/66; "33 phường, 62 xã" vs gold 23/72);
  - 24 province passages say "chín thành phố trực thuộc trung ương" (gold: 6) or carry 2026 dates;
  - Quảng Ninh district leads say "thuộc thành phố Quảng Ninh".

  With the end-2025 cut-off, all 34 new-province infoboxes match the gold phường/xã/đặc khu counts
  exactly, and no passage mentions "9 thành phố trực thuộc trung ương" or "năm 2026". The
  trade-off is more stale district pages (section 3). `--new-before latest` restores the old
  behaviour; the latest revisions remain in the cache.
- **Title resolution is historical.** Page ids follow pages across moves. For each title we check
  three things: the move log (pages moved away after the cut-off), the merge-history log, and
  redirects as of the cut-off. This was necessary. After the reform, editors moved many articles
  ("Bình Định" became "Bình Định (tỉnh)"; "Cầu Giấy" became "Cầu Giấy (quận cũ)") and moved
  unrelated articles onto the freed titles. For example, "An Dương", "Ân Thi", "Kinh Môn",
  "Lạc Sơn", "Mai Châu", "Nghi Xuân", "Vĩnh Châu" and "Lệ Thủy" now hold articles about Chinese
  places. The naive "revision of this title before the date" method returned those Chinese
  articles for 14 districts. All of them are fixed.
- **Validation** (a wrong passage is worse than a missing one). For an old-era passage:
  - the entity name must be in the lead or infobox;
  - for districts, the entity must be the grammatical subject of the first sentence
    ("<Tên> là (một) huyện/quận/thị xã/thành phố ...");
  - for districts, the old province name must appear.

  Failures are excluded and listed in `fetch_log.jsonl`.

## 2. Coverage

| entity set | old passages | new passages | admin_text present (old / new) |
|---|---|---|---|
| old_province (63) | 63 | 63 | 63 / 63 |
| new_province (34) | 34 | 34 | 34 / 34 |
| old_district (696) | **694** | 696 | 694 / 692 |

There are 759 distinct pages. One page can serve two entities: "Tuyên Quang" is both old province
08 and new province 08. In that case the rows share their text but have different `passage_id`s.

**Gaps:**

- Old passages for **Cầu Giấy** and **Hoàn Kiếm** (Hà Nội) are missing. Their pre-reform
  history was moved or merged, and the resolved page's pre-cut-off content is the article for an
  old ward (Dịch Vọng Hậu, Hàng Trống). Validation rejected both. The merge destinations
  ("Cầu Giấy (quận)", "Hoàn Kiếm (quận)") hold only 2019 and 2006 article revisions, so no 2025
  revision of the quận articles could be recovered.
- 4 new-era district passages have no administrative section: Hoàn Kiếm and Ngũ Hành Sơn (the
  pages now describe the phường), TX Quảng Trị (now describes the phường), and Thường Xuân
  (Thanh Hóa). (With the latest revisions it was 26: 24 Thanh Hóa pages, TX Quảng Trị and Hoàng
  Sa. Three of those Thanh Hóa pages, Nghi Sơn, Sầm Sơn and TP Thanh Hóa, have a "Lịch sử và
  hành chính" section, which the extractor skips on purpose because its heading starts with
  "Lịch sử".) Old-era passages for these districts do have admin_text.

**entity_code join.** All 1,584 passages are joined to `data/processed`:

- 1,536 by name;
- 44 by a spelling-variant key (Hoà/Hòa, Thuỷ/Thủy, Đăk/Đak, Mù Cang/Căng Chải, Ia H'Drai);
- 4 by the infobox "Mã hành chính", accepted only when the code names a district in the same
  province with a similar name (M'Drắk, Phú Quý).

The infobox code agrees with `entity_code` on every passage where both exist, with 3 exceptions.
These need a decision in the canonical tables:

| passage | Wikipedia infobox | data/processed |
|---|---|---|
| Đạ Huoai (Lâm Đồng) | 681 | 682 |
| TP Hoa Lư (Ninh Bình) | 369 | 374 |
| Hòa Vang (Đà Nẵng) | 697 | 497 (697 looks like a Wikipedia typo) |

Phú Mỹ (Bà Rịa – Vũng Tàu) is a thị xã in the Wikipedia list but a thành phố in both its page
and `districts_old`. The passage is kept, with the warning `subtype_differs`.

## 3. Do the "new" passages reflect the reform?

`mentions_reform` (`report.py`) has two levels:

- **strict** (lower bound): an explicit phrase such as "là một tỉnh … cũ" (at most 3 words
  between the type and "cũ"), "34 tỉnh", "202/2025/QH15", "1 tháng 7 năm 2025",
  "nay là một phần của"; or a sentence that combines "2025" with a restructuring word (sáp nhập,
  hợp nhất, sắp xếp, giải thể, chính quyền hai cấp, …).
- **wide** (upper bound, the default): strict plus any descriptive words before "cũ" up to the
  next comma ("là một huyện miền núi biên giới cũ"), "<X> trước đây là <unit>" at the start of a
  line, "<X> cũ là <unit>", and "là (một) đặc khu". To keep historical phrasing out, the "cũ" form
  does not cross "tỉnh/thuộc/của/từng" ("là một huyện thuộc tỉnh Cần Thơ cũ", "tỉnh lỵ của tỉnh
  Kiến Tường cũ"), and "trước đây là" inside a parenthesis does not count ("Huế (trước đây là tỉnh
  …)").

The rate on old-era passages is the false-positive baseline. The wide regex adds no old-era
matches.

| set / era | n | lead, strict | lead, wide | lead + admin_text (wide) | infobox lists only phường/xã/đặc khu |
|---|---|---|---|---|---|
| old_province / old | 63 | 0 | 0 | 2 | 0 |
| old_province / new | 63 | 54 | 54 | 54 | 34 |
| new_province / old | 34 | 0 | 0 | 2 | 0 |
| new_province / new | 34 | 25 | 25 | 25 | **34** |
| old_district / old | 694 | 2 | 2 | 37* | – |
| old_district / new | 696 | **458** | **480** | 487 | – |

\*Old-era district admin sections mostly describe the 2023–2025 commune mergers in force from
2025-01-01, not the July 2025 reform. That is why `new_text_reflects_reform` (below) ignores
admin_text. The 2 old-era district lead matches are historical: Mang Yang "nay là một phần của",
Thủ Đức "là huyện Thủ Đức cũ".

**Provinces.** All 63 + 34 new-era province passages reflect the reform. Every one has an infobox
"Phân chia hành chính" that lists only phường/xã/đặc khu matching the gold counts, and every
new-province passage has the full ward list in its admin section (section 4). 54/63 old-province
leads and 25/34 new-province leads also say it in words. The absorbed provinces say so
explicitly, e.g. "Bình Dương là một tỉnh cũ … (nay tương ứng với phần phía bắc của Thành phố Hồ
Chí Minh)".

**Districts: stale new-era copies.** `quality.jsonl` gives each new-era row
`new_text_reflects_reform` = the `text` (lead + key infobox facts) mentions the reform (wide), OR
the page now describes the replacing commune-level unit (`lead_subject_type` phường/xã/đặc khu),
OR (provinces) the infobox lists only commune-level units. It also gives `text_similarity_to_old`
(difflib ratio vs. the old-era `text`).

- old_district / new: **484/696 reflect the reform; 212 do not**. 209 of those are near-copies of
  the old text (similarity ≥ 0.95), e.g. Bắc Hà (rev 2025-11-19, similarity 1.0): "Bắc Hà là một huyện
  nằm ở phía đông bắc của tỉnh Lào Cai … Phân chia hành chính: 1 thị trấn, 17 xã". Used as "new" context, they would state the pre-reform
  structure as current and give no conflict in "mixed". **The generator must not use new-era
  passages with `new_text_reflects_reform == false`; use template passages for them** (SPEC).
- Trade-off of the end-2025 cut-off: with the latest (2026) revisions, the same flag marks only 57
  district pages as stale (49 near-copies), but those revisions carry the 2026 drift above. A district passage's
  only "new" content is the line "X là một huyện cũ", which a template reproduces, so one dated
  era definition for all pages was chosen over a per-set mix.
- 19 new-era district pages now describe the commune-level unit that replaced the district
  (`lead_subject_type`; also a warning in `fetch_log.jsonl`): 12 đặc khu, 4 phường (Cầu Giấy,
  Hoàn Kiếm, Ngũ Hành Sơn, Quảng Trị), 3 xã (Kỳ Anh, Phù Mỹ, Tây Sơn). Caveat: the huyện Kỳ Anh
  page (end-2025) reads "Kỳ Anh là một Xã ven biển …" but keeps the district's infobox facts
  (761.62 km², 120,518 people), so its numbers are not those of Xã Kỳ Anh.
- **The admin_text of new-era district pages still lists the old (pre-reform) communes**, because
  the district no longer exists. Use these as "this district is gone" evidence, not as the new
  ward structure.

## 4. Do the admin sections list ward names?

Ward-name recall is measured against `data/processed`. A name counts as found when it appears as a
table cell, a list item, or a comma-, "·"- or "và"-separated token. Matching ignores tone-mark
placement and dash style.

| set / era | gold wards | entities with ≥90% of their wards named | ≥50% | micro recall |
|---|---|---|---|---|
| new_province / new vs `wards_new` (3,321) | 3,321 | **34/34** | 34/34 | **0.997** |
| old_district / old vs `wards_old` | 10,035 | 657/694 | 688/694 | 0.989 |

- **New provinces.** Every province page lists its full new ward table (name | area | population).
  All 10 misses are spelling differences: Lào Cai "Phong Du Hạ/Thượng" (gold "Phong Dụ"), Gia Lai
  "Đăk Rong / Đăk Sơmei / Đăk Pơ / K'Dang / S'Ró / H'Ra / K'Bang" (gold "Đak …", "KDang", "SRó",
  "Hra", "Kbang"), Đắk Lắk "Ea H'Leo" spelling.
- **Old ward lists live on the district pages**, not the province pages. Old province admin
  sections list districts with their commune counts only.
- **Stated commune count vs gold.** On 22 old-era district pages the stated count ("Huyện X có N
  đơn vị hành chính cấp xã") differs from the gold count (591 match; 81 give no count). Examples:
  Vụ Bản 18 vs 14, Ân Thi 21 vs 18, Gio Linh 17 vs 14, Yên Mô 17 vs 14. Revision age does **not**
  explain these: 19 of the 22 are on 2025 revisions (only Ân Thi 2024-11-20, Đô Lương 2024-12-17
  and Tuần Giáo 2023-10-04 predate 2025), and 97 of the 108 pre-2025 revisions state the gold
  count. Most likely the editors updated the revision but not the count sentence after the
  2025-01-01 commune mergers. Not adjudicated.
- **The stated count is not a freshness signal on its own.** Triệu Phong (rev 2025-05-01) states
  the gold count 16 but lists Triệu Sơn, Triệu Lăng, Triệu Vân and Triệu An, which are not gold
  old wards. `quality.jsonl` therefore also gives `admin_listed_names` (names enumerated in the
  "có N đơn vị hành chính cấp xã …, bao gồm …" sentence) and `admin_names_not_in_gold`. 25 old-era
  district passages list 35 names not in gold. Most are spellings in the Central Highlands
  (Đắk/Đăk, Ea Kuếh); the stale ones are Triệu Phong (4), Thường Tín (Nụ Hiệp, Thống Nhất) and
  Gia Lộc (Gia Khánh).
- The premature case (Hoài Nhơn, updated *too early*, see section 1) is now repaired by the
  step-back.
- **Lower recall in the Central Highlands** (Gia Lai, Đắk Lắk, Kon Tum, Đắk Nông, Lâm Đồng) is
  mostly a spelling issue (Ia/Ea, Đăk/Đắk, apostrophes), not missing content.

## 5. Caveats

- **2026 events.** Per Wikipedia (not verified against official sources), three provinces became
  centrally-run cities in 2026: Đồng Nai (from 2026-04-30), Quảng Ninh (2026-09-01, NQ 36/2026/QH16)
  and Bắc Ninh (2026-09-20, NQ 39/2026/QH16). The country is now "25 tỉnh, 9 thành phố", and the
  HCMC page mentions a 2026-08 plan to turn 29 xã into phường. The passages no longer reflect any
  of this (end-2025 cut-off). The eval's `+sysdate` condition says "Hôm nay là ngày 13/10/2026",
  while gold and passages describe the end-2025 state. That is an evaluation-design question
  (addressed in the paper's data-version paragraph).
- **Cross-check of the reform list.**
  - The Wikipedia "Năm 2025" list of 23 mergers matches `provinces_new.merged_from` exactly.
  - The 11 provinces kept as-is match SPEC: Hà Nội, Huế, Lai Châu, Điện Biên, Sơn La, Lạng Sơn,
    Quảng Ninh, Thanh Hóa, Nghệ An, Hà Tĩnh, Cao Bằng.
  - Wikipedia writes "Bà Rịa – Vũng Tàu" with an en dash; `data/processed` uses a hyphen.
- **`text` is short for districts** (median 330 chars), because district leads are one or two
  sentences. Infobox key facts are appended when the lead is under 1,200 chars. Province leads
  have a median of about 1,000 chars.
- **admin_text cap.** No admin section reached the 8,000-char cap. The largest is Thái Nguyên new
  at 7.1k.
- **The reform-mention detector is regex-based.** Report strict–wide as a range. 12 random
  "reflects" district leads were read by hand and were all correct. Only about 10 of the 1,584
  passages were read end to end; everything else rests on the automatic checks.
- **Unverified.** Infobox codes, ward spellings and 2026 events come from Wikipedia. The 22
  count mismatches above were not adjudicated; whether Wikipedia or the gold table is right is
  unknown.

## 6. Recommendations for the generator

- **Provinces: Wikipedia is usable for both eras** (100% coverage, all new-era passages consistent
  with the gold counts). For the "new" condition, `new_province/new` `admin_text` contains the full
  ward list of each new province.
- **Ward membership: use the old district passage** (`old_district/old`, 694/696) for the old
  location, and the new province passage for the new one. Prefer old district passages with
  `stated_count_matches_gold != false` and empty `admin_names_not_in_gold`, or use template
  passages.
- **New-era district passages:** use only those with `new_text_reflects_reform == true` (484/696).
- **Use template passages** for:
  - Cầu Giấy and Hoàn Kiếm (old);
  - the 212 stale new-era district passages;
  - any item whose gold ward name is not found in the chosen passage's admin_text. Check this per
    item with `viadmin.wiki.report.name_in_text(name, admin_text)`; `quality.jsonl` gives only
    per-passage totals.
