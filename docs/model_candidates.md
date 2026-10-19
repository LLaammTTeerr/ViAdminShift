# Model candidates: pre- vs post-reform knowledge cutoff

Every repo id below was checked against the live Hugging Face API
(`/api/models/<id>`: existence, `createdAt`, gating, licence tag, safetensors parameter count,
`architectures`). vLLM support was checked against `docs.vllm.ai/en/latest/models/supported_models.html`
and `vllm/model_executor/models/registry.py` on `main` (fetched the same day). No weights were downloaded
and no hosted inference was used.

## Headline finding (read this first)

**No open-weight model of 14B or smaller that we found has a *stated* knowledge cutoff after 1 July 2025.**

- Several models **released** in 2026 have **stated** cutoffs well before the reform. Their release dates are misleading:
  Gemma 4 (all sizes, released Apr–May 2026): **January 2025**. Olmo 3 (Nov 2025): **Dec 2024**.
  Nemotron-3-Nano-4B (Mar 2026): **Sep 2024**. LFM2.5-1.2B (Jan 2026): **mid-2024**.
- The latest stated small-model cutoff is **Ministral 3 (3B/8B/14B)**. Its EU training-data summary says
  "The latest date of data collection was July 2025". That is the reform month itself, so we treat it as a straddle.
- For the strongest post-reform candidates (Qwen3.5 small, Tiny Aya, LFM2.5-2.6B, Apertus v1.5, Granite 4.1/4.2),
  **the cutoff is unstated**. The "post-reform" group is therefore defined by release date plus an unstated cutoff,
  **not** by evidence that the reform is in the training data. → Run an empirical cutoff probe before relying on the
  grouping (see the last section).
- **Stated cutoffs are pretraining cutoffs.** Post-training (SFT/RL) data can be months newer. For example,
  Nemotron-3-Nano-30B states pretraining 2025-06-25 but post-training 2025-11-28. Gemma 4 adds "We may periodically
  update models after this date." A "pre" model released after early 2025 (Qwen3, Gemma 3, Gemma 4) could have picked up
  the headline via instruction data. For these, failing the headline question is informative; passing it is not.

### Reform timeline: what counts as "pre"

The merger was public **before** 1 July 2025 (sources: vietnam-briefing.com, luatvietnam.vn):

| Date | Event |
|---|---|
| 28 Feb 2025 | Conclusion 127-KL/TW: draft a proposal to merge provinces and drop the district level |
| 12 Apr 2025 | Resolution 60-NQ/TW: the 34-unit figure |
| 14 Apr 2025 | Decision 759: the government's plan to rearrange 52 provincial units into the 34-unit map |
| 12 Jun 2025 | Resolution 202/2025/QH15: provincial mergers enacted |
| 1 Jul 2025 | Districts cease to operate |

Commune-level arrangement resolutions (NA Standing Committee) date from about mid-June 2025. *We did not verify this here.*

A model with a **Mar–Jun 2025** cutoff may already know the "34 provinces" headline from pre-implementation news. It is
unlikely to know the final ward names. **Clean pre-reform controls should have cutoffs before about Feb 2025.**

## Candidate table

The release date is the public release where known. Otherwise it is the HF repo `createdAt`, marked "(repo)".
Parameter counts are safetensors totals from the HF API, including vision or audio towers where present.

Group key:
- **pre** = stated or inferable cutoff before Feb 2025
- **pre (announce-era)** = cutoff Mar–Jun 2025
- **straddle** = cutoff about July 2025
- **post?** = released after Oct 2025 with an unstated cutoff
- **decoy** = released after the reform but with a stated pre-reform cutoff (useful as a negative control)

