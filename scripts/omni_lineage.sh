#!/bin/bash
# Family lineages on the reseller (cue3 ladder, 549 items): when does knowledge of the reform appear in each family,
# and does the no-cue default persist once it has? Newest / most informative first; stops once the provider refuses requests.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
R=results/minitest; I=$R/items; L=$R/omni_lineage.log; OR=https://api.cheaperinference.com
OFF='{"thinking": {"type": "disabled"}}'
touch $R/omni_lineage.out
run() {  # model
  grep -q PROVIDER-STOP $R/omni_lineage.out $R/omni_controls.out && return
  for t in 1 2 3; do
    python3 scripts/minitest.py run --items $I/cue3_items.jsonl --url $OR --api-key-env OR_TOKEN --model $1 --extra "$OFF" \
      --max-tokens 1024 --par 4 --out $R/omni/preds_cue3_$1.jsonl >> $L 2>&1 && { echo "$(date +%T) done $1"; return; }
    tail -n 5 $L | grep -q "402\|nsufficient\|credit" && { echo "$(date +%T) PROVIDER-STOP $1"; return; }  # the provider refuses requests
    sleep 60
  done; echo "$(date +%T) FAIL $1"
}
wave() { for m in "$@"; do run $m & done; wait; }
wave gpt-6.1-sol glm-5.2 deepseek-v4-flash grok-4.6 gpt-5.6-sol
wave gpt-6-luna gpt-6-astra glm-5.1 deepseek-v4-pro-0813 grok-4.5
wave gpt-5.4 glm-5 glm-4.7 deepseek-v4-flash-0731 glm-5.3-prime
echo "$(date +%T) OMNI_LINEAGE_DONE"
