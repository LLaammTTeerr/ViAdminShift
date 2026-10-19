#!/bin/bash
# Reviewer control: the same T1np questions WITHOUT "Chỉ trả lời ngắn gọn bằng tên, không giải thích" (answer briefly,
# name only), plain system prompt and today's date in it; reasoning off. Do models flag the reform when free to explain?
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items/sysdate_nosuffix_items.jsonl; S=results/minitest/sysprompt; L=results/minitest/nosuffix.log
S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."; OFF='{"reasoning": {"enabled": false}}'
go() {  # url keyenv model short src extra tag system rpm
  python3 scripts/minitest.py run --items $I --url $1 --api-key-env $2 --model $3 --extra "$6" --max-tokens 1024 --par 4 \
    ${9:+--rpm $9} --only T1np_ward_province:absorbed --system "$8" --out $S/preds_$7_$4__$5.jsonl >> $L 2>&1 \
    && echo "$(date +%T) done $4 $7" || echo "$(date +%T) FAIL $4 $7"
}
( go https://api.deepseek.com DS_TOKEN deepseek-flash deepseek-flash api '{"thinking": {"type": "disabled"}}' sys0ns "$S0"
  go https://api.deepseek.com DS_TOKEN deepseek-flash deepseek-flash api '{"thinking": {"type": "disabled"}}' sys1ns "$S1" ) &
for m in openai/gpt-6-sol:gpt-6-sol openai/gpt-6-luna:gpt-6-luna; do
  ( go https://openrouter.ai/api OPENROUTER_TOKEN ${m%%:*} ${m#*:} orouter "$OFF" sys0ns "$S0" 15
    go https://openrouter.ai/api OPENROUTER_TOKEN ${m%%:*} ${m#*:} orouter "$OFF" sys1ns "$S1" 15 ) &
done
wait; echo "$(date +%T) NOSUFFIX_DONE"
