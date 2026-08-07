"""DivaBot — shared LLM client.

Single LLM layer used by all DivaBot frontends (Discord, WhatsApp, CLI).
Two providers are supported:

  * ``local``    — a llama.cpp server exposing the OpenAI-compatible
                   ``/v1/completions`` endpoint (default).
  * ``deepseek`` — the DeepSeek API (``/v1/chat/completions``).

Environment variables:
    LLM_PROVIDER          "local" (default) or "deepseek".
    LLAMA_API_URL         Local llama.cpp base URL (default: http://localhost:8080/v1).
    LLAMA_MODEL           Model name reported to the local server (default: llama-3-8b).
    DEEPSEEK_API_KEY      DeepSeek API key (required when LLM_PROVIDER=deepseek).
    DEEPSEEK_BASE_URL     Default: https://api.deepseek.com/v1
    DEEPSEEK_MODEL        Default: deepseek-chat
    DIVA_SYSTEM_PROMPT    System prompt for chat-style providers.
    LLM_MAX_TOKENS        Default: 512.
    LLM_TEMPERATURE       Default: 0.7.
    LLM_TIMEOUT           HTTP timeout in seconds (default: 120).
    LLM_MAX_RETRIES       Retries per request with exponential backoff (default: 2).
"""

import logging
import os
import time
from pathlib import Path

import requests

LOG = logging.getLogger("divabot.llm")


def _load_dotenv(path: str | Path = "~/.hermes/.env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (does not override)."""
    env_file = Path(path).expanduser()
    if not env_file.is_file():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROVIDER = os.getenv("LLM_PROVIDER", "local").lower()  # "local" | "deepseek"
API_URL = os.getenv("LLAMA_API_URL", "http://localhost:8080/v1")
MODEL = os.getenv("LLAMA_MODEL", "llama-3-8b")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
SYSTEM_PROMPT = os.getenv(
    "DIVA_SYSTEM_PROMPT",
    "You are Diva, a helpful and witty assistant. Keep answers concise.",
)

MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------
def ask_llm(prompt: str) -> str:
    """Ask the configured LLM provider and return the plain-text answer."""
    if PROVIDER == "deepseek":
        return _ask_deepseek(prompt)
    return _ask_local(prompt)


def _ask_local(prompt: str) -> str:
    """Query a local llama.cpp server (OpenAI-compatible ``/completions``)."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "stream": False,
    }
    return _post_with_retry(
        f"{API_URL}/completions",
        payload,
        lambda data: data["choices"][0]["text"].strip(),
        source="local llama.cpp",
    )


def _ask_deepseek(prompt: str) -> str:
    """Query the DeepSeek API (OpenAI-compatible ``/chat/completions``)."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not set (required with LLM_PROVIDER=deepseek)")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    return _post_with_retry(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        payload,
        lambda data: data["choices"][0]["message"]["content"].strip(),
        source="DeepSeek",
        headers=headers,
    )


def _post_with_retry(url: str, payload: dict, extract, source: str, headers=None) -> str:
    """POST to an OpenAI-compatible endpoint with retries and exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return extract(resp.json())
        except (requests.RequestException, KeyError, ValueError) as err:
            last_error = err
            LOG.warning("%s attempt %d/%d failed: %s", source, attempt + 1, MAX_RETRIES + 1, err)
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)  # 1s, 2s, ...
    raise RuntimeError(f"{source} unavailable after {MAX_RETRIES + 1} attempts: {last_error}")
