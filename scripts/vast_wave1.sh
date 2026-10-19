#!/usr/bin/env bash
# Wave 1: mini-test (closed v2 + mixed-doc RAG) on all downloaded models, 4 GPUs.
cd /workspace/viadmin
R=./vast_run_models.sh; SETS="minitest_items rag_items"
$R 0 8100 "$SETS" Qwen/Qwen3-1.7B Qwen/Qwen3-4B Qwen/Qwen3-8B Qwen/Qwen3.5-2B > wave1_gpu0.log 2>&1 &
$R 1 8101 "$SETS" Qwen/Qwen3.5-4B Qwen/Qwen3.5-9B unsloth/Llama-3.2-3B-Instruct > wave1_gpu1.log 2>&1 &
$R 2 8102 "$SETS" google/gemma-4-E4B-it unsloth/gemma-3-4b-it CohereLabs/tiny-aya-global > wave1_gpu2.log 2>&1 &
$R 3 8103 "$SETS" mistralai/Ministral-3-8B-Instruct-2512 SeaLLMs/SeaLLMs-v3-7B-Chat > wave1_gpu3.log 2>&1 &
wait
$R 0,1 8110 "$SETS" google/gemma-4-12B-it > wave1_tp2.log 2>&1
$R 0,1,2,3 8120 "$SETS" Qwen/Qwen3.8-27B > wave1_tp4.log 2>&1
echo WAVE1_DONE
