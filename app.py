"""A small chatbot on Crusoe.

    ./chat.sh        or        uv run python app.py

The interface lives here. Everything it actually does lives in crusoe_chat/,
one short module per idea. Open notebook.ipynb to see those used directly.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr  # noqa: E402

from crusoe_chat import client, config, documents, memory, sessions  # noqa: E402

# Crusoe palette. Ratios are against white, from the brand kit.
BLACK = "#000000"        # body text, 21:1
WHITE = "#FFFFFF"
YELLOW = "#CEEB13"       # accent only, always with black text, 15.52:1
TEAL = "#395761"         # secondary text, 7.75:1
CEMENT = "#E4E2E0"       # borders
INK_SOFT = "#4A4A4A"     # muted text, ~9:1

CSS = f"""
:root, .dark {{
    --body-background-fill: {WHITE} !important;
    --background-fill-primary: {WHITE} !important;
    --body-text-color: {BLACK} !important;
}}
html, body, .gradio-container, .gradio-container.dark, gradio-app {{
    background: {WHITE} !important;
    color: {BLACK} !important;
}}
.gradio-container {{
    font-family: 'Inter Tight', -apple-system, BlinkMacSystemFont, sans-serif;
    max-width: 1280px !important;
}}
#masthead {{ border-bottom: 3px solid {YELLOW}; padding: 2px 0 14px 0; margin-bottom: 18px; }}
#masthead .eyebrow {{
    display: inline-block; font-family: 'Roboto Mono', monospace;
    background: {YELLOW}; color: {BLACK}; font-size: 11px;
    letter-spacing: 2.2px; padding: 4px 10px; margin: 0 0 9px 0;
}}
#masthead h1 {{
    font-family: 'Roboto Mono', monospace; color: {BLACK};
    font-size: 24px; font-weight: 500; margin: 0 0 5px 0;
}}
#masthead p.sub {{ color: {TEAL}; font-size: 13.5px; margin: 0; }}
.hint {{ color: {INK_SOFT} !important; font-size: 12.5px; font-family: 'Roboto Mono', monospace; }}
#sidebar {{ border-right: 1px solid {CEMENT}; padding-right: 14px; }}
footer {{ display: none !important; }}
"""


def _light(**pairs) -> dict:
    """Pin a theme variable to the same value in light and dark mode."""
    out = {}
    for name, value in pairs.items():
        out[name] = value
        out[f"{name}_dark"] = value
    return out


THEME = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c50="#F8FCDB", c100="#F1F9B7", c200="#E9F68E", c300="#E0F262",
        c400="#D7EF3B", c500=YELLOW, c600="#A8C00F", c700="#7E900B",
        c800="#546008", c900="#2A3004", c950="#151802",
    ),
    neutral_hue=gr.themes.Color(
        c50="#FAFAFA", c100="#F4F4F3", c200=CEMENT, c300="#C9C7C5",
        c400="#A3A3A3", c500="#7A7A7A", c600="#5C5C5C", c700=INK_SOFT,
        c800="#2B2B2B", c900="#141414", c950=BLACK,
    ),
    font=[gr.themes.GoogleFont("Inter Tight"), "sans-serif"],
    font_mono=[gr.themes.GoogleFont("Roboto Mono"), "monospace"],
).set(
    **_light(
        body_background_fill=WHITE, background_fill_primary=WHITE,
        background_fill_secondary="#FAFAFA", block_background_fill=WHITE,
        block_border_color=CEMENT, block_label_background_fill=WHITE,
        block_label_text_color=TEAL, block_title_text_color=BLACK,
        body_text_color=BLACK, body_text_color_subdued=INK_SOFT,
        border_color_primary=CEMENT, border_color_accent=YELLOW,
        input_background_fill=WHITE, input_border_color=CEMENT,
        input_placeholder_color="#8A8A8A",
        button_primary_background_fill=YELLOW,
        button_primary_background_fill_hover="#BBD511",
        button_primary_text_color=BLACK, button_primary_border_color=YELLOW,
        button_secondary_background_fill=WHITE, button_secondary_text_color=BLACK,
        button_secondary_border_color=CEMENT, panel_background_fill=WHITE,
    )
)


# --------------------------------------------------------------------------
# Actions. Each one takes the current session, and returns the updated one.
# --------------------------------------------------------------------------


EMPTY_ENTRY = {"text": "", "files": []}


def session_choices() -> list[tuple[str, str]]:
    """The sidebar list: (what you see, the session id)."""
    return [(sessions.label(s), s["id"]) for s in sessions.list_all()]


def respond(user_text: str, files: list, session: dict, model: str, system_prompt: str):
    """Send a message and stream the answer back."""
    session = dict(session)
    session["model"] = model
    user_text = (user_text or "").strip()

    # Read anything newly dropped in.
    notes = []
    for path in files or []:
        name = Path(path).name
        if any(d["name"] == name for d in session["documents"]):
            continue
        try:
            session["documents"].append({"name": name, "text": documents.read(path)})
            notes.append(f"Attached **{name}**")
        except ValueError as exc:
            notes.append(f"Could not read **{name}**: {exc}")

    if not user_text and not notes:
        yield session, session["messages"], gr.update(), gr.update()
        return

    if not user_text:
        # Files only, no question yet. Acknowledge and wait.
        session["messages"] = session["messages"] + [
            {"role": "assistant", "content": "\n".join(notes) + "\n\nWhat would you like to know?"}
        ]
        sessions.save(session)
        yield (session, session["messages"], gr.update(choices=session_choices()),
               gr.update(value=EMPTY_ENTRY))
        return

    history = session["messages"]
    shown = history + [{"role": "user", "content": user_text}, {"role": "assistant", "content": ""}]
    yield session, shown, gr.update(), gr.update(value=EMPTY_ENTRY)

    payload = memory.build_messages(
        history=history,
        user_text=user_text,
        system_prompt=system_prompt or config.DEFAULT_SYSTEM_PROMPT,
        documents=documents.as_context(session["documents"]),
    )

    reply = ""
    try:
        for piece in client.stream(payload, model=model):
            reply += piece
            shown[-1]["content"] = reply
            yield session, shown, gr.update(), gr.update()
    except Exception as exc:  # noqa: BLE001
        reply = f"Something went wrong.\n\n`{type(exc).__name__}: {str(exc)[:300]}`"
        shown[-1]["content"] = reply

    if not reply.strip():
        reply = f"{model} returned nothing. Try another model."
        shown[-1]["content"] = reply

    prefix = ("\n".join(notes) + "\n\n") if notes else ""
    session["messages"] = history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": prefix + reply},
    ]
    sessions.save(session)
    yield (session, session["messages"], gr.update(choices=session_choices()),
           gr.update(value=EMPTY_ENTRY))


def start_new(model: str):
    fresh = sessions.new_session(model)
    return (fresh, [], gr.update(choices=session_choices(), value=None),
            gr.update(value=EMPTY_ENTRY), docs_label(fresh))


def open_session(session_id: str, current: dict):
    if not session_id:
        return current, current["messages"], docs_label(current), current["model"]
    loaded = sessions.load(session_id)
    if not loaded:
        return current, current["messages"], docs_label(current), current["model"]
    loaded.setdefault("documents", [])
    return loaded, loaded["messages"], docs_label(loaded), loaded.get("model", config.DEFAULT_MODEL)


def remove_session(session_id: str, current: dict, model: str):
    if session_id:
        sessions.delete(session_id)
    if session_id and session_id == current.get("id"):
        return start_new(model)
    return (current, current["messages"], gr.update(choices=session_choices(), value=None),
            gr.update(value=EMPTY_ENTRY), docs_label(current))


def docs_label(session: dict) -> str:
    docs = session.get("documents") or []
    if not docs:
        return "No documents attached. Drop a file into the box below to add one."
    names = ", ".join(d["name"] for d in docs)
    return f"**{len(docs)} attached:** {names}"


def clear_documents(session: dict):
    session = dict(session)
    session["documents"] = []
    sessions.save(session)
    return session, docs_label(session)


# --------------------------------------------------------------------------
# The interface
# --------------------------------------------------------------------------


def build_ui() -> gr.Blocks:
    models = client.list_models()
    default_model = config.DEFAULT_MODEL if config.DEFAULT_MODEL in models else models[0]

    with gr.Blocks(title="Crusoe Chat", analytics_enabled=False, fill_height=True) as demo:
        session = gr.State(sessions.new_session(default_model))

        gr.HTML(
            """<div id="masthead">
              <p class="eyebrow">CRUSOE</p>
              <h1>Chat</h1>
              <p class="sub">Open models, your API key, your laptop.
                 Nothing leaves this machine except your messages to Crusoe.</p>
            </div>"""
        )

        with gr.Row():
            # ---------------------------------------------------- sidebar
            with gr.Column(scale=1, min_width=230, elem_id="sidebar"):
                new_btn = gr.Button("New chat", variant="primary")
                model_picker = gr.Dropdown(
                    choices=models, value=default_model, label="Model",
                    info="Switch any time, mid-conversation.",
                )
                history_list = gr.Radio(
                    choices=session_choices(), value=None, label="Earlier chats",
                    info="Saved on this machine, in the sessions folder.",
                )
                delete_btn = gr.Button("Delete selected")
                with gr.Accordion("Instructions for the assistant", open=False):
                    system_prompt = gr.Textbox(
                        value=config.DEFAULT_SYSTEM_PROMPT, lines=6, show_label=False,
                        info="Change how it behaves. Applies to your next message.",
                    )

            # ------------------------------------------------------- chat
            with gr.Column(scale=4):
                chatbot = gr.Chatbot(height=520, show_label=False, resizable=True)
                docs_note = gr.Markdown(
                    "No documents attached. Drop a file into the box below to add one.",
                    elem_classes="hint",
                )
                entry = gr.MultimodalTextbox(
                    show_label=False, submit_btn=True, lines=2, max_lines=14,
                    placeholder="Ask anything. Drag a file in to ask about it.",
                    file_types=[f".{s.lstrip('.')}" for s in sorted(documents.SUPPORTED)],
                )
                clear_docs_btn = gr.Button("Remove attached documents", size="sm")

        # ------------------------------------------------------------ wiring
        def on_submit(payload, sess, model, prompt):
            yield from respond(
                (payload or {}).get("text", ""), (payload or {}).get("files", []),
                sess, model, prompt,
            )

        entry.submit(
            on_submit, [entry, session, model_picker, system_prompt],
            [session, chatbot, history_list, entry],
        ).then(lambda s: docs_label(s), session, docs_note)

        new_btn.click(
            start_new, model_picker,
            [session, chatbot, history_list, entry, docs_note],
        )
        history_list.change(
            open_session, [history_list, session],
            [session, chatbot, docs_note, model_picker],
        )
        delete_btn.click(
            remove_session, [history_list, session, model_picker],
            [session, chatbot, history_list, entry, docs_note],
        )
        clear_docs_btn.click(clear_documents, session, [session, docs_note])

    return demo


def main() -> None:
    config.ensure_api_key()  # asks here in the terminal if nothing is saved yet
    print("\n  Crusoe Chat is starting. Your browser will open in a moment.")
    print("  Press Control-C in this window to stop it.\n")
    build_ui().launch(theme=THEME, css=CSS, inbrowser=True)


if __name__ == "__main__":
    main()
