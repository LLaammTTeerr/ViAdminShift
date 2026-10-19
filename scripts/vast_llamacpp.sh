#!/usr/bin/env bash
# Like vast_run_models.sh, but with llama.cpp CUDA: convert the HF snapshot to a bf16 GGUF, serve it,
# run the item sets, delete the GGUF. Usage: vast_llamacpp.sh <gpus e.g. 0 or 0,1> <port> "<sets>" model...
# A model given as repo:file.gguf is downloaded as a prebuilt GGUF (name = file stem; for a sharded file give the
# -00001-of-N shard and all shards are fetched). cue3full_items only runs if the model passes `minitest.py knows`
# on cue3_items (pre-registered: absorbed/reform >= 0.50), so put cue3_items first in the sets.
set -u
GPUS=$1; PORT=$2; SETS=$3; shift 3
LC=/workspace/tools/llama.cpp-v060; CONV=/workspace/convert-env/bin/python; GG=/workspace/gguf
mkdir -p $GG
source /workspace/.hf_env; export HF_HOME=/workspace/.hf_home
cd /workspace/viadmin
# downloads fail transiently when several run at once: retry
dl() { for i in 1 2 3; do "$@" && return 0; sleep 20; done; return 1; }
for m in "$@"; do
  prebuilt=""
  case "$m" in *.gguf) prebuilt=${m#*:}; m=${m%%:*}; name=$(basename "$prebuilt" .gguf); name=${name%-00001-of-*} ;; *) name=$(basename "$m") ;; esac
  todo=""
  for s in $SETS; do
    out="preds_${s}_$name.jsonl"
    if [ "$s" = cue3full_items ] && [ -s "preds_cue3_items_$name.jsonl" ] && [ "$(wc -l < "preds_cue3_items_$name.jsonl")" -ge \
      "$(wc -l < cue3_items.jsonl)" ] && ! python3 minitest.py knows "preds_cue3_items_$name.jsonl" > /dev/null; then continue; fi
    if [ ! -s "$out" ] || [ "$(wc -l < "$out")" -lt "$(wc -l < "$s.jsonl")" ]; then todo="$todo $s"; fi
  done
  [ -z "$todo" ] && continue
  if [ -n "$prebuilt" ]; then
    gguf=$GG/$prebuilt
    dl uvx --from huggingface_hub hf download "$m" --include "${prebuilt/-00001-of-/-*-of-}" --local-dir $GG > /dev/null 2>&1 \
      && [ -s "$gguf" ] \
      || { echo "$(date +%T) DL-FAIL $name"; continue; }
  else
    snap=$(dl uvx --from huggingface_hub hf download "$m" --exclude "*.gguf" --exclude "*.pth" --exclude "original/*" \
      --exclude "consolidated*" 2>&1 | sed -n 's/^ *path: //p' | tail -1)
    [ -d "$snap" ] || { echo "$(date +%T) DL-FAIL $name"; continue; }
    gguf=$GG/$name-bf16.gguf
    if [ ! -s "$gguf" ]; then
      echo "$(date +%T) convert $name"
      $CONV $LC/convert_hf_to_gguf.py "$snap" --outtype bf16 --outfile "$gguf" > "conv_$name.log" 2>&1 \
        || { echo "$(date +%T) CONV-FAIL $name"; rm -f "$gguf"; continue; }
    fi
  fi
  CUDA_VISIBLE_DEVICES=$GPUS $LC/build-cuda/bin/llama-server -m "$gguf" --port "$PORT" --host 127.0.0.1 -ngl 99 \
    --jinja -c ${CTX:-32768} -np ${NP:-8} -fa on > "lcpp_$name.log" 2>&1 &
  pid=$!
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do
    sleep 5; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL $name"; break; }
  done
  if kill -0 $pid 2>/dev/null; then
    ok=1
    for s in $todo; do
      if [ "$s" = cue3full_items ] && ! python3 minitest.py knows "preds_cue3_items_$name.jsonl" >> "run_$name.log"; then
        [ -e "preds_cue3_items_$name.jsonl" ] || continue
        echo "$(date +%T) skip-full $name (does not know the update)"; continue
      fi
      echo "$(date +%T) start $name $s"
      python3 minitest.py run --items "$s.jsonl" --url "http://127.0.0.1:$PORT" --model "$name" --par ${PAR:-8} ${EXTRA:+--extra "$EXTRA"} \
        --out "preds_${s}_$name.jsonl" --max-tokens ${MAXTOK:-64} 2>> "run_$name.log" || { ok=""; echo "$(date +%T) RUN-FAIL $name $s"; }
      if python3 -c "import json,sys; ps=[json.loads(l) for l in open(sys.argv[1])]; sys.exit(sum(not (p.get('output') or '').strip() for p in ps) > 0.2*len(ps))" "preds_${s}_$name.jsonl"; then :; else
        mv "preds_${s}_$name.jsonl" "preds_${s}_$name.jsonl.empty"; ok=""; echo "$(date +%T) EMPTY-FAIL $name $s (mostly empty outputs)"
      fi
    done
    kill $pid; wait $pid 2>/dev/null
    [ -z "$prebuilt" ] && rm -f "$gguf"
    [ -n "$prebuilt" ] && [ -n "$ok" ] && rm -f $GG/${prebuilt/-00001-of-/-*-of-}
    # disk rotation: the HF checkpoint is no longer needed once every set is done
    [ -z "$prebuilt" ] && [ -n "$ok" ] && [ -n "${ROTATE:-1}" ] && rm -rf "$HF_HOME/hub/models--${m//\//--}" \
      && python3 hf_gc.py "$HF_HOME" >> "run_$name.log" 2>&1
  fi
  echo "$(date +%T) done $name"
done
