"""Where the API lives, and how we find your key.

Crusoe speaks the OpenAI protocol, so the only things that make this "Crusoe"
are the base URL and your key.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
SESSIONS_DIR = ROOT / "sessions"

# Chat completions. This is the only endpoint the chatbot uses.
BASE_URL = "https://api.inference.crusoecloud.com/v1"

# A good all-rounder. You can change it in the app at any time.
DEFAULT_MODEL = "openai/gpt-oss-120b"

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant running on Crusoe. "
    "Be direct and concise. Lead with the answer, then the reasoning. "
    "Use lists only when the content is genuinely a list. "
    "If you are unsure, say so instead of inventing detail."
)

KEY_HELP = (
    "Get a key at https://console.crusoecloud.com  ->  Intelligence Foundry  ->  API Keys"
)


def read_saved_key() -> str:
    """Look in .env, then in the environment."""
    load_dotenv(ENV_PATH)
    return os.environ.get("CRUSOE_API_KEY", "").strip()


def save_api_key(key: str) -> None:
    """Write the key to .env, keeping anything else already in there."""
    key = key.strip()
    lines, replaced = [], False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("CRUSOE_API_KEY="):
                lines.append(f"CRUSOE_API_KEY={key}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.insert(0, f"CRUSOE_API_KEY={key}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV_PATH.chmod(0o600)
    except OSError:
        pass
    os.environ["CRUSOE_API_KEY"] = key


def _in_notebook() -> bool:
    try:
        from IPython import get_ipython

        return get_ipython() is not None
    except Exception:  # noqa: BLE001
        return False


def ensure_api_key(prompt: bool = True) -> str:
    """Return the API key, asking for it once if we do not have one yet."""
    key = read_saved_key()
    if key:
        return key

    if not prompt:
        raise RuntimeError(f"CRUSOE_API_KEY is not set. Run ./setup.sh. {KEY_HELP}")

    import getpass
    import sys

    if not (sys.stdin and (sys.stdin.isatty() or _in_notebook())):
        raise RuntimeError(
            f"CRUSOE_API_KEY is not set and there is nobody to ask. Run ./setup.sh. {KEY_HELP}"
        )

    print("No Crusoe API key found yet.")
    print(KEY_HELP)
    try:
        key = getpass.getpass("Paste your Crusoe API key (hidden): ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise RuntimeError("No API key entered.") from exc
    if not key:
        raise RuntimeError(f"No API key entered. {KEY_HELP}")

    save_api_key(key)
    print(f"Saved to {ENV_PATH.name}. You will not be asked again.")
    return key
