"""DivaBot — Discord layer.

Discord bot that answers using an LLM. Two providers are supported:

  * ``local``   — a llama.cpp server exposing the OpenAI-compatible
                  ``/v1/completions`` endpoint (default).
  * ``deepseek`` — the DeepSeek API (``/v1/chat/completions``).

Usage:
    DISCORD_TOKEN=<token> .venv/bin/python bot_discord.py

Configuration (environment variables):
    DISCORD_TOKEN         Discord bot token (required).
    LLM_PROVIDER          "local" (default) or "deepseek".
    LLAMA_API_URL         Local llama.cpp base URL (default: http://localhost:8080/v1).
    LLAMA_MODEL           Model name reported to the local server (default: llama-3-8b).
    DEEPSEEK_API_KEY      DeepSeek API key (required when LLM_PROVIDER=deepseek).
    DEEPSEEK_BASE_URL     Default: https://api.deepseek.com/v1
    DEEPSEEK_MODEL        Default: deepseek-chat
    DIVA_SYSTEM_PROMPT    System prompt for DeepSeek / chat-style providers.
    LLM_MAX_TOKENS        Default: 512.
    LLM_TEMPERATURE       Default: 0.7.
    LLM_TIMEOUT           HTTP timeout in seconds (default: 120).
    LLM_MAX_RETRIES       Retries per request with backoff (default: 2).

First-time Discord setup:
  1. Go to https://discord.com/developers/applications -> New Application
  2. Bot tab -> Reset Token -> copy the token
  3. Enable the message content intent in the Bot tab
  4. OAuth2 -> URL Generator -> scope "bot" -> permissions "Send Messages"
  5. Open the generated URL in a browser and invite the bot to a server
  6. Run this script with the token

On Discord:  ``!diva <question>``  or mention the bot and ask anything.
"""

import asyncio
import logging
import os

import discord
from discord.ext import commands

from llm_client import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, MODEL, PROVIDER, _load_dotenv, ask_llm

LOG = logging.getLogger("divabot")

DISCORD_MESSAGE_LIMIT = 2000  # hard cap on Discord message length


# ---------------------------------------------------------------------------
# Discord bot
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    model = MODEL if PROVIDER == "local" else DEEPSEEK_MODEL
    LOG.info("Diva online as %s — provider=%s model=%s", bot.user, PROVIDER, model)
    LOG.info("Invite link: %s", _invite_url(os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN", "")))


async def _reply(context, prompt: str) -> None:
    """Ask the LLM off the event loop and reply within Discord's length limit."""
    try:
        answer = await asyncio.to_thread(ask_llm, prompt)
    except RuntimeError as err:
        await context.reply(f"⚠️ {err}")
        return
    await context.reply(answer[:DISCORD_MESSAGE_LIMIT])


@bot.command()
async def diva(ctx, *, question: str):
    """!diva <question> — ask Diva anything."""
    async with ctx.typing():
        await _reply(ctx, question)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if bot.user in message.mentions:
        async with message.channel.typing():
            await _reply(message, message.content)
        return
    await bot.process_commands(message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _client_id_from_token(token: str) -> str:
    """Decode the application ID embedded in a Discord bot token (first segment)."""
    import base64
    try:
        payload = token.split(".")[0]
        payload += "=" * (-len(payload) % 4)
        return str(int(base64.b64decode(payload).decode()))
    except (IndexError, ValueError, UnicodeDecodeError):
        return ""


def _invite_url(token: str, permissions: int = 2048) -> str:
    """Build an OAuth2 invite URL for the bot (2048 = Send Messages)."""
    client_id = _client_id_from_token(token)
    return (
        f"https://discord.com/api/oauth2/authorize?client_id={client_id}"
        f"&permissions={permissions}&scope=bot%20applications.commands"
    )


def _install_gateway_watchdog(token: str) -> None:
    """Surface Discord gateway close codes (e.g. 4014) immediately.

    discord.py logs close codes at DEBUG and retries silently for ~15s before
    raising, which is confusing. This filter promotes the important ones to a
    single WARNING with actionable fix instructions and drops the rest.
    """
    logger = logging.getLogger("discord.gateway")
    if getattr(logger, "_diva_watchdog", False):
        return
    logger._diva_watchdog = True

    client_id = _client_id_from_token(token)

    class GatewayWatch(logging.Filter):
        _warned = False

        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            if "4014" in msg or "Disallowed intent" in msg:
                if not GatewayWatch._warned:
                    GatewayWatch._warned = True
                    record.msg = (
                        "DISCORD INTENT ERROR (4014): the bot requests the Message Content "
                        "intent but it is not enabled. Fix:\n"
                        f"  1. Open https://discord.com/developers/applications/{client_id}/bot\n"
                        '  2. Under Privileged Gateway Intents, enable "Message Content Intent"\n'
                        "  3. Click Save, then re-run this script."
                    )
                    record.args = ()  # the original args no longer match the rewritten msg
                    record.levelno = logging.WARNING
                    record.levelname = "WARNING"
                return True
            return False

    logger.setLevel(logging.DEBUG)
    logger.addFilter(GatewayWatch())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "DISCORD_TOKEN is missing. Create the bot at discord.com/developers and run:\n"
            "  DISCORD_TOKEN=<token> .venv/bin/python bot_discord.py"
        )
    if PROVIDER == "deepseek" and not DEEPSEEK_API_KEY:
        raise SystemExit("LLM_PROVIDER=deepseek requires DEEPSEEK_API_KEY to be set.")

    _install_gateway_watchdog(token)

    try:
        bot.run(token)
    except discord.PrivilegedIntentsRequired:
        raise SystemExit(
            "\nDiscord rejected the connection (4014: disallowed intent).\n"
            "Fix: https://discord.com/developers/applications -> your app -> Bot tab\n"
            "  1. Under Privileged Gateway Intents, enable \"Message Content Intent\".\n"
            "  2. Save. Then re-run this script.\n"
            f"  3. Invite the bot to a server if you haven't yet:\n     {_invite_url(token)}"
        ) from None


if __name__ == "__main__":
    main()
