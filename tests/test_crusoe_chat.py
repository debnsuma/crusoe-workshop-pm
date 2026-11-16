"""Tests for the chatbot's moving parts.

Everything here runs offline except the one test marked 'live'.

    uv run pytest
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crusoe_chat import config, documents, memory, sessions  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the session store at a throwaway folder."""
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")
    return tmp_path


# ------------------------------------------------------------------- memory


def test_build_messages_has_system_history_then_question():
    history = [{"role": "user", "content": "first"}, {"role": "assistant", "content": "answer"}]
    out = memory.build_messages(history, "second")
    assert [m["role"] for m in out] == ["system", "user", "assistant", "user"]
    assert out[0]["content"] == config.DEFAULT_SYSTEM_PROMPT
    assert out[-1]["content"] == "second"


def test_build_messages_strips_whitespace_from_the_question():
    assert memory.build_messages([], "  hello  ")[-1]["content"] == "hello"


def test_documents_go_into_the_system_message():
    out = memory.build_messages([], "q", documents="CONTRACT TEXT")
    assert "CONTRACT TEXT" in out[0]["content"]
    assert config.DEFAULT_SYSTEM_PROMPT in out[0]["content"]
    # and nowhere else
    assert all("CONTRACT TEXT" not in m["content"] for m in out[1:])


def test_a_custom_system_prompt_is_used():
    out = memory.build_messages([], "q", system_prompt="Talk like a pirate.")
    assert out[0]["content"] == "Talk like a pirate."


def test_clean_history_drops_junk():
    messy = [
        {"role": "user", "content": "keep"},
        {"role": "system", "content": "drop, system is set separately"},
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "   "},
        {"role": "user", "content": None},
        {"nonsense": True},
        {"role": "assistant", "content": "keep too"},
    ]
    assert [m["content"] for m in memory.clean_history(messy)] == ["keep", "keep too"]


def test_clean_history_handles_none():
    assert memory.clean_history(None) == []


def test_fit_to_budget_keeps_the_most_recent():
    history = [{"role": "user", "content": f"{i}" * 100} for i in range(10)]
    kept = memory.fit_to_budget(history, budget_chars=250)
    assert len(kept) == 2
    assert kept[-1]["content"].startswith("9")      # newest survives
    assert kept[0]["content"].startswith("8")       # order preserved


def test_fit_to_budget_keeps_everything_when_it_fits():
    history = [{"role": "user", "content": "short"}]
    assert memory.fit_to_budget(history, budget_chars=10_000) == history


def test_fit_to_budget_of_zero_keeps_nothing():
    assert memory.fit_to_budget([{"role": "user", "content": "x"}], budget_chars=0) == []


def test_long_history_is_trimmed_inside_build_messages():
    history = [{"role": "user", "content": "y" * 1000} for _ in range(50)]
    out = memory.build_messages(history, "now", budget_chars=3000)
    assert len(out) < 10
    assert out[-1]["content"] == "now"


@pytest.mark.parametrize(
    "text,expected",
    [("", "New chat"), ("   ", "New chat"), ("Short one", "Short one"),
     ("a  b\n\nc", "a b c")],
)
def test_title_from(text, expected):
    assert memory.title_from(text) == expected


def test_title_from_truncates_politely():
    title = memory.title_from("w" * 200)
    assert len(title) <= 48 and title.endswith("...")


# ----------------------------------------------------------------- sessions


def test_new_session_starts_empty():
    s = sessions.new_session("some-model")
    assert s["messages"] == [] and s["documents"] == []
    assert s["model"] == "some-model" and len(s["id"]) == 12


def test_save_and_load_round_trip(store):
    s = sessions.new_session()
    s["messages"] = [{"role": "user", "content": "remember this"},
                     {"role": "assistant", "content": "done"}]
    sessions.save(s)
    back = sessions.load(s["id"])
    assert back["messages"] == s["messages"]


def test_empty_sessions_are_not_saved(store):
    s = sessions.new_session()
    sessions.save(s)
    assert sessions.list_all() == []
    assert sessions.load(s["id"]) is None


