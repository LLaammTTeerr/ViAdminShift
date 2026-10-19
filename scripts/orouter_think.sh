#!/bin/bash
# Reasoning ON (provider default effort) for GPT-6 and Kimi-K3 through OpenRouter, T1np absorbed units, plain system
# prompt / today's date in it / "as of" in the question: does reasoning explain the gap between the reseller runs
# (which reasoned despite "thinking disabled") and the reasoning-off OpenRouter runs?
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; S=results/minitest/sysprompt; L=results/minitest/orouter/think.log
ON='{"reasoning": {"enabled": true}}'; S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."
go() {  # model short tag items system
  python3 scripts/minitest.py run --items $I/$4 --url https://openrouter.ai/api --api-key-env OPENROUTER_TOKEN --model $1 \
    --extra "$ON" --max-tokens 8192 --par 4 --rpm 19 --only T1np_ward_province:absorbed \
    --out $S/preds_$3_$2__orouter_think.jsonl --system "$5" >> $L 2>&1 && echo "$(date +%T) done $2 $3" || echo "$(date +%T) FAIL $2 $3"
}
for M in "openai/gpt-6-sol gpt-6-sol" "moonshotai/kimi-k3 kimi-k3"; do
  set -- $M
  ( go $1 $2 sys0 sysdate_items.jsonl "$S0"; go $1 $2 sys1 sysdate_items.jsonl "$S1"; go $1 $2 sys0q sysdate_q_items.jsonl "$S0" ) &
done
wait; echo "$(date +%T) THINK_DONE"
