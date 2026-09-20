# DivaBot — local DIVA-style bot

## What it is
Chat bot that answers using an LLM. Two providers (shared `llm_client.py`):
- **DeepSeek API**: OpenAI-compatible `/chat/completions`, `LLM_PROVIDER=deepseek`
- **Local**: llama.cpp server on http://localhost:8080 (`/completions`), `LLM_PROVIDER=local` (default)

Frontends (both use the same `ask_llm()`):
- **Discord**: `bot_discord.py` — `!diva <question>` + mention replies
- **WhatsApp**: `bot_whatsapp.py` — polls the local Baileys bridge, replies in your self-chat

## Architecture
- LLM layer: `llm_client.py` — providers, retries/backoff, `.env` auto-load
- Discord: `bot_discord.py` — token from `DISCORD_TOKEN` or `DISCORD_BOT_TOKEN`; gateway watchdog prints actionable fixes (4014 etc.)
- WhatsApp: `bot_whatsapp.py` + vendored `whatsapp_bridge/` (Baileys, port 3001, own session dir `whatsapp_session/`)
  - Pair once: `scripts/run_whatsapp_bridge.sh` → scan QR
  - `self-chat` mode: only your "Message yourself" chat reaches the LLM
- llama.cpp: `scripts/run_llama_server.sh` (model from `MODEL_PATH` or `configs/llama_config.json`)
- CLI: `scripts/llm_cli.py`
- Venv: `.venv`. Run with `.venv/bin/python` (or console scripts `diva-discord` / `diva-whatsapp` after `pip install -e .`)

## Conventions
- Never hardcode secrets: env vars, auto-loaded from `.env` or `~/.hermes/.env` (gitignored)
- LLM calls run via `asyncio.to_thread`, 120s timeout, retries with backoff
- Discord: answers truncated to 2000 chars
- WhatsApp: bridge auto-chunks long replies; typing indicator before answering
- Failures print actionable fixes (4014 intent, unpaired bridge, model missing)

## Status
- [x] DeepSeek + local llama.cpp providers (DeepSeek verified live)
- [x] Discord bot (verified live)
- [x] WhatsApp bot, self-chat mode (verified live)
- [ ] WhatsApp group mode / media replies
- [x] Docker: `Dockerfile` + `docker-compose.yml` (perfiles: core/local/whatsapp) — Discord+DeepSeek verified live in container
- [x] systemd units for always-on bots (see Always-on below)

## Always-on
Bots run as systemd user units, installed from `systemd/`.
- Install and start: `./scripts/install_systemd.sh` (idempotent; also `enable --now` for all three units)
- Units: `divabot-discord.service`, `divabot-whatsapp.service`, `divabot-whatsapp-bridge.service`
- Logs: `journalctl --user -u divabot-discord -f` (same with `divabot-whatsapp` / `divabot-whatsapp-bridge`)
- `sudo loginctl enable-linger eve` starts them at boot without a graphical login
- Docker compose remains available, but the systemd user units now own the bots
