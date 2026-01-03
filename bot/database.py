"""
database.py — Supabase Database Layer (MVP)

Tables:
1. settings - Per-server configuration
2. prompts  - Daily drawing prompts
"""

import os
from datetime import date, datetime
from typing import Optional
import pytz
from supabase import create_client, Client
from dotenv import load_dotenv

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
        .select("prompt_text, created_at") \
        .eq("server_id", server_id) \
        .gte("created_at", today) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    
    return result.data[0] if result.data else None
