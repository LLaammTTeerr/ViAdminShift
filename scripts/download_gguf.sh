#!/usr/bin/env bash
# Download the Q8_0 GGUF set used in the paper (same quantisation for every model).
# Usage: download_gguf.sh <dest_dir>
set -u
DEST=${1:-$HOME/models}; mkdir -p "$DEST"; cd "$DEST"
while read -r repo file out; do
  [ -z "$repo" ] && continue
  out=${out:-$(basename "$file")}
  if [ -s "$out" ] && [ ! -e "$out.part" ]; then echo "skip $out"; continue; fi
  ( touch "$out.part" && curl -fsSL --retry 10 --retry-all-errors --retry-delay 5 -C - -o "$out" "https://huggingface.co/$repo/resolve/main/$file" \
      && rm -f "$out.part" && echo "done $out $(du -h "$out" | cut -f1)" || echo "FAIL $out" ) &
done <<'LIST'
unsloth/Qwen3-1.7B-GGUF Qwen3-1.7B-Q8_0.gguf
unsloth/Qwen3-4B-GGUF Qwen3-4B-Q8_0.gguf
unsloth/Qwen3-8B-GGUF Qwen3-8B-Q8_0.gguf
unsloth/Qwen3.5-2B-GGUF Qwen3.5-2B-Q8_0.gguf
unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q8_0.gguf
unsloth/Llama-3.2-3B-Instruct-GGUF Llama-3.2-3B-Instruct-Q8_0.gguf
unsloth/gemma-3-4b-it-GGUF gemma-3-4b-it-Q8_0.gguf
unsloth/gemma-4-E4B-it-GGUF gemma-4-E4B-it-Q8_0.gguf
unsloth/Ministral-3-8B-Instruct-2512-GGUF Ministral-3-8B-Instruct-2512-Q8_0.gguf
CohereLabs/tiny-aya-global-GGUF tiny-aya-global-q8_0.gguf
featherless-ai-quants/SeaLLMs-SeaLLMs-v3-7B-Chat-GGUF SeaLLMs-SeaLLMs-v3-7B-Chat-Q8_0.gguf SeaLLMs-v3-7B-Chat.Q8_0.gguf
LIST
wait
