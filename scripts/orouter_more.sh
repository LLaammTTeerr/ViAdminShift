#!/bin/bash
# Models added through OpenRouter after the knowledge-gate screen (scripts/orouter_screen.sh), 19 rpm per model:
#  - GPT-6-Luna, GPT-5.6-Terra, Tencent HY4 (reasoning off): full cue ladder (cue3 + cue3np), date placement, agent test;
#  - Grok-4.7, Step-5 (reasoning mandatory, lowest effort): full cue ladder only;
#  - Kimi-K3: resume the two runs interrupted by a network timeout.
# Everything resumes (completed ids are skipped).
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; O=results/minitest/orouter; S=results/minitest/sysprompt; L=$O/more.log
URL=https://openrouter.ai/api; OFF='{"reasoning": {"enabled": false}}'; LOW='{"reasoning": {"effort": "low"}}'
S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."; S25="$S0 Hôm nay là ngày 01/01/2025."
SA="$S0 Hãy trả lời theo thông tin tính đến tháng 10/2026."
mt() {  # model extra maxtok items out [only] [system]
  python3 scripts/minitest.py run --items $I/$4 --url $URL --api-key-env OPENROUTER_TOKEN --model $1 --extra "$2" \
    --max-tokens $3 --par 4 --rpm 19 --out $5 ${6:+--only $6} ${7:+--system "$7"} >> $L 2>&1 \
    && echo "$(date +%T) done ${1#*/} $(basename $5) $6" || echo "$(date +%T) FAIL ${1#*/} $(basename $5) $6"
}
ladder() {  # model extra maxtok
  local s=${1#*/}
  mt $1 "$2" $3 cue3_items.jsonl $O/preds_cue3_$s.jsonl; mt $1 "$2" $3 cue3np_items.jsonl $O/preds_cue3np_$s.jsonl
}
placement() {  # model
  local s=${1#*/} NP=T1np_ward_province:absorbed T1=T1_ward_province:absorbed
  mt $1 "$OFF" 1024 sysdate_items.jsonl $S/preds_sys0_${s}__orouter.jsonl $NP "$S0"
  mt $1 "$OFF" 1024 sysdate_items.jsonl $S/preds_sys1_${s}__orouter.jsonl $NP "$S1"
  mt $1 "$OFF" 1024 sysdate_q_items.jsonl $S/preds_sys0q_${s}__orouter.jsonl $NP "$S0"
  mt $1 "$OFF" 1024 sysdate_qm_items.jsonl $S/preds_sys0qm_${s}__orouter.jsonl $NP "$S0"
  mt $1 "$OFF" 1024 sysdate_items.jsonl results/review/preds_sysasof_${s}__orouter.jsonl $NP "$SA"
  mt $1 "$OFF" 1024 sysdate_items.jsonl $S/preds_sys0_${s}__orouter.jsonl $T1 "$S0"
  mt $1 "$OFF" 1024 sysdate_items.jsonl $S/preds_sys1_${s}__orouter.jsonl $T1 "$S1"
  mt $1 "$OFF" 1024 sysdate_items.jsonl $S/preds_sys2025_${s}__orouter.jsonl $T1 "$S25"
  mt $1 "$OFF" 1024 sysdate_q2025_items.jsonl $S/preds_q2025_${s}__orouter.jsonl $T1
}
agent() { python3 scripts/agent_date.py run $1 --paper --rpm 19 >> $L 2>&1 && echo "$(date +%T) done $1 agent" || echo "$(date +%T) FAIL $1 agent"; }
for m in openai/gpt-6-luna openai/gpt-5.6-terra tencent/hy4-preview; do
  ( ladder $m "$OFF" 1024; placement $m; agent ${m#*/} ) &
done
for m in x-ai/grok-4.7 stepfun/step-5-preview; do ( ladder $m "$LOW" 4096 ) & done
( mt moonshotai/kimi-k3 "$OFF" 1024 sysdate_items.jsonl $S/preds_sys1_kimi-k3__orouter.jsonl T1np_ward_province:absorbed "$S1"
  agent kimi-k3 ) &
wait; echo "$(date +%T) ORouter_MORE_DONE"
