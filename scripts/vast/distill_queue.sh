#!/bin/bash
# Distilled 9B student of a reform-aware teacher (Kimi-K3) on GPU1 (shared with the Q6/Q5 rung), once the GPU1
# benchmark runner ($1) has finished. Small context to fit beside the rung. MiMo-V2.6-Distill already done.
cd /workspace/viadmin
while kill -0 "$1" 2>/dev/null; do sleep 20; done
CTX=8192 NP=8 PAR=8 MAXTOK=1024 EXTRA="{\"chat_template_kwargs\": {\"enable_thinking\": false}}" \
  ./vast_llamacpp.sh 1 8145 "cue3_items cue3np_items minitest_items" \
  mradermacher/Qwen3.5-9B-Kimi-k3-Distilled-GGUF:Qwen3.5-9B-Kimi-k3-Distilled.Q8_0.gguf >> distill.log 2>&1
echo "$(date +%T) DISTILL_DONE" >> distill.log
