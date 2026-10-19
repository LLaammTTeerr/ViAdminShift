#!/usr/bin/env bash
# Quantization ladder on Muse-Glimmer-30B (an open model that knows the update): same items (cue3sub: absorbed + kept
# controls at 3 cue levels), same reasoning setting, one run per quant. Q8_0 comes from the main run.
# Waits for the GPU2,3 queue runner (pid $1) to finish first.
cd /workspace/viadmin
while kill -0 "$1" 2>/dev/null; do sleep 30; done
export EXTRA='{"chat_template_kwargs": {"reasoning_strength": "none"}}' MAXTOK=1024
R=./vast_llamacpp.sh; S=cue3sub_items; U=unsloth/Muse-Glimmer-30B-GGUF
CTX=16384 NP=16 PAR=16 $R 2 8141 $S $U:Muse-Glimmer-30B-UD-Q4_K_XL.gguf $U:Muse-Glimmer-30B-UD-Q2_K_XL.gguf > ladder_gpu2.log 2>&1 &
CTX=16384 NP=16 PAR=16 $R 3 8142 $S $U:Muse-Glimmer-30B-UD-Q3_K_XL.gguf $U:Muse-Glimmer-30B-UD-IQ2_XXS.gguf > ladder_gpu3.log 2>&1 &
wait
CTX=32768 NP=32 PAR=32 $R 2,3 8143 $S $U:Muse-Glimmer-30B-UD-Q6_K_XL.gguf $U:Muse-Glimmer-30B-UD-Q5_K_M.gguf > ladder_pair.log 2>&1
echo LADDER_DONE
