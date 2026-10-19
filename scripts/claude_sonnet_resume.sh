#!/bin/bash
# Resume Sonnet 5.5 thinking-OFF runs (cue3 + cue3sub) that hit 429 before the retry fix.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
X='{"temperature": null, "thinking": {"type": "between_tools"}}'; O=results/minitest/claude_nothink
for s in cue3 cue3sub; do t=$s; [ $s = cue3sub ] && t=cue3full
  python3 scripts/minitest.py run --items results/minitest/items/${s}_items.jsonl --url https://api.anthropic.com --api-key-env CL_TOKEN \
    --model claude-sonnet-5-5 --extra "$X" --max-tokens 2048 --par 4 --out $O/preds_${t}_claude-sonnet-5-5.jsonl > /dev/null 2>> results/minitest/claude_resume.log \
    && echo "$(date +%T) done sonnet-nothink $s" || echo "$(date +%T) FAIL sonnet-nothink $s"
done
