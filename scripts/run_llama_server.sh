#!/bin/bash
# DivaBot — llama.cpp server launcher (local LLM provider).
#
# Starts llama-server exposing the OpenAI-compatible API on http://localhost:8080.
# The model path is resolved from (highest priority first):
#   1. $MODEL_PATH env var
#   2. "model_path" in configs/llama_config.json
#
# Example:
#   MODEL_PATH=~/models/Hermes-3-Llama-3.1-8B.Q8_0.gguf ./scripts/run_llama_server.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # project root

CONFIG_PATH="${DIVABOT_CONFIG:-$(pwd)/configs/llama_config.json}"

# Resolve the model path.
MODEL_PATH="${MODEL_PATH:-}"
if [ -z "$MODEL_PATH" ] && [ -f "$CONFIG_PATH" ]; then
  MODEL_PATH="$(grep -oP '"model_path"\s*:\s*"\K[^"]+' "$CONFIG_PATH" || true)"
fi
if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
  echo "❌ Model not found: ${MODEL_PATH:-<unset>}" >&2
  echo "   Set MODEL_PATH to a GGUF file (see configs/llama_config.json)." >&2
  echo "   Example: MODEL_PATH=~/models/Hermes-3-Llama-3.1-8B.Q8_0.gguf $0" >&2
  exit 1
fi
MODEL_PATH="$(readlink -f "$MODEL_PATH")"

echo "🚀 Starting llama.cpp server..."
echo "Model: $MODEL_PATH"
echo "Config: $CONFIG_PATH"

llama-server -m "$MODEL_PATH" \
  --ctx-size 4096 \
  --n-gpu-layers 99 \
  --n-threads 8 \
  --temp 0.7 \
  --host 0.0.0.0 \
  --port 8080
