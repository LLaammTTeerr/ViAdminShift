#!/bin/bash
# Date-placement / phrasing / pre-reform-date controls for the reseller-served knowers, run in priority order so that
# whatever completes before the provider refuses requests forms whole cells:
#   sys0q (as-of in Q) -> sys0qm (today-is in Q) -> sys2025 (2025 date in sys) -> q2025 (2025 date in Q),
#   first for GPT-6, Kimi-K3, GLM-5.3, then GLM-5.3-Flash and GPT-5.5 (whose endpoint injects today's date).
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
R=results/minitest; I=$R/items; O=$R/sysprompt; L=$R/omni_controls.log; OR=https://api.cheaperinference.com
OFF='{"thinking": {"type": "disabled"}}'
SYS0="Bạn là một trợ lý hữu ích."; SYS25="$SYS0 Hôm nay là ngày 01/01/2025."
touch $R/omni_controls.out
run() {  # model items tag system
  grep -q PROVIDER-STOP $R/omni_controls.out && return
  for t in 1 2 3; do
    python3 scripts/minitest.py run --items $I/$2 --url $OR --api-key-env OR_TOKEN --model $1 --extra "$OFF" --max-tokens 1024 \
      --par 6 --out $O/preds_$3_$1__omni.jsonl ${4:+--system "$4"} >> $L 2>&1 && { echo "$(date +%T) done $1 $3"; return; }
    tail -n 5 $L | grep -q "402\|nsufficient\|credit" && { echo "$(date +%T) PROVIDER-STOP $1 $3"; return; }  # the provider refuses requests
    sleep 60
  done; echo "$(date +%T) FAIL $1 $3"
}
phase() {  # tag items system models...
  local tag=$1 items=$2 sys=$3; shift 3
  for m in "$@"; do run $m $items $tag "$sys" & done; wait
}
for M in "gpt-6-sol kimi-k3 glm-5.3" "glm-5.3-flash gpt-5.5"; do
  phase sys0q sysdate_q_items.jsonl "$SYS0" $M
  phase sys0qm sysdate_qm_items.jsonl "$SYS0" $M
  phase sys2025 sysdate_items.jsonl "$SYS25" $M
  phase q2025 sysdate_q2025_items.jsonl "" $M
done
echo "$(date +%T) OMNI_CONTROLS_DONE"
