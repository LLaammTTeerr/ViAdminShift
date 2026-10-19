#!/usr/bin/env bash
# Wave 1 via llama.cpp CUDA: cue ladder (quick, then full only for models that know the update) + closed v2 + RAG.
# GPUs 2,3: models with stated post-reform knowledge cutoffs first (prebuilt Q8_0), then gemma-4-12B.
# GPUs 0 / 1: small bf16 models, then Qwen-SEA-LION-27B on the pair. Finally all 4: the largest local models.
cd /workspace/viadmin
R=./vast_llamacpp.sh; SETS="cue3_items cue3full_items minitest_items rag_items"
$R 2,3 8123 "$SETS" unsloth/Qwen3.8-27B-GGUF:Qwen3.8-27B-Q8_0.gguf \
  unsloth/Muse-Glimmer-30B-GGUF:Muse-Glimmer-30B-Q8_0.gguf \
  unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF:NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q8_0.gguf \
  aisingapore/Nemotron-SEA-LION-v4.8-30B-A3B-GGUF:Nemotron-SEA-LION-v4.8-30B-A3B-Q8_0.gguf \
  google/gemma-4-12B-it > wave1_tp2.log 2>&1 &
pair=$!
(
  $R 0 8100 "$SETS" CohereLabs/tiny-aya-global Qwen/Qwen3-8B Qwen/Qwen3-1.7B mistralai/Ministral-3-8B-Instruct-2512 \
    unsloth/Llama-3.2-3B-Instruct Qwen/Qwen3.5-2B > wave1_gpu0.log 2>&1 &
  $R 1 8101 "$SETS" Qwen/Qwen3-4B Qwen/Qwen3.5-9B Qwen/Qwen3.5-4B SeaLLMs/SeaLLMs-v3-7B-Chat google/gemma-4-E4B-it \
    unsloth/gemma-3-4b-it > wave1_gpu1.log 2>&1 &
  wait
  $R 0,1 8110 "$SETS" aisingapore/Qwen-SEA-LION-v4.5-27B-IT-GGUF:Qwen-SEA-LION-v4.5-27B-IT-Q8_0.gguf > wave1_tp01.log 2>&1
) &
wait
$R 0,1,2,3 8120 "$SETS" \
  bartowski/moonshotai_Kimi-Linear-48B-A3B-Instruct-GGUF:moonshotai_Kimi-Linear-48B-A3B-Instruct-Q8_0/moonshotai_Kimi-Linear-48B-A3B-Instruct-Q8_0-00001-of-00002.gguf \
  unsloth/Mistral-Small-4-119B-2603-GGUF:UD-Q4_K_XL/Mistral-Small-4-119B-2603-UD-Q4_K_XL-00001-of-00003.gguf > wave1_tp4.log 2>&1
echo WAVE1_DONE
