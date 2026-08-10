#!/bin/bash
# DivaBot — generate the project .env for Docker from the shared Hermes env.
#
# Sources (first that exists wins per key):
#   $DIVABOT_ENV_FILE, ./env-source (optional), ~/.hermes/.env
# Writes/updates ./.env — never prints secrets.
#
# Usage:  ./scripts/setup_docker_env.sh
#         (then: docker compose up -d discord)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # project root

OUT="${DIVABOT_ENV_FILE:-$(pwd)/.env}"

# Keys DivaBot understands (see .env.example).
KEYS=(
  LLM_PROVIDER
  DEEPSEEK_API_KEY
  DEEPSEEK_BASE_URL
  DEEPSEEK_MODEL
  LLAMA_API_URL
  LLAMA_MODEL
  DISCORD_TOKEN
  DISCORD_BOT_TOKEN
  WHATSAPP_ALLOWED_USERS
  WHATSAPP_POLL_INTERVAL
  DIVA_SYSTEM_PROMPT
  LLM_MAX_TOKENS
  LLM_TEMPERATURE
  LLM_TIMEOUT
  LLM_MAX_RETRIES
)

# Collect candidate source files in priority order.
SOURCES=()
[ -n "${DIVABOT_ENV_FILE:-}" ] && [ -f "$DIVABOT_ENV_FILE" ] && SOURCES+=("$DIVABOT_ENV_FILE")
[ -f "$(pwd)/env-source" ] && SOURCES+=("$(pwd)/env-source")
[ -f "${HOME}/.hermes/.env" ] && SOURCES+=("${HOME}/.hermes/.env")

if [ "${#SOURCES[@]}" -eq 0 ]; then
  echo "❌ No env source found (looked at DIVABOT_ENV_FILE, ./env-source, ~/.hermes/.env)." >&2
  echo "   Create $OUT manually from .env.example." >&2
  exit 1
fi

# Start from the previous $OUT (keeps user edits), then overlay sources.
[ -f "$OUT" ] && cp "$OUT" "$OUT.tmp" || : > "$OUT.tmp"

for key in "${KEYS[@]}"; do
  value=""
  for src in "${SOURCES[@]}"; do
    value="$(grep -E "^${key}=" "$src" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
    [ -n "$value" ] && break
  done
  if [ -n "$value" ]; then
    # Replace or append the key in the tmp file.
    if grep -qE "^${key}=" "$OUT.tmp"; then
      sed -i "s|^${key}=.*|${key}=${value}|" "$OUT.tmp"
    else
      printf '%s=%s\n' "$key" "$value" >> "$OUT.tmp"
    fi
  fi
done

mv "$OUT.tmp" "$OUT"
chmod 600 "$OUT"

found=0
for key in DISCORD_TOKEN DISCORD_BOT_TOKEN DEEPSEEK_API_KEY LLM_PROVIDER; do
  grep -qE "^${key}=.+" "$OUT" && found=$((found + 1))
done
echo "✅ $OUT written (${found}/4 core keys present)."
echo "   Start with:  docker compose up -d discord"
echo "   Local model: docker compose --profile local up -d"
