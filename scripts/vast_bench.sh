#!/usr/bin/env bash
# Full benchmark (viadmin.eval.runner, openai backend) on prebuilt Q8_0 GGUFs served by llama.cpp CUDA.
# Conditions run in the given priority order; each is resumable and gets a done_<cond> marker when complete.
# Usage: vast_bench.sh <gpus> <port> "<conditions>" repo:file.gguf ...   (sharded: give the -00001-of-N file)
set -u
GPUS=$1; PORT=$2; CONDS=$3; shift 3
LC=/workspace/tools/llama.cpp-v060; GG=/workspace/gguf; PY=/workspace/vi-env/bin/python
source /workspace/.hf_env; export HF_HOME=/workspace/.hf_home
export PYTHONPATH=/workspace/viadmin/src OPENAI_API_KEY=none
cd /workspace/viadmin
# downloads fail transiently when several run at once: retry
dl() { for i in 1 2 3; do "$@" && return 0; sleep 20; done; return 1; }
for spec in "$@"; do
  m=${spec%%:*}; prebuilt=${spec#*:}; name=$(basename "$prebuilt" .gguf); name=${name%-00001-of-*}
  out=bench/$name; mkdir -p "$out"
  todo=""; for c in $CONDS; do [ -e "$out/done_$c" ] || todo="$todo $c"; done
  [ -z "$todo" ] && continue
  gguf=$GG/$prebuilt
  dl uvx --from huggingface_hub hf download "$m" --include "${prebuilt/-00001-of-/-*-of-}" --local-dir $GG > /dev/null 2>&1 \
    && [ -s "$gguf" ] || { echo "$(date +%T) DL-FAIL $name"; continue; }
  CUDA_VISIBLE_DEVICES=$GPUS $LC/build-cuda/bin/llama-server -m "$gguf" --port "$PORT" --host 127.0.0.1 -ngl 99 \
    --jinja -c ${CTX:-32768} -np ${NP:-16} -fa on > "lcpp_bench_$name.log" 2>&1 &
  pid=$!
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do
    sleep 5; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL $name"; break; }
  done
  ok=""
  if kill -0 $pid 2>/dev/null; then
    ok=1
    for c in $todo; do
      echo "$(date +%T) start $name $c"
      $PY -m viadmin.eval.runner --backend openai --base-url "http://127.0.0.1:$PORT/v1" --model "$name" \
        --template-kwargs --concurrency ${NP:-16} --conditions "$c" --out "$out" >> "$out/runner.log" 2>&1 \
        && touch "$out/done_$c" || { ok=""; echo "$(date +%T) RUN-FAIL $name $c"; }
    done
    kill $pid; wait $pid 2>/dev/null
  fi
  [ -n "$ok" ] && rm -f $GG/${prebuilt/-00001-of-/-*-of-}
  echo "$(date +%T) done $name"
done
