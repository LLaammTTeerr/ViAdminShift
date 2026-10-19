#!/bin/bash
# Step-5 (passed the knowledge gate): complete its cue ladder (base set + T1np) like the other OpenRouter knowers,
# after round2b.sh; reasoning cannot be disabled, lowest effort; one request at a time. Resumes.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
while pgrep -f "[b]ash scripts/round2b.sh" > /dev/null; do sleep 30; done
I=results/minitest/items; O=results/minitest/orouter; L=$O/more.log; LOW='{"reasoning": {"effort": "low"}}'
for f in cue3 cue3np; do
  python3 scripts/minitest.py run --items $I/${f}_items.jsonl --url https://openrouter.ai/api --api-key-env OPENROUTER_TOKEN \
    --model stepfun/step-5-preview --extra "$LOW" --max-tokens 4096 --par 2 --rpm 19 --out $O/preds_${f}_step-5-preview.jsonl \
    >> $L 2>&1 && echo "$(date +%T) done step-5 $f" || echo "$(date +%T) FAIL step-5 $f"
done
echo "$(date +%T) ROUND2C_DONE"
