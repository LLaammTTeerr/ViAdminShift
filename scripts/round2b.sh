#!/bin/bash
# Retry of round2.sh cells whose requests the provider refused (parallel reasoning calls each reserving their maximum size):
# one request at a time; Kimi-K3 (confound control) before GPT-5.6-Terra (reasoning on). Resumes.
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
while pgrep -f "[b]ash scripts/round2.sh" > /dev/null; do sleep 30; done
I=results/minitest/items; S=results/minitest/sysprompt; R=results/review; L=results/minitest/round2.log
ON='{"reasoning": {"enabled": true}}'; S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."
SA="$S0 Hãy trả lời theo thông tin tính đến tháng 10/2026."
think() {
  python3 scripts/minitest.py run --items $I/$4 --url https://openrouter.ai/api --api-key-env OPENROUTER_TOKEN --model $1 \
    --extra "$ON" --max-tokens 4096 --par 1 --rpm 19 --only T1np_ward_province:absorbed \
    --out $5/preds_$3_$2__orouter_think.jsonl --system "$6" >> $L 2>&1 && echo "$(date +%T) done $2 think $3" || echo "$(date +%T) FAIL $2 think $3"
}
think moonshotai/kimi-k3 kimi-k3 sys0qm sysdate_qm_items.jsonl $S "$S0"; think moonshotai/kimi-k3 kimi-k3 sysasof sysdate_items.jsonl $R "$SA"
think tencent/hy4-preview hy4-preview sys1 sysdate_items.jsonl $S "$S1"
M=openai/gpt-5.6-terra; T=gpt-5.6-terra
think $M $T sys0 sysdate_items.jsonl $S "$S0"; think $M $T sys1 sysdate_items.jsonl $S "$S1"; think $M $T sys0q sysdate_q_items.jsonl $S "$S0"
think $M $T sys0qm sysdate_qm_items.jsonl $S "$S0"; think $M $T sysasof sysdate_items.jsonl $R "$SA"
echo "$(date +%T) ROUND2B_DONE"
