"""Saved conversations.

Each session is one JSON file in the sessions/ folder. Plain text, yours to
read, back up, or delete. Nothing is sent anywhere but Crusoe.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from . import config, memory


def _dir() -> Path:
    config.SESSIONS_DIR.mkdir(exist_ok=True)
    return config.SESSIONS_DIR


def new_session(model: str = config.DEFAULT_MODEL) -> dict:
    now = time.time()
    return {
        "id": uuid.uuid4().hex[:12],
        "title": "New chat",
        "model": model,
        "created": now,
        "updated": now,
        "messages": [],
        "documents": [],
    }


def _path(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", session_id)[:32]
    if not safe:
        raise ValueError("bad session id")
    return _dir() / f"{safe}.json"


def save(session: dict) -> None:
    """Write a session to disk. Empty chats are not worth saving."""
    if not session.get("messages"):
        return
    session["updated"] = time.time()
    if session.get("title") in (None, "", "New chat"):
        first = next((m["content"] for m in session["messages"] if m["role"] == "user"), "")
        session["title"] = memory.title_from(first)
    _path(session["id"]).write_text(
        json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load(session_id: str) -> dict | None:
    path = _path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def delete(session_id: str) -> bool:
    path = _path(session_id)
    if path.exists():
        path.unlink()
        return True
    return False


def list_all() -> list[dict]:
    """Every saved session, most recently used first."""
    out = []
    for path in _dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "id": data.get("id", path.stem),
                "title": data.get("title", "Untitled"),
                "updated": data.get("updated", 0),
                "turns": len(data.get("messages", [])),
            }
        )
    out.sort(key=lambda s: s["updated"], reverse=True)
    return out


def label(summary: dict) -> str:
    """How a session appears in the sidebar list."""
    when = time.strftime("%d %b %H:%M", time.localtime(summary.get("updated", 0)))
    return f"{summary['title']}  ·  {when}"
