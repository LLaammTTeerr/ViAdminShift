#!/usr/bin/env bash
# GPU2,3 chain after the queue runner (pid $1): Muse-Glimmer Q8 template-date ablation, then the large ladder rungs.
cd /workspace/viadmin
while kill -0 "$1" 2>/dev/null; do sleep 30; done
LS=/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server
CUDA_VISIBLE_DEVICES=2,3 $LS -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf --port 8130 --host 127.0.0.1 -ngl 99 --jinja \
  -c 65536 -np 32 -fa on > lcpp_muse_tmpl.log 2>&1 &
pid=$!
until curl -sf http://127.0.0.1:8130/health >/dev/null; do sleep 3; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL muse tmpl"; break; }; done
echo "$(date +%T) start muse template ablation"
./muse_tmpl.sh > muse_tmpl.out 2>&1
echo "$(date +%T) done muse template ablation"
kill $pid; wait $pid 2>/dev/null
export EXTRA='{"chat_template_kwargs": {"reasoning_strength": "none"}}' MAXTOK=1024
U=unsloth/Muse-Glimmer-30B-GGUF
CTX=32768 NP=32 PAR=32 ./vast_llamacpp.sh 2,3 8143 cue3sub_items $U:Muse-Glimmer-30B-UD-Q6_K_XL.gguf $U:Muse-Glimmer-30B-UD-Q5_K_M.gguf > ladder_pair.log 2>&1
echo "$(date +%T) LADDER_PAIR_DONE"
