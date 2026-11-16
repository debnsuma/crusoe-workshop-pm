"""Talking to Crusoe.

Three functions, and every one of them is a thin wrapper over the standard
OpenAI client. There is no Crusoe SDK to learn.
"""

from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from . import config

# Reasoning models spend tokens thinking before they answer, so leave headroom.
MAX_OUTPUT_TOKENS = 8000


def client() -> OpenAI:
    """The standard OpenAI client, pointed at Crusoe."""
    return OpenAI(api_key=config.ensure_api_key(), base_url=config.BASE_URL, timeout=120.0)


def list_models(fallback: bool = True) -> list[str]:
    """Every model you can call right now, newest list straight from the API."""
    try:
        names = sorted(m.id for m in client().models.list().data)
        return names or ([config.DEFAULT_MODEL] if fallback else [])
    except Exception:  # noqa: BLE001
        return [config.DEFAULT_MODEL] if fallback else []


def ask(messages: list[dict], model: str = config.DEFAULT_MODEL, temperature: float = 0.3) -> str:
    """Send messages, get the whole answer back at once."""
    response = client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    return response.choices[0].message.content or ""


def stream(
    messages: list[dict], model: str = config.DEFAULT_MODEL, temperature: float = 0.3
) -> Iterator[str]:
    """Send messages, get the answer back a piece at a time."""
    chunks = client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=MAX_OUTPUT_TOKENS,
        stream=True,
    )
    for chunk in chunks:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
