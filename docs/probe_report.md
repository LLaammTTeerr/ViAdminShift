# Knowledge-cutoff probe

Code: `src/viadmin/probe/` · data: `data/probe/` · test: `tests/test_probe.py`.

## Why

Stated cutoffs are missing or unreliable for the candidate models (`docs/model_candidates.md`).
Qwen3 has only an unofficial 2025-03-31. Qwen3.5 states none. Gemma 4 states January 2025.
Ministral 3 says "data collected up to July 2025". We want to group models by **what they answer
correctly**, not by release date or model card. The probe has two parts:

1. **Dated MCQs** (`probe_items.jsonl`): 83 four-option questions in Vietnamese.
   - 6 are 2023 anchors.
   - 1–4 non-reform items fall in every month from 2024-09 to 2026-03 (≥3 per month).
   - 9 reform-timeline items sit in 2025-02, -04, -06 and -07.
   - The scorer turns per-month accuracy into an **effective cutoff**.
2. **Headline questions** (`headline_probe.jsonl`): 8 open short-answer questions about the
   reform. Each has `answer` (post-reform) and `old_answer` (pre-reform). These measure
   *outdated* answers directly, e.g. "63 tỉnh".

## Files

| file | rows | content |
|---|---|---|
| `data/probe/probe_items.jsonl` | 83 | `{id, month, topic, question, choices, answer, source_url, notes}` + runner fields `{qtype:"P_cutoff", format:"mcq", answer_aliases:[], old_answer, meta}` |
| `data/probe/headline_probe.jsonl` | 8 | benchmark item schema (`qtype:"T0_headline"`, `format:"short"`, `answer`, `answer_aliases`, `old_answer`) + `{month, topic, source_url, notes}`; passes `viadmin.eval.validate` with 0 problems |
| `data/probe/probe_all.jsonl` | 91 | both files concatenated (one runner input) |
| `src/viadmin/probe/build_items.py` | | single source of truth for all items. Rebuild with `uv run python -m viadmin.probe.build_items` |
| `src/viadmin/probe/score_probe.py` | | scorer, cutoff rule and text plot |

- **`month`** is the month in which the answer became publicly knowable, not the month the event
  was scheduled. For example, the Oscars item is dated to the ceremony, and the reform effective
  date is dated to the month it was fixed (see the reform table).
- **`old_answer`** is set on reform MCQs: it is the choice that is correct under the pre-reform
  structure, so the shared scorer labels that pick `outdated`. It is null on non-reform items.
- **Choice order:** the correct option plus three distractors are shuffled with
  `random.Random(f"13:{id}")`. Seed 13 is combined with the item id, so adding or removing an item
  never reshuffles the others.
- **Gold letter distribution:** A 23, B 22, C 17, D 21.
- **Validator:** `viadmin.eval.validate` rejects `qtype` "P_cutoff" as unknown. This is expected:
  the linter targets `data/benchmark/items.jsonl`, and it reports no other problem on the probe
  items.

## Running

```bash
# 1) generate (closed book; add +sysdate as a second condition if wanted)
uv run python -m viadmin.eval.runner --backend vllm --model Qwen/Qwen3.5-4B \
  --items data/probe/probe_all.jsonl --conditions closed --out results/probe_qwen3.5-4b
# 2) score + text plot (+ optional JSON)
uv run python -m viadmin.probe.score_probe --preds results/probe_qwen3.5-4b/predictions.jsonl \
  --condition closed --json results/probe_qwen3.5-4b/probe_scores.json
```

`score_probe` accepts any JSONL with `item_id` and `raw_output`. Optional `model` and `condition`
columns produce one report per (model, condition).

Do not rely on the runner's own `scores.json` for the headline items. The shared scorer reads
"3.321" (Vietnamese thousands separator) as the integers 3 and 321. `score_probe` strips
thousands separators before grading numeric golds. `answer_aliases` and `old_answer` also carry
"3.321" / "10.035", so a bare answer is graded correctly by both scorers. A sentence such as
"Cả nước có 3.321 xã" is graded correctly only by `score_probe`.

Example output (synthetic predictions: a model that knows ~90% of facts up to 2025-06 and
guesses afterwards):

```
bin       n   acc  0              2/3      1  reform
anchor    6  1.00  ################|########
2025-05   3  0.67  ################|
2025-06   4  0.75  ################|##        3/3    <- estimate
2025-07   4  0.25  ######          |          0/1
...
2026-03   4  0.75  ################|##
effective cutoff: 2025-06 [bracket 2025-06 .. 2026-03]
headline probe: 5/8 correct, 3 outdated  01:C 02:C 03:O 04:O 05:C 06:O 07:C 08:C
```

