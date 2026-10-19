#!/bin/bash
# Knowledge-gate screen for models not yet in the paper (OpenRouter): the 80 absorbed T1 items with the reform cue
# (pre-registered gate: correct >= 0.50). Reasoning off where the endpoint allows it, otherwise the lowest effort.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
O=results/minitest/orouter; L=$O/screen.log
OFF='{"reasoning": {"enabled": false}}'; LOW='{"reasoning": {"effort": "low"}}'
go() {  # model extra maxtokens
  local s=${1#*/}
  python3 scripts/minitest.py run --items results/minitest/items/cue3_items.jsonl --url https://openrouter.ai/api \
    --api-key-env OPENROUTER_TOKEN --model $1 --extra "$2" --max-tokens $3 --par 4 --rpm 19 \
    --only T1_ward_province:absorbed:reform --out $O/preds_cue3_$s.jsonl >> $L 2>&1
  python3 scripts/minitest.py knows $O/preds_cue3_$s.jsonl
}
for m in mistralai/mistral-large-4-0 tencent/hy4-preview openai/gpt-6-luna meituan/longcat-2.0 openai/gpt-5.6-terra; do
  go $m "$OFF" 1024 &
done
for m in x-ai/grok-4.7 google/gemini-4-argon stepfun/step-5-preview; do go $m "$LOW" 4096 & done
wait; echo SCREEN_DONE
