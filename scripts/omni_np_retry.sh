#!/bin/bash
# Resume OmniRoute no-province jobs until each has 360 items (transient provider errors outlast in-run retries).
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items/cue3np_items.jsonl; L=results/minitest/omni_np_retry.log
job() {
  f=results/minitest/omni/preds_cue3np_$1.jsonl
  for t in 1 2 3 4 5 6; do
    [ "$(cat $f 2>/dev/null | wc -l)" -ge 360 ] && { echo "$(date +%T) done $1"; return; }
    pgrep -f "[m]initest.py run.*cue3np.*--model $1 " >/dev/null && { sleep 120; continue; }  # original job still running
    python3 scripts/minitest.py run --items $I --url https://api.cheaperinference.com --api-key-env OR_TOKEN --model $1 \
      --extra "$2" --max-tokens 1024 --par 4 --out $f >> $L 2>&1 || sleep 120
  done; echo "$(date +%T) FAIL $1 $(wc -l < $f)/360"
}
OFF='{"thinking": {"type": "disabled"}}'
for m in gpt-6-sol kimi-k3 glm-5.3 glm-5.3-flash muse-spark-1.2 gpt-5.5 grok-4.7 qwen3.8-flash deepseek-v4.1-flash claude-opus-5.5 qwen3.8-max; do job $m "$OFF" & done
job deepseek-v4-pro '{}' &
wait; echo OMNI_NP_DONE
