#!/bin/bash
# Re-run Claude no-province jobs (resume) until each has all 360 items; low concurrency, errors logged.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items/cue3np_items.jsonl; AN=https://api.anthropic.com; L=results/minitest/claude_np_retry.log
job() {  # model extra outdir
  f=$3/preds_cue3np_$1.jsonl
  for t in 1 2 3 4 5 6; do
    [ "$(cat $f 2>/dev/null | wc -l)" -ge 360 ] && { echo "$(date +%T) done $1 [$3]"; return; }
    python3 scripts/minitest.py run --items $I --url $AN --api-key-env CL_TOKEN --model $1 --extra "$2" \
      --max-tokens 1024 --par 2 --out $f >> $L 2>&1 || sleep 120
  done; echo "$(date +%T) FAIL $1 [$3] $(wc -l < $f)/360"
}
job claude-haiku-5-5 '{"temperature": null}' results/minitest/claude_think &
job claude-fable-5-1 '{"temperature": null}' results/minitest/claude &
job claude-haiku-5-5 '{"temperature": null, "thinking": {"type": "disabled"}}' results/minitest/claude &
wait; echo NP_RETRY_DONE
