#!/usr/bin/env bash
# Install DivaBot systemd user units and start the bots.
set -euo pipefail

UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "${UNIT_DIR}"

cp systemd/*.service "${UNIT_DIR}/"
systemctl --user daemon-reload
systemctl --user enable --now divabot-discord.service divabot-whatsapp-bridge.service divabot-whatsapp.service

systemctl --user status divabot-discord.service divabot-whatsapp-bridge.service divabot-whatsapp.service

cat <<'EOF'

Note: run `sudo loginctl enable-linger eve` so the units start at boot
without requiring a graphical login.
EOF
