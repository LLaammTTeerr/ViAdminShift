#!/bin/bash
# Second-review controls on Muse-Glimmer Q8, after the closed-book split (muse_meet.sh) has freed all four GPUs.
#   sysasof          : "answer as of 10/2026" in the system prompt (fills the date-placement row)
#   newname, prefix  : frame and prefix controls; "-nodate" = our plain system prompt replaces the template's date
#                      block (comparable to the API models), default = template injects today's date (as in Table cue)
#   r2, r3 (-nodate) : repeats of the no-date cue ladder
cd /workspace/viadmin
until grep -q MUSE_MEET_DONE muse_split.out 2>/dev/null; do sleep 60; done
LS=/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server; M=Muse-Glimmer-30B-Q8_0
X='{"chat_template_kwargs": {"reasoning_strength": "none"}}'
S0="You are a helpful AI assistant."; SA="Bạn là một trợ lý hữu ích. Hãy trả lời theo thông tin tính đến tháng 10/2026."
serve() {  # gpus port
  CUDA_VISIBLE_DEVICES=$1 $LS -m /workspace/keep/$M.gguf --port $2 --host 127.0.0.1 -ngl 99 --jinja -c 65536 -np 32 -fa on > lcpp_review_$2.log 2>&1 &
  echo $!
}
go() {  # port tag items model [system]
  python3 minitest_sys.py run --items $3 --url http://127.0.0.1:$1 --model $4 --extra "$X" --max-tokens 1024 --par 16 \
    --out review/preds_$2_$4__gpu.jsonl ${5:+--system "$5"} >> muse_review.log 2>&1 \
    && echo "$(date +%T) done $2 $4" || echo "$(date +%T) FAIL $2 $4"
}
mkdir -p review
pa=$(serve 0,1 8136); pb=$(serve 2,3 8137)
for p in 8136 8137; do until curl -sf http://127.0.0.1:$p/health >/dev/null; do sleep 3; done; done
echo "$(date +%T) start muse_review"
( go 8136 sysasof sysdate_items.jsonl $M "$SA"; go 8136 newname newname_items.jsonl $M-nodate "$S0"; go 8136 prefix prefix_items.jsonl $M-nodate "$S0"
  go 8136 newname newname_items.jsonl $M ) &
( go 8137 r2 cue3_items.jsonl $M-nodate "$S0"; go 8137 r3 cue3_items.jsonl $M-nodate "$S0"; go 8137 prefix prefix_items.jsonl $M ) &
wait; kill $pa $pb; wait 2>/dev/null; echo "$(date +%T) MUSE_REVIEW_DONE"
