#!/bin/bash
# Prefetch GGUFs queued later so their downloads overlap with running jobs (the run scripts skip files already present).
source /workspace/.hf_env
get() { for t in 1 2 3 4 5 6 7 8; do uvx --from huggingface_hub hf download "$1" --include "$2" --local-dir /workspace/gguf > /dev/null 2>&1 && { echo "$(date +%T) prefetched $2"; return; }; sleep 30; done; echo "$(date +%T) PREFETCH-FAIL $2"; }
get mradermacher/Qwen3.5-9B-Kimi-k3-Distilled-GGUF Qwen3.5-9B-Kimi-k3-Distilled.Q8_0.gguf &
get unsloth/Muse-Glimmer-30B-GGUF Muse-Glimmer-30B-UD-Q5_K_M.gguf &
wait
