#!/usr/bin/env bash
# Benchmark conditions on Muse-Glimmer Q8 (only open-weight knower) on GPUs 2,3 while the queue runner ($1) is paused.
cd /workspace/viadmin
source /workspace/.hf_env; export PYTHONPATH=/workspace/viadmin/src OPENAI_API_KEY=none
LS=/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server; PY=/workspace/vi-env/bin/python
kill -STOP "$1"; echo "$(date +%T) paused runner $1"
CUDA_VISIBLE_DEVICES=2,3 $LS -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf --port 8131 --host 127.0.0.1 -ngl 99 --jinja \
  -c 65536 -np 32 -fa on > lcpp_bench_Muse-Glimmer-30B-Q8_0.log 2>&1 &
pid=$!
until curl -sf http://127.0.0.1:8131/health >/dev/null; do sleep 3; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL"; kill -CONT "$1"; exit 1; }; done
out=bench/Muse-Glimmer-30B-Q8_0-sub1k; mkdir -p $out
for c in closed rag_mixed rag_new rag_mixed+date; do
  [ -e $out/done_$c ] && continue
  echo "$(date +%T) start Muse-Glimmer-30B-Q8_0 $c"
  $PY -m viadmin.eval.runner --backend openai --base-url http://127.0.0.1:8131/v1 --model Muse-Glimmer-30B-Q8_0 \
    --extra-body "{\"chat_template_kwargs\": {\"reasoning_strength\": \"none\"}}" --max-new-short 1024 --max-new-mcq 1024 \
    --items data/benchmark/items_sub1k.jsonl --concurrency 32 --conditions "$c" --out $out >> $out/runner.log 2>&1 && touch $out/done_$c || echo "$(date +%T) RUN-FAIL $c"
done
kill $pid; wait $pid 2>/dev/null
kill -CONT "$1"; echo "$(date +%T) done Muse-Glimmer-30B-Q8_0; resumed runner $1"
