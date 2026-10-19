#!/bin/bash
# Robustness: T1 without the old province in the question (cue3np_items, same 120 wards as cue3 T1).
# Each model is run with the exact settings of its cue3 run; preds go next to them as preds_cue3np_<model>.jsonl
# so analyze_cue.py merges both into one row.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items/cue3np_items.jsonl
OR=https://api.cheaperinference.com; AN=https://api.anthropic.com; DS=https://api.deepseek.com
OFF='{"thinking": {"type": "disabled"}}'
go() {  # url keyenv model extra outdir
  python3 scripts/minitest.py run --items $I --url $1 --api-key-env $2 --model $3 --extra "$4" \
    --max-tokens 1024 --par ${PAR:-6} --out $5/preds_cue3np_$3.jsonl > /dev/null 2>&1 \
    && echo "$(date +%T) done $3 [$5]" || echo "$(date +%T) FAIL $3 [$5]"
}
for m in gpt-6-sol kimi-k3 glm-5.3 glm-5.3-flash muse-spark-1.2 gpt-5.5 grok-4.7 qwen3.8-flash deepseek-v4.1-flash claude-opus-5.5 qwen3.8-max; do
  go $OR OR_TOKEN $m "$OFF" results/minitest/omni &
done
go $OR OR_TOKEN deepseek-v4-pro '{}' results/minitest/omni &
for m in deepseek-flash deepseek-v4-pro; do go $DS DS_TOKEN $m "$OFF" results/minitest/api & done
go $AN CL_TOKEN claude-sonnet-5-5 '{"temperature": null}' results/minitest/claude &
go $AN CL_TOKEN claude-fable-5-1 '{"temperature": null}' results/minitest/claude &
go $AN CL_TOKEN claude-haiku-5-5 '{"temperature": null, "thinking": {"type": "disabled"}}' results/minitest/claude &
PAR=3 go $AN CL_TOKEN claude-opus-5-5 '{"temperature": null, "reasoning_effort": "none"}' results/minitest/claude &
go $AN CL_TOKEN claude-sonnet-5-5 '{"temperature": null, "thinking": {"type": "between_tools"}}' results/minitest/claude_nothink &
go $AN CL_TOKEN claude-haiku-5-5 '{"temperature": null}' results/minitest/claude_think &
wait; echo NP_DONE
