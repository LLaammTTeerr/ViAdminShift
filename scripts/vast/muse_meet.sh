#!/bin/bash
# When split A (GPUs 2,3) finishes items_rest_b, its server is stopped by muse_closed_split.sh. Start a new Q8 server
# on GPUs 2,3 and run items_rest_a in REVERSE order into ...-rest-A2, while split B works forward through the same
# file. Stop both once their union covers all of items_rest_a; the merge deduplicates the overlap.
cd /workspace/viadmin
source /workspace/.hf_env; export PYTHONPATH=/workspace/viadmin/src OPENAI_API_KEY=none
PY=/workspace/vi-env/bin/python; A=bench/Muse-Glimmer-30B-Q8_0-rest; B=bench/Muse-Glimmer-30B-Q8_0-rest-B; A2=bench/Muse-Glimmer-30B-Q8_0-rest-A2
mkdir -p $A2; tac data/benchmark/items_rest_a.jsonl > data/benchmark/items_rest_arev.jsonl
until [ -f $A/done_closed ]; do sleep 20; done
while pgrep -f "[p]ort 8133" > /dev/null; do sleep 5; done
echo "$(date +%T) start Muse-meet"
CUDA_VISIBLE_DEVICES=2,3 /workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server -m /workspace/keep/Muse-Glimmer-30B-Q8_0.gguf \
  --port 8135 --host 127.0.0.1 -ngl 99 --jinja -c 65536 -np 32 -fa on > lcpp_muse_A2.log 2>&1 & S=$!
until curl -sf http://127.0.0.1:8135/health > /dev/null; do sleep 5; done
$PY -m viadmin.eval.runner --backend openai --base-url http://127.0.0.1:8135/v1 --model Muse-Glimmer-30B-Q8_0 \
  --extra-body "{\"chat_template_kwargs\": {\"reasoning_strength\": \"none\"}}" --max-new-short 1024 --max-new-mcq 1024 \
  --items data/benchmark/items_rest_arev.jsonl --concurrency 32 --conditions closed --out $A2 >> $A2/runner.log 2>&1 &
covered() { $PY - <<PYEOF
import json
need={json.loads(l)["id"] for l in open("data/benchmark/items_rest_a.jsonl")}
have=set()
for d in ("$B","$A2"):
    try:
        have|={json.loads(l)["item_id"] for l in open(d+"/predictions.jsonl") if "\"closed\"" in l}
    except FileNotFoundError: pass
print(len(need-have))
PYEOF
}
while true; do
  left=$(covered); [ "$left" = 0 ] && break
  pgrep -f "[i]tems_rest_a.jsonl --concurrency" > /dev/null || pgrep -f "[i]tems_rest_arev" > /dev/null || break
  sleep 60
done
echo "$(date +%T) Muse-meet covered (left=$left); stopping"
pkill -f "[i]tems_rest_arev"; pkill -f "[i]tems_rest_a.jsonl --concurrency"; sleep 5; kill $S
pkill -f "[p]ort 8134"; echo "$(date +%T) MUSE_MEET_DONE"
