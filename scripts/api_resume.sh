#!/usr/bin/env bash
# Resume the OmniRoute runs whose requests the provider had refused (Claude models go through the Anthropic API instead).
# 1) stratified deep subset (cue3sub) for models that know the update; reuses answers already in preds_cue3full_*.
# 2) finish the 549-item cue ladder for models whose requests the provider had refused.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
U=https://api.cheaperinference.com
python3 scripts/api_sweep.py --items results/minitest/items/cue3sub_items.jsonl --url $U --api-key-env OR_TOKEN \
  --outdir results/minitest/omni_full --tag cue3full --models-par 5 --par 8 \
  gpt-6-sol muse-spark-1.2 kimi-k3 glm-5.3 minimax-m3
python3 scripts/api_sweep.py --items results/minitest/items/cue3_items.jsonl --url $U --api-key-env OR_TOKEN \
  --outdir results/minitest/omni --tag cue3 --models-par 5 --par 8 \
  gpt-5.5 gemini-3.1-pro qwen3.8-flash qwen3.8-2.4t-a95b gpt-oss-120b gemma-4-31b-it qwen3.6-27b grok-4.7
