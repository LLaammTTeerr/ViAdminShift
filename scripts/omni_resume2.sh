#!/bin/bash
# Second resumption of the OmniRoute runs. Phase 1 (must-have): finish no-province runs + system-prompt date experiment.
# Phase 2: finish cue3sub for 4 knowers + cue3 for new models. Grok-4.7 skipped (~2,900 reasoning tok/call).
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
R=results/minitest; I=$R/items; OR=https://api.cheaperinference.com; AN=https://api.anthropic.com; DS=https://api.deepseek.com
OFF='{"thinking": {"type": "disabled"}}'
SYS0="Bạn là một trợ lý hữu ích."; SYS1="Bạn là một trợ lý hữu ích. Hôm nay là ngày 13/10/2026."
run() {  # url keyenv model extra items out par [system]
  for t in 1 2 3; do
    python3 scripts/minitest.py run --items $5 --url $1 --api-key-env $2 --model $3 --extra "$4" --max-tokens 1024 \
      --par $7 --out $6 ${8:+--system "$8"} >> $R/resume2.log 2>&1 && { echo "$(date +%T) done $3 $(basename $6)"; return; }
    grep -q "402" <(tail -n 3 $R/resume2.log) && { echo "$(date +%T) PROVIDER-STOP $3"; return; }
    sleep 60
  done; echo "$(date +%T) FAIL $3 $(basename $6)"
}
sys() {  # url keyenv model extra src par
  mkdir -p $R/sysprompt
  run $1 $2 $3 "$4" $I/sysdate_items.jsonl $R/sysprompt/preds_sys0_$3__$5.jsonl $6 "$SYS0"
  run $1 $2 $3 "$4" $I/sysdate_items.jsonl $R/sysprompt/preds_sys1_$3__$5.jsonl $6 "$SYS1"
}
# ---- phase 1
for m in kimi-k3 muse-spark-1.2 glm-5.3-flash claude-opus-5.5 gpt-5.5 qwen3.8-flash; do
  run $OR OR_TOKEN $m "$OFF" $I/cue3np_items.jsonl $R/omni/preds_cue3np_$m.jsonl 6 &
done
for m in gpt-6-sol kimi-k3 glm-5.3 glm-5.3-flash muse-spark-1.2 gpt-5.5 qwen3.8-flash deepseek-v4.1-flash qwen3.8-max; do
  sys $OR OR_TOKEN $m "$OFF" omni 6 &
done
sys $OR OR_TOKEN deepseek-v4-pro '{}' omni 6 &
sys $DS DS_TOKEN deepseek-flash "$OFF" api 8 &
sys $AN CL_TOKEN claude-sonnet-5-5 '{"temperature": null, "thinking": {"type": "between_tools"}}' claude_nothink 2 &
sys $AN CL_TOKEN claude-haiku-5-5 '{"temperature": null, "thinking": {"type": "disabled"}}' claude 2 &
sys $AN CL_TOKEN claude-opus-5-5 '{"temperature": null, "reasoning_effort": "none"}' claude 2 &
sys $AN CL_TOKEN claude-fable-5-1 '{"temperature": null}' claude 2 &
wait; echo PHASE1_DONE
# ---- phase 2
for m in gpt-6-sol muse-spark-1.2 kimi-k3 glm-5.3; do
  run $OR OR_TOKEN $m "$OFF" $I/cue3sub_items.jsonl $R/omni_full/preds_cue3full_$m.jsonl 6 &
done
for m in gpt-5.5 gemini-3.1-pro qwen3.8-2.4t-a95b gpt-oss-120b gemma-4-31b-it; do
  run $OR OR_TOKEN $m "$OFF" $I/cue3_items.jsonl $R/omni/preds_cue3_$m.jsonl 6 &
done
run $OR OR_TOKEN qwen3.6-27b '{"reasoning_effort": "minimal"}' $I/cue3_items.jsonl $R/omni/preds_cue3_qwen3.6-27b.jsonl 6 &
wait; echo PHASE2_DONE
