#!/bin/bash
# Muse-Glimmer template-date ablation on the running server (port 8130). minitest_sys.py = minitest.py with --system.
cd /workspace/viadmin
M=Muse-Glimmer-30B-Q8_0; U=http://127.0.0.1:8130
R='"reasoning_strength": "none"'
go() {  # tag items extra [system]
  python3 minitest_sys.py run --items $2 --url $U --model $M-$1 --extra "$3" --max-tokens 1024 --par 8 \
    --out preds_${4:+}$(basename $2 _items.jsonl)_items_$M-$1.jsonl ${5:+--system "$5"} >> muse_tmpl.log 2>&1 \
    && echo "$(date +%T) done $1 $(basename $2)" || echo "$(date +%T) FAIL $1 $(basename $2)"
}
S0="You are a helpful AI assistant."
go nodate cue3_items.jsonl "{\"chat_template_kwargs\": {$R}}" "" "$S0" &
go nodate cue3np_items.jsonl "{\"chat_template_kwargs\": {$R}}" "" "$S0" &
go cutoffonly sysdate_items.jsonl "{\"chat_template_kwargs\": {$R}}" "" "$S0
Knowledge cutoff: 2026-01-04." &
go date2025 sysdate_items.jsonl "{\"chat_template_kwargs\": {$R, \"current_date\": \"2025-01-01\"}}" &
wait; echo TMPL_DONE
