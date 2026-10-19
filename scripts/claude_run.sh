#!/bin/bash
# Claude models via Anthropic's OpenAI-compatible endpoint (key in $CL_TOKEN).
# Temperature is rejected by these models -> dropped via {"temperature": null}.
# Opus cannot disable thinking on this endpoint; reasoning_effort=none is its minimum.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
U=https://api.anthropic.com; I=results/minitest/items
declare -A X=(
  [claude-sonnet-5-5]='{"temperature": null}'
  [claude-fable-5-1]='{"temperature": null}'
  [claude-haiku-5-5]='{"temperature": null, "thinking": {"type": "disabled"}}'
  [claude-opus-5-5]='{"temperature": null, "reasoning_effort": "none"}'
)
one() {
  m=$1; par=8; [ $m = claude-opus-5-5 ] && par=4
  python3 scripts/minitest.py run --items $I/cue3_items.jsonl --url $U --model $m --api-key-env CL_TOKEN \
    --extra "${X[$m]}" --max-tokens 1024 --par $par --out results/minitest/claude/preds_cue3_$m.jsonl || { echo "FAIL $m cue3"; return; }
  if python3 scripts/minitest.py knows results/minitest/claude/preds_cue3_$m.jsonl; then
    python3 scripts/minitest.py run --items $I/cue3sub_items.jsonl --url $U --model $m --api-key-env CL_TOKEN \
      --extra "${X[$m]}" --max-tokens 1024 --par $par --out results/minitest/claude/preds_cue3full_$m.jsonl || echo "FAIL $m cue3sub"
  fi
  echo "$(date +%T) done $m"
}
mkdir -p results/minitest/claude
for m in "${!X[@]}"; do one $m & done; wait; echo CLAUDE_DONE
