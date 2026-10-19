#!/bin/bash
# Reviewer-requested controls, own keys only (Anthropic, DeepSeek):
#   sys0qm : plain system prompt + the SAME date sentence as sys1 ("Hôm nay là ngày 13/10/2026.") in the question
#            -> location vs wording confound of sys1 vs sys0q
#   sys2025: plain system prompt + "Hôm nay là ngày 01/01/2025." -> does a pre-reform system date select the old map?
#   q2025  : no system prompt, "Tính đến tháng 1/2025, " in the question -> pre-reform date in the question
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; O=results/minitest/sysprompt; L=results/minitest/review_controls.log
SYS0="Bạn là một trợ lý hữu ích."; SYS25="$SYS0 Hôm nay là ngày 01/01/2025."
one() {  # items tag system url keyenv model extra src par
  python3 scripts/minitest.py run --items $I/$1 --url $4 --api-key-env $5 --model $6 --extra "$7" --max-tokens 1024 --par $9 \
    ${3:+--system "$3"} --out $O/preds_$2_$6__$8.jsonl > /dev/null 2>> $L && echo "$(date +%T) done $2 $6" || echo "$(date +%T) FAIL $2 $6"
}
model() {  # url keyenv model extra src par
  one sysdate_qm_items.jsonl sys0qm "$SYS0" "$@"
  one sysdate_items.jsonl sys2025 "$SYS25" "$@"
  one sysdate_q2025_items.jsonl q2025 "" "$@"
}
model https://api.deepseek.com DS_TOKEN deepseek-flash '{"thinking": {"type": "disabled"}}' api 8 &
model https://api.anthropic.com CL_TOKEN claude-sonnet-5-5 '{"temperature": null, "thinking": {"type": "between_tools"}}' claude_nothink 4 &
model https://api.anthropic.com CL_TOKEN claude-haiku-5-5 '{"temperature": null, "thinking": {"type": "disabled"}}' claude 4 &
model https://api.anthropic.com CL_TOKEN claude-opus-5-5 '{"temperature": null, "reasoning_effort": "none"}' claude 4 &
model https://api.anthropic.com CL_TOKEN claude-fable-5-1 '{"temperature": null}' claude 4 &
wait; echo REVIEW_CONTROLS_DONE
