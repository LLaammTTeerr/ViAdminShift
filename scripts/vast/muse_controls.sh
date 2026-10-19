#!/bin/bash
# Date-placement controls on the open-weight knower (Muse-Glimmer Q8, GPUs 2,3), same conditions as the API runs:
# sys0, sys1 (+date in system), sys0q (date cue in question), sys0qm (system date sentence moved into question),
# sys2025 (pre-reform date in system), q2025 (pre-reform date in question, no system prompt -> template injects today).
cd /workspace/viadmin
LS=/workspace/tools/llama.cpp-v060/build-cuda/bin/llama-server; M=Muse-Glimmer-30B-Q8_0; U=http://127.0.0.1:8133
CUDA_VISIBLE_DEVICES=2,3 $LS -m /workspace/keep/$M.gguf --port 8133 --host 127.0.0.1 -ngl 99 --jinja -c 65536 -np 32 -fa on > lcpp_muse_controls.log 2>&1 &
pid=$!
until curl -sf $U/health >/dev/null; do sleep 3; kill -0 $pid 2>/dev/null || { echo "$(date +%T) SERVE-FAIL"; exit 1; }; done
X='{"chat_template_kwargs": {"reasoning_strength": "none"}}'
S0="Bạn là một trợ lý hữu ích."; S1="$S0 Hôm nay là ngày 13/10/2026."; S25="$S0 Hôm nay là ngày 01/01/2025."
go() {  # tag items [system]
  python3 minitest_sys.py run --items $2 --url $U --model $M --extra "$X" --max-tokens 1024 --par 8 \
    --out preds_$1_${M}__gpu.jsonl ${3:+--system "$3"} >> muse_controls.log 2>&1 \
    && echo "$(date +%T) done $1" || echo "$(date +%T) FAIL $1"
}
go sys0 sysdate_items.jsonl "$S0" & go sys1 sysdate_items.jsonl "$S1" & go sys0q sysdate_q_items.jsonl "$S0" &
go sys0qm sysdate_qm_items.jsonl "$S0" & go sys2025 sysdate_items.jsonl "$S25" & go q2025 sysdate_q2025_items.jsonl &
wait; kill $pid; wait $pid 2>/dev/null; echo "$(date +%T) MUSE_CONTROLS_DONE"
