"""A small chatbot on Crusoe.

    config     your API key, the base URL, the default model
    client     three thin wrappers over the OpenAI client
    memory     how a conversation is assembled and kept to a size
    sessions   saved conversations, one JSON file each
    documents  turning a dropped file into text

Start with notebook.ipynb to see each of these used directly.
"""

from . import client, config, documents, memory, sessions

__all__ = ["client", "config", "documents", "memory", "sessions"]
