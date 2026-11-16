"""Confirm the API key works and Crusoe is reachable.

    uv run python scripts/check_setup.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crusoe_chat import client, config  # noqa: E402


def main() -> int:
    try:
        key = config.ensure_api_key()
    except RuntimeError as exc:
        print(f"No API key: {exc}")
        return 1
    print(f"API key      ...{key[-4:]}")

    models = client.list_models(fallback=False)
    if not models:
        print("Could not reach Crusoe, or the key was rejected.")
        return 1
    print(f"Models       {len(models)} available")

    try:
        started = time.time()
        reply = client.ask(
            [{"role": "user", "content": "Reply with exactly: ready"}],
            model=config.DEFAULT_MODEL,
            temperature=0,
        )
        elapsed = time.time() - started
    except Exception as exc:  # noqa: BLE001
        print(f"The test call failed: {type(exc).__name__}: {str(exc)[:160]}")
        return 1

    print(f"Test call    {config.DEFAULT_MODEL} answered in {elapsed:.1f}s")
    print(f"Reply        {reply.strip()[:40]!r}")
    print("\nYou are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
