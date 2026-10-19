#!/usr/bin/env bash
# Run the closed-book mini-test for each GGUF model with llama-server on CPU (one model at a time).
# Usage: run_minitest_cpu.sh <port> <threads> model1.gguf model2.gguf ...
set -u
PORT=$1; THREADS=$2; shift 2
BIN=~/tools/llama.cpp-v060/build-cpu/bin
cd ~/viadmin
for m in "$@"; do
  name=$(basename "$m" .gguf)
  while [ -e "$m.part" ] || [ ! -s "$m" ]; do sleep 60; done   # wait for download
  [ -s "preds_$name.jsonl" ] && [ "$(wc -l < "preds_$name.jsonl")" -ge "$(wc -l < minitest_items.jsonl)" ] && continue
  $BIN/llama-server -m "$m" --jinja -t "$THREADS" -c 4096 -np 1 --port "$PORT" --host 127.0.0.1 > "server_$name.log" 2>&1 &
  pid=$!
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do sleep 2; kill -0 $pid 2>/dev/null || break; done
  echo "$(date +%T) start $name"
  python3 minitest.py run --items minitest_items.jsonl --url "http://127.0.0.1:$PORT" --model "$name" --out "preds_$name.jsonl" 2>> "run_$name.log" || echo "FAIL $name"
  kill $pid; wait $pid 2>/dev/null
  echo "$(date +%T) done $name"
done
