"""DivaBot — LLM CLI client.

Talk to Diva's LLM backends straight from the terminal. Uses the same shared
layer as the Discord and WhatsApp bots (llm_client.ask_llm).

Usage:
    python scripts/llm_cli.py "your prompt here"
    echo "piped prompt" | python scripts/llm_cli.py
"""

import sys

from llm_client import _load_dotenv, ask_llm


def main() -> None:
    _load_dotenv()

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = sys.stdin.read().strip() or "Explain what an API is in one sentence."

    print(f"🧠 Diva thinking about: {prompt}")
    try:
        answer = ask_llm(prompt)
    except RuntimeError as err:
        print(f"❌ {err}", file=sys.stderr)
        raise SystemExit(1) from err
    print("-" * 30)
    print(f"🤖 {answer}")


if __name__ == "__main__":
    main()
