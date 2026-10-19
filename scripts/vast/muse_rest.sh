#!/bin/bash
# Muse-Glimmer Q8 rag_mixed then closed on the remaining 6,733 benchmark items (full-set comparability), reusing the
# Muse server already loaded on GPUs 2,3 (port 8133, pid $2). The ladder-pair runner ($1, waiting on the Q6 download)
# is paused meanwhile and resumed at the end; the server is then stopped.
cd /workspace/viadmin
source /workspace/.hf_env; export PYTHONPATH=/workspace/viadmin/src OPENAI_API_KEY=none
PY=/workspace/vi-env/bin/python
kill -STOP "$1"
out=bench/Muse-Glimmer-30B-Q8_0-rest; mkdir -p $out
for c in rag_mixed closed; do
  echo "$(date +%T) start Muse-rest $c"
  $PY -m viadmin.eval.runner --backend openai --base-url http://127.0.0.1:8133/v1 --model Muse-Glimmer-30B-Q8_0 \
    --extra-body "{\"chat_template_kwargs\": {\"reasoning_strength\": \"none\"}}" --max-new-short 1024 --max-new-mcq 1024 \
    --items data/benchmark/items_rest.jsonl --concurrency 32 --conditions "$c" --out $out >> $out/runner.log 2>&1 \
    && touch $out/done_$c || echo "$(date +%T) RUN-FAIL $c"
done
kill "$2"; kill -CONT "$1"; echo "$(date +%T) done Muse-rest; resumed $1"
