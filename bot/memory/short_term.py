"""
memory/short_term.py — Short-Term Memory

In-memory conversation history per server.
Lost on restart. For persistent memories, see db.py.
"""

from bot.config import MAX_SHORT_TERM_MESSAGES

# Stores recent conversation history per server (lost on restart)
_short_term_memory: dict[str, list[dict]] = {}


def get_conversation_history(server_id: str, limit: int = None) -> list[dict]:
    """Get conversation history for a server, optionally limited to last N messages."""
    history = _short_term_memory.get(server_id, [])
    if limit:
        return history[-limit:]
    return history


def add_to_history(
    server_id: str,
    role: str,
    content: str,
    username: str = None,
    images: list[str] = None
):
    """Add a message to conversation history."""
    if server_id not in _short_term_memory:
        _short_term_memory[server_id] = []
    
    msg = {
        "role": role,
        "content": content,
        "username": username
    }
    if images:
        msg["images"] = images
    
    _short_term_memory[server_id].append(msg)
    
    # Trim to max size
    if len(_short_term_memory[server_id]) > MAX_SHORT_TERM_MESSAGES:
        _short_term_memory[server_id] = _short_term_memory[server_id][-MAX_SHORT_TERM_MESSAGES:]

