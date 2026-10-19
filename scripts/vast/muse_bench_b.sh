#!/usr/bin/env bash
# Second Muse-Glimmer Q8 instance on GPUs 0,1 (queues there paused: pids in $@) for rag_new and rag_mixed+date;
# claims each condition in the main dir (done_ marker) so muse_bench2.sh on GPUs 2,3 skips it.
cd /workspace/viadmin
source /workspace/.hf_env; export PYTHONPATH=/workspace/viadmin/src OPENAI_API_KEY=none
LS=/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server; PY=/workspace/vi-env/bin/python
CUDA_VISIBLE_DEVICES=0,1 $LS -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf --port 8132 --host 127.0.0.1 -ngl 99 --jinja \
  -c 65536 -np 32 -fa on > lcpp_bench_b_Muse-Glimmer-30B-Q8_0.log 2>&1 &
pid=$!
until curl -sf http://127.0.0.1:8132/health >/dev/null; do sleep 3; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL b"; kill -CONT "$@"; exit 1; }; done
main=bench/Muse-Glimmer-30B-Q8_0-sub1k; out=bench/Muse-Glimmer-30B-Q8_0-sub1k-b; mkdir -p $out
for c in rag_new rag_mixed+date; do
  [ -e $main/done_$c ] && continue
  touch $main/done_$c   # claim
  echo "$(date +%T) start b Muse-Glimmer-30B-Q8_0 $c"
  $PY -m viadmin.eval.runner --backend openai --base-url http://127.0.0.1:8132/v1 --model Muse-Glimmer-30B-Q8_0 \
    --extra-body "{\"chat_template_kwargs\": {\"reasoning_strength\": \"none\"}}" --max-new-short 1024 --max-new-mcq 1024 \
    --items data/benchmark/items_sub1k.jsonl --concurrency 32 --conditions "$c" --out $out >> $out/runner.log 2>&1 \
    && touch $out/done_$c || echo "$(date +%T) RUN-FAIL b $c"
done
kill $pid; wait $pid 2>/dev/null
kill -CONT "$@"; echo "$(date +%T) done b Muse-Glimmer-30B-Q8_0; resumed $*"
