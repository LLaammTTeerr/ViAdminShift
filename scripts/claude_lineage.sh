#!/bin/bash
# Claude lineage (Oct 2025 -> Sep 2026) on the cue ladder: when does knowledge of the reform appear, and does the
# old-map default persist across generations? Own key (CL_TOKEN). Knowers then get cue3np and the date controls.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; O=results/minitest/claude; L=results/minitest/claude_lineage.log
U=https://api.anthropic.com; SYS0="Bạn là một trợ lý hữu ích."; SYS1="$SYS0 Hôm nay là ngày 13/10/2026."
SYS25="$SYS0 Hôm nay là ngày 01/01/2025."
run() {  # model extra items out [system]
  python3 scripts/minitest.py run --items $I/$3 --url $U --api-key-env CL_TOKEN --model $1 --extra "$2" --max-tokens 1024 \
    --par 3 --out $4 ${5:+--system "$5"} > /dev/null 2>> $L && echo "$(date +%T) done $1 $3 $(basename $4)" || echo "$(date +%T) FAIL $1 $(basename $4)"
}
one() {  # model extra
  run $1 "$2" cue3_items.jsonl $O/preds_cue3_$1.jsonl
  if python3 scripts/minitest.py knows $O/preds_cue3_$1.jsonl > /dev/null 2>&1; then
    echo "$(date +%T) KNOWS $1"
    run $1 "$2" cue3np_items.jsonl $O/preds_cue3np_$1.jsonl
    S=results/minitest/sysprompt
    run $1 "$2" sysdate_items.jsonl $S/preds_sys0_$1__claude.jsonl "$SYS0"
    run $1 "$2" sysdate_items.jsonl $S/preds_sys1_$1__claude.jsonl "$SYS1"
    run $1 "$2" sysdate_q_items.jsonl $S/preds_sys0q_$1__claude.jsonl "$SYS0"
    run $1 "$2" sysdate_qm_items.jsonl $S/preds_sys0qm_$1__claude.jsonl "$SYS0"
    run $1 "$2" sysdate_items.jsonl $S/preds_sys2025_$1__claude.jsonl "$SYS25"
  else echo "$(date +%T) NOT-KNOWS $1"; fi
}
A='{"temperature": 0, "thinking": {"type": "disabled"}}'; B='{"temperature": null, "thinking": {"type": "disabled"}}'
one claude-haiku-4-5-20251001 "$A" & one claude-opus-4-5-20251101 "$A" & one claude-opus-4-6 "$A" & one claude-sonnet-4-6 "$A" &
one claude-opus-4-7 "$B" & one claude-opus-4-8 "$B" & one claude-sonnet-5 "$B" & one claude-opus-5 "$B" &
one claude-fable-5 '{"temperature": null, "reasoning_effort": "none"}' &
wait; echo LINEAGE_DONE
