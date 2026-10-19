#!/usr/bin/env bash
# Muse-Glimmer (knows the update): stratified full ladder (cue3sub) + mini + RAG at high parallelism, then resume the
# paused GPU2,3 queue runner (pid in $1).
cd /workspace/viadmin
RUNNER=$1
kill $(pgrep -f "^/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server -m /workspace/keep/Muse") 2>/dev/null; sleep 3
CUDA_VISIBLE_DEVICES=2,3 /workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf \
  --port 8130 --host 127.0.0.1 -ngl 99 --jinja -c 65536 -np 32 -fa on > lcpp_muse_full.log 2>&1 &
pid=$!
until curl -sf http://127.0.0.1:8130/health >/dev/null; do sleep 3; kill -0 $pid 2>/dev/null || { echo SERVE-FAIL; kill -CONT $RUNNER; exit 1; }; done
name=Muse-Glimmer-30B-Q8_0; EX='{"chat_template_kwargs": {"reasoning_strength": "none"}}'
for pair in "cue3sub_items cue3full_items" "minitest_items minitest_items" "rag_items rag_items"; do
  set -- $pair; items=$1; tag=$2
  echo "$(date +%T) start $name $items"
  python3 minitest.py run --items $items.jsonl --url http://127.0.0.1:8130 --model $name --par 32 --extra "$EX" \
    --max-tokens 1024 --out preds_${tag}_$name.jsonl 2>> run_muse_full.log

done
kill $pid; wait $pid 2>/dev/null
echo "$(date +%T) done $name"; kill -CONT $RUNNER && echo "resumed GPU2,3 runner"
