# ViAdminShift evaluation harness

Code: `src/viadmin/eval/` · tests: `tests/test_eval_*.py` (`uv run pytest -q`).

| module | role |
|---|---|
| `normalize.py` | NFC, lowercase, tone-placement canonicalisation, admin-prefix stripping, diacritic stripping, admin level of a prefix |
| `aliases.py` | alias tables: `EQUIVALENT`, `LEGACY`, `SOFT`, `PROVINCE_NAMES` (see "Alias decisions") |
| `prompts.py` | Vietnamese templates, condition parser, chat-template helper (`enable_thinking=False`) |
| `backends.py` | `hf` (transformers, optional bnb NF4), `vllm` (lazy import), `openai` (OpenAI-compatible), `FakeBackend` |
| `scorer.py` | MCQ letter extraction, short-answer matching, labels `correct/outdated/other_wrong/invalid` |
| `metrics.py` | aggregation into `scores.json` (+ consistency metric) |
| `runner.py` | CLI, resumable; `--rescore`, `--validate` |
| `validate.py` | items linter (`uv run python -m viadmin.eval.validate data/benchmark/items.jsonl`) |
| `smoke.py` | GPU smoke test (8 toy MCQs) |

## Environment

* `torch==2.13.0` (PyPI wheel, `+cu130`) and `transformers>=5.10.4,<5.18` (resolved 5.17.0) are pinned
  **because vLLM 0.31.0 pins `torch==2.13.0` and `transformers<5.18`**. A universal `uv.lock` must
  hold a single torch version, so without these pins `uv` resolves the optional `vllm` extra to the
  ancient vLLM 0.2.5 (no Qwen3 support). With the pins, the local environment and the GPU-server environment use
  the same torch/transformers.
* vLLM is an optional extra and is **not installed locally**:
  ```bash
  uv sync --extra vllm          # on a GPU server only
  # fallback if the lock cannot be used there:
  uv pip install "vllm==0.31.0"  # pulls torch==2.13.0, same as the lock
  ```
* Other deps: `accelerate`, `bitsandbytes` (NF4), `openai` (client for any OpenAI-compatible endpoint).

## Running

```bash
uv run python -m viadmin.eval.runner --backend hf --model Qwen/Qwen3-1.7B --quant 4bit \
  --items data/benchmark/items.jsonl --contexts data/benchmark/contexts.jsonl \
  --passages data/wiki/passages.jsonl,data/benchmark/template_passages.jsonl \
  --conditions closed,rag_new,rag_mixed,rag_mixed+date,rag_mixed+recency,rag_mixed+sysdate \
  --limit 50 --out results/qwen3-1.7b_nf4_smoke

# vLLM (rented GPU)
uv run python -m viadmin.eval.runner --backend vllm --model Qwen/Qwen3-8B --max-model-len 4096 \
  --conditions closed,rag_new,rag_mixed --out results/qwen3-8b

# any OpenAI-compatible server (key from $OPENAI_API_KEY or --api-key-env NAME)
uv run python -m viadmin.eval.runner --backend openai --base-url http://host:8000/v1 \
  --model Qwen/Qwen3-8B --template-kwargs --conditions closed --out results/qwen3-8b_api

uv run python -m viadmin.eval.runner --items data/benchmark/items.jsonl --validate   # lint items
uv run python -m viadmin.eval.runner --items data/benchmark/items.jsonl --rescore --out results/<run>
```

* `--passages` takes a comma-separated list; missing files are skipped; a `passage_id` defined
  differently in two files is an error. Default: `data/wiki/passages.jsonl,data/benchmark/template_passages.jsonl`.
* A missing context row or missing passage id is a hard error, raised **before** any generation.
  `closed` needs no context rows.
* Resumable: `(item_id, condition)` pairs already in `predictions.jsonl` are skipped; the runner
  refuses to append predictions from a different `--model` to the same `--out`.
* A filtered run (`--qtypes`/`--limit`) never deletes other stored predictions: at the end ALL stored rows are
  rescored against the full `--items` file; rows of unknown item ids are kept unchanged and counted as
  `n_unscored_predictions`. Resume only skips pairs whose stored `prompt_sha1` equals the prompt this run
  would send; a mismatch (changed items, `--today`, `--passage-fields`, contexts, PROMPT_VERSION) stops
  the run. `run_config.json` keeps earlier invocations in `previous_runs`.
