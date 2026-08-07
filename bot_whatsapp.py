"""DivaBot — WhatsApp layer (Baileys bridge client).

Listens to the local WhatsApp bridge (``whatsapp_bridge/bridge.js``) and
answers every text message with the LLM (see ``llm_client.py`` for providers).

The bridge runs a Baileys session: you pair once by scanning a QR code with
your phone, then the bridge stays connected. In ``self-chat`` mode (default)
only your own "Message yourself" chat is forwarded — exactly what you want for
a personal assistant; the bridge enforces this, so stranger DMs never reach
the LLM.

Architecture::

    WhatsApp  <--Baileys-->  bridge.js (port 3001)  <--HTTP-->  bot_whatsapp.py  --ask_llm()-->  LLM

Setup:
    1. Pair once:   ./Diva/scripts/run_whatsapp_bridge.sh   (scan the QR with the phone)
    2. Run:         LLM_PROVIDER=deepseek .venv/bin/python bot_whatsapp.py

Configuration (environment variables):
    WHATSAPP_BRIDGE_URL       Bridge base URL (default: http://127.0.0.1:3001).
    WHATSAPP_ALLOWED_USERS    Comma-separated numbers, international format,
                              e.g. 5491158432267. Optional — the bridge's
                              self-chat mode already restricts input.
    WHATSAPP_POLL_INTERVAL    Seconds between queue polls (default: 1).
"""

import asyncio
import logging
import os
from typing import Any

import requests

from llm_client import _load_dotenv, ask_llm

LOG = logging.getLogger("divabot.whatsapp")

_load_dotenv()

BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3001").rstrip("/")
POLL_INTERVAL = float(os.getenv("WHATSAPP_POLL_INTERVAL", "1.0"))
ALLOWED_USERS = {
    u.strip().lstrip("+")
    for u in os.getenv("WHATSAPP_ALLOWED_USERS", "").split(",")
    if u.strip()
}

# De-dupe safety net across bridge restarts (a restart can re-deliver the tail
# of its in-memory queue; the id set is bounded and pruned).
_PROCESSED_IDS: set[str] = set()
_MAX_PROCESSED = 2000


# ---------------------------------------------------------------------------
# Bridge client
# ---------------------------------------------------------------------------
def _bridge(path: str, method: str = "GET", **kwargs) -> requests.Response:
    """Call the bridge, raising a clear error if it is down or not paired."""
    try:
        resp = requests.request(method, f"{BRIDGE_URL}{path}", timeout=30, **kwargs)
    except requests.RequestException as err:
        raise RuntimeError(
            f"cannot reach WhatsApp bridge at {BRIDGE_URL} (is it running?) — {err}"
        ) from err
    if resp.status_code in (503,):
        raise RuntimeError("WhatsApp bridge is not connected to WhatsApp yet (QR not paired?)")
    resp.raise_for_status()
    return resp


def fetch_messages() -> list[dict[str, Any]]:
    """Drain the bridge's inbound queue (each event arrives exactly once)."""
    try:
        return _bridge("/messages").json()
    except RuntimeError:
        raise


def bridge_status() -> str:
    """Human-readable pairing/connection status from the bridge /health."""
    try:
        data = _bridge("/health").json()
    except RuntimeError as err:
        return f"unreachable ({err})"
    status = data.get("status", "unknown")
    if status == "connected":
        return "connected & paired ✓"
    return "running but NOT paired — scan the QR shown by run_whatsapp_bridge.sh"


def send_text(chat_id: str, text: str, reply_to: str | None = None) -> None:
    """Send a text reply through the bridge (it auto-chunks long messages)."""
    _bridge("/send", method="POST", json={"chatId": chat_id, "message": text, "replyTo": reply_to})


def send_typing(chat_id: str) -> None:
    """Show the WhatsApp composing indicator (best effort)."""
    try:
        _bridge("/typing", method="POST", json={"chatId": chat_id})
    except (RuntimeError, requests.RequestException):
        pass


# ---------------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------------
def _is_allowed(chat_id: str, sender_id: str) -> bool:
    """Allowlist check (defense in depth; the bridge already gates in self-chat)."""
    if not ALLOWED_USERS:
        return True
    numbers = {chat_id.split("@")[0].lstrip("+"), sender_id.split("@")[0].lstrip("+")}
    return bool(numbers & ALLOWED_USERS)


async def handle_event(event: dict[str, Any]) -> None:
    """Process one inbound bridge event and reply via the LLM."""
    msg_id = event.get("messageId") or ""
    if msg_id and msg_id in _PROCESSED_IDS:
        return
    if event.get("fromOwner"):
        return  # owner-typed message from a bot-mode session; not for us

    body = (event.get("body") or "").strip()
    if not body:
        LOG.info("ignoring non-text event (media=%s)", event.get("mediaType") or "none")
        return

    chat_id = event.get("chatId") or ""
    sender_id = event.get("senderId") or ""
    if not chat_id:
        LOG.warning("dropping event without chatId: %r", event)
        return
    if not _is_allowed(chat_id, sender_id):
        LOG.info("ignoring message from non-allowlisted number: %s", chat_id)
        return

    if msg_id:
        _PROCESSED_IDS.add(msg_id)
        if len(_PROCESSED_IDS) > _MAX_PROCESSED:
            _PROCESSED_IDS.clear()

    LOG.info("asking LLM: %r", body[:100])
    send_typing(chat_id)
    try:
        answer = await asyncio.to_thread(ask_llm, body)
    except RuntimeError as err:
        LOG.error("LLM failed: %s", err)
        try:
            send_text(chat_id, f"⚠️ {err}")
        except RuntimeError as send_err:
            LOG.error("could not send error reply: %s", send_err)
        return

    try:
        send_text(chat_id, answer, reply_to=msg_id or None)
        LOG.info("replied (%d chars)", len(answer))
    except (RuntimeError, requests.RequestException) as err:
        LOG.error("could not send reply: %s", err)


async def poll_loop() -> None:
    """Poll the bridge queue forever and handle each event in order."""
    LOG.info("Diva WhatsApp online — bridge=%s provider=%s status=%s",
             BRIDGE_URL, os.getenv("LLM_PROVIDER", "local"), bridge_status())
    while True:
        try:
            events = fetch_messages()
        except RuntimeError as err:
            LOG.warning("%s (retrying in %ss)", err, POLL_INTERVAL)
            await asyncio.sleep(POLL_INTERVAL)
            continue

        for event in events:
            try:
                await handle_event(event)
            except Exception:  # noqa: BLE001 — never kill the poll loop
                LOG.exception("unhandled error while processing event %r", event)
        await asyncio.sleep(POLL_INTERVAL)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        LOG.info("Diva WhatsApp stopped.")


if __name__ == "__main__":
    main()
