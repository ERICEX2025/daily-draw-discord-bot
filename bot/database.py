"""
database.py — Supabase Database Layer

Tables:
1. settings - Per-server configuration
2. prompts  - Daily drawing prompts
3. memories - Long-term memories (things Mai decides to remember)
"""

import os
from datetime import date, datetime, timedelta
from typing import Optional
import pytz
from supabase import create_client, Client
from dotenv import load_dotenv

from bot.config import (
    MEMORIES_DEFAULT_LIMIT,
    MEMORIES_FOR_CONTEXT,
    MEMORIES_USER_SPECIFIC,
)

load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


async def init_db():
    """No-op for Supabase — tables created via SQL."""
    pass


# =============================================================================
# SETTINGS
# =============================================================================

async def get_settings(server_id: str) -> dict:
    """Get settings for a server, creating defaults if needed."""
    result = supabase.table("settings").select("*").eq("server_id", server_id).execute()
    
    if result.data:
        return result.data[0]
    
    defaults = {
        "server_id": server_id,
        "channel_id": None,
        "post_time": "09:00",
        "timezone": "America/New_York",
        "paused_until": None,  # ISO datetime string when paused
        "theme": "anime and video game inspired"
    }
    supabase.table("settings").insert(defaults).execute()
    return defaults


async def update_settings(server_id: str, **kwargs) -> None:
    """Update settings for a server."""
    await get_settings(server_id)
    
    valid_fields = ["channel_id", "post_time", "timezone", "paused_until", "theme"]
    updates = {k: v for k, v in kwargs.items() if k in valid_fields}
    
    if updates:
        supabase.table("settings").update(updates).eq("server_id", server_id).execute()


async def get_all_servers_for_posting() -> list[dict]:
    """Get all servers with a configured channel."""
    result = supabase.table("settings").select("*").not_.is_("channel_id", "null").execute()
    return result.data or []


# =============================================================================
# PROMPTS
# =============================================================================

async def save_prompt(server_id: str, prompt_text: str) -> int:
    """Save a new prompt."""
    result = supabase.table("prompts").insert({
        "server_id": server_id,
        "prompt_text": prompt_text
    }).execute()
    return result.data[0]["id"] if result.data else 0


async def get_prompt_history(server_id: str, limit: Optional[int] = None) -> list[dict]:
    """Get prompts for a server, most recent first."""
    query = supabase.table("prompts") \
        .select("prompt_text, created_at") \
        .eq("server_id", server_id) \
        .order("created_at", desc=True)
    
    if limit:
        query = query.limit(limit)
    
    return query.execute().data or []


async def get_todays_prompt(server_id: str, timezone: str = "America/New_York") -> Optional[dict]:
    """
    Get today's prompt if one exists.
    
    Uses the server's configured timezone to determine what "today" means.
    This prevents duplicate posts when the bot runs in a different timezone.
    """
    # Get "today" in the server's timezone
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("America/New_York")
    
    today = datetime.now(tz).date().isoformat()
    
    result = supabase.table("prompts") \
        .select("id, prompt_text, created_at") \
        .eq("server_id", server_id) \
        .gte("created_at", today) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    
    return result.data[0] if result.data else None


async def delete_todays_prompt(server_id: str, timezone: str = "America/New_York") -> bool:
    """
    Delete today's prompt to allow a reroll.
    
    Returns True if a prompt was deleted, False if there was nothing to delete.
    """
    prompt = await get_todays_prompt(server_id, timezone)
    if not prompt:
        return False
    
    supabase.table("prompts").delete().eq("id", prompt["id"]).execute()
    return True


# =============================================================================
# MEMORIES (Long-term)
# =============================================================================

# Memory categories and their default expiry (days, None = never)
MEMORY_EXPIRY = {
    "user_fact": None,       # "Alice loves dragons" - never expires
    "preference": None,      # "Eric prefers 9am" - never expires
    "event": None,           # "Hit 100 prompts" - never expires
    "conversation": 30,      # Daily summaries - 30 days
    "general": 60,           # Misc observations - 60 days
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
    """
    Save a long-term memory with category and importance.
    
    Args:
        server_id: The Discord server
        memory: What to remember
        user_id: Optional - who this memory is about
        category: user_fact, preference, event, conversation, general
        importance: 1-5, higher = more important (defaults based on category)
    """
    # Set defaults based on category
    if importance is None:
        importance = MEMORY_IMPORTANCE.get(category, 3)
    
    # Calculate expiry date if applicable
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
    limit: int = MEMORIES_DEFAULT_LIMIT,
    include_expired: bool = False
) -> list[dict]:
    """
    Get memories for a server, with smart prioritization.
    
    Returns memories ordered by importance (desc), then recency.
    Excludes expired memories by default.
    """
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
        # Filter out expired memories (expires_at is null OR in the future)
        now = datetime.now().isoformat()
        query = query.or_(f"expires_at.is.null,expires_at.gt.{now}")
    
    return query.execute().data or []


async def get_memories_for_context(
    server_id: str,
    current_user: Optional[str] = None,
    limit: int = MEMORIES_FOR_CONTEXT
) -> list[dict]:
    """
    Get the most relevant memories for conversation context.
    
    Prioritizes:
    1. High importance memories
    2. Memories about the current user (if provided)
    3. Recent memories
    """
    # Get high-importance memories
    important = await get_memories(server_id, limit=limit)
    
    # If we have a current user, also fetch their specific memories
    user_memories = []
    if current_user:
        user_memories = await get_memories(server_id, user_id=current_user, limit=MEMORIES_USER_SPECIFIC)
    
    # Combine and dedupe (user memories first, then important)
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
    """
    Delete all expired memories.
    
    Args:
        server_id: Optional - only cleanup for this server
        
    Returns:
        Number of memories deleted
    """
    now = datetime.now().isoformat()
    
    query = supabase.table("memories") \
        .delete() \
        .lt("expires_at", now) \
        .not_.is_("expires_at", "null")
    
    if server_id:
        query = query.eq("server_id", server_id)
    
    result = query.execute()
    return len(result.data) if result.data else 0
