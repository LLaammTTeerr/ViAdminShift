#!/bin/bash
# Claude Fable 5.1 at its lowest reasoning setting (reasoning_effort=none), the setting Opus 5.5 and Fable 5 ran at.
# Repeats every Fable 5.1 run made at the default setting (cue ladder, no-province T1, system-prompt date, review
# controls) with the same items, prompts and limits; outputs carry the source tag claude_none, next to the default-
# setting files (source claude), which stay as the reasoning comparison.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
R=results/minitest; I=$R/items; U=https://api.anthropic.com; M=claude-fable-5-1; L=$R/fable51_none.log
X='{"temperature": null, "reasoning_effort": "none"}'
SYS0="Bạn là một trợ lý hữu ích."; SYS1="$SYS0 Hôm nay là ngày 13/10/2026."; SYS25="$SYS0 Hôm nay là ngày 01/01/2025."
SYSA="$SYS0 Hãy trả lời theo thông tin tính đến tháng 10/2026."
one() {  # items out [system]
  python3 scripts/minitest.py run --items $I/$1 --url $U --api-key-env CL_TOKEN --model $M --extra "$X" --max-tokens 1024 \
    --par 4 --out $2 ${3:+--system "$3"} > /dev/null 2>> $L && echo "$(date +%T) done $(basename $2)" || echo "$(date +%T) FAIL $(basename $2)"
}
mkdir -p $R/claude_none $R/sysprompt results/review
{ one cue3_items.jsonl $R/claude_none/preds_cue3_$M.jsonl
  one cue3np_items.jsonl $R/claude_none/preds_cue3np_$M.jsonl
  one cue3sub_items.jsonl $R/claude_none/preds_cue3full_$M.jsonl; } &
{ one sysdate_items.jsonl $R/sysprompt/preds_sys0_${M}__claude_none.jsonl "$SYS0"
  one sysdate_items.jsonl $R/sysprompt/preds_sys1_${M}__claude_none.jsonl "$SYS1"
  one sysdate_q_items.jsonl $R/sysprompt/preds_sys0q_${M}__claude_none.jsonl "$SYS0"
  one sysdate_qm_items.jsonl $R/sysprompt/preds_sys0qm_${M}__claude_none.jsonl "$SYS0"
  one sysdate_items.jsonl $R/sysprompt/preds_sys2025_${M}__claude_none.jsonl "$SYS25"
  one sysdate_q2025_items.jsonl $R/sysprompt/preds_q2025_${M}__claude_none.jsonl; } &
{ one newname_items.jsonl results/review/preds_newname_${M}__claude_none.jsonl
  one prefix_items.jsonl results/review/preds_prefix_${M}__claude_none.jsonl
  one sysdate_items.jsonl results/review/preds_sysasof_${M}__claude_none.jsonl "$SYSA"; } &
wait; echo FABLE51_NONE_DONE
