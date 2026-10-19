#!/bin/bash
# Round 2 (ARR revision), OpenRouter + DeepSeek API. Per model, one chain at 19 rpm (OpenRouter per-model limit), models
# in parallel, in a fixed order. Everything resumes (completed ids are skipped).
#  A. reasoning ON, GPT-6 / Kimi-K3: "today is" in the question (sys0qm) and "as of" in the system prompt (sysasof)
#  B. n=300: paper units + 220 absorbed / 40 kept others, reasoning off: sys1, sys0q, sys0qm, sysasof (agent_date --ext)
#  C. query rewriting (rewrites_deepseek-flash.jsonl) answered by each model, reasoning off
#  D. reasoning ON for GPT-6-Luna, GPT-5.6-Terra, HY4: sys0, sys1, sys0q, sys0qm, sysasof; Luna also the agent conditions
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
I=results/minitest/items; S=results/minitest/sysprompt; R=results/review; L=results/minitest/round2.log
ON='{"reasoning": {"enabled": true}}'; S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."
SA="$S0 Hãy trả lời theo thông tin tính đến tháng 10/2026."
think() {  # model short tag items outdir system
  python3 scripts/minitest.py run --items $I/$4 --url https://openrouter.ai/api --api-key-env OPENROUTER_TOKEN --model $1 \
    --extra "$ON" --max-tokens 8192 --par 4 --rpm 19 --only T1np_ward_province:absorbed \
    --out $5/preds_$3_$2__orouter_think.jsonl --system "$6" >> $L 2>&1 && echo "$(date +%T) done $2 think $3" || echo "$(date +%T) FAIL $2 think $3"
}
agent() {  # short label args...
  local s=$1 lab=$2; shift 2
  python3 scripts/agent_date.py run $s --rpm 19 "$@" >> $L 2>&1 && echo "$(date +%T) done $s $lab" || echo "$(date +%T) FAIL $s $lab"
}
think5() {  # model short
  think $1 $2 sys0 sysdate_items.jsonl $S "$S0"; think $1 $2 sys1 sysdate_items.jsonl $S "$S1"
  think $1 $2 sys0q sysdate_q_items.jsonl $S "$S0"; think $1 $2 sys0qm sysdate_qm_items.jsonl $S "$S0"
  think $1 $2 sysasof sysdate_items.jsonl $R "$SA"
}
B="--ext --conds sys1,sys0q,sys0qm,sysasof"; C="--paper --conds rewrite"
( think openai/gpt-6-sol gpt-6-sol sys0qm sysdate_qm_items.jsonl $S "$S0"; think openai/gpt-6-sol gpt-6-sol sysasof sysdate_items.jsonl $R "$SA"
  agent gpt-6-sol n300 $B; agent gpt-6-sol rewrite $C ) &
( agent kimi-k3 n300 $B; agent kimi-k3 rewrite $C
  think moonshotai/kimi-k3 kimi-k3 sys0qm sysdate_qm_items.jsonl $S "$S0"; think moonshotai/kimi-k3 kimi-k3 sysasof sysdate_items.jsonl $R "$SA" ) &
( think5 openai/gpt-6-luna gpt-6-luna; agent gpt-6-luna n300 $B; agent gpt-6-luna rewrite $C; agent gpt-6-luna think-agent --paper --think ) &
( agent hy4-preview n300 $B; agent hy4-preview rewrite $C; think5 tencent/hy4-preview hy4-preview ) &
( agent gpt-5.6-terra n300 $B; agent gpt-5.6-terra rewrite $C; think5 openai/gpt-5.6-terra gpt-5.6-terra ) &
( python3 scripts/agent_date.py run deepseek-flash --ext --conds sysasof,rewrite >> $L 2>&1; echo "$(date +%T) done deepseek ext+rewrite" ) &
wait; echo "$(date +%T) ROUND2_DONE"
