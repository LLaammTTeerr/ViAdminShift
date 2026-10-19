#!/bin/bash
# Confound control: plain system prompt (sys0) + date IN THE QUESTION. Compared with sys1 (date in system prompt),
# this isolates date location with system-prompt presence held fixed. Own keys only (Anthropic, DeepSeek).
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items/sysdate_q_items.jsonl; O=results/minitest/sysprompt; SYS0="Bạn là một trợ lý hữu ích."
go() {  # url keyenv model extra src par
  python3 scripts/minitest.py run --items $I --url $1 --api-key-env $2 --model $3 --extra "$4" --max-tokens 1024 --par $6 \
    --system "$SYS0" --out $O/preds_sys0q_$3__$5.jsonl > /dev/null 2>> results/minitest/sys_dateq.log \
    && echo "$(date +%T) done $3" || echo "$(date +%T) FAIL $3"
}
go https://api.deepseek.com DS_TOKEN deepseek-flash '{"thinking": {"type": "disabled"}}' api 8 &
go https://api.anthropic.com CL_TOKEN claude-sonnet-5-5 '{"temperature": null, "thinking": {"type": "between_tools"}}' claude_nothink 4 &
go https://api.anthropic.com CL_TOKEN claude-haiku-5-5 '{"temperature": null, "thinking": {"type": "disabled"}}' claude 4 &
go https://api.anthropic.com CL_TOKEN claude-opus-5-5 '{"temperature": null, "reasoning_effort": "none"}' claude 4 &
go https://api.anthropic.com CL_TOKEN claude-fable-5-1 '{"temperature": null}' claude 4 &
wait; echo SYSQ_DONE
