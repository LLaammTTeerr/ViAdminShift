# Benchmark runs (`results/bench/`)

Licence: CC BY-SA 4.0, except `tiny-aya-global-q8_0/`, CC BY-NC-SA 4.0 (see `../../data/LICENSE.md`, which also
states the terms of the hosted models' outputs).

One directory per model: `predictions.jsonl`, `scores.json`, `run_config.json` (every invocation, oldest first, in
`previous_runs`, with its token limits in `max_new_tokens`). `Muse-Glimmer-30B-Q8_0-full/` has no `run_config.json`:
it is the union of the closed-book and `rag_mixed` rows of `Muse-Glimmer-30B-Q8_0-sub1k/` (1,262 items) and of the
same conditions on the complement `data/benchmark/items_rest.jsonl` (6,733 items, run in two parts by
`scripts/vast/muse_rest.sh` and `muse_closed_split.sh`), so it covers all 7,995 items in both conditions. All its
rows were produced with the same settings as the sub1k run (`run_config.json` there): llama.cpp server, Q8_0 GGUF,
`chat_template_kwargs.reasoning_strength = none`, 1,024 new tokens for MCQ and short answers, concurrency 32;
`scores.json` is the runner's `--rescore` output for its `predictions.jsonl`. The runs of the retrieval section are produced with
`scripts/bench_api.sh` (API models) and the runner directly (local models); the tables with `scripts/analyze_rag.py`
and then `scripts/analyze_bench_extra.py` (in that order: the second rewrites `qtype_table.tex` without the leaked items).

Token limits are 16 (MCQ) / 64 (short answer); no DeepSeek-V4.1-Flash or GPT-6-Luna answer reached them. The two Claude
models often explain before answering.
For these, answers that stopped at the limit were deleted from `predictions.jsonl` with `scripts/drop_truncated.py`
and the same prompts sent again with higher limits (resume checks `prompt_sha1`, so the prompt is identical):

| model | first limits | re-asked | still cut at the end |
|---|---|---|---|
| Claude-Haiku-5.5 (OpenRouter) | 16 / 64 | 1,058 at 64 / 128 (1,035 closed, 6 rag_new, 6 rag_mixed, 11 rag_mixed+date); of these, 296 cut again at 512 / 512 (293 closed, 1 per retrieval condition) | 0 |
| Claude-Sonnet-5.5 (Anthropic, OpenAI-compatible endpoint) | 64 / 128 | 1,850 at 512 / 512 (1,849 closed, 1 rag_mixed) | 85 closed, scored as returned |

`muse_bench2.out` and `muse_bench_b.out` are the driver logs of `scripts/vast/muse_bench2.sh` and `muse_bench_b.sh`,
which split the Muse-Glimmer sub1k conditions between two GPU pairs; the second pair's rows were merged into
`Muse-Glimmer-30B-Q8_0-sub1k/predictions.jsonl`.

All other answers are the first ones given. `dropped_truncated.jsonl` in each directory holds the deleted answers
(raw output, prompt hash, the limits they were generated at): Haiku's 1,058 answers at 16 / 64 and Sonnet's 1,850 at
64 / 128. Both were taken from copies of `predictions.jsonl` made before the deletion; Haiku's 296 answers of
the 64 / 128 pass were not copied and are not available.

The retrieval conditions of the API models other than DeepSeek-V4.1-Flash run on
`data/benchmark/items_rag_sub.jsonl` (`scripts/make_rag_items.py`); closed-book always runs all 7,995 items.
