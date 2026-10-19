# ViAdminShift — project specification

Working title: *Did the Map Change? Benchmarking LLMs on Vietnam's 2025 Administrative Restructuring*.

## Research questions
- **RQ1 (closed-book):** Do LLMs know the post-1/7/2025 administrative structure? Is the
  *surface* fact ("34 provinces", "Bình Dương merged into TP.HCM") known while *entailed,
  ward-level* facts are not? (surface-vs-deep update gap)
- **RQ2 (RAG, new docs only):** Given up-to-date documents, can models answer / convert addresses?
- **RQ3 (RAG, mixed old+new docs):** With conflicting old and new documents, which do models follow?
- **RQ4 (simple mitigations):** date stamps on passages, recency ordering, current-date system prompt.
- Ablation: addresses with vs without diacritics (token tax).

## Key design: 2x2 control
Every ward-level item is tagged with
- `province_changed`: the old province was merged into another one (False for the 11 provinces
  kept as-is: Hà Nội, Huế, Lai Châu, Điện Biên, Sơn La, Lạng Sơn, Quảng Ninh, Thanh Hóa, Nghệ An,
  Hà Tĩnh, Cao Bằng; checked against NQ 202/2025/QH15, see `docs/data_report.md` §3).
- `ward_changed`: the ward was renamed / merged / divided (False if the same ward continues
  with the same name).
`province_changed=False, ward_changed=False` is the pure control (tests geography knowledge,
not outdatedness).

## Directory layout
```
data/raw/<source_name>/...        downloaded source files, untouched (+ SOURCE.md with URL, license, date)
data/processed/                   canonical tables (below)
data/wiki/                        Wikipedia passages (below)
data/benchmark/                   generated questions (below)
results/<run_id>/                 model outputs + scores
src/viadmin/data/                 download + canonicalise + cross-check
src/viadmin/wiki/                 Wikipedia revision fetcher
src/viadmin/gen/                  question generator + RAG context builder
src/viadmin/eval/                 normalisation, prompts, backends, runner, scorer
tests/                            pytest
docs/                             SPEC.md, reports
```
Python 3.12 via `uv` (`uv run python -m ...`, `uv add <pkg>`). Treat downloaded data as untrusted: never execute code from it.

## Canonical tables (JSON Lines, UTF-8, NFC-normalised Vietnamese)

