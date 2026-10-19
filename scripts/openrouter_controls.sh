#!/bin/bash
# GPT-6 and Kimi-K3 through OpenRouter (reasoning off), one provider for every condition. New OpenRouter accounts are
# limited to 20 requests per minute per model, so each model runs sequentially at 19 rpm (the two models in parallel):
#  1. date placement on absorbed units (80 each): T1np under sys0, sys1, sys0q, sys0qm, sysasof; T1 under sys0, sys1,
#     sys2025, q2025 (the cells of the date-placement tables);
#  2. agent settings (scripts/agent_date.py) on the paper's 80 absorbed + 40 kept T1np units.
# Everything resumes (completed ids are skipped).
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; O=results/minitest/sysprompt; L=results/minitest/openrouter_controls.log
URL=https://openrouter.ai/api; OFF='{"reasoning": {"enabled": false}}'
S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."; S25="$S0 Hôm nay là ngày 01/01/2025."
SA="$S0 Hãy trả lời theo thông tin tính đến tháng 10/2026."
go() {  # model short tag items only outdir system
  python3 scripts/minitest.py run --items $I/$4 --url $URL --api-key-env OPENROUTER_TOKEN --model $1 --extra "$OFF" \
    --max-tokens 1024 --par 4 --rpm 19 --only $5 --out $6/preds_$3_$2__orouter.jsonl ${7:+--system "$7"} >> $L 2>&1 \
    && echo "$(date +%T) done $2 $3 $5" || echo "$(date +%T) FAIL $2 $3 $5"
}
chain() {  # model short
  local NP=T1np_ward_province:absorbed T1=T1_ward_province:absorbed
  go $1 $2 sys0 sysdate_items.jsonl $NP $O "$S0"; go $1 $2 sys1 sysdate_items.jsonl $NP $O "$S1"
  go $1 $2 sys0q sysdate_q_items.jsonl $NP $O "$S0"; go $1 $2 sys0qm sysdate_qm_items.jsonl $NP $O "$S0"
  go $1 $2 sysasof sysdate_items.jsonl $NP results/review "$SA"
  go $1 $2 sys0 sysdate_items.jsonl $T1 $O "$S0"; go $1 $2 sys1 sysdate_items.jsonl $T1 $O "$S1"
  go $1 $2 sys2025 sysdate_items.jsonl $T1 $O "$S25"; go $1 $2 q2025 sysdate_q2025_items.jsonl $T1 $O
  python3 scripts/agent_date.py run $2 --paper --rpm 19 >> $L 2>&1 && echo "$(date +%T) done $2 agent" || echo "$(date +%T) FAIL $2 agent"
}
chain openai/gpt-6-sol gpt-6-sol & chain moonshotai/kimi-k3 kimi-k3 &
wait; echo "$(date +%T) OPENROUTER_CONTROLS_DONE"