* `--rescore` relabels the stored `raw_output`s with the current scorer and rewrites `scores.json`
  (use this after any scorer fix; never hand-edit labels).
* Answers cut at the token limit (`truncated: true`) are re-asked by removing them and resuming with higher limits:
  `uv run python scripts/drop_truncated.py results/bench/<model>`, then `scripts/bench_api.sh` with the same arguments
  and `MAX_MCQ`/`MAX_SHORT` raised. The removed rows go to `dropped_truncated.jsonl` (raw output, prompt hash and the
  limits they were generated at, no scores). Done for the Claude benchmark runs (see `results/bench/README.md`).
* Other flags: `--qtypes T1_membership,T6_reverse`, `--today 2026-10-13` (date for `+sysdate`),
  `--passage-fields text,admin_text` (default `text`; the wiki `admin_text` holds ward lists but is up to 8,000 chars),
  `--max-model-len 8192` (vLLM), `--max-new-mcq 16`, `--max-new-short 64`, `--hf-batch-size 8`, `--batch-size 32` (items per
  backend call / flush), `--enable-thinking` (off by default; do not use for the paper runs).

### Outputs (`results/<run_id>/`)
* `predictions.jsonl`: `item_id, condition, model, raw_output, parsed, label` (SPEC) plus
  `match_detail, correct_nodiac, label_nodiac, label_strict, truncated, prompt_sha1`.
* `scores.json`: per condition → `all`, `by_qtype` (each with `cells` `pc{0|1}_wc{0|1}` / `na`),
  `by_format`, `by_diacritics` (`with`/`without`/`na`), `by_qtype_format`, `consistency`.
  Each stats block: `n, accuracy, outdated_rate, accuracy_nodiac, outdated_rate_nodiac, labels{4}, labels_nodiac{4},
  match_detail{}, truncated` (nodiac rates over all rows; MCQ rows use their label). Top level also has
  `n_predictions` and `n_unscored_predictions`.
* `dropped_truncated.jsonl` (only after a re-ask): the removed truncated answers, see above.
* `run_config.json`: backend info (model, quant, dtype...), conditions, `prompt_version`, `today`, `passage_fields`, argv,
  `previous_runs` (earlier invocations into the same directory, oldest first).

## Prompt conditions (exact definitions)

Condition string = `base[+mitigation]*`, e.g. `rag_mixed+date+sysdate`.

| part | effect |
|---|---|
| `closed` | no passages |
| `rag_new` | passages of contexts.jsonl condition `new`, stored order |
| `rag_mixed` | passages of contexts.jsonl condition `mixed`, stored (deterministically shuffled) order |
| `+date` | each passage header gets `(cập nhật ngày dd/mm/yyyy)` from `revision_timestamp`; no other change |
| `+recency` | passages re-sorted oldest → newest (newest last, nearest the question) + one sentence: "Các tài liệu được sắp xếp theo thời gian cập nhật, từ cũ nhất đến mới nhất (tài liệu cuối cùng là mới nhất)."; no dates shown |
| `+sysdate` | system prompt gets "Hôm nay là ngày 13/10/2026." (`--today`) |

System prompt (all conditions): "Bạn là một trợ lý hữu ích. Hãy trả lời chính xác và ngắn gọn bằng tiếng Việt."
Answer instructions: MCQ → "Chỉ trả lời bằng một chữ cái (A, B, C hoặc D) …"; short → "Chỉ trả lời bằng tên đầy đủ của đơn vị hành chính được hỏi, kèm loại đơn vị (phường/xã/đặc khu hoặc tỉnh/thành phố) …" (the type is requested because the scorer demands a ward prefix for province-named wards),
or "một con số" if the gold is numeric, or "địa chỉ mới (tên phường/xã/đặc khu, tỉnh/thành phố)" for
`T4_address` / comma-separated golds. Chat templates are rendered with `enable_thinking=False`
(Qwen3 → empty `<think></think>` block, verified in `test_qwen3_template_thinking_disabled`);
templates that reject a system role get it folded into the first user turn. `PROMPT_VERSION = "v1"`.

## Scoring rules

