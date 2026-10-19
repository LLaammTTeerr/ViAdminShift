#!/usr/bin/env bash
# Use GPU2,3 while the queue runner ($1) downloads its next model: pause the runner's bash only (its download child keeps
# going), run the Muse-Glimmer Q8 template ablation, then resume the runner.
cd /workspace/viadmin
kill -STOP "$1"
LS=/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server
CUDA_VISIBLE_DEVICES=2,3 $LS -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf --port 8130 --host 127.0.0.1 -ngl 99 --jinja \
  -c 65536 -np 32 -fa on > lcpp_muse_tmpl.log 2>&1 &
pid=$!
ok=1
until curl -sf http://127.0.0.1:8130/health >/dev/null; do sleep 3; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL muse tmpl"; ok=0; break; }; done
[ $ok = 1 ] && { echo "$(date +%T) start muse template ablation (GPU2,3 during download)"; ./muse_tmpl.sh > muse_tmpl.out 2>&1; echo "$(date +%T) done muse template ablation"; }
kill $pid; wait $pid 2>/dev/null
kill -CONT "$1" && echo "$(date +%T) resumed GPU2,3 runner"