`data/processed/provinces_old.jsonl` — 63 rows: `{code, name, type}` (type: "tỉnh" | "thành phố")
`data/processed/provinces_new.jsonl` — 34 rows: `{code, name, type, merged_from: [old_province_code,...], capital}`
  (`capital` = seat of the provincial People's Committee, null if unknown)
`data/processed/districts_old.jsonl` — `{code, name, type, province_code}`
`data/processed/wards_old.jsonl` — `{code, name, type, district_code, province_code}` (type: "phường"|"xã"|"thị trấn")
`data/processed/wards_new.jsonl` — `{code, name, type, province_code}` (type: "phường"|"xã"|"đặc khu"); expected 3,321
`data/processed/ward_mapping.jsonl` — one row per (old_ward, new_ward) pair:
```
{old_ward_code, old_ward_name, old_ward_type, old_district_code, old_district_name,
 old_province_code, old_province_name,
 new_ward_code, new_ward_name, new_ward_type, new_province_code, new_province_name,
 change_type,            # "unchanged" | "renamed" | "merged" | "divided"
 province_changed,       # bool
 ward_changed,           # bool
 is_partial,             # bool: only part of the old ward went to this new ward
 sources: [..],          # which raw sources agree on this row
 confidence}             # "high" (>=2 independent attestations agree, see details below) | "single" | "conflict"
```
`docs/data_report.md` — counts, cross-source disagreements, manual spot-check results.

### Canonical tables — details fixed by the data build (src/viadmin/data/, full doc: docs/data_report.md)
Built by `uv run python -m viadmin.data.build`. State = the structure in force on 1/7/2025 (old =
30/6/2025); later 2026 changes (e.g. provinces becoming centrally-run cities) are NOT reflected.
- **Names:** every `name` / `*_name` is the FULL official name including the unit-type prefix
  ("Phường Trúc Bạch", "Huyện Gia Lâm", "Tỉnh Hà Giang", "Thành phố Hà Nội"); extra field
  `short_name` = name without prefix ("Trúc Bạch", "Hà Nội"; "Phường 1" → short "1"; numbered wards
  may also use Roman numerals, e.g. "Phường IV" (TP Tây Ninh), "Phường I" (Vị Thanh)). Spelling is
  the registry's (GSO/NSO), incl. its tone-mark placement ("Hoà" and "Hòa" both occur): match names
  with `viadmin.data.normalize.name_key` (tone-placement/case/apostrophe-insensitive), never `==`.
  **Old ward names:** when the GSO registry and the NSO conversion table spell an old ward
  differently, the UBTVQH ward-level resolution (NQ 1654–1687/NQ-UBTVQH15, clause forming the ward's
  new unit) decides; when they agree, that spelling is kept. 176 old wards take the resolution/NSO
  spelling (e.g. "Xã Kim Chung" → "Xã Kim Trung", "Xã Hưng Yên" → "Xã Hưng Yên Nam", "Thị trấn Phó
  Bảng" → "Thị trấn Phố Bảng"), 4 keep the registry's (resolution agrees, or a documented exception);
  the other spelling is kept as `name_alt` / `old_ward_name_alt`. Unit type changes only if the
  resolution states it.
  Apostrophes are normalised to ASCII `'` ("Cư M'gar"). `type` is lowercase.
- **Codes:** GSO/NSO codes as zero-padded strings: province 2 digits, district 3, ward 5. A new
  province keeps the code of one of its components (new Bắc Ninh = 24, old Bắc Giang's code), so
  never infer `province_changed` from code or name equality.
- `provinces_old`: + `short_name`. Type "thành phố" = the 6 centrally-run cities (incl. Huế since 1/1/2025).
- `provinces_new`: + `short_name`, `seat_old_province_code` (old province whose centre hosts the new
  provincial political-administrative centre, NQ 60-NQ/TW; e.g. Lào Cai → "15" Yên Bái).
  `capital` is null for all rows (the exact seat ward is not verified).
- `districts_old`: 696 rows, + `short_name`, `has_wards` (false for the 5 island districts without a
  commune level: Bạch Long Vĩ, Cồn Cỏ, Hoàng Sa, Lý Sơn, Côn Đảo). type: quận|huyện|thị xã|thành phố.
- `wards_old`: 10,035 rows (official pre-reform count), + `short_name`, `name_alt` (non-canonical
  spelling of the name from the other registry, null if none; never a verified-wrong value).
- `wards_new`: 3,321 rows, + `short_name`, `resolution` (e.g. "1656/NQ-UBTVQH15"). The 5 đặc khu
  formed from island districts (codes 11948, 19742, 20333, 21548, 26732) have NO ward_mapping row.
- `ward_mapping` (10,566 rows) definitions, per row (o = old ward, n = new ward):
  - `n_new_targets` = #distinct new wards o maps to; `n_old_sources` = #distinct old wards n is formed from.
  - `change_type` (precedence top-down): `divided` if n_new_targets > 1 (o was split; ALL its rows are
    divided, even the row whose new ward keeps o's name); else `merged` if n_old_sources > 1 (o went
    wholly into a new ward formed from several old wards — includes the case where the new ward keeps
    o's name, see `name_changed`); else `unchanged` if same name (by `name_key`) or the NSO note says
    "Giữ nguyên" with same unit type (then `spelling_variant`=true when old and new are spelt
    differently; 0 rows since old names follow the resolution); else `renamed` (1:1, different name or unit type,
    e.g. "Thị trấn Mường Lát" → "Xã Mường Lát", "Xã Thổ Châu" → "Đặc khu Thổ Châu").
  - `ward_changed` = change_type != "unchanged". `province_changed` = the new province has
    len(merged_from) > 1 (False exactly for the 11 provinces kept by NQ 202/2025/QH15).
  - `is_partial` = n_new_targets > 1.
  - `sources` ⊆ ["nso", "resolution", "vietnamadminunits", "undertheseanlp", "vietaddr"]; "nso"
    (official NSO conversion table) is the backbone and present on every row except pairs the NSO
    table lacks but the resolution states (`RESOLUTION_ADDED_PAIRS` in build.py, currently 1:
    Xã Hòa Thắng → Xã Hồng Thái, NQ 1671 k.46), whose `sources[0]` is "resolution".
    "resolution" = the pair was checked BY HAND against the resolution text (only a few rows; the
    automatic clause parse is a check, not a source). Independent attestations: A = nso
    (+ derivative vietaddr), B = vietnamadminunits (+ derivative undertheseanlp), R = resolution.
  - `confidence`: "high" = at least two of {A, B, R} contain the pair; "conflict" = only nso has it
    and vietnamadminunits maps o elsewhere; "single" = only nso, B silent. (Currently all rows high.)
  - extensions: `name_changed` (old vs new full name differ by name_key; old = canonical spelling),
    `province_name_changed` (old vs new province full name differ by name_key — False e.g. for old
    Tuyên Quang → new Tuyên Quang although `province_changed`=True), `surface_answer_changed` =
    name_changed OR province_name_changed (False ⇒ the "ward, province" answer is literally the same
    before and after: 1,147 rows outside the pure-control cell; the generator must stratify on or
    exclude these in "changed" cells, else outdated-rate is biased), `spelling_variant`,
    `target_set_agrees` (both lineages give the identical set of new wards for o), `n_old_sources`,
    `n_new_targets`, `nso_note` (NSO "Ghi chú": "Nhập toàn bộ" | "Nhập một phần…" | "Giữ nguyên" | …;
    for rows added from the resolution it is build-generated: "Nhập một phần (bổ sung theo NQ …)"),
    `bando_mentions_old_ward` (o named in the sapnhap.bando.com.vn composition text of n, compared
    without spaces/hyphens/type prefix and with both spellings; for bando's "Không sáp nhập" = n is
    1:1; weak aid, null if text unavailable), `resolution`, `old_ward_name_alt` (= wards_old.name_alt:
    the non-canonical spelling, e.g. "Thị trấn Phó Bảng" for canonical "Thị trấn Phố Bảng"; else
    null — use as an extra alias for old-name answers, never as the gold).
  - Non-ward areas merged into new wards have no row: the 5 island districts above, the Kim Sơn
    coastal mudflat ("khu vực bãi bồi ven biển") → Xã Kim Đông (NQ 1674 k.97) and "Trường bắn TB1" →
    Xã Biên Sơn (NQ 1658 k.34). T2 composition items for Kim Đông / Biên Sơn must exclude or mention them.
- Extra outputs: `data/processed/build_stats.json` (all counts), `data/processed/crosscheck_issues.jsonl`
  (every disagreement / data fix, with `kind`).

## Wikipedia passages
`data/wiki/passages.jsonl` (built by `uv run python -m viadmin.wiki.build`; report: docs/wiki_report.md):
`{passage_id, title, entity_type ("province"|"district"), entity_code, era ("old"|"new"),
  revision_id, revision_timestamp, text,
  # extensions (Wikipedia build):
  entity_set ("old_province"|"new_province"|"old_district"), entity_name, entity_subtype,
  parent_name, entity_code_method, wiki_admin_code, lead_subject_type, page_id,
  admin_heading, admin_text, infobox_text}`
- One row per (entity, era). A page can serve two entities (e.g. the "Tuyên Quang" page is both
  old province 08 and new province 08), so rows may share text but have distinct `passage_id`s
  (`wiki-<entityset>-<slug>-<era>`, e.g. `wiki-oldprovince-binh-duong-old`,
  `wiki-olddistrict-tien-giang--huyen-chau-thanh-old`).
- `entity_set` says which canonical table the entity belongs to; `entity_code` is the code in
  that table (`provinces_old` / `provinces_new` / `districts_old`), joined by normalised name
  (districts: name + old province + type); null if the join failed.
- `entity_name`: name as in the Wikipedia list (no "Tỉnh"/"Huyện" prefix, except
  "Thành phố Hồ Chí Minh"); `entity_subtype` (districts only): huyện|quận|thị xã|thành phố|huyện đảo;
  `parent_name` (districts only): old province name.
- `entity_code_method`: "name" | "name_variant" (tone-placement/Đăk-Đak/spacing variants) |
  "wiki_infobox_code" (infobox code names a same-province district with a similar name).
- `lead_subject_type`: districts only — the unit type the lead's first sentence predicates of the
  entity ("huyện", "quận", ...; for era "new" it can be "phường"/"đặc khu" when the page now describes
  the commune-level unit that replaced the district).
- `wiki_admin_code`: "Mã hành chính" read from the page's infobox (null if absent) — a cross-check
  of `entity_code` (for the era matching the entity set).
- era "old": the last revision **strictly before 2025-06-12T00:00:00Z** (resolution date) of the page
  that carried the entity's article at that time (titles resolved historically: redirects as of the
  cut-off and later page moves are followed). **Step-back:** if that revision already shows the
  post-reform state — its first sentence calls the entity former ("là một huyện cũ", "trước đây
  là", "nay là/thuộc"), or (districts) < 50% of the gold old wards are named in admin_text AND the
  stated commune count differs from gold — up to 10 earlier revisions of the same page (not before
  2025-01-01) are tried and the newest clean one is used; if none is clean the passage is dropped.
  Logged in fetch_log.jsonl (`status` "stepped_back" / "rejected_stale_content"; the cut-off
  revision's own line gets status "superseded_stale").
- era "new": the last revision of the same page **strictly before 2026-01-01T00:00:00Z** (fixer
  pass; was "latest"), kept only if after 2025-07-15 and not a redirect. Reason: latest
  (2026) revisions contradict the 1/7/2025 gold — Bắc Ninh / Đồng Nai / Quảng Ninh became
  centrally-run cities in 2026 per Wikipedia ("9 thành phố trực thuộc trung ương"; 22 Bắc Ninh /
  Đồng Nai wards listed as phường that are xã in wards_new). End-2025 revisions match the gold
  counts. `--new-before latest` restores the old behaviour. Pages not edited between 2025-07-15 and
  2026-01-01 have no new-era passage (fetch_log status "no_new_revision").
- `text`: plain text of the lead (no wiki markup, references, hatnotes, infobox), cut at a sentence
  boundary at <= 1,500 chars; if the lead is shorter than 1,200 chars, key infobox facts are appended as
  "key: value" lines (Thủ phủ / Trụ sở UBND / Phân chia hành chính / Diện tích / Dân số / Mã hành chính...).
- `admin_text`: the administrative-divisions section ("Hành chính", "Đơn vị hành chính",
  "Phân chia hành chính", "Tổ chức hành chính", ... incl. subsections) as plain text, tables rendered
  as one row per line with cells joined by " | ", capped at 8,000 chars at a line boundary; null if
  the page has no such section. `admin_heading` = the heading used.
- `infobox_text`: all infobox rows as "key: value" lines (null if no infobox).
- `data/wiki/quality.jsonl` (per passage_id): `mentions_reform` (wide regex, upper bound),
  `mentions_reform_strict` (lower bound), `stated_commune_count`, and for
  new_province/new + old_district/old: `gold_wards`, `gold_wards_named_in_admin_text`,
  `stated_count_matches_gold` (vs data/processed). old_district/old also: `admin_listed_names`
  (#names in the "có N đơn vị hành chính cấp xã ..., bao gồm ..." sentence) and
  `admin_names_not_in_gold` (listed names that are not gold old wards of that district: stale or
  differently-spelt lists — `stated_count_matches_gold` alone is NOT a freshness signal, e.g. Triệu
  Phong states the gold count 16 but lists 4 communes merged on 2025-01-01). Every era "new" row also:
  `text_similarity_to_old` (difflib ratio of `text` vs the same entity's old `text`, null if none)
  and `new_text_reflects_reform` = mentions_reform (wide) computed on `text` ONLY (not admin_text,
  whose old-era district versions already mention the 2025-01-01 commune mergers) OR lead_subject_type ∈ {phường, xã, đặc khu,
  thị trấn} OR (provinces) infobox lists only phường/xã/đặc khu.
  **Generator rule:** a new-era passage with `new_text_reflects_reform == false` is a stale copy of
  the pre-reform page (states the old structure as current); do NOT use it in "new"/"mixed" contexts
  — use a template passage instead. New-era *district* admin_text still lists the old communes
  (the district no longer exists): it is "this district is gone" evidence, not the new structure.
- All text NFC-normalised. Passages failing validation (entity name not in lead; for districts also
  old province name and unit type in the old-era lead) are excluded and listed in
  `data/wiki/fetch_log.jsonl` together with missing revisions.

## Benchmark items
`data/benchmark/items.jsonl`:
```
{id, qtype,          # "T1_membership" | "T2_composition" | "T3_existence" | "T4_address" | "T6_reverse" | "T0_headline"
                     #  | "T1_newname" | "T5_ward_successor"   (depth addendum below; added to viadmin.eval.validate.QTYPES)
 question,           # Vietnamese, self-contained
 format,             # "mcq" | "short"
 choices,            # list[str] for mcq (4 options, shuffled deterministically by id), else null
 answer,             # gold: letter for mcq, canonical string for short
 answer_aliases,     # list[str] accepted for short answers
 old_answer,         # the answer that would be correct under the OLD structure (null if N/A)
 meta: {province_changed, ward_changed, change_type, old_province_code, new_province_code,
        old_ward_code, new_ward_code, consistency_group, has_diacritics}}
```
- `old_answer` lets us measure "answered with outdated knowledge" separately from "wrong".
- `consistency_group`: links a T6_reverse item (old province → new province) with the T1 items
  for wards inside that old province, to measure surface-vs-deep consistency.
- Ambiguous ward names (e.g. "Phường 1") must always be disambiguated with district + old province.
- Seeded, deterministic generation (seed 13). Stratified sampling over the 2x2 control cells.

### Knowledge depth levels (addendum — generator MUST implement)
A T1 question that names the old province ("X, trước đây thuộc huyện D, tỉnh P") only tests whether
the model knows P→Q and composes it; it is NOT deep ward-level knowledge. Tag every item with
`meta.depth` and generate all three levels:
- `surface`  — T0_headline, T6_reverse (old province → new province), T2_composition.
- `compose`  — T1_membership with the old province named in the question (ripple/composition test).
               Analysis: accuracy on compose items GIVEN the model got the matching T6 item right.
- `deep`     — requires ward-level facts that cannot be derived from province-level knowledge:
  * `T1_newname`: "Phường/Xã <NEW ward name> (đơn vị hành chính cấp xã sau ngày 1/7/2025) thuộc
    tỉnh/thành phố nào?" Only new ward names that are unique nationwide among new wards. Gold = new
    province. Set old_answer = the old province when the new name coincides with an old ward name
    located in a different (absorbed) old province (then an outdated answer is identifiable); record
    `meta.name_reused_from_old` (bool).
  * `T5_ward_successor` (MCQ + short): "Sau sắp xếp năm 2025, xã/phường X (huyện D, tỉnh P cũ) nay thuộc
    xã/phường mới nào?" Gold = new ward name (non-divided, confidence high only). MCQ distractors: other
    new wards in the same new province, never one that also received part of X.
  * T4_address is also `deep` (new ward part) — score province and ward components separately.
Control cells are small (pc0_wc0 = 43 rows, pc1_wc0 = 84 rows): use ALL of them, do not subsample;
report counts; analysis will use bootstrap CIs.

### Cue factor (addendum 2 — generator MUST implement)
Pilot evidence (DeepSeek-V4.1-Flash): province-level facts are answered correctly when the question
mentions the reform ("Sau đợt sắp xếp đơn vị hành chính năm 2025, …") but answered with the OLD
structure when it does not ("Hiện nay, … thuộc tỉnh nào?"). So for T6_reverse, T1_membership (compose),
T1_newname and T5_ward_successor generate THREE variants of every item, sharing the same gold:
- `meta.cue = "none"`  — a plain present-tense question a user would type with an OLD address. It must NOT
  contain any temporal/change marker: no "trước đây", no "cũ", no "sau sắp xếp", no "hiện nay còn",
  no "mới". E.g. "Xã Đại Hợp, huyện Tứ Kỳ, tỉnh Hải Dương thuộc tỉnh/thành phố nào?" /
  "Địa bàn tỉnh Hà Giang thuộc đơn vị hành chính cấp tỉnh nào?" (gold = the CURRENT answer, by convention
  questions are about the present; state this convention in the paper).
- `meta.cue = "date"`  — the same question prefixed with "Tính đến tháng 10/2026, " (temporal grounding
  without naming the event; this is the closed-book analogue of the sysdate mitigation).
- `meta.cue = "reform"` — prefixed with "Sau đợt sắp xếp đơn vị hành chính năm 2025, " (names the event).
Link the three via `meta.cue_group`. Ids: `<base_id>__none` / `__date` / `__reform`. Keep all other wording identical.
Analysis = depth (surface/compose/deep) × cue (none/date/reform) × 2x2 control cell. Control check: in models
that do not know the reform, cue=reform must NOT raise accuracy (it asserts a premise but not the answer).

### Benchmark items — details fixed by the generator (src/viadmin/gen/, report: docs/benchmark_report.md)
Built by `uv run python -m viadmin.gen.generate` (seed 13, per-key RNG `random.Random(f"13:{key}")`,
byte-identical re-runs; sha256 in `data/benchmark/build_stats.json`); checked by
`uv run python -m viadmin.gen.validate` and `tests/test_gen_*.py`. 7,995 items.
- **Ids / order:** `T0-NN`, `T6-<oldprov>-<mcq|short>__<cue>`, `T1-<oldward>__<cue>`, `T1N-<newward>__<cue>`,
  `T5-<oldward>-<mcq|short>__<cue>`, `T4-<oldward>` (+ twin `T4-<oldward>-nd`), `T3-<prov|dist|neww|oldw|keepw>-<code>`,
  `T2-<newprov>`. File order interleaves qtypes round-robin (cue variants / twins adjacent) so `--limit N` is a mix.
  MCQ choice order is shuffled by `cue_group` (identical across the three cue variants).
- **Wording (cue=none base strings; date/reform variants only add the SPEC prefix):** T6 "Địa bàn tỉnh P thuộc
  đơn vị hành chính cấp tỉnh nào?"; T1 "Xã X, huyện D, tỉnh P thuộc tỉnh/thành phố nào?"; T1_newname "Xã Y thuộc
  tỉnh/thành phố nào?"; T5 "Địa bàn xã X, huyện D, tỉnh P thuộc đơn vị hành chính cấp xã nào?" (old-structure
  answer = X itself, so it is identifiable). These replace earlier "Hiện nay … (trước đây …)" templates (forbidden markers).
  T4 "Địa chỉ cũ: Số n, thôn/ấp/tổ dân phố/khu phố m, xã X, huyện D, tỉnh P. Địa chỉ này hiện nay được viết theo đơn vị
  hành chính hai cấp (cấp xã, cấp tỉnh) như thế nào?" (house part fake, seeded; "ấp/khu phố" for province code ≥ 70).
- **Formats:** T1, T1_newname, T2, T3 MCQ only; T6, T5 MCQ + short; T4 short; T0 7 MCQ + 5 short.
- **T3_existence is a 4-way MCQ** (linter needs 4 choices): "Có, là ĐVHC cấp tỉnh / cấp huyện / cấp xã" or "Không, hiện
  không còn (hoặc không phải) là một ĐVHC". Entities: 63 old provinces (absorbed → Không, old answer cấp tỉnh; kept or
  namesake → cấp tỉnh), 60 old districts (Không; old cấp huyện; districts that became a đặc khu excluded), 60 new wards
  (cấp xã; old answer Không — names absent from the namesake old province), 65 abolished old wards (Không; old cấp xã;
  bare name absent from ALL new wards nationwide), 60 unchanged wards (cấp xã). Balance is on `meta.t3_exists` (154/154).
- **2x2 sampling rule:** only `confidence=="high"` rows (currently all). Control cells pc0_wc0 (43) and pc1_wc0 (84) are
  used in full; in the changed cells an old ward is eligible only when the asked surface changed: province_changed ⇒
  `province_name_changed`, ward_changed ⇒ the BARE ward name changed for every target (unit-type-only changes such as
  "Thị trấn Trà Lĩnh → Xã Trà Lĩnh" count as unchanged, because the scorer strips unit prefixes). Hence pc1_wc1 contains
  only wards of absorbed provinces; the 36 namesake rows of pc1_wc0 keep `old_answer=null`,
  `meta.surface_answer_changed=false`, `meta.cell_pure=false` (filter them for a pure cell). Large cells: 400 (T1),
  150 (T5), ~336 (T4) old wards, spread round-robin over old provinces. Divided wards are excluded from T4/T5 (no unique
  new ward) and from T3 ward items; T1 keeps them (the province is unique).
- **T5 extra exclusion:** an old ward whose bare name is the name of ANOTHER current ward of the same new province (264 old
  wards) is skipped (the outdated choice would be a real, different ward).
- **T1_newname:** bare name unique among the 3,321 new wards; old namesakes = old wards (incl. `name_alt`) and old districts
  with the same bare name; skipped when they lie in >1 old province or outside the gold's components; `old_answer` = that
  old province when its name differs from the gold (`meta.old_answer_province`, `meta.name_reused_from_old`). 240 base items:
  120 identifiable-outdated, 60 other merged-province, 60 kept-province.
- **Distractors:** province MCQs = old province (when its name changed) + nearest new provinces by centroid distance
  (vietnamadminunits coordinates, ranking only); T5 = old ward name (when changed) + nearest new wards of the same new
  province; T2 = "Chỉ có tỉnh Y (giữ nguyên…)" (= old answer) + swap/superset/subset sets built from neighbouring old
  provinces. No two choices collide under `normalize_name` or without diacritics.
- **Diacritics ablation:** 400 T4 items (stratified by cell: 22/168/42/168) have a twin `…-nd` whose ADDRESS (not the
  instruction) is diacritic-free; same gold; both carry `meta.twin_id = <id of the diacritised item>`.
- **meta extensions:** `depth` (T0/T6/T2 + T3 province/district = surface; T1 = compose; T1_newname/T5/T4 + T3 ward kinds =
  deep), `cue`, `cue_group`, `surface_answer_changed` (for the asked answer), `cell_pure`, `name_changed`,
  `province_name_changed`, `old_ward_name`, `old_district_name`, `old_province_name`, `new_ward_name`, `new_province_name`,
  `gold_name_in_question` (T4/T5: the gold ward's bare name occurs in the question, e.g. named after the old district),
  `divided`, `new_ward_codes` (T1), T4: `gold_ward`, `gold_province`, `old_address`, `house_part`, `twin_id`; T3:
  `entity_kind`, `entity_name`, `t3_gold_kind` (P/D/W/N), `t3_exists`, `name_survives_as_ward` (districts); T2:
  `components`; T0: `fact`; `context_source` / `context_source_old` ("wiki" | "template": source of the new / old passage);
  `old_answer_dropped` (short items whose old answer the scorer could not tell apart from the gold).
- `consistency_group` = old province code on T6, T1, T5, T4 items (T1_newname/T2/T3/T0: null). NOTE: `metrics.consistency`
  pools all cues and both T6 formats into "surface"; analyses should filter by `meta.cue` / format first.

`data/benchmark/contexts.jsonl`: `{item_id, condition ("none"|"new"|"mixed"), passages: [passage_id,...]}`
- "mixed": the relevant old + new passage(s), order randomised deterministically.
- Generator details: one row per (item, condition) for every item. none → `[]`; new → exactly one era-"new" passage
  whose text contains the gold names (`must_contain`, re-verified by the validator; numbered wards are matched with their
  prefix, "Phường 4"); mixed → one era-"old" passage + the SAME new passage, shuffled by the item's cue group / twin id;
  the old passage contains the old answer when it changed (`must_contain_old`); every old passage is older than its new
  partner (`+recency` relies on it); total ≤ 2,500 chars. Extra row fields: `sources` (wiki|template per passage),
  `eras`, `must_contain`, `must_contain_old`.
- Passages live in `data/benchmark/template_passages.jsonl` (wiki schema subset + `source`), two kinds:
  `source="wiki_excerpt"` (id `wikix_<wiki passage_id>_<sha1[:8]>`, `derived_from` = wiki passage_id; title, era,
  revision_id, revision_timestamp copied; text = lead sentence(s) + the relevant admin_text line, ≤ 1,250 chars) and
  `source="template"` (id `tpl_<kind>_<code>`, encyclopedic Vietnamese generated from data/processed; fixed synthetic
  timestamps: era old 2025-06-01T00:00:00Z, era new 2025-10-01T00:00:00Z). Raw wiki rows are never referenced directly
  (their admin_text is up to 8,000 chars). New-era wiki rows with `new_text_reflects_reform == false` are never used;
  old-district wiki rows are used only when `stated_count_matches_gold != false`, `admin_names_not_in_gold` is empty and
  `mentions_reform` is false.

## Evaluation
- Prompt conditions: `closed`, `rag_new`, `rag_mixed`, plus mitigations `rag_mixed+date`,
  `rag_mixed+recency`, `rag_mixed+sysdate`.
- Answers: MCQ → letter extraction; short → normalised match (NFC, lowercase, strip admin prefixes
  like "tỉnh/thành phố/tp./phường/xã/thị trấn/đặc khu", collapse whitespace; alias table e.g.
  "TP.HCM" = "Thành phố Hồ Chí Minh"; diacritic-insensitive match reported separately).
- Each prediction is labelled `correct` | `outdated` (matches old_answer) | `other_wrong` | `invalid`.
- Backends: `vllm` (rented GPU), `hf` (transformers, 4-bit on the 4 GB laptop GPU), `openai`
  (any OpenAI-compatible endpoint). Greedy decoding, max_new_tokens small, thinking disabled.
- Output: `results/<run_id>/predictions.jsonl` and `results/<run_id>/scores.json`.

### Evaluation — details fixed by the eval harness (src/viadmin/eval/, full doc: docs/eval_README.md)
- Conditions are `base[+mitigation]*` (composable, e.g. `rag_mixed+date+sysdate`; `closed+sysdate` allowed).
  closed → contexts condition "none" (rows optional); rag_new → "new"; rag_mixed* → "mixed".
  `+date`: each passage header shows "(cập nhật ngày dd/mm/yyyy)" from `revision_timestamp`, order
  unchanged, no extra instruction. `+recency`: passages sorted oldest → newest (newest last) plus one
  sentence stating that order, no dates. `+sysdate`: system prompt + "Hôm nay là ngày 13/10/2026."
  (configurable `--today`). Base system prompt identical across conditions.
- Passage body = `text` by default; `--passage-fields text,admin_text` appends other fields.
  Passage ids are looked up in `data/wiki/passages.jsonl` and `data/benchmark/template_passages.jsonl`
  (same schema; at least `passage_id, title, revision_timestamp, text`). Missing ids = hard error.
- **Gold answer format contract (generator):** short `answer` is a canonical name WITH its admin
  prefix ("Phường Sài Gòn", "Thành phố Hồ Chí Minh") or, for addresses, comma-separated segments
  from smallest to largest unit ("Phường Sài Gòn, Thành phố Hồ Chí Minh"); scoring is segment-wise
  (extra leading street segments and a trailing "Việt Nam" are tolerated). Numeric answers
  (T0 counts) are plain digits ("34"). Keep the prefix on ward golds: for wards whose bare name is a
  province name (43 in wards_new, e.g. "Phường Bình Dương") the scorer only accepts predictions that
  carry a ward-level prefix. `old_answer` for MCQ may be a letter or the old choice text.
- Alias policy (gold side only): TP.HCM variants = Thành phố Hồ Chí Minh; "Sài Gòn" is NOT accepted for
  TP.HCM (phường Sài Gòn exists since 1/7/2025; tracked as `match_detail=soft_alias`);
  "Thừa Thiên Huế" for gold "Huế" is labelled `outdated` (`match_detail=legacy_name`; renamed
  1/1/2025 by NQ 175/2024/QH15).
- predictions.jsonl rows additionally carry `match_detail, correct_nodiac, label_nodiac, label_strict,
  truncated, prompt_sha1`. `label_nodiac` = same pipeline with diacritic-insensitive matching against
  gold, old AND legacy names ("Binh Duong" for old "Bình Dương" → outdated); MCQ: = label.
  `label_strict` = diacritic-sensitive label. For items with `meta.has_diacritics == false` the main
  `label` is `label_nodiac` (match_detail prefixed `nodiac:`), so the ablation does not penalise a model
  for not restoring diacritics; for all other items `label == label_strict`.
- scores.json: `n_predictions`, `n_unscored_predictions` (rows whose item_id is not in the items file:
  kept in predictions.jsonl, never deleted, not scored); per condition → `all`,
  `by_qtype{qtype: {all, cells{pc0_wc0..pc1_wc1|na}}}`, `by_format`, `by_diacritics`, `by_qtype_format`,
  `consistency`; each block has `n, accuracy, outdated_rate, accuracy_nodiac, outdated_rate_nodiac,
  labels, labels_nodiac, match_detail, truncated`.
- Runner: a filtered run (`--qtypes`, `--limit`) rescores ALL stored predictions against the full
  items file. Resume skips stored (item, condition) pairs only if their `prompt_sha1` equals the prompt
  that would be sent now; otherwise it stops (changed items/`--today`/`--passage-fields`/contexts/
  PROMPT_VERSION → use another `--out`). `run_config.json` = latest invocation + `previous_runs` list.
- **Short-answer scoring rules (fixer pass; details in docs/eval_README.md):**
  - Admin levels: phường/xã/thị trấn/đặc khu = W, quận/huyện/thị xã = D, tỉnh/thủ đô = P,
    thành phố/TP = C (province OR abolished provincial city: compatible with P and D, never with W);
    an unprefixed pre-reform province name counts as P/C. "Thành phố Vũng Tàu", "Quận Hoàn Kiếm",
    "Thị xã Bến Cát" are NOT the new wards Phường Vũng Tàu / Hoàn Kiếm / Bến Cát (`level_mismatch`).
    Abbreviations "P./X./Q./H./TX." are expanded ("TT." is not: it often means Thừa Thiên).
  - Containment in free text is level-checked: a ward target needs a ward prefix right before the
    name (so "vũng tàu" inside "Tỉnh Bà Rịa - Vũng Tàu" does not count); a province/city target is
    rejected right after a ward/district prefix ("Phường Bình Dương, TP.HCM" is correct for gold
    TP.HCM / old Bình Dương). A hit strictly inside a hit of the other name is ignored.
  - Past/origin parentheticals and trailing clauses ("(cũ)", "(trước đây là …)", "(sáp nhập từ …)",
    ", trước đây …", "giảm từ …", "vốn/từng …") are removed before scoring; relation clauses after a
    past marker are ignored unless a present marker (nay/hiện/bây giờ/từ ngày…) follows it. Naming both
    the new and the old name (in either order) is `other_wrong/ambiguous`.
  - Addresses: " - " separates segments only before a unit prefix (real names "Văn Miếu - Quốc Tử
    Giám", "Bà Rịa - Vũng Tàu" keep it); "thuộc" and non-past parentheticals are segment separators;
    "Địa chỉ (mới):" is stripped; "X nay là Y" scores Y. An old address also matches without its
    district ("Phường Phú Cường, Tỉnh Bình Dương" → outdated). New ward + abolished district + new
    province → `other_wrong/extra_district`; ward only → `other_wrong/partial`.
  - Numbers: dates (1/7/2025, năm 2025) and resolution numbers (202/2025/QH15) are ignored;
    Vietnamese thousands separators are joined ("3.321" = 3321); numbers in past clauses are dropped
    ("giảm từ 63", "(trước đây là 63)", "từ 63 … xuống 34" → 34). Gold and old both present → ambiguous.
  - Abstention (`invalid/abstain`) only for answers starting with "không biết/không rõ/…/xin lỗi" or
    being exactly "N/A"/"NA"/"unknown" (place names "Na Rì", "Na Sầm"… are answers). Hedges
    ("Không chắc, nhưng có lẽ là X") are stripped and X is scored.
  - MCQ: an explicit letter (keyword/leading) beats a choice text that starts with a letter
    ("Đáp án: C, vì Xã A Lưới 1 …" → C), except when the letter is the start of that choice text
    ("Đáp án: A Lưới"). Lower-case letters are accepted after a keyword at the end/before a delimiter
    ("đáp án là b"); choice texts are matched with aliases ("TP.HCM"); "X sáp nhập vào Y" → Y.
- Consistency (per condition, groups having ≥1 T6_reverse and ≥1 other item): surface = all T6 items of
  the group correct; reports `surface_acc`, `deep_acc_given_surface`, `deep_acc_given_surface_wrong`,
  `fully_consistent_rate`, `surface_only_rate` (surface right, ≥1 deep item wrong), `deep_only_rate`.
- **T4 component scoring:** `scorer.score_address_components(item, raw)` labels the ward
  and the province of an address answer separately (`correct`/`outdated`/`other_wrong`/`invalid`; province = last
  segment, ward = first ward-level segment; old names from `meta.old_ward_name`/`meta.old_province_name`; nodiac
  matching for `has_diacritics=false`). It runs for every item with `meta.gold_ward` + `meta.gold_province`;
  `ScoreResult.components` → predictions rows `components: {ward, province}` → scores.json stats blocks get
  `components: {ward: {n, accuracy, outdated_rate, labels}, province: {...}, both_correct_rate}` (only when present).
- `T2_composition` and `T3_existence` must be `format: "mcq"`: the scorer has no short-answer rule for
  yes/no or unordered-list golds (the linter rejects short T2/T3). Adding one needs a new scorer rule.
- Short-answer prompt asks for the full unit name WITH its type (phường/xã/đặc khu, tỉnh/thành phố);
  `+date`/`+recency` require `revision_timestamp` on every passage (hard error otherwise).
- `--limit N` takes the first N items in file order (generator: interleave qtypes or use `--qtypes`).
- Items linter: `uv run python -m viadmin.eval.validate data/benchmark/items.jsonl` (generator should
  run it; 0 problems expected).
  It also flags `has_diacritics=false` items whose old answer equals the gold once diacritics are
  removed (e.g. Xã Tân Thành / Xã Tân Thạnh) or whose MCQ choices collide without diacritics: for
  those items the main label uses diacritic-insensitive matching, so such items must be avoided.