The lucky pass in 2026-03 does not move the estimate. It only widens the bracket.

## Effective-cutoff rule

The same rule is written in the `score_probe` docstring.

1. **Inputs.**
   - The rule uses **non-reform** items only by default (`--topic`). Reform accuracy is printed
     beside each month, so reform knowledge and general recency stay separate.
   - Threshold T = **2/3**. A month **passes** if it has n ≥ 2 items and accuracy ≥ 2/3. With 3
     items that means ≥ 2 correct; with 4 items, ≥ 3 correct.
   - Months with n < 2 are ignored. None exist in the current file.
2. **Estimate (change point).**
   - For each passing month m, count the disagreements with the step model "known ≤ m, unknown
     after": failing months ≤ m plus passing months > m.
   - The estimate is the passing month with the fewest disagreements. Ties go to the **latest**
     month.
   - In words, this is the last month with accuracy ≥ 2/3 that is followed by a consistent drop.
   - Why: random guessing (4 options) passes a 3-item month with p ≈ 0.16 and a 4-item month with
     p ≈ 0.05. For a model whose cutoff is mid-2025, the 9 later months give about a 50% chance of
     at least one lucky pass. So "last month ≥ 2/3" on its own would often push the estimate
     late.
3. **Bracket.**
   - `lower` = the month before the first failing month (solid up to here).
   - `upper` = the last passing month.
   - The estimate always lies in [lower, upper]. Report the bracket together with the estimate.
4. **Flags.**
   - `right_censored`: the estimate is 2026-03. Report "≥ 2026-03".
   - `none_pass`: report "< 2024-09".
   - `weak_anchor`: anchor accuracy < 2/3. The model fails 2023 facts, so a low estimate reflects
     weak Vietnamese or a weak model, not an early cutoff.

Unit tests cover these cases: a clean step, a lucky late month, an early dip, all known, none
known with weak anchors, and n < 2.

## Items per month

| bin | non-reform | reform | total |
|---|---|---|---|
| anchor (2023-03…2023-11) | 6 | 0 | 6 |
| 2024-09 | 4 | 0 | 4 |
| 2024-10 | 3 | 0 | 3 |
| 2024-11 | 4 | 0 | 4 |
| 2024-12 | 3 | 0 | 3 |
| 2025-01 | 3 | 0 | 3 |
| 2025-02 | 3 | 1 | 4 |
| 2025-03 | 4 | 0 | 4 |
| 2025-04 | 3 | 4 | 7 |
| 2025-05 | 3 | 0 | 3 |
| 2025-06 | 4 | 3 | 7 |
| 2025-07 | 4 | 1 | 5 |
| 2025-08 | 3 | 0 | 3 |
| 2025-09 | 4 | 0 | 4 |
| 2025-10 | 4 | 0 | 4 |
| 2025-11 | 4 | 0 | 4 |
| 2025-12 | 3 | 0 | 3 |
| 2026-01 | 4 | 0 | 4 |
| 2026-02 | 4 | 0 | 4 |
| 2026-03 | 4 | 0 | 4 |
| **total** | **74** | **9** | **83** |

Every month bin reaches ≥ 3 non-reform items.

Mix of items:
- 29 of the 83 items are directly about Vietnam: the 9 reform items and 20 non-reform items
  (storms, state leaders, US tariffs on Vietnam, Vietnamese sport, UNESCO, policy, accidents).
- The rest are global events: elections, leaders, prizes, sports finals and named disasters.

## Item list (gold answer and source)

Every fact was checked against the linked page.
- Wikipedia pages were read as full plain-text extracts through the MediaWiki API.
- News and legal pages were fetched in full.
- The supporting sentence is quoted or paraphrased in each item's `notes`.

