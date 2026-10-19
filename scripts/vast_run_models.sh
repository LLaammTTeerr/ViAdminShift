#!/usr/bin/env bash
# Serve each model with vLLM on the given GPUs and run item sets against it, one model at a time.
# Usage: vast_run_models.sh <gpus e.g. 0 or 0,1,2,3> <port> <item sets "a b"> model1 model2 ...
# Writes preds_<set>_<model-basename>.jsonl in /workspace/viadmin. Skips finished (set, model) pairs.
set -u
GPUS=$1; PORT=$2; SETS=$3; shift 3
TP=$(echo "$GPUS" | tr ',' '\n' | wc -l)
VLLM=/workspace/vllm-env/bin/vllm
source /workspace/.hf_env; export HF_HOME=/workspace/.hf_home
cd /workspace/viadmin
for m in "$@"; do
  name=$(basename "$m")
  todo=""
  for s in $SETS; do
    out="preds_${s}_$name.jsonl"
    if [ ! -s "$out" ] || [ "$(wc -l < "$out")" -lt "$(wc -l < "$s.jsonl")" ]; then todo="$todo $s"; fi
  done
  [ -z "$todo" ] && continue
  uvx --from huggingface_hub hf download "$m" --exclude "*.gguf" --exclude "*.pth" --exclude "original/*" --exclude "consolidated*" \
    > /dev/null 2>&1 || { echo "$(date +%T) DL-FAIL $name"; continue; }
  extra=""
  case "$m" in
    *gemma-3*|*gemma-4*|*Qwen3.5*|*Qwen3.6*|*Qwen3.8*|*Ministral-3*) extra="--limit-mm-per-prompt {\"image\":0}" ;;
  esac
  CUDA_VISIBLE_DEVICES=$GPUS $VLLM serve "$m" --port "$PORT" --host 127.0.0.1 --tensor-parallel-size "$TP" \
    --max-model-len 8192 --gpu-memory-utilization 0.90 --served-model-name "$name" $extra > "vllm_$name.log" 2>&1 &
  pid=$!
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do
    sleep 5; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL $name"; break; }
  done
  if kill -0 $pid 2>/dev/null; then
    for s in $todo; do
      echo "$(date +%T) start $name $s"
      python3 minitest.py run --items "$s.jsonl" --url "http://127.0.0.1:$PORT" --model "$name" \
        --out "preds_${s}_$name.jsonl" --max-tokens 64 2>> "run_$name.log" || echo "$(date +%T) RUN-FAIL $name $s"
    done
    kill $pid; wait $pid 2>/dev/null
  fi
  echo "$(date +%T) done $name"
done
