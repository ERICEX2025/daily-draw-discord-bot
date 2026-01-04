"""
memory/long_term.py — Long-Term Memory (Supabase)

Persistent memories that survive restarts.
"""

from typing import Optional
from datetime import datetime, timedelta

from bot.services.db import supabase
from bot.config import (
    MEMORIES_FOR_CONTEXT,
    MEMORIES_USER_SPECIFIC,
)

# Memory categories and their default expiry (days, None = never)
MEMORY_EXPIRY = {
    "user_fact": None,
    "preference": None,
    "event": None,
    "conversation": 30,
    "general": 60,
}

# Default importance by category (1-5)
MEMORY_IMPORTANCE = {
    "user_fact": 4,
    "preference": 4,
    "event": 5,
    "conversation": 2,
    "general": 3,
}


async def save_memory(
    server_id: str,
    memory: str,
    user_id: Optional[str] = None,
    category: str = "general",
    importance: Optional[int] = None
) -> int:
    """Save a long-term memory."""
    if importance is None:
        importance = MEMORY_IMPORTANCE.get(category, 3)
    
    expiry_days = MEMORY_EXPIRY.get(category)
    expires_at = None
    if expiry_days:
        expires_at = (datetime.now() + timedelta(days=expiry_days)).isoformat()
    
    result = supabase.table("memories").insert({
        "server_id": server_id,
        "user_id": user_id,
        "memory": memory,
        "category": category,
        "importance": importance,
        "expires_at": expires_at
    }).execute()
    return result.data[0]["id"] if result.data else 0


async def get_memories(
    server_id: str,
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = None,
    include_expired: bool = False
) -> list[dict]:
    """Get memories for a server. Limit is required."""
    if limit is None:
        raise ValueError("limit is required for get_memories()")
    
    query = supabase.table("memories") \
        .select("id, memory, user_id, category, importance, created_at, expires_at") \
        .eq("server_id", server_id) \
        .order("importance", desc=True) \
        .order("created_at", desc=True) \
        .limit(limit)
    
    if user_id:
        query = query.eq("user_id", user_id)
    
    if category:
        query = query.eq("category", category)
    
    if not include_expired:
        now = datetime.now().isoformat()
        query = query.or_(f"expires_at.is.null,expires_at.gt.{now}")
    
    return query.execute().data or []


async def get_memories_for_context(
    server_id: str,
    current_user: Optional[str] = None,
    limit: int = MEMORIES_FOR_CONTEXT
) -> list[dict]:
    """Get the most relevant memories for conversation context."""
    important = await get_memories(server_id, limit=limit)
    
    user_memories = []
    if current_user:
        user_memories = await get_memories(server_id, user_id=current_user, limit=MEMORIES_USER_SPECIFIC)
    
    seen_ids = set()
    result = []
    
    for m in user_memories + important:
        if m["id"] not in seen_ids:
            seen_ids.add(m["id"])
            result.append(m)
            if len(result) >= limit:
                break
    
    return result


async def delete_memory(memory_id: int) -> bool:
    """Delete a specific memory by ID."""
    result = supabase.table("memories").delete().eq("id", memory_id).execute()
    return len(result.data) > 0 if result.data else False


async def cleanup_expired_memories(server_id: Optional[str] = None) -> int:
    """Delete all expired memories."""
    now = datetime.now().isoformat()
    
    query = supabase.table("memories") \
        .delete() \
        .lt("expires_at", now) \
        .not_.is_("expires_at", "null")
    
    if server_id:
        query = query.eq("server_id", server_id)
    
    result = query.execute()
    return len(result.data) if result.data else 0