| id | month | topic | gold answer | source |
|---|---|---|---|---|
| probe-anchor-01 | 2023-03 |  | Võ Văn Thưởng | [en: Võ Văn Thưởng](<https://en.wikipedia.org/wiki/Võ_Văn_Thưởng>) |
| probe-anchor-02 | 2023-08 |  | Ấn Độ | [en: Chandrayaan-3](<https://en.wikipedia.org/wiki/Chandrayaan-3>) |
| probe-anchor-03 | 2023-08 |  | Tây Ban Nha | [en: 2023 FIFA Women's World Cup final](<https://en.wikipedia.org/wiki/2023_FIFA_Women's_World_Cup_final>) |
| probe-anchor-04 | 2023-10 |  | Narges Mohammadi | [en: 2023 Nobel Peace Prize](<https://en.wikipedia.org/wiki/2023_Nobel_Peace_Prize>) |
| probe-anchor-05 | 2023-10 |  | Nam Phi | [en: 2023 Rugby World Cup final](<https://en.wikipedia.org/wiki/2023_Rugby_World_Cup_final>) |
| probe-anchor-06 | 2023-11 |  | Javier Milei | [en: 2023 Argentine general election](<https://en.wikipedia.org/wiki/2023_Argentine_general_election>) |
| probe-2024-09-n01 | 2024-09 |  | Yagi | [en: Typhoon Yagi](<https://en.wikipedia.org/wiki/Typhoon_Yagi>) |
| probe-2024-09-n02 | 2024-09 |  | Cầu Phong Châu | [vi: Cầu Phong Châu](<https://vi.wikipedia.org/wiki/Cầu_Phong_Châu>) |
| probe-2024-09-n03 | 2024-09 |  | Anura Kumara Dissanayake | [en: 2024 Sri Lankan presidential election](<https://en.wikipedia.org/wiki/2024_Sri_Lankan_presidential_election>) |
| probe-2024-09-n04 | 2024-09 |  | Ishiba Shigeru | [en: 2024 Liberal Democratic Party presidential election](<https://en.wikipedia.org/wiki/2024_Liberal_Democratic_Party_presidential_election>) |
| probe-2024-10-n01 | 2024-10 |  | Lương Cường | [en: Lương Cường](<https://en.wikipedia.org/wiki/Lương_Cường>) |
| probe-2024-10-n02 | 2024-10 |  | Han Kang | [en: Han Kang](<https://en.wikipedia.org/wiki/Han_Kang>) |
| probe-2024-10-n03 | 2024-10 |  | Tổ chức Nihon Hidankyo (Nhật Bản) | [en: 2024 Nobel Peace Prize](<https://en.wikipedia.org/wiki/2024_Nobel_Peace_Prize>) |
| probe-2024-11-n01 | 2024-11 |  | Huỳnh Thị Thanh Thủy | [en: Miss International 2024](<https://en.wikipedia.org/wiki/Miss_International_2024>) |
| probe-2024-11-n02 | 2024-11 |  | Đan Mạch | [en: Miss Universe 2024](<https://en.wikipedia.org/wiki/Miss_Universe_2024>) |
| probe-2024-11-n03 | 2024-11 |  | Marco Rubio | [en: Marco Rubio](<https://en.wikipedia.org/wiki/Marco_Rubio>) |
| probe-2024-11-n04 | 2024-11 |  | Trở thành thành phố Huế trực thuộc trung ương | [vi: Huế](<https://vi.wikipedia.org/wiki/Huế>) |
| probe-2024-12-n01 | 2024-12 |  | Nga | [en: Fall of the Assad regime](<https://en.wikipedia.org/wiki/Fall_of_the_Assad_regime>) |
| probe-2024-12-n02 | 2024-12 |  | Ban bố thiết quân luật | [en: 2024 South Korean martial law crisis](<https://en.wikipedia.org/wiki/2024_South_Korean_martial_law_crisis>) |
| probe-2024-12-n03 | 2024-12 |  | François Bayrou | [en: François Bayrou](<https://en.wikipedia.org/wiki/François_Bayrou>) |
| probe-2025-01-n01 | 2025-01 |  | Việt Nam | [en: 2024 ASEAN Championship final](<https://en.wikipedia.org/wiki/2024_ASEAN_Championship_final>) |
| probe-2025-01-n02 | 2025-01 |  | Joseph Aoun | [en: Joseph Aoun](<https://en.wikipedia.org/wiki/Joseph_Aoun>) |
| probe-2025-01-n03 | 2025-01 |  | DeepSeek-R1 | [en: DeepSeek](<https://en.wikipedia.org/wiki/DeepSeek>) |
| probe-2025-02-n01 | 2025-02 |  | Philadelphia Eagles | [en: Super Bowl LIX](<https://en.wikipedia.org/wiki/Super_Bowl_LIX>) |
| probe-2025-02-n02 | 2025-02 |  | Bộ Tài nguyên và Môi trường | [en: Ministry of Agriculture and Environment](<https://en.wikipedia.org/wiki/Ministry_of_Agriculture_and_Environment>) |
| probe-2025-02-n03 | 2025-02 |  | Na Tra 2 (Ne Zha 2) | [en: Ne Zha 2](<https://en.wikipedia.org/wiki/Ne_Zha_2>) |
| probe-2025-02-r01 | 2025-02 | reform | Sáp nhập một số tỉnh, không tổ chức cấp huyện, tiếp tục sáp nhập cấp xã | [baolaocai.vn](<https://baolaocai.vn/bo-chinh-tri-chi-dao-som-trinh-chu-truong-sap-nhap-mot-so-tinh-tam-dung-dai-hoi-dang-cap-huyen-xa-post398194.html>) |
| probe-2025-03-n01 | 2025-03 |  | Anora | [en: 97th Academy Awards](<https://en.wikipedia.org/wiki/97th_Academy_Awards>) |
| probe-2025-03-n02 | 2025-03 |  | Myanmar | [en: 2025 Myanmar earthquake](<https://en.wikipedia.org/wiki/2025_Myanmar_earthquake>) |
| probe-2025-03-n03 | 2025-03 |  | Kirsty Coventry | [en: 144th IOC Session](<https://en.wikipedia.org/wiki/144th_IOC_Session>) |
| probe-2025-03-n04 | 2025-03 |  | Mark Carney | [en: Mark Carney](<https://en.wikipedia.org/wiki/Mark_Carney>) |
| probe-2025-04-n01 | 2025-04 |  | Đã qua đời vào tháng 4/2025 | [en: Death and funeral of Pope Francis](<https://en.wikipedia.org/wiki/Death_and_funeral_of_Pope_Francis>) |
| probe-2025-04-n02 | 2025-04 |  | Chấp thuận luận tội, phế truất ông khỏi chức vụ | [en: Impeachment of Yoon Suk Yeol](<https://en.wikipedia.org/wiki/Impeachment_of_Yoon_Suk_Yeol>) |
| probe-2025-04-n03 | 2025-04 |  | 46% | [en: Liberation Day tariffs](<https://en.wikipedia.org/wiki/Liberation_Day_tariffs>) |
| probe-2025-04-r01 | 2025-04 | reform | 34 | [tapchicongthuong.vn](<https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm>) |
| probe-2025-04-r02 | 2025-04 | reform | Hợp nhất với TP.HCM và tỉnh Bà Rịa – Vũng Tàu, lấy tên Thành phố Hồ Chí Minh | [tapchicongthuong.vn](<https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm>) |
| probe-2025-04-r03 | 2025-04 | reform | Nghệ An | [tapchicongthuong.vn](<https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm>) |
| probe-2025-04-r04 | 2025-04 | reform | Tại tỉnh Yên Bái cũ | [tapchicongthuong.vn](<https://tapchicongthuong.vn/du-kien-cu-the-34-don-vi-hanh-chinh-cap-tinh-sau-sap-nhap--hop-nhat-139371.htm>) |
| probe-2025-05-n01 | 2025-05 |  | Lêô XIV (Leo XIV) | [en: Death and funeral of Pope Francis](<https://en.wikipedia.org/wiki/Death_and_funeral_of_Pope_Francis>) |
| probe-2025-05-n02 | 2025-05 |  | Paris Saint-Germain | [en: 2025 UEFA Champions League final](<https://en.wikipedia.org/wiki/2025_UEFA_Champions_League_final>) |
| probe-2025-05-n03 | 2025-05 |  | Telegram | [en: 2025 in Vietnam](<https://en.wikipedia.org/wiki/2025_in_Vietnam>) |
| probe-2025-06-n01 | 2025-06 |  | Lee Jae-myung | [en: 2025 South Korean presidential election](<https://en.wikipedia.org/wiki/2025_South_Korean_presidential_election>) |
| probe-2025-06-n02 | 2025-06 |  | Ahmedabad (Ấn Độ) | [en: Air India Flight 171](<https://en.wikipedia.org/wiki/Air_India_Flight_171>) |
| probe-2025-06-n03 | 2025-06 |  | Oklahoma City Thunder | [en: 2025 NBA Finals](<https://en.wikipedia.org/wiki/2025_NBA_Finals>) |
| probe-2025-06-n04 | 2025-06 |  | Đã được bãi bỏ từ tháng 6/2025 | [en: 2025 in Vietnam](<https://en.wikipedia.org/wiki/2025_in_Vietnam>) |
| probe-2025-06-r01 | 2025-06 | reform | Sắp xếp đơn vị hành chính cấp tỉnh (cả nước còn 34 tỉnh, thành phố) | [luatvietnam.vn](<https://luatvietnam.vn/hanh-chinh/nghi-quyet-202-2025-qh15-cua-quoc-hoi-ve-viec-sap-xep-don-vi-hanh-chinh-cap-tinh-402728-d1.html>) |
| probe-2025-06-r02 | 2025-06 | reform | 3.321 | [vietnamplus.vn](<https://www.vietnamplus.vn/uy-ban-thuong-vu-quoc-hoi-ca-nuoc-con-3321-don-vi-hanh-chinh-cap-xa-post1042624.vnp>) |
| probe-2025-06-r03 | 2025-06 | reform | 01/7/2025 | [luatvietnam.vn](<https://luatvietnam.vn/hanh-chinh/nghi-quyet-202-2025-qh15-cua-quoc-hoi-ve-viec-sap-xep-don-vi-hanh-chinh-cap-tinh-402728-d1.html>) |
| probe-2025-07-n01 | 2025-07 |  | Vịnh Hạ Long | [en: Capsizing of the Wonder Sea](<https://en.wikipedia.org/wiki/Capsizing_of_the_Wonder_Sea>) |
| probe-2025-07-n02 | 2025-07 |  | 20% | [en: Liberation Day tariffs](<https://en.wikipedia.org/wiki/Liberation_Day_tariffs>) |
| probe-2025-07-n03 | 2025-07 |  | Chelsea | [en: 2025 FIFA Club World Cup final](<https://en.wikipedia.org/wiki/2025_FIFA_Club_World_Cup_final>) |
| probe-2025-07-n04 | 2025-07 |  | Quần thể di tích và danh thắng Yên Tử – Vĩnh Nghiêm – Côn Sơn, Kiếp Bạc | [vi: Quần thể di tích và danh thắng Yên Tử – Vĩnh Nghiêm – Côn Sơn, Kiếp Bạc](<https://vi.wikipedia.org/wiki/Quần_thể_di_tích_và_danh_thắng_Yên_Tử_–_Vĩnh_Nghiêm_–_Côn_Sơn,_Kiếp_Bạc>) |
| probe-2025-07-r01 | 2025-07 | reform | Hai cấp: cấp tỉnh và cấp xã (không còn cấp huyện) | [pbgdpl.cantho.gov.vn](<https://pbgdpl.cantho.gov.vn/nghi-quyet-sua-doi-bo-sung-mot-so-dieu-cua-hien-phap-nuoc-cong-hoa-xa-hoi-chu-nghia-viet-nam>) |
| probe-2025-08-n01 | 2025-08 |  | Kajiki | [vi: Bão Kajiki (2025)](<https://vi.wikipedia.org/wiki/Bão_Kajiki_(2025)>) |
| probe-2025-08-n02 | 2025-08 |  | Anchorage, Alaska (Mỹ) | [en: 2025 Russia–United States summit](<https://en.wikipedia.org/wiki/2025_Russia–United_States_summit>) |
| probe-2025-08-n03 | 2025-08 |  | Paetongtarn Shinawatra | [en: Paetongtarn Shinawatra](<https://en.wikipedia.org/wiki/Paetongtarn_Shinawatra>) |
| probe-2025-09-n01 | 2025-09 |  | Bualoi | [vi: Bão Bualoi (2025)](<https://vi.wikipedia.org/wiki/Bão_Bualoi_(2025)>) |
| probe-2025-09-n02 | 2025-09 |  | Anutin Charnvirakul | [en: Anutin Charnvirakul](<https://en.wikipedia.org/wiki/Anutin_Charnvirakul>) |
| probe-2025-09-n03 | 2025-09 |  | Ousmane Dembélé | [en: Ousmane Dembélé](<https://en.wikipedia.org/wiki/Ousmane_Dembélé>) |
| probe-2025-09-n04 | 2025-09 |  | Sushila Karki | [en: Sushila Karki](<https://en.wikipedia.org/wiki/Sushila_Karki>) |
| probe-2025-10-n01 | 2025-10 |  | Takaichi Sanae | [en: Sanae Takaichi](<https://en.wikipedia.org/wiki/Sanae_Takaichi>) |
| probe-2025-10-n02 | 2025-10 |  | María Corina Machado | [en: 2025 Nobel Peace Prize](<https://en.wikipedia.org/wiki/2025_Nobel_Peace_Prize>) |
| probe-2025-10-n03 | 2025-10 |  | László Krasznahorkai | [en: 2025 Nobel Prize in Literature](<https://en.wikipedia.org/wiki/2025_Nobel_Prize_in_Literature>) |
| probe-2025-10-n04 | 2025-10 |  | Matmo | [vi: Bão Matmo (2025)](<https://vi.wikipedia.org/wiki/Bão_Matmo_(2025)>) |
| probe-2025-11-n01 | 2025-11 |  | Zohran Mamdani | [en: 2025 New York City mayoral election](<https://en.wikipedia.org/wiki/2025_New_York_City_mayoral_election>) |
| probe-2025-11-n02 | 2025-11 |  | Mexico | [en: Miss Universe 2025](<https://en.wikipedia.org/wiki/Miss_Universe_2025>) |
| probe-2025-11-n03 | 2025-11 |  | Hồng Kông | [en: Wang Fuk Court fire](<https://en.wikipedia.org/wiki/Wang_Fuk_Court_fire>) |
| probe-2025-11-n04 | 2025-11 |  | Kalmaegi | [vi: Bão Kalmaegi (2025)](<https://vi.wikipedia.org/wiki/Bão_Kalmaegi_(2025)>) |
| probe-2025-12-n01 | 2025-12 |  | U22 Việt Nam thắng U22 Thái Lan 3–2 sau hiệp phụ | [en: Football at the 2025 SEA Games – Men's tournament final](<https://en.wikipedia.org/wiki/Football_at_the_2025_SEA_Games_–_Men's_tournament_final>) |
| probe-2025-12-n02 | 2025-12 |  | José Antonio Kast | [en: 2025 Chilean general election](<https://en.wikipedia.org/wiki/2025_Chilean_general_election>) |
| probe-2025-12-n03 | 2025-12 |  | Bãi biển Bondi, Sydney (Úc) | [en: Bondi Beach shooting](<https://en.wikipedia.org/wiki/Bondi_Beach_shooting>) |
| probe-2026-01-n01 | 2026-01 |  | Bị lực lượng Mỹ bắt giữ và đưa sang Mỹ | [en: 2026 United States intervention in Venezuela](<https://en.wikipedia.org/wiki/2026_United_States_intervention_in_Venezuela>) |
| probe-2026-01-n02 | 2026-01 |  | Tô Lâm | [en: 14th National Congress of the Communist Party of Vietnam](<https://en.wikipedia.org/wiki/14th_National_Congress_of_the_Communist_Party_of_Vietnam>) |
| probe-2026-01-n03 | 2026-01 |  | U23 Trung Quốc | [en: 2026 AFC U-23 Asian Cup](<https://en.wikipedia.org/wiki/2026_AFC_U-23_Asian_Cup>) |
| probe-2026-01-n04 | 2026-01 |  | Elena Rybakina | [en: 2026 Australian Open – Women's singles](<https://en.wikipedia.org/wiki/2026_Australian_Open_–_Women's_singles>) |
| probe-2026-02-n01 | 2026-02 |  | Seattle Seahawks | [en: Super Bowl LX](<https://en.wikipedia.org/wiki/Super_Bowl_LX>) |
| probe-2026-02-n02 | 2026-02 |  | Đảng Dân tộc chủ nghĩa Bangladesh (BNP) | [en: 2026 Bangladeshi general election](<https://en.wikipedia.org/wiki/2026_Bangladeshi_general_election>) |
| probe-2026-02-n03 | 2026-02 |  | António José Seguro | [en: 2026 Portuguese presidential election](<https://en.wikipedia.org/wiki/2026_Portuguese_presidential_election>) |
| probe-2026-02-n04 | 2026-02 |  | Bhumjaithai | [en: Anutin Charnvirakul](<https://en.wikipedia.org/wiki/Anutin_Charnvirakul>) |
| probe-2026-03-n01 | 2026-03 |  | One Battle After Another | [en: 98th Academy Awards](<https://en.wikipedia.org/wiki/98th_Academy_Awards>) |
| probe-2026-03-n02 | 2026-03 |  | Venezuela | [en: 2026 World Baseball Classic championship](<https://en.wikipedia.org/wiki/2026_World_Baseball_Classic_championship>) |
| probe-2026-03-n03 | 2026-03 |  | Đảng Rastriya Swatantra (RSP) | [en: 2026 Nepalese general election](<https://en.wikipedia.org/wiki/2026_Nepalese_general_election>) |
| probe-2026-03-n04 | 2026-03 |  | Mojtaba Khamenei | [en: 2026 Iranian supreme leader election](<https://en.wikipedia.org/wiki/2026_Iranian_supreme_leader_election>) |

Supporting pages that are not the item's `source_url`:
- [en: 2024 in Vietnam](<https://en.wikipedia.org/wiki/2024_in_Vietnam>): Lương Cường selected 21 Oct.
- [en: 2025 Vietnamese administrative reforms](<https://en.wikipedia.org/wiki/2025_Vietnamese_administrative_reforms>):
  14 ministries on 18 Feb 2025, and the early-timeline facts below.
- [en: 2025 Ballon d'Or](<https://en.wikipedia.org/wiki/2025_Ballon_d%27Or>): ceremony date.
- [en: 2026 Thai general election](<https://en.wikipedia.org/wiki/2026_Thai_general_election>): election date.
- [en: Assassination of Ali Khamenei](<https://en.wikipedia.org/wiki/Assassination_of_Ali_Khamenei>).

## Reform timeline: items and proposal-vs-final check

| month | fact probed | item | primary / secondary source |
|---|---|---|---|
| 2025-02 | KL 127-KL/TW (28/2/2025): study merging provinces, **no district level**, keep merging communes, 2-tier model | r01 | baolaocai.vn (full text of the conclusion's key paragraph) |
| 2025-04 | NQ 60-NQ/TW (12/4/2025): **34** provincial units (28 tỉnh + 6 thành phố) | r01 | tapchicongthuong.vn (NQ 60 list), luatvietnam.vn |
| 2025-04 | proposed merger list: Bình Dương + BR-VT + TP.HCM → TP.HCM | r02 | NQ 60 list |
| 2025-04 | the 11 units kept unchanged (Nghệ An) | r03 | NQ 60 list; NQ 202 (Cần Thơ Sở Tư pháp summary) |
| 2025-04 | seat ≠ name: new Lào Cai seated in former Yên Bái | r04 | NQ 60 list; `provinces_new.jsonl` `seat_old_province_code`=15 |
| 2025-06 | NQ 202/2025/QH15 (12/6/2025) = provincial arrangement, in force on passage | r01 | luatvietnam.vn full text (Art. 1–2, "thông qua ngày 12 tháng 6 năm 2025") |
| 2025-06 | **3,321** commune-level units (2,621 xã + 687 phường + 13 đặc khu), UBTVQH 16/6/2025; old 10,035 | r02 | vietnamplus.vn, vneconomy.vn |
| 2025-06 | new provinces and 2-tier government operate from **1/7/2025** | r03 | NQ 202 Art. 2(2) |
| 2025-07 | district level abolished, 2-tier local government in force (NQ 203/2025/QH15, constitution amendment of 16/6/2025) | r01 | pbgdpl.cantho.gov.vn |

**Do the final merger groups differ from the earliest proposals?** We checked all 23 merger
groups in the NQ 60-NQ/TW annex (12/4/2025, tapchicongthuong.vn). Their names and
political-administrative seats are **identical** to NQ 202/2025/QH15 and to
`data/processed/provinces_new.jsonl` (`merged_from`, `seat_old_province_code`). We found **no
group that changed between April and June 2025**. The plan did change in other respects, and the
distractors use these changes on purpose:

- **Province count.**
  - 11/3/2025: the Government Party Committee proposed cutting provincial units by about 50%
    (thesaigontimes.vn, "Dự kiến giảm khoảng 50% đơn vị hành chính cấp tỉnh"). That implies about
    32 units.
  - Final: 34, a 46% cut. Distractor "32" in r01.
- **Commune count.**
  - 11/3/2025: proposed cut of 60–70%.
  - 28/3/2025: Kết luận 137-KL/TW (luatvietnam.vn) set "giảm khoảng 50%", i.e. about 5,000 units.
    Distractor "Khoảng 5.000".
  - 12/4/2025: NQ 60 restored 60–70%.
  - 16/6/2025: final −66.91%, i.e. 3,321.
  - A May 2025 draft already totalled 3,321 but split differently: 2,636 xã and 672 phường
    (vietnamplus, related link dated 11/05/2025). The final split is 2,621 xã and 687 phường.
- **Start date of the new provinces.**
  - March–April 2025 plan: merged provinces were to start on **1/9/2025** (PM's 11/3 timeline;
    Home Affairs Minister: provincial mergers "before August 30 … starting from September 1").
    Communes and the end of the district level were set for 1/7.
  - NQ 202 (June) moved the provinces to **1/7/2025** as well. Distractor "01/9/2025" in r03.
- **Special zones (đặc khu).** QĐ 759/QĐ-TTg (14/4/2025) lists 11 island districts becoming đặc
  khu, plus Phú Quốc and Thổ Châu still "under study". The final count is 13, matching
  `wards_new.jsonl`.
- **Late-2025 rumours.** Social-media lists of a further merger to 16 provinces were denied by
  the Ministry of Home Affairs (sggp.org.vn, baovanhoa.vn, Nov 2025). The probe does not use them.

## Headline probe (short answer, `headline_probe.jsonl`)

| id | question (abridged) | gold | old_answer |
|---|---|---|---|
| headline-01 | bao nhiêu ĐVHC cấp tỉnh? | 34 | 63 |
| headline-02 | bao nhiêu ĐVHC cấp xã? | 3321 (aliases 3.321, 3,321) | 10035 / 10.035 / 10,035 |
| headline-03 | chính quyền địa phương mấy cấp? | 2 | 3 |
| headline-04 | Bình Dương nay thuộc? | Thành phố Hồ Chí Minh | Tỉnh Bình Dương |
| headline-05 | Hà Giang nay thuộc? | Tỉnh Tuyên Quang | Tỉnh Hà Giang |
| headline-06 | Quảng Nam nay thuộc? | Thành phố Đà Nẵng | Tỉnh Quảng Nam |
| headline-07 | Kon Tum nay thuộc? | Tỉnh Quảng Ngãi | Tỉnh Kon Tum |
| headline-08 | Đắk Nông nay thuộc? | Tỉnh Lâm Đồng | Tỉnh Đắk Nông |

These golds are stable as of 2026-10. Some provinces became centrally-run cities in 2026 (e.g.
Đồng Nai, 30/4/2026; vi.wikipedia now says Huế is "một trong chín thành phố trực thuộc trung
ương"). So the probe deliberately avoids asking "how many centrally-run cities". The provincial
total is still 34.

## Caveats

1. **Guessable items.** Some answers can be reached from priors:
   - favourites winning (OKC Thunder 2025-06; Tô Lâm re-elected 2026-01, flagged weak in `notes`);
   - large or famous options (Nghệ An is the largest province; "Hạ Long" is the best-known bay);
   - elimination of implausible options.

   Distractors were chosen to resist this. Where possible they are runner-ups, the previous
   holder, or the *other* real event of the same type, e.g. Srettha vs Paetongtarn, Wipha/Yagi vs
   Kajiki, and the 46% vs 20% tariff. Chance level is 25%, and a 3-item month passes by luck about
   16% of the time (4-item: 5%). Hence the change-point rule and the bracket. Read single months as noisy.
2. **Post-training data can be newer than pretraining.** A model may know a few late,
   high-salience facts (the Pope's death, the 34-province headline) through SFT/RL data, system
   prompts or vendor patches, while its pretraining cutoff is earlier.
   - The probe measures *effective* knowledge, not the pretraining date.
   - A pass is weak evidence of a later cutoff; a consistent fail is strong evidence of an
     earlier one.
   - Report the bracket, not just the estimate.
3. **Announce-era knowledge.** The reform was public in stages (Feb plan → Apr list/34 → Jun laws
   → Jul in force). A model with a Mar–Jun 2025 cutoff can know "34 tỉnh" without knowing the
   implementation. It may also answer with the obsolete 1/9/2025 date or the ~50% commune target.
   Read the reform column per month, not as one number. Items r01 (Feb) and r01–r04 (Apr) are
   knowable from announcements; 2025-06 r02/r03 and 2025-07 r01 need June–July data.
4. **"Hiện nay" questions** (Pope 2025-04, two-child rule 2025-06, 2-tier 2025-07 and most
   headline items) depend on the model's sense of "now". With `+sysdate` (today = 13/10/2026), a
   model that knows the plan but not its execution may still answer correctly. Compare `closed`
   with `closed+sysdate`.
5. **Month labels are approximate at month boundaries.** Examples:
   - The AFF Cup final spanned 2 and 5 Jan 2025.
   - Ne Zha 2 was released 29 Jan 2025 and passed Inside Out 2 "in less than three weeks", i.e.
     in mid-Feb.
   - Rybakina won on the last weekend of Jan 2026.
   - Khamenei died 28 Feb 2026; we only ask about his successor (9 Mar).

   A model whose data ends mid-month may be partially right on that month.
6. **Sources.** Wikipedia is the source for most non-reform items (en, or vi for Vietnamese storm
   names). Reform facts come from Vietnamese legal and news sites (luatvietnam, tapchicongthuong,
   vietnamplus, Sở Tư pháp Cần Thơ, baolaocai) and are cross-checked against the project's
   canonical tables.
   - thuvienphapluat.vn returned HTTP 403, so its pages were not used.
   - The NQ 68-NQ/TW (private economy) candidate item was dropped because no fetched page stated
     its date.
7. **Vietnamese only.** Models with weak Vietnamese (Ministral 3, Olmo 3, Nemotron) may fail
   anchors. The `weak_anchor` flag marks those runs as inconclusive. Do not read them as early
   cutoffs.
8. **Scorer interplay.** MCQ letters are extracted by `viadmin.eval.scorer`. Choices are long
   Vietnamese phrases, so a model that copies the option text is still matched by the scorer's
   text-matching fallback. For numeric short answers, use `score_probe`, not the runner's
   `scores.json` (see the thousands-separator note above).

## Months that could not be filled

None. Every month bin from 2024-09 to 2026-03 has ≥ 3 verified non-reform items.
