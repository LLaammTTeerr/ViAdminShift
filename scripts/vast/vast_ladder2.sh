#!/usr/bin/env bash
# Quantization ladder v2: small rungs NOW on the spare memory of GPU0/GPU1 (each shares with a small benchmark model);
# large rungs on GPU2,3 after the queue runner (pid $1) finishes. Same items/settings as v1.
cd /workspace/viadmin
export EXTRA='{"chat_template_kwargs": {"reasoning_strength": "none"}}' MAXTOK=1024
R=./vast_llamacpp.sh; S=cue3sub_items; U=unsloth/Muse-Glimmer-30B-GGUF
CTX=16384 NP=16 PAR=16 $R 0 8141 $S $U:Muse-Glimmer-30B-UD-Q4_K_XL.gguf $U:Muse-Glimmer-30B-UD-Q3_K_XL.gguf > ladder_gpu0.log 2>&1 &
CTX=16384 NP=16 PAR=16 $R 1 8142 $S $U:Muse-Glimmer-30B-UD-Q2_K_XL.gguf $U:Muse-Glimmer-30B-UD-IQ2_XXS.gguf > ladder_gpu1.log 2>&1 &
while kill -0 "$1" 2>/dev/null; do sleep 30; done
CTX=32768 NP=32 PAR=32 $R 2,3 8143 $S $U:Muse-Glimmer-30B-UD-Q6_K_XL.gguf $U:Muse-Glimmer-30B-UD-Q5_K_M.gguf > ladder_pair.log 2>&1
wait
echo LADDER_DONE
