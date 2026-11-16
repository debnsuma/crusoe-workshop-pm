"""Reading dropped files.

A model only reads text, so every attachment is turned into text and pasted
into the system message. That is all "chat with your documents" means at this
size: no database, no embeddings, no retrieval step.

It works well up to roughly a long report. Past that, trim or split the file.
"""

from __future__ import annotations

from pathlib import Path

# Anything that is already text.
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".sh", ".sql", ".html", ".xml", ".log", ".rst", ".ini", ".toml",
}

# Handled by a reader below.
BINARY_SUFFIXES = {".pdf", ".docx"}

SUPPORTED = TEXT_SUFFIXES | BINARY_SUFFIXES

# Keep one file from eating the whole context window.
MAX_CHARS_PER_FILE = 40_000


def read(path: str | Path) -> str:
    """Return the text of one file, or raise ValueError explaining why not."""
    path = Path(path)
    if not path.exists():
        raise ValueError(f"{path.name}: file not found")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _read_pdf(path)
    elif suffix == ".docx":
        text = _read_docx(path)
    elif suffix in TEXT_SUFFIXES or suffix == "":
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(
            f"{path.name}: {suffix or 'this file type'} is not supported. "
            f"Try {', '.join(sorted(SUPPORTED))}"
        )

    if not text.strip():
        raise ValueError(f"{path.name}: no readable text found")
    return _truncate(text, path.name)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ValueError("PDF support needs pypdf. Run ./setup.sh again.") from exc
    try:
        pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{path.name}: could not read this PDF ({exc})") from exc
    text = "\n\n".join(pages)
    if not text.strip():
        raise ValueError(f"{path.name}: this PDF has no selectable text, it may be a scan")
    return text


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Word support needs python-docx. Run ./setup.sh again.") from exc
    try:
        return "\n".join(p.text for p in Document(str(path)).paragraphs)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{path.name}: could not read this Word file ({exc})") from exc


def _truncate(text: str, name: str) -> str:
    if len(text) <= MAX_CHARS_PER_FILE:
        return text
    return (
        text[:MAX_CHARS_PER_FILE]
        + f"\n\n[{name} was longer than {MAX_CHARS_PER_FILE:,} characters and was cut off here]"
    )


def as_context(documents: list[dict]) -> str:
    """Turn the attached files into one block for the system message."""
    parts = []
    for doc in documents:
        parts.append(f"--- Document: {doc['name']} ---\n{doc['text']}")
    return "\n\n".join(parts)
