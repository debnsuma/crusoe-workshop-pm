"""Memory, demystified.

The API is stateless. It does not remember your last message. "Memory" is
nothing more than sending the earlier turns back with every new question.

That is the whole trick, and it is why a long chat costs more than a short
one: you are re-sending the conversation each time. `fit_to_budget` keeps
that from growing without limit.
"""

from __future__ import annotations

from . import config

# Roughly four characters per token, so this is about 24k tokens of history.
DEFAULT_BUDGET_CHARS = 96_000


def build_messages(
    history: list[dict],
    user_text: str,
    system_prompt: str = config.DEFAULT_SYSTEM_PROMPT,
    documents: str = "",
    budget_chars: int = DEFAULT_BUDGET_CHARS,
) -> list[dict]:
    """Assemble exactly what gets posted to the API.

    Order matters: the system prompt sets behaviour, any attached documents
    come next as context, then the conversation so far, then the new question.
    """
    system = system_prompt
    if documents.strip():
        system = (
            f"{system_prompt}\n\n"
            "The user has attached the following document(s). Use them when "
            "they are relevant, and say so when the answer is not in them.\n\n"
            f"{documents.strip()}"
        )

    messages = [{"role": "system", "content": system}]
    messages += fit_to_budget(clean_history(history), budget_chars)
    messages.append({"role": "user", "content": user_text.strip()})
    return messages


def clean_history(history: list[dict]) -> list[dict]:
    """Keep only well-formed user and assistant turns."""
    out = []
    for turn in history or []:
        role, content = turn.get("role"), turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content})
    return out


def fit_to_budget(history: list[dict], budget_chars: int = DEFAULT_BUDGET_CHARS) -> list[dict]:
    """Drop the oldest turns until the history fits.

    Recent turns matter most, so we trim from the front. The system prompt and
    the new question are added separately and are never dropped.
    """
    if budget_chars <= 0:
        return []
    kept: list[dict] = []
    total = 0
    for turn in reversed(history):
        size = len(turn["content"])
        if total + size > budget_chars:
            break
        kept.append(turn)
        total += size
    kept.reverse()
    return kept


def title_from(text: str, limit: int = 48) -> str:
    """A short name for a session, taken from its first message."""
    words = " ".join((text or "").split())
    if not words:
        return "New chat"
    return words if len(words) <= limit else words[: limit - 3].rstrip() + "..."