| repo id | params | release | stated cutoff | source | Vietnamese | vLLM | licence / gating | group |
|---|---|---|---|---|---|---|---|---|
| `Qwen/Qwen3-1.7B` | 2.03B | 2025-04-29 | unstated (unofficial: 2025-03-31, OpenRouter) | [card](https://huggingface.co/Qwen/Qwen3-1.7B), [tracker](https://metehan.ai/articles/llm-knowledge-cutoff-dates/) | yes (Qwen3 report lists vi; 119 langs) | yes (`Qwen3ForCausalLM`) | Apache-2.0, open | pre (announce-era?) |
| `Qwen/Qwen3-4B` | 4.02B | 2025-04-29 | unstated (unofficial: 2025-03-31) | [card](https://huggingface.co/Qwen/Qwen3-4B), [report](https://arxiv.org/abs/2505.09388) | yes | yes | Apache-2.0, open | pre (borderline-early) |
| `Qwen/Qwen3-8B` | 8.19B | 2025-04-29 | unstated (unofficial: 2025-03-31) | [card](https://huggingface.co/Qwen/Qwen3-8B) | yes | yes | Apache-2.0, open | pre (borderline-early) |
| `Qwen/Qwen3-14B` | 14.8B | 2025-04-29 | unstated (unofficial: 2025-03-31) | [card](https://huggingface.co/Qwen/Qwen3-14B) | yes | yes | Apache-2.0, open | pre (borderline-early), larger |
| `Qwen/Qwen3-4B-Instruct-2507` | 4.02B | 2025-08 | unstated (unofficial: 2025-06-30) | [card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) | yes | yes | Apache-2.0, open | pre (announce-era); avoid as control |
| `Qwen/Qwen3.5-0.8B` | 0.87B | 2026-03-02 | **unstated** | [card](https://huggingface.co/Qwen/Qwen3.5-0.8B) | 201 langs claimed; vi not named in card | yes (`Qwen3_5ForConditionalGeneration`) | Apache-2.0, open | post? |
| `Qwen/Qwen3.5-2B` | 2.27B | 2026-03-02 | **unstated** | [card](https://huggingface.co/Qwen/Qwen3.5-2B) | 201 langs claimed; vi not named in card | yes | Apache-2.0, open | post? |
| `Qwen/Qwen3.5-4B` | 4.66B (incl. vision) | 2026-03-02 | **unstated** (API system prompts claim "2026"; unofficial) | [card](https://huggingface.co/Qwen/Qwen3.5-4B), [tracker](https://metehan.ai/articles/llm-knowledge-cutoff-dates/) | 201 langs claimed; vi not named in card | yes | Apache-2.0, open | post? |
| `Qwen/Qwen3.5-9B` | 9.65B (incl. vision) | 2026-03-02 | **unstated** | [card](https://huggingface.co/Qwen/Qwen3.5-9B) | 201 langs claimed; vi not named in card | yes | Apache-2.0, open | post?, larger |
| `meta-llama/Llama-3.2-3B-Instruct` | 3.21B | 2024-09-25 | **Dec 2023** | [model card (GitHub)](https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md) | not officially (8 langs); usable | yes | Llama 3.2 licence, **gated (manual)** | pre |
| `meta-llama/Llama-3.1-8B-Instruct` | 8.03B | 2024-07-23 | **Dec 2023** | [model card (GitHub)](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md) | not officially; usable | yes | Llama 3.1 licence, **gated (manual)** | pre |
| `google/gemma-3-4b-it` | 4.30B | 2025-03-12 | **Aug 2024** | [card](https://ai.google.dev/gemma/docs/core/model_card_3) | 140+ langs (vi not named) | yes | Gemma ToU, **gated (click-through)** | pre |
| `google/gemma-3-12b-it` | 12.2B | 2025-03-12 | **Aug 2024** | same | same | yes | same | pre, larger |
| `google/gemma-3n-E4B-it` | 7.85B (E4B eff.) | 2025-06 | not checked (gated card) | [card](https://huggingface.co/google/gemma-3n-E4B-it) | 140 langs | yes | Gemma ToU, gated | pre (unverified) |
| `google/gemma-4-E2B-it` | 5.12B (2.3B eff.) | 2026-04-02 | **Jan 2025** | [card](https://huggingface.co/google/gemma-4-E2B-it), [EU summary](https://storage.googleapis.com/transparencyreport/report-downloads/pdf-report-nn_2026-7-31_2026-7-31_en_v1.pdf) | 140+ langs (vi not named) | yes (`Gemma4ForConditionalGeneration`) | Apache-2.0, open | **decoy** |
| `google/gemma-4-E4B-it` | 8.00B (4B eff.) | 2026-04-02 | **Jan 2025** | same | same | yes | Apache-2.0, open | **decoy** (negative control) |
| `google/gemma-4-12B-it` | 12.0B | 2026-05-23 (repo) | **Jan 2025** | [card](https://huggingface.co/google/gemma-4-12B-it) | same | yes (`Gemma4UnifiedForConditionalGeneration`) | Apache-2.0, open | decoy, larger |
| `mistralai/Ministral-3-3B-Instruct-2512` | 3.85B (incl. vision) | 2025-12-02 | **data collected up to July 2025** (EU summary) | [card](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512), [EU summary (archived)](https://aial.ie/research/gpai-training-transparency/archive/Ministral_3_3B_2026_08_03.pdf) | **not listed** (11 langs, no vi) | yes (`Mistral3ForConditionalGeneration`) | Apache-2.0, open | straddle |
| `mistralai/Ministral-3-8B-Instruct-2512` | 8.92B total incl. vision encoder (LM alone slightly >8B; unverified split) | 2025-12-02 | **up to July 2025** | [card](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512), [EU summary (archived)](https://aial.ie/research/gpai-training-transparency/archive/Ministral_3_8B_2026_08_03.pdf), [paper](https://arxiv.org/abs/2601.08584) | not listed | yes | Apache-2.0, open | straddle |
| `mistralai/Ministral-3-14B-Instruct-2512` | 13.9B | 2025-12-02 | **up to July 2025** (EU summary) | [card](https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512), [EU summary (archived)](https://aial.ie/research/gpai-training-transparency/archive/Ministral_3_14B_2026_08_03.pdf) | not listed | yes | Apache-2.0, open | straddle, larger |
| `allenai/Olmo-3-7B-Instruct` | 7.30B | 2025-11-20 | **Dec 2024** | [card](https://huggingface.co/allenai/Olmo-3-7B-Instruct) | English-only | yes (`Olmo3ForCausalLM`) | Apache-2.0, open | decoy / pre |
| `ibm-granite/granite-4.0-micro` | 3.40B | 2025-10-02 | unstated | [card](https://huggingface.co/ibm-granite/granite-4.0-micro) | not listed (12 langs) | yes | Apache-2.0, open | unclear |
| `ibm-granite/granite-4.1-8b` | 8.79B | 2026-04-29 | unstated | [card](https://huggingface.co/ibm-granite/granite-4.1-8b) | **not listed** (12 langs, no vi) | yes (`GraniteForCausalLM`) | Apache-2.0, open | post? |
| `ibm-granite/granite-4.2-8b` | 8.79B | 2026-08-25 | unstated (post-trained from 4.1 base) | [card](https://huggingface.co/ibm-granite/granite-4.2-8b) | not listed | yes | Apache-2.0, open | post? (same base as 4.1) |
| `CohereLabs/tiny-aya-global` | 3.35B | 2026-02-17 | unstated (tech report has no cutoff) | [card](https://huggingface.co/CohereLabs/tiny-aya-global), [report](https://arxiv.org/abs/2603.11510) | **yes** (70 langs incl. vi) | yes (`Cohere2ForCausalLM`) | **CC-BY-NC-4.0**, gated (auto) | post? |
| `LiquidAI/LFM2.5-2.6B` | 2.70B | 2026-07-28 (repo); about Aug 2026 | unstated | [card](https://huggingface.co/LiquidAI/LFM2.5-2.6B) | **yes** (vi listed) | yes (`Lfm2ForCausalLM`) | LFM Open License v1.0, open | unclear (1.2B sibling states mid-2024; card says "not recommended for knowledge-heavy tasks") |
| `LiquidAI/LFM2.5-1.2B-Instruct` | 1.17B | 2026-01 | **mid-2024** | [card](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) | not listed | yes | LFM Open License, open | decoy |
| `swiss-ai/Apertus-8B-Instruct-2509` | 8.05B | 2025-09-02 | unstated | [card](https://huggingface.co/swiss-ai/Apertus-8B-Instruct-2509) | yes (1000+ langs) | yes (`ApertusForCausalLM`) | Apache-2.0 + AUP click-through | unclear (likely pre) |
| `swiss-ai/Apertus-v1.5-8B` | 8.90B (multimodal) | 2026-07-24 | unstated (EU summary exists but sits in a gated repo; not read) | [card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B), [EPFL](https://ai.epfl.ch/apertus-1-5-building-the-next-generation-of-open-ai-infrastructure/) | likely yes (1.0 was 1000+ langs) | **not in vLLM registry** (`Apertus1p5ForConditionalGeneration`) | Apache-2.0, **gated (auto)** | post? (continued pretraining of 1.0, about 4T tokens, per a third party) |
| `nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16` | 3.97B | 2026-03-16 | **Sep 2024** | [card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16) | English only | yes (`NemotronHForCausalLM`) | NVIDIA Open Model Licence | decoy |
| `nvidia/NVIDIA-Nemotron-Nano-9B-v2` | 8.89B | 2025-08-18 | **Sep 2024** | [card](https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-9B-v2) | not listed | yes | NVIDIA Open Model Licence | decoy |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` | 31.6B total / 3B active | 2025-12 | **pretrain 2025-06-25; post-train 2025-11-28** | [card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) | not listed | yes | NVIDIA Open Model Licence | pre (announce-era) + post-reform SFT; too large |
| `HuggingFaceTB/SmolLM3-3B` | 3.08B | 2025-07-08 | latest pretraining dataset Feb 2025 (EU summary) | [card](https://huggingface.co/HuggingFaceTB/SmolLM3-3B), [EU summary](https://huggingface.co/spaces/hfmlsoc/smollm3-eu-data-transparency) | weak (6 main langs) | yes | Apache-2.0, open | pre |
| `microsoft/Phi-4-mini-instruct` | 3.84B | 2025-02 | **June 2024** | [card](https://huggingface.co/microsoft/Phi-4-mini-instruct) | not listed (vi absent from 24 langs tag) | yes | MIT, open | pre |
| `Viet-Mistral/Vistral-7B-Chat` | 7.29B | 2024-01 | unstated (Mistral-7B + Vietnamese CPT; data ≤2023) | [card](https://huggingface.co/Viet-Mistral/Vistral-7B-Chat) | **Vietnamese-specialised** | yes (`MistralForCausalLM`) | **gated (manual)**; tag afl-3.0 | pre |
| `SeaLLMs/SeaLLMs-v3-7B-Chat` | 7.62B | 2024-07 | unstated (Qwen2 base; ≤mid-2024 by construction) | [card](https://huggingface.co/SeaLLMs/SeaLLMs-v3-7B-Chat) | **yes** (SEA focus) | yes (`Qwen2ForCausalLM`) | SeaLLMs licence ("other"), open | pre |
| `SeaLLMs/SeaLLMs-v3-1.5B-Chat` | 1.54B | 2024-07 | unstated (as above) | [card](https://huggingface.co/SeaLLMs/SeaLLMs-v3-1.5B-Chat) | yes | yes | same | pre |
| `arcee-ai/Arcee-VyLinh` | 3.40B | 2024-10 | unstated (Qwen2.5-3B base) | [card](https://huggingface.co/arcee-ai/Arcee-VyLinh) | **Vietnamese-specialised** | yes | Apache-2.0, open | pre |
| `vinai/PhoGPT-4B-Chat` | 3.7B | 2024-01 | unstated (≤2023) | [card](https://huggingface.co/vinai/PhoGPT-4B-Chat) | Vietnamese-only | yes (`MPTForCausalLM` is in the registry; not on the docs page) | BSD-3, open | pre |
| `GreenNode/GreenMind-Medium-14B-R1` | 14.8B | 2025-04-15 | unstated (Qwen2.5-14B base) | [card](https://huggingface.co/GreenNode/GreenMind-Medium-14B-R1) | Vietnamese-specialised | yes | MIT, open | pre, larger |
| `aisingapore/Llama-SEA-LION-v3.5-8B-R` | 8.03B | 2025-04 | Dec 2023 base (Llama 3.1) + SEA CPT; unstated | [card](https://huggingface.co/aisingapore/Llama-SEA-LION-v3.5-8B-R) | yes | yes | Llama 3.1 licence | pre |
| `aisingapore/Gemma-SEA-LION-v4.5-E2B-IT` | 5.12B (2.3B eff.) | 2026-05 | base Gemma 4 = Jan 2025; distilled on SEA-Instruct-**2602** | [card](https://huggingface.co/aisingapore/Gemma-SEA-LION-v4.5-E2B-IT) | yes | yes (Gemma4) | MIT, open | confounded: pre base + post SFT |
| `aisingapore/Qwen-SEA-LION-v4-8B-VL` | 8.77B | 2025-11-21 | base Qwen3-VL-8B (unstated); SEA SFT | [card](https://huggingface.co/aisingapore/Qwen-SEA-LION-v4-8B-VL) | yes | yes (`Qwen3VLForConditionalGeneration`) | MIT, open | unclear |
| `aisingapore/Apertus-SEA-LION-v4-8B-IT` | 8.05B | 2026-02-05 | base Apertus 1.0 (unstated) | [card](https://huggingface.co/aisingapore/Apertus-SEA-LION-v4-8B-IT) | yes | yes | MIT, open | unclear |

### Families checked and found to have no relevant small release

| Family | What exists on HF |
|---|---|
| Llama 4.x / 5 | Only Llama-4-Scout/Maverick (17B-active MoE, Apr 2025). No small Llama after 3.2. |
| Phi-5 | Not on HF. Newest small Phi is Phi-4-mini (2025-02). |
| Qwen3.6 / Qwen3.8 | Only 27B and up (Qwen3.6-27B, Qwen3.8-27B, MoE). No small dense sizes. Qwen4 only as an internal `qwen4_exp` arch inside Qwen3.8-Flash-Next (180B). |
| GLM | GLM-4.6V-Flash is 10.3B (VLM, Dec 2025, zh/en only, cutoff unstated). GLM-5.x Flash is 321B. |
| DeepSeek | No new small distills (V3.2/V4 are large; only speculative-decoding drafters). |
| OLMo / SmolLM | No OLMo 4 / Olmo 3.5. No SmolLM4. |
| Vietnamese institutions | No new open LLM from VinAI, Viettel, FPT, VNPT, Zalo or GreenNode after July 2025 (HF author and keyword search). Recent "Vietnamese" repos are community fine-tunes of Qwen3/Qwen3.5. |

`Vikhrmodels/Vistral-24B-Instruct` is a Russian model despite the name.

**Also checked, cutoff unstated, not shortlisted:**

| Model | params | release | Note |
|---|---|---|---|
| `tiiuae/Falcon-H1R-7B` | 7.6B | Jan 2026 | |
| `tencent/Hunyuan-7B-Instruct` | 7.5B | Aug 2025 | |
| `arcee-ai/Trinity-Nano-Preview` | 6.1B MoE | Dec 2025 | |
| `LGAI-EXAONE/EXAONE-4.0-1.2B` | 1.3B | Jul 2025 | ko/en/es |
| `ibm-granite/granite-4.0-h-tiny` | 6.9B MoE | Oct 2025 | |
| `zai-org/GLM-4.6V-Flash` | 10.3B | Dec 2025 | zh/en |
| `microsoft/FrogNano-4B-2609` | | | Qwen3.5-4B coding fine-tune; English only |

## Recommended set

### Core, 8B or smaller

| Role | Model | Why |
|---|---|---|
| **Matched pair (pre)** | `Qwen/Qwen3-4B` | Apr 2025 release. Unofficial cutoff 2025-03-31, which is announce-era-early, before Resolution 60. |
| **Matched pair (post)** | `Qwen/Qwen3.5-4B` | Mar 2026 release, cutoff unstated. Same vendor and same size class (4.66B incl. vision tower; run text-only). Cleanest same-family comparison available. Add `Qwen3.5-2B` vs `Qwen3-1.7B` as a second, smaller pair. |
| Pre | `meta-llama/Llama-3.2-3B-Instruct` | Stated Dec 2023, a very clean control. Use `Llama-3.1-8B-Instruct` instead to match 8B. Gated: request access early. |
| Pre | `google/gemma-3-4b-it` | Stated Aug 2024. Gated click-through. |
| Pre (Vietnamese-specialised) | `SeaLLMs/SeaLLMs-v3-7B-Chat` or `Viet-Mistral/Vistral-7B-Chat` | 2024 data. Shows that Vietnamese fluency does not equal reform knowledge. Vistral needs manual gating approval, so SeaLLMs-v3 is the safer default. |
| Post? | `CohereLabs/tiny-aya-global` (or `CohereLabs/tiny-aya-water`) | Feb 2026, explicit Vietnamese support, cutoff unstated. NC licence is fine for research. `-water` is the Asia-Pacific/Europe region-tuned variant (vi listed, same licence and gating) and may be stronger on Vietnamese. `-global` is the default. |
| Straddle / post | `mistralai/Ministral-3-8B-Instruct-2512` | The **only** small model with a stated cutoff in or after July 2025 ("up to July 2025"). Vietnamese is not an officially supported language, so expect weaker Vietnamese overall. Report it as "straddle". |
| **Negative control** | `google/gemma-4-E4B-it` | Released Apr 2026 but stated cutoff Jan 2025. If it fails the headline question while Qwen3.5 passes, that supports the claim that the cutoff matters, not the release date. Strongly recommended. Only a *fail* is informative: a pass could come from post-training data newer than the pretraining cutoff. |

### Optional larger scale point (≤14B)

`Qwen/Qwen3-14B` (pre) vs `Qwen/Qwen3.5-9B` (post?, 9.65B), plus `mistralai/Ministral-3-14B-Instruct-2512` (straddle) and
`google/gemma-4-12B-it` (decoy).

`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (3B active) is the only model found that states both a pre-reform pretraining
cutoff (2025-06-25) and a post-reform post-training cutoff (2025-11-28). It is interesting as a "post-training only"
case, but it is 31.6B total.

### Not recommended as core

| Model(s) | Reason |
|---|---|
| Granite 4.1/4.2 | No Vietnamese; cutoff unstated |
| Olmo 3 | English-only; Dec 2024 |
| Apertus v1.5 | Arch not in the vLLM registry; gated; cutoff unstated |
| LFM2.5-2.6B | Cutoff unstated; sibling states mid-2024; vendor says not for knowledge tasks |
| Qwen3-4B-Instruct-2507 | Announce-era cutoff muddies the "pre" side |
| PhoGPT | No vLLM support |
| SEA-LION v4.x | Confounded base/post-training dates; use only as a side analysis |

## Key uncertainties and what to do about them

1. **Qwen3.5 cutoff is unstated.** It is not in the HF card, there is no text tech report, and the only "2026" claim comes
   from API system prompts. Qwen3's 2025-03-31 date is also unofficial (an OpenRouter figure). The matched pair rests on
   release-date ordering.
2. **Tiny Aya, LFM2.5-2.6B, Apertus v1.5 and Granite 4.x cutoffs are unstated.** The Apertus v1.5 EU summary exists
   (`Apertus_1_5_EU_Public_Summary.pdf` in the gated repo) and would likely answer this once access is accepted.
3. **Ministral 3's "July 2025" is the latest collection date for *some* dataset.** Most of its knowledge comes from
   Mistral Small 3.1 (released Mar 2025), its pruning/distillation parent.
4. **Not checked here (gated cards):** Vistral's card text and Gemma 3n's cutoff.
5. **Empirical cutoff probe (do it before trusting the groups).** Ask every model, in Vietnamese and without
   retrieval:
   - (a) "Việt Nam hiện có bao nhiêu tỉnh, thành phố trực thuộc trung ương?"
   - (b) 3–5 widely reported non-reform events from Aug–Dec 2025, as a generic recency check.

   Optionally, compare the per-token log-likelihood of short post-July-2025 Vietnamese news snippets that use new
   province names against pre-reform paraphrases. Then regroup models by observed behaviour, with release and stated
   cutoff as covariates.
6. **Text-only use of VLM checkpoints.** Qwen3.5, Ministral 3 and Gemma 4 are vision-language checkpoints. vLLM supports
   them, but load them with images disabled (e.g. `limit_mm_per_prompt={"image": 0}`). Verify on the vLLM version you
   pin, because Qwen3.5's gated-DeltaNet hybrid needs a recent vLLM.
7. **Free hosted endpoints (noted, not used):** OpenRouter lists `liquid/lfm-2.5-2.6b:free`.