def test_title_comes_from_the_first_user_message(store):
    s = sessions.new_session()
    s["messages"] = [{"role": "assistant", "content": "hello there"},
                     {"role": "user", "content": "How do I reset my password?"}]
    sessions.save(s)
    assert sessions.load(s["id"])["title"] == "How do I reset my password?"


def test_an_existing_title_is_kept(store):
    s = sessions.new_session()
    s["title"] = "My own name"
    s["messages"] = [{"role": "user", "content": "anything"}]
    sessions.save(s)
    assert sessions.load(s["id"])["title"] == "My own name"


def test_list_is_newest_first(store):
    import time

    for i in range(3):
        s = sessions.new_session()
        s["messages"] = [{"role": "user", "content": f"chat {i}"}]
        sessions.save(s)
        time.sleep(0.01)
    listed = sessions.list_all()
    assert [x["title"] for x in listed] == ["chat 2", "chat 1", "chat 0"]
    assert listed[0]["turns"] == 1


def test_delete_removes_it(store):
    s = sessions.new_session()
    s["messages"] = [{"role": "user", "content": "bye"}]
    sessions.save(s)
    assert sessions.delete(s["id"]) is True
    assert sessions.load(s["id"]) is None
    assert sessions.delete(s["id"]) is False


def test_load_of_an_unknown_id_is_none(store):
    assert sessions.load("doesnotexist") is None


def test_a_corrupt_session_file_is_skipped(store):
    good = sessions.new_session()
    good["messages"] = [{"role": "user", "content": "fine"}]
    sessions.save(good)
    (config.SESSIONS_DIR / "broken.json").write_text("{not json", encoding="utf-8")
    assert [s["title"] for s in sessions.list_all()] == ["fine"]
    assert sessions.load("broken") is None


def test_session_ids_cannot_escape_the_folder(store):
    """A crafted id must never touch a path outside sessions/."""
    crafted = sessions._path("../../etc/passwd")
    assert crafted.parent == config.SESSIONS_DIR
    assert ".." not in str(crafted) and "/etc/" not in str(crafted)
    assert sessions.load("../../etc/passwd") is None
    with pytest.raises(ValueError):
        sessions._path("../..")           # nothing left after sanitising


def test_label_shows_title_and_time(store):
    s = sessions.new_session()
    s["messages"] = [{"role": "user", "content": "hello world"}]
    sessions.save(s)
    assert "hello world" in sessions.label(sessions.list_all()[0])


# ---------------------------------------------------------------- documents


def test_reads_a_text_file(tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("# Title\n\nSome content.", encoding="utf-8")
    assert "Some content." in documents.read(f)


@pytest.mark.parametrize("suffix", [".txt", ".csv", ".json", ".py", ".log", ".yaml"])
def test_common_text_types_are_supported(tmp_path, suffix):
    f = tmp_path / f"file{suffix}"
    f.write_text("hello", encoding="utf-8")
    assert documents.read(f) == "hello"


def test_unsupported_type_explains_itself(tmp_path):
    f = tmp_path / "picture.heic"
    f.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError, match="not supported"):
        documents.read(f)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        documents.read(tmp_path / "nope.txt")


def test_empty_file_is_reported(tmp_path):
    f = tmp_path / "blank.txt"
    f.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="no readable text"):
        documents.read(f)


