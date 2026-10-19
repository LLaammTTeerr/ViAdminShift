#!/usr/bin/env bash
# CPU (RAM) runner for CPU servers: prebuilt GGUF -> llama-server on N threads -> minitest sets -> delete.
# Usage: cpu_run.sh <llama-server> <threads> <port> "<sets>" repo:file.gguf ...   (run from the dir holding the sets)
# Downloads use curl -C - (resumable). Reasoning models get chat_template_kwargs to keep thinking off/low.
set -u
LS=$1; T=$2; PORT=$3; SETS=$4; shift 4
MD=${MODELS_DIR:-$HOME/models}; mkdir -p "$MD"
EXTRA='{"chat_template_kwargs": {"enable_thinking": false, "reasoning_effort": "low"}}'
for spec in "$@"; do
  repo=${spec%%:*}; file=${spec#*:}; name=$(basename "$file" .gguf)
  todo=""
  for s in $SETS; do
    out="preds_${s}_$name.jsonl"
    if [ ! -s "$out" ] || [ "$(wc -l < "$out")" -lt "$(wc -l < "$s.jsonl")" ]; then todo="$todo $s"; fi
  done
  [ -z "$todo" ] && continue
  f="$MD/$(basename "$file")"
  curl -sfL -C - --retry 5 -o "$f" "https://huggingface.co/$repo/resolve/main/$file" || { echo "$(date +%T) DL-FAIL $name"; continue; }
  $LS -m "$f" --port "$PORT" --host 127.0.0.1 -t "$T" -tb "$T" --jinja -c 8192 -np 4 > "lcpp_$name.log" 2>&1 &
  pid=$!
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do
    sleep 5; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL $name"; break; }
  done
  ok=""
  if kill -0 $pid 2>/dev/null; then
    ok=1
    for s in $todo; do
      echo "$(date +%T) start $name $s"
      python3 minitest.py run --items "$s.jsonl" --url "http://127.0.0.1:$PORT" --model "$name" --par 4 --extra "$EXTRA" \
        --out "preds_${s}_$name.jsonl" --max-tokens 512 2>> "run_$name.log" || { ok=""; echo "$(date +%T) RUN-FAIL $name $s"; }
    done
    kill $pid; wait $pid 2>/dev/null
  fi
  [ -n "$ok" ] && rm -f "$f"
  echo "$(date +%T) done $name"
done
