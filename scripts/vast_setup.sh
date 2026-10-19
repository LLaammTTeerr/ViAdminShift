#!/usr/bin/env bash
# Rented GPU box setup: vLLM env + bf16 model downloads (large post-reform models first).
# Usage: vast_setup.sh install | download
set -u
export HF_HOME=${HF_HOME:-/workspace/.hf_home}
case "$1" in
  install)
    uv venv /workspace/vllm-env -p 3.12 -q
    VIRTUAL_ENV=/workspace/vllm-env uv pip install -q vllm huggingface_hub hf_transfer
    /workspace/vllm-env/bin/python -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__, torch.cuda.device_count())"
    ;;
  download)
    MODELS="CohereLabs/tiny-aya-global Qwen/Qwen3.8-27B Qwen/Qwen3.5-9B google/gemma-4-12B-it Qwen/Qwen3.5-4B Qwen/Qwen3-4B \
      mistralai/Ministral-3-8B-Instruct-2512 Qwen/Qwen3-8B google/gemma-4-E4B-it SeaLLMs/SeaLLMs-v3-7B-Chat \
      unsloth/Llama-3.2-3B-Instruct unsloth/gemma-3-4b-it Qwen/Qwen3.5-2B Qwen/Qwen3-1.7B"
    echo $MODELS | tr ' ' '\n' | xargs -P ${DL_PAR:-4} -I{} sh -c \
      'uvx --from huggingface_hub hf download {} --exclude "*.gguf" --exclude "*.pth" --exclude "original/*" --exclude "consolidated*" > /dev/null 2>&1 \
         && echo "$(date +%T) ok {}" || echo "$(date +%T) FAIL {}"'
    ;;
esac