def test_a_huge_file_is_cut_off(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("z" * (documents.MAX_CHARS_PER_FILE + 5000), encoding="utf-8")
    out = documents.read(f)
    assert len(out) < documents.MAX_CHARS_PER_FILE + 200
    assert "cut off here" in out


def test_undecodable_bytes_do_not_crash(tmp_path):
    f = tmp_path / "weird.txt"
    f.write_bytes(b"ok \xff\xfe bytes")
    assert "ok" in documents.read(f)


def test_as_context_labels_each_document():
    block = documents.as_context(
        [{"name": "a.txt", "text": "AAA"}, {"name": "b.md", "text": "BBB"}]
    )
    assert "Document: a.txt" in block and "AAA" in block
    assert "Document: b.md" in block and "BBB" in block


def test_as_context_of_nothing_is_empty():
    assert documents.as_context([]) == ""


# ---------------------------------------------------------------------- key


def test_save_and_read_the_key(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setenv("CRUSOE_API_KEY", "placeholder")   # restored on teardown
    monkeypatch.delenv("CRUSOE_API_KEY")
    config.save_api_key("sk-abc-123")
    assert "CRUSOE_API_KEY=sk-abc-123" in env.read_text()
    assert config.ensure_api_key(prompt=False) == "sk-abc-123"


def test_saving_the_key_keeps_other_settings(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CRUSOE_API_KEY=old\nOTHER=keep\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setenv("CRUSOE_API_KEY", "placeholder")
    config.save_api_key("new")
    text = env.read_text()
    assert "CRUSOE_API_KEY=new" in text and "OTHER=keep" in text and "old" not in text


def test_a_missing_key_explains_where_to_get_one(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "none.env")
    monkeypatch.setenv("CRUSOE_API_KEY", "placeholder")
    monkeypatch.delenv("CRUSOE_API_KEY")
    with pytest.raises(RuntimeError, match="console.crusoecloud.com"):
        config.ensure_api_key(prompt=False)


# ------------------------------------------------------------------ the app


def test_docs_label_reflects_attachments():
    import app

    assert "No documents" in app.docs_label({"documents": []})
    label = app.docs_label({"documents": [{"name": "a.pdf", "text": "x"}]})
    assert "1 attached" in label and "a.pdf" in label


def test_clear_documents_empties_and_keeps_messages(store):
    import app

    session = sessions.new_session()
    session["messages"] = [{"role": "user", "content": "hi"}]
    session["documents"] = [{"name": "a.txt", "text": "x"}]
    updated, label = app.clear_documents(session)
    assert updated["documents"] == []
    assert updated["messages"] == session["messages"]
    assert "No documents" in label


def test_start_new_gives_an_empty_session(store):
    import app

    session, history, _choices, entry, label = app.start_new("some-model")
    assert session["messages"] == [] and history == []
    assert session["model"] == "some-model"
    assert "No documents" in label
    cleared = entry.get("value") if isinstance(entry, dict) else getattr(entry, "value", None)
    assert cleared == app.EMPTY_ENTRY


def test_respond_streams_and_saves(store, monkeypatch):
    import app
    from crusoe_chat import client

    monkeypatch.setattr(client, "stream", lambda *a, **k: iter(["Hel", "lo"]))
    session = sessions.new_session()
    frames = list(app.respond("hi there", [], session, "m", config.DEFAULT_SYSTEM_PROMPT))

    final_session, final_history = frames[-1][0], frames[-1][1]
    assert [m["content"] for m in final_history] == ["hi there", "Hello"]
    assert sessions.load(final_session["id"])["messages"] == final_history


def test_respond_sends_the_earlier_turns(store, monkeypatch):
    """The whole point of memory: history must reach the API."""
    import app
    from crusoe_chat import client

    seen = {}

    def fake_stream(messages, model=None, **kw):
        seen["messages"] = messages
        return iter(["ok"])

    monkeypatch.setattr(client, "stream", fake_stream)
    session = sessions.new_session()
    session["messages"] = [{"role": "user", "content": "earlier"},
                           {"role": "assistant", "content": "reply"}]
    list(app.respond("now", [], session, "m", config.DEFAULT_SYSTEM_PROMPT))

    assert [m["content"] for m in seen["messages"]] == [
        config.DEFAULT_SYSTEM_PROMPT, "earlier", "reply", "now",
    ]


def test_respond_reports_an_api_failure(store, monkeypatch):
    import app
    from crusoe_chat import client

    def boom(*a, **k):
        raise RuntimeError("endpoint down")

    monkeypatch.setattr(client, "stream", boom)
    frames = list(app.respond("hi", [], sessions.new_session(), "m", "sys"))
    assert "Something went wrong" in frames[-1][1][-1]["content"]


def test_respond_handles_an_empty_reply(store, monkeypatch):
    import app
    from crusoe_chat import client

    monkeypatch.setattr(client, "stream", lambda *a, **k: iter([""]))
    frames = list(app.respond("hi", [], sessions.new_session(), "quiet", "sys"))
    assert "returned nothing" in frames[-1][1][-1]["content"]


def test_respond_ignores_an_empty_message(store):
    import app

    session = sessions.new_session()
    frames = list(app.respond("   ", [], session, "m", "sys"))
    assert frames[-1][1] == []


def test_dropping_a_file_attaches_it(store, tmp_path, monkeypatch):
    import app
    from crusoe_chat import client

    doc = tmp_path / "spec.md"
    doc.write_text("The widget must be blue.", encoding="utf-8")
    captured = {}

    def fake_stream(messages, model=None, **kw):
        captured["system"] = messages[0]["content"]
        return iter(["noted"])

    monkeypatch.setattr(client, "stream", fake_stream)
    session = sessions.new_session()
    frames = list(app.respond("what colour?", [str(doc)], session, "m", "sys"))

    assert "The widget must be blue." in captured["system"]
    assert frames[-1][0]["documents"][0]["name"] == "spec.md"


def test_an_unreadable_file_does_not_stop_the_chat(store, tmp_path, monkeypatch):
    import app
    from crusoe_chat import client

    bad = tmp_path / "image.heic"
    bad.write_bytes(b"\x00")
    monkeypatch.setattr(client, "stream", lambda *a, **k: iter(["fine"]))
    frames = list(app.respond("hello", [str(bad)], sessions.new_session(), "m", "sys"))
    reply = frames[-1][1][-1]["content"]
    assert "Could not read" in reply and "fine" in reply


def test_the_same_file_is_not_attached_twice(store, tmp_path, monkeypatch):
    import app
    from crusoe_chat import client

    doc = tmp_path / "a.txt"
    doc.write_text("content", encoding="utf-8")
    monkeypatch.setattr(client, "stream", lambda *a, **k: iter(["ok"]))
    session = sessions.new_session()
    session = list(app.respond("one", [str(doc)], session, "m", "sys"))[-1][0]
    session = list(app.respond("two", [str(doc)], session, "m", "sys"))[-1][0]
    assert len(session["documents"]) == 1


# ------------------------------------------------------------------ live API

live = pytest.mark.skipif(
    not os.environ.get("CRUSOE_API_KEY") and not (ROOT / ".env").exists(),
    reason="no CRUSOE_API_KEY, skipping the live call",
)


@live
@pytest.mark.live
def test_the_api_actually_remembers_when_given_history():
    from crusoe_chat import client

    answer = client.ask(
        [
            {"role": "user", "content": "My favourite colour is teal."},
            {"role": "assistant", "content": "Teal it is."},
            {"role": "user", "content": "What is my favourite colour? Answer in one word."},
        ],
        temperature=0,
    )
    assert "teal" in answer.lower()


# ------------------------------------------------- pdf and word attachments


def _make_pdf(path: Path, text: str) -> None:
    """A minimal one-page PDF, so the test needs no fixture file."""
    content = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    buf, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(buf)
    buf += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(buf))


def test_reads_a_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    _make_pdf(pdf, "Total headcount is 412 people")
    assert "412" in documents.read(pdf)


def test_a_pdf_with_no_text_says_it_may_be_a_scan(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _make_pdf(pdf, "")
    with pytest.raises(ValueError, match="scan"):
        documents.read(pdf)


def test_reads_a_word_document(tmp_path):
    from docx import Document as Docx

    doc = Docx()
    doc.add_heading("Quarterly Notes")
    doc.add_paragraph("Revenue grew by 23 percent.")
    path = tmp_path / "notes.docx"
    doc.save(str(path))
    assert "23 percent" in documents.read(path)
