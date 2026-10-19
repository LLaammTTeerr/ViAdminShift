#!/bin/bash
# Second-review controls, own keys only (Anthropic, DeepSeek), for the first-party knowers:
#   newname : post-reform ward name, no district, none/date/reform  -> frame-following vs temporal default
#   prefix  : "Hiện nay, " (currently) and a content-free filler on T1/T1np -> is "as of" special, or any prefix?
#   sysasof : "answer as of 10/2026" in the SYSTEM prompt (completes placement x phrasing)
#   r2, r3  : two repeats of the cue3 ladder -> run-to-run variance at default temperature
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; O=results/review; L=$O/run.log; mkdir -p $O
SYSA="Bạn là một trợ lý hữu ích. Hãy trả lời theo thông tin tính đến tháng 10/2026."
one() {  # items tag system url keyenv model extra src par
  python3 scripts/minitest.py run --items $I/$1 --url $4 --api-key-env $5 --model $6 --extra "$7" --max-tokens 1024 --par $9 \
    ${3:+--system "$3"} --out $O/preds_$2_$6__$8.jsonl > /dev/null 2>> $L && echo "$(date +%T) done $2 $6" || echo "$(date +%T) FAIL $2 $6"
}
model() {  # url keyenv model extra src par
  one newname_items.jsonl newname "" "$@"
  one prefix_items.jsonl prefix "" "$@"
  one sysdate_items.jsonl sysasof "$SYSA" "$@"
  one cue3_items.jsonl r2 "" "$@"
  one cue3_items.jsonl r3 "" "$@"
}
model https://api.deepseek.com DS_TOKEN deepseek-flash '{"thinking": {"type": "disabled"}}' api 8 &
model https://api.anthropic.com CL_TOKEN claude-sonnet-5-5 '{"temperature": null, "thinking": {"type": "between_tools"}}' claude_nothink 4 &
model https://api.anthropic.com CL_TOKEN claude-haiku-5-5 '{"temperature": null, "thinking": {"type": "disabled"}}' claude 4 &
model https://api.anthropic.com CL_TOKEN claude-opus-5-5 '{"temperature": null, "reasoning_effort": "none"}' claude 4 &
model https://api.anthropic.com CL_TOKEN claude-fable-5-1 '{"temperature": null}' claude 4 &
wait; echo REVIEW2_DONE
