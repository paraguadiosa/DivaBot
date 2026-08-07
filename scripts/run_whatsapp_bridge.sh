#!/bin/bash
# DivaBot — WhatsApp bridge launcher.
#
# Starts the Baileys bridge (whatsapp_bridge/bridge.js) on its own port with
# its own session, so it does not interfere with a Hermes WhatsApp bridge if
# one is running (Hermes uses port 3000 by default).
#
# First run: prints a QR code — scan it from WhatsApp: Settings -> Linked
# devices -> Link a device. After that the session persists (no QR needed).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # project root

PORT="${WHATSAPP_BRIDGE_PORT:-3001}"
SESSION_DIR="${WHATSAPP_SESSION_DIR:-$(pwd)/whatsapp_session}"
MODE="${WHATSAPP_MODE:-self-chat}"

# Load WHATSAPP_* settings: from $DIVABOT_ENV_FILE, else a local .env, else
# the shared ~/.hermes/.env used by Hermes (all optional).
for env_file in "${DIVABOT_ENV_FILE:-}" "$(pwd)/.env" "${HOME}/.hermes/.env"; do
  if [ -n "$env_file" ] && [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
    break
  fi
done

# Diva branding on outgoing messages instead of a generic prefix.
export WHATSAPP_REPLY_PREFIX="${WHATSAPP_REPLY_PREFIX:-✨ *Diva*\n────────────\n}"

echo "🚀 Starting Diva WhatsApp bridge on port $PORT (mode: $MODE)"
echo "   Session: $SESSION_DIR"
exec node whatsapp_bridge/bridge.js \
  --port "$PORT" \
  --session "$SESSION_DIR" \
  --mode "$MODE"