**Normalisation** (`normalize_name`, applied to gold and prediction alike): NFC → lowercase →
tone-placement canonicalisation (`hoà`=`hòa`, `thuỷ`=`thủy`, `khoẻ`=`khỏe`; NFC alone does not
unify these) → `tp.`→`tp `, unit abbreviations `P./X./Q./H./TX.` expanded (`TT.` is not: "TT. Huế"
usually means Thừa Thiên Huế) → punctuation/hyphens → space → strip **one** leading admin prefix
(longest first: thành phố, thủ đô, thị trấn, thị xã, đặc khu, tỉnh, tp, phường, xã, quận, huyện;
never leaving an empty string) → leading zeros of numbers (`Phường 01` = `Phường 1`).
Diacritic stripping maps `đ/Đ → d/D` explicitly.

**Diacritic-insensitive label**: every row has `label_nodiac` (the same short-answer pipeline with
diacritic-insensitive matching against gold, old AND legacy names, so "Binh Duong" for old "Bình
Dương" is `outdated` and "Thua Thien Hue" for Huế is `outdated`; MCQ: = `label`) and
`correct_nodiac = label_nodiac == "correct"`. `label_strict` is the diacritic-sensitive label. For
items with `meta.has_diacritics == false` the main `label` is `label_nodiac` (`match_detail`
prefixed `nodiac:`); otherwise `label == label_strict`. Compare `accuracy_nodiac` /
`outdated_rate_nodiac` across `by_diacritics` splits for the token-tax ablation.

**MCQ** (on the diacritised text — never strip diacritics first, or "Đáp án" becomes "D"):
`<think>` blocks and markdown removed, then in order: bare letter (`B`, `B.`, `(B)`, `**B**`, `b`) →
bare letter on the first line followed by an explanation → keyword (`Đáp án: B`, `Câu trả lời là C`,
`chọn D`, `Answer: A`; a lower-case letter only at the end or before a delimiter: `đáp án là b`;
two different letters → invalid) → leading letter with a hard delimiter (`B.`, `B)`, `B:`, `(B)`;
a plain space is not enough because "A Lưới" is a place name) → a choice text that itself starts
with a lone letter ("Xã A Lưới 1", "B'Lao") → trailing `… là B` → unique match of the text against
the choice texts (exact incl. alias expansion, e.g. "TP.HCM"; then whole-token containment with
sub-string choices like "An Phú"/"Tân An Phú" resolved; several hits → the one in the present-tense
relation clause, "Tỉnh Bình Dương đã sáp nhập vào Thành phố Hồ Chí Minh" → TP.HCM). A keyword or
leading letter that is the first letter of a letterish choice text ("Đáp án: A Lưới") is not taken
as a letter; otherwise an explicit letter always beats a mentioned letterish choice text
("Đáp án: C, vì Xã A Lưới 1 đã bị đổi tên" → C). Nothing found → `invalid`.
`old_answer` may be a letter or a choice text.

**Short answers**: the first non-empty line, with "Đáp án:", "Địa chỉ (mới):" etc. removed and hedges
("Không chắc, nhưng có lẽ là X", "Có lẽ là X") stripped. Gold accept-set = `answer` +
`answer_aliases` + `EQUIVALENT` expansions (gold side only). An `old_answer` identical to the gold
after normalisation is ignored for outdatedness (unchanged items can only be `correct`). Past/origin
material is removed before steps 4-6: parentheticals containing a past/origin marker ("(cũ)",
"(trước đây là …)", "(sáp nhập từ …)", "(gồm …)") and a trailing clause starting with one
(", trước đây …", ", giảm từ …"); other parentheticals become a comma segment. Order:
1. whole line = gold → `correct`; = old_answer → `outdated`; = a `LEGACY` name of the gold →
   `outdated` (`legacy_name`).
2. empty → `invalid/empty`; abstention → `invalid/abstain`: the line starts with "tôi không biết /
   không rõ / không chắc / không có thông tin / không thể xác định / xin lỗi / I don't know", or is
   exactly "N/A", "NA", "unknown", "không có" (place names such as "Na Rì" are answers).
3. numeric gold (T0 counts): integers stated as the current value — dates (`1/7/2025`, `năm 2025`)
   and resolution numbers (`202/2025/QH15`) removed, thousands separators joined (`3.321` = 3321),
   numbers in past clauses dropped (`giảm từ 63`, `(trước đây là 63)`, `từ 63 … xuống 34`).
   Gold and old both present → `other_wrong/ambiguous`.
4. multi-segment golds (addresses) → see below.
5. **relation clauses** — small models often echo the question: "Bình Dương (cũ) thuộc Thành phố Hồ Chí
   Minh." Only the text after a relation verb (thuộc, thuộc về, trực thuộc (lower-case "trực" only:
   "Xã Nam Trực thuộc …"), là, (được) sáp nhập vào, hợp nhất vào, nhập vào, chuyển về/thành, đổi tên
   thành, trở thành) is scored; a clause whose preceding context ends in a past marker (trước, trước
   đây/kia/năm/ngày/khi, từng, vốn, ban đầu, nguyên là, cũ là, …) without a later present marker
   (nay, hiện, bây giờ, từ ngày, sau sáp nhập, …) is ignored; leading "nay/hiện nay/…" stripped.
   Gold-only → `correct` (`relation`), old-only → `outdated`, both → `other_wrong/ambiguous`; then
   level-checked containment within those clauses; then the subject before the verb is accepted if it
   equals the gold ("Phường Sài Gòn là phường mới…").
