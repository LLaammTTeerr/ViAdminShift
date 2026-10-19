#!/usr/bin/env bash
# Run the mini-test item sets for each GGUF model with llama-server (one model at a time).
# Usage: run_minitest.sh <workdir> <port> model1.gguf model2.gguf ...
# Env: LLAMA_BIN (dir with llama-server, default: on PATH), LLAMA_ARGS (e.g. "-t 20" for CPU, "-ngl 99" for Metal),
#      ITEM_SETS (default "minitest_items rag_items").
set -u
WORK=$1; PORT=$2; shift 2
BIN=${LLAMA_BIN:+$LLAMA_BIN/}llama-server
ARGS=${LLAMA_ARGS:-}
SETS=${ITEM_SETS:-"minitest_items rag_items"}
cd "$WORK"
for m in "$@"; do
  name=$(basename "$m" .gguf)
  while [ -e "$m.part" ] || [ ! -s "$m" ]; do sleep 60; done   # wait for download
  todo=""
  for s in $SETS; do
    out="preds_${s}_$name.jsonl"
    if [ ! -s "$out" ] || [ "$(wc -l < "$out")" -lt "$(wc -l < "$s.jsonl")" ]; then todo="$todo $s"; fi
  done
  [ -z "$todo" ] && continue
  $BIN -m "$m" --jinja $ARGS -c 4096 -np 1 --port "$PORT" --host 127.0.0.1 > "server_$name.log" 2>&1 &
  pid=$!
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do sleep 2; kill -0 $pid 2>/dev/null || break; done
  for s in $todo; do
    echo "$(date +%T) start $name $s"
    python3 minitest.py run --items "$s.jsonl" --url "http://127.0.0.1:$PORT" --model "$name" \
      --out "preds_${s}_$name.jsonl" 2>> "run_$name.log" || echo "FAIL $name $s"
  done
  kill $pid; wait $pid 2>/dev/null
  echo "$(date +%T) done $name"
done
