"""
memory/ — Memory Systems

Short-term: In-memory conversation history (lost on restart)
Long-term: Database-backed memories in Supabase (persistent)
"""

# Short-term (in-memory)
from bot.memory.short_term import (
    get_conversation_history,
    add_to_history,
)

# Long-term (Supabase)
from bot.memory.long_term import (
    save_memory,
    get_memories,
    get_memories_for_context,
    delete_memory,
    cleanup_expired_memories,
)

__all__ = [
    # Short-term
    "get_conversation_history",
    "add_to_history",
    # Long-term
    "save_memory",
    "get_memories",
    "get_memories_for_context",
    "delete_memory",
    "cleanup_expired_memories",
]
