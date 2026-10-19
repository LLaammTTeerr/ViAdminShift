#!/bin/bash
# Speed up the Muse-Glimmer Q8 full-set run (muse_rest.sh, GPUs 2,3) by splitting its second condition, closed:
#   B: once the Q6/Q5 rung runner ($1, GPUs 0,1) exits, a second Q8 server on GPUs 0,1 runs closed on items_rest_a
#      (first 4,000 items) into ...-rest-B.
#   A: once muse_rest has finished rag_mixed, its own closed pass (on all items) is stopped and replaced by closed on
#      items_rest_b (remaining 2,733) into ...-rest, on the existing server ($2 = pid of port 8133).
cd /workspace/viadmin
source /workspace/.hf_env; export PYTHONPATH=/workspace/viadmin/src OPENAI_API_KEY=none
PY=/workspace/vi-env/bin/python; A=bench/Muse-Glimmer-30B-Q8_0-rest; B=bench/Muse-Glimmer-30B-Q8_0-rest-B; mkdir -p $B
EB="{\"chat_template_kwargs\": {\"reasoning_strength\": \"none\"}}"
run() {  # port items out
  $PY -m viadmin.eval.runner --backend openai --base-url http://127.0.0.1:$1/v1 --model Muse-Glimmer-30B-Q8_0 \
    --extra-body "$EB" --max-new-short 1024 --max-new-mcq 1024 --items $2 --concurrency 32 --conditions closed --out $3 >> $3/runner.log 2>&1
}
(
  while kill -0 "$1" 2>/dev/null; do sleep 20; done
  echo "$(date +%T) start Muse-split B"
  CUDA_VISIBLE_DEVICES=0,1 /workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf \
    --port 8134 --host 127.0.0.1 -ngl 99 --jinja -c 65536 -np 32 -fa on > lcpp_muse_B.log 2>&1 & S=$!
  until curl -sf http://127.0.0.1:8134/health > /dev/null; do sleep 5; done
  run 8134 data/benchmark/items_rest_a.jsonl $B && touch $B/done_closed || echo "$(date +%T) RUN-FAIL B"
  kill $S; echo "$(date +%T) done Muse-split B"
) &
(
  until [ -f $A/done_rag_mixed ]; do sleep 10; done
  pkill -f "[m]use_rest.sh"; pkill -f "[i]tems_rest.jsonl --concurrency 32 --conditions closed"
  echo "$(date +%T) start Muse-split A"
  run 8133 data/benchmark/items_rest_b.jsonl $A && touch $A/done_closed || echo "$(date +%T) RUN-FAIL A"
  kill "$2"; echo "$(date +%T) done Muse-split A"
) &
wait; echo "$(date +%T) MUSE_SPLIT_DONE"
