#!/bin/bash
# Same-model thinking ablation (complements claude_run.sh):
#   Sonnet 5.5 thinking OFF ("between_tools" = no thinking without tools)  -> results/minitest/claude_nothink
#   Haiku 5.5 thinking ON (default adaptive)                               -> results/minitest/claude_think
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
U=https://api.anthropic.com; I=results/minitest/items
go() {  # model outdir extra
  mkdir -p $2
  for s in cue3 cue3sub; do
    t=$s; [ $s = cue3sub ] && t=cue3full
    python3 scripts/minitest.py run --items $I/${s}_items.jsonl --url $U --model $1 --api-key-env CL_TOKEN \
      --extra "$3" --max-tokens 2048 --par 8 --out $2/preds_${t}_$1.jsonl || echo "FAIL $1 $s"
  done; echo "$(date +%T) done $1 $2"
}
go claude-sonnet-5-5 results/minitest/claude_nothink '{"temperature": null, "thinking": {"type": "between_tools"}}' &
go claude-haiku-5-5 results/minitest/claude_think '{"temperature": null}' &
wait; echo ABLATION_DONE