6. otherwise the first segment (split on `, ; ( [`, ` / ` and a spaced dash followed by a unit
   prefix); the other name (old vs gold) also present in the answer line, in either order →
   `other_wrong/ambiguous`.
7. level-checked containment on the whole output (`contained`; keys that are all digits or < 3
   chars are never searched; gold & old both present → `ambiguous`) → `other_wrong` (details
   `soft_alias`, `level_mismatch`, `ambiguous_province_name` where relevant).

**Multi-segment golds** (addresses, "Phường X, Tỉnh Y"): segment-wise, the last n prediction segments
must match the n gold segments with compatible levels (trailing "Việt Nam" dropped); extra leading
segments (street) are allowed (`address_suffix`). Before segmenting: " - " becomes a separator only
when followed by a unit prefix (real names "Văn Miếu - Quốc Tử Giám", "Lâm Viên - Đà Lạt", "Bà Rịa -
Vũng Tàu" keep it); for "X nay là / được sáp nhập vào / đổi tên thành Y" only Y is scored; "thuộc"
becomes a separator. Old addresses with ≥ 3 segments also match without their middle (district)
segment ("Phường Phú Cường, Tỉnh Bình Dương" → `outdated`). New ward + abolished district + new
province → `other_wrong/extra_district`; ward only → `other_wrong/partial`.

**Admin level checks**: ward = phường/xã/thị trấn/đặc khu (W); district = quận/huyện/thị xã (D);
province = tỉnh/thủ đô (P); "thành phố"/"tp" = C (a centrally-run city or an abolished provincial
city: compatible with P and D, never with W); an unprefixed pre-reform province name is treated as
P/C. Incompatible levels never match ("Quận 1" ≠ "Phường 1"; "Thành phố Vũng Tàu", "Quận Hoàn
Kiếm", "Thị xã Bến Cát" ≠ the new wards Phường Vũng Tàu / Hoàn Kiếm / Bến Cát → `level_mismatch`;
2,266 ward_mapping rows have an old district named like the new ward). Containment hits are
level-checked against the prefix immediately before the hit: a ward target needs a ward prefix there
(so "vũng tàu" inside "Tỉnh Bà Rịa - Vũng Tàu" does not count for Phường Vũng Tàu); a province/city
target is rejected right after a ward or district prefix ("Phường Bình Dương, Thành phố Hồ Chí Minh"
is `correct` for gold TP.HCM with old Bình Dương). A hit lying strictly inside a hit of the other
name is ignored.
In addition, **for ward golds whose bare name is a province name the prediction must carry a
ward-level prefix**: `wards_new.jsonl` has 43 such post-reform wards (Phường Bình Dương, Xã Hòa Bình,
Phường Bắc Giang, ...), and a bare "Bình Dương" is ambiguous with the old province.

## Alias decisions (`aliases.py`)

* **EQUIVALENT** (counted correct): TP.HCM / TP HCM / TPHCM / TP. Hồ Chí Minh / HCM / HCMC /
  Ho Chi Minh City / Thành phố Hồ Chí Minh; Hà Nội / Thủ đô Hà Nội / Hanoi; BR-VT variants;
  Đắk Lắk / Đăk Lăk / Đắc Lắc; Đắk Nông variants; Kon Tum / Kontum; Bắc Kạn / Bắc Cạn; Đà Nẵng / Danang.
* **Sài Gòn is NOT an alias of TP.HCM** (`SOFT`, labelled `other_wrong` with `match_detail=soft_alias`,
  so a lenient re-scoring is possible): since 1/7/2025 *phường Sài Gòn* is a ward of TP.HCM
  (Nghị quyết 1685/NQ-UBTVQH15: Bến Nghé + parts of Đa Kao and Nguyễn Thái Bình; present in
  `data/processed/wards_new.jsonl`, code 26740). Aliases are gold-side only, so a gold "Phường Sài Gòn"
  accepts "Sài Gòn" but never "TP.HCM".
* **Thừa Thiên Huế → Huế is a LEGACY name** (labelled `outdated`, `match_detail=legacy_name`):
  Nghị quyết 175/2024/QH15 (30/11/2024, effective 01/01/2025) turned the whole province of
  Thừa Thiên Huế into the centrally-run city Huế. So "Thừa Thiên Huế" is outdated (pre-2025) even
  though it predates the 1/7/2025 reform; it is not counted correct. The canonical
  `provinces_old.jsonl` already uses "Huế". Analyses can separate rename confusion (legacy_name) from
  merge confusion (old_answer).

## Items linter (`--validate`)
Checks: required fields, known qtype/format, 4 choices, answer letter valid, choices that collide
after normalisation or are aliases of each other, MCQ `old_answer` that maps to no choice, short
`old_answer` that differs from `answer` textually but would be accepted as correct by the scorer
(would make "outdated" undetectable), duplicate ids.

## GPU smoke test (laptop)

`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True uv run python -m viadmin.eval.smoke --quant {none,4bit}`
— RTX 3050 Ti Laptop (4096 MiB, 3.68 GiB usable), torch 2.13.0+cu130, transformers 5.17.0,
bitsandbytes 0.50.2, Qwen/Qwen3-1.7B (rev 70d244cc).

| setting | result |
|---|---|
| bf16 (no quant) | **OOM while loading weights** (3.57 GiB allocated at 91 % of tensors) — fp16 has the same footprint |
| 4-bit NF4 (double quant, bf16 compute), batch 8, max_new_tokens 16 | loads in 7.4 s; **peak VRAM 2178 MiB allocated / 2210 MiB reserved**; 8 closed-book MCQs in 0.87 s → **≈ 9.2 items/s** |
| runner end-to-end, NF4, 4–5 fixture items × 4–6 conditions (RAG prompts ~250 tokens, mixed MCQ/short, tiny batches) | ≈ 2.9–4.4 items/s |

So on the laptop use `--quant 4bit`. Toy outputs looked sane (bare letters, sometimes a letter followed by
"Giải thích: …", which the scorer handles). With the short-answer prompt, Qwen3-1.7B usually answers in a
sentence that echoes the question ("Bình Dương (cũ) thuộc Thành phố Hồ Chí Minh.") — hence rule 5. Numbers on the rented GPU with vLLM will differ completely.

## Known limitations
* `T2_composition` / `T3_existence` short answers (unordered lists, yes/no) have no scoring rule; the
  linter rejects them — these qtypes must be MCQ.
* `--limit N` takes the first N items in file order (use `--qtypes` to target a qtype).
* `+date` / `+recency` raise if a passage lacks `revision_timestamp`; timestamps are parsed (timezone-aware) for sorting.
* `run()` always finishes by re-scoring every stored prediction, so `scores.json` never mixes scorer versions.
* No `trust_remote_code` anywhere: all models are loaded with native transformers/vLLM code only.
* Prefix stripping conflates same-name units of the same level-less form ("Phường X" vs "Xã X" when the
  prediction has no prefix). Within one province there are no such collisions in `wards_new.jsonl`
  but 10 within-province pairs collide **without diacritics** (e.g. Xã Tân Thành /
  Xã Tân Thạnh), which only affects `label_nodiac` (and the main label of no-diacritic items).
* The containment fallback is level-checked (see above) but can still over-accept a province name that
  is part of a longer, unprefixed name; it is reported as `match_detail=contained` so its share can be
  checked and it can be switched off (`scorer.ALLOW_CONTAINMENT = False`) followed by `--rescore`.
* An answer naming the OLD district for a ward question ("Quận Hoàn Kiếm" for the new Phường Hoàn Kiếm)
  is `other_wrong/level_mismatch`, not `outdated`: items carry no old-district field to compare with.
* Past/present detection is lexical (marker words within the clause); unusual phrasings can still be
  misread — check `match_detail` (`relation`, `ambiguous`) on real outputs.
* vLLM backend was checked against the vLLM 0.31.0 source (`LLM.chat(..., chat_template_kwargs=...)`)
  but not executed (not installed locally).
