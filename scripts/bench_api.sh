#!/bin/bash
# Benchmark run for one API model in the four conditions, resuming until every item is answered.
#   bash scripts/bench_api.sh <base url> <key env var> <model id> <out dir> '<extra body json>'
# The runner skips answered items, so each pass only retries what failed (timeouts, HTTP 429/503).
# Answers cut at the limit: run scripts/drop_truncated.py <out dir>, then this script again with higher MAX_MCQ/MAX_SHORT.
# Optional environment:
#   RAG_ITEMS  item file for the three retrieval conditions (default: all items). The reduced runs use
#              data/benchmark/items_rag_sub.jsonl (scripts/make_rag_items.py); closed-book always runs all items.
#   MAX_MCQ, MAX_SHORT  answer token limits (runner defaults 16 / 64; 64 / 128 for models that may open with a phrase)
#   OPENAI_RPM  requests-per-minute cap;  CONC  concurrency (default 16);  OPENAI_TIMEOUT  seconds (default 180)
cd "$(dirname "$0")/.." && set -a && . ./.env && set +a
URL=$1 KEY=$2 MODEL=$3 OUT=$4 EXTRA=$5
export OPENAI_TIMEOUT=${OPENAI_TIMEOUT:-180}
ALL=data/benchmark/items.jsonl RAG=${RAG_ITEMS:-$ALL}
for spec in "closed:$ALL" "rag_new:$RAG" "rag_mixed:$RAG" "rag_mixed+date:$RAG"; do
  cond=${spec%%:*} items=${spec#*:} N=$(wc -l < "${spec#*:}")
  for pass in $(seq 1 30); do
    uv run python -m viadmin.eval.runner --backend openai --base-url "$URL" --api-key-env "$KEY" --model "$MODEL" \
      --extra-body "$EXTRA" --concurrency "${CONC:-16}" --conditions "$cond" --items "$items" \
      ${MAX_MCQ:+--max-new-mcq $MAX_MCQ} ${MAX_SHORT:+--max-new-short $MAX_SHORT} --out "$OUT" >> "$OUT.log" 2>&1
    done_n=$(python3 -c "import json,sys; print(sum(1 for l in open('$OUT/predictions.jsonl') if json.loads(l)['condition']=='$cond'))" 2>/dev/null || echo 0)
    echo "$(date +%T) $cond pass $pass: $done_n/$N"
    [ "$done_n" -ge "$N" ] && break
    sleep 30
  done
done
echo "BENCH_API_DONE"
