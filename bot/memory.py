"""
memory.py — Short-Term Memory Store

In-memory conversation history shared across modules.
This allows both main.py (for chat) and scheduler.py (for daily prompts) 
to access recent conversations.

Note: This is lost on restart. Long-term memories are in Supabase.
"""

from bot.config import MAX_SHORT_TERM_MESSAGES

# Stores recent conversation history per server
# Format: { "server_id": [{"role": "user/assistant", "content": "...", "username": "..."}, ...] }
short_term_memory: dict[str, list[dict]] = {}


def get_conversation_history(server_id: str) -> list[dict]:
    """Get conversation history for a server."""
    return short_term_memory.get(server_id, [])


def add_to_history(server_id: str, role: str, content: str, username: str = None):
    """Add a message to conversation history."""
    if server_id not in short_term_memory:
        short_term_memory[server_id] = []
    
    short_term_memory[server_id].append({
        "role": role,
        "content": content,
        "username": username
    })
    
    # Trim to max size
    if len(short_term_memory[server_id]) > MAX_SHORT_TERM_MESSAGES:
        short_term_memory[server_id] = short_term_memory[server_id][-MAX_SHORT_TERM_MESSAGES:]


def get_recent_messages(server_id: str, limit: int = 6) -> list[dict]:
    """
    Get recent messages for context (e.g., for daily prompts).
    
    Returns messages in chronological order (oldest first).
    """
    history = short_term_memory.get(server_id, [])
    return history[-limit:] if history else []

