"""
database.py — SQLite Database Layer

This file handles all persistent storage using SQLite.
SQLite is a file-based database that requires no server setup.

Tables:
1. prompts     - All generated drawing prompts
2. settings    - Per-server configuration (post time, theme, channel)
3. conversations - Chat history for GPT context

Why SQLite?
- Zero setup (just works)
- Data stored in a single file (mai_san.db)
- Fast enough for small-medium bots
- Easy to backup (just copy the file)

Note: All functions are async using aiosqlite for non-blocking operations.
This is important because Discord.py is async.
"""

import aiosqlite
from datetime import datetime
from typing import Optional
import os

# Path to the database file (in the same directory as this script)
DB_PATH = os.path.join(os.path.dirname(__file__), "mai_san.db")


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

async def init_db():
    """
    Initialize the database by creating tables if they don't exist.
    
    This is called once when the bot starts (in main.py's on_ready event).
    It's safe to call multiple times - tables are only created if missing.
    
    Tables created:
    - prompts: Stores all generated drawing prompts
    - settings: Per-server configuration
    - conversations: Chat history for GPT context
    """
    async with aiosqlite.connect(DB_PATH) as db:
        
        # ----- PROMPTS TABLE -----
        # Stores every drawing prompt that has been generated
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,       -- Discord server ID
                prompt_text TEXT NOT NULL,     -- The actual prompt
                theme TEXT,                    -- Optional theme (e.g., "fantasy")
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ----- SETTINGS TABLE -----
        # One row per Discord server with their configuration
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                server_id TEXT PRIMARY KEY,    -- Discord server ID (unique)
                channel_id TEXT,               -- Channel ID for daily prompts
                post_time TEXT DEFAULT '09:00', -- When to post (HH:MM format)
                timezone TEXT DEFAULT 'America/New_York',
                current_theme TEXT,            -- Active theme (or NULL)
                theme_days_remaining INTEGER DEFAULT 0  -- Days left for theme
            )
        """)
        
        # ----- CONVERSATIONS TABLE -----
        # Stores chat messages for GPT context
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,       -- Discord server ID
                user_id TEXT NOT NULL,         -- Discord user ID
                role TEXT NOT NULL,            -- "user" or "assistant"
                content TEXT NOT NULL,         -- The message content
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Save changes
        await db.commit()


# =============================================================================
# PROMPT FUNCTIONS
# =============================================================================

async def save_prompt(server_id: str, prompt_text: str, theme: Optional[str] = None) -> int:
    """
    Save a new prompt to the database.
    
    Called when:
    - User requests a new prompt via chat
    - Daily scheduler generates the automatic prompt
    
    Args:
        server_id: The Discord server ID
        prompt_text: The generated prompt text
        theme: Optional theme that was used (for filtering later)
        
    Returns:
        The ID of the newly created prompt record
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO prompts (server_id, prompt_text, theme) VALUES (?, ?, ?)",
            (server_id, prompt_text, theme)
        )
        await db.commit()
        return cursor.lastrowid


async def get_prompt_history(server_id: str, days: int = 7) -> list[dict]:
    """
    Get recent prompts for a server.
    
    Used when users ask "what did we draw last week?" or similar.
    
    Args:
        server_id: The Discord server ID
        days: How many recent prompts to retrieve (default 7)
        
    Returns:
        List of dicts with prompt_text, theme, and created_at
        Ordered by most recent first
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Row factory makes rows accessible as dicts
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT prompt_text, theme, created_at 
            FROM prompts 
            WHERE server_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (server_id, days)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_todays_prompt(server_id: str) -> Optional[dict]:
    """
    Get today's prompt if one exists.
    
    Used by the daily scheduler to avoid posting duplicate prompts.
    If a prompt was already generated today, this returns it.
    
    Args:
        server_id: The Discord server ID
        
    Returns:
        Dict with prompt details, or None if no prompt today
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT prompt_text, theme, created_at 
            FROM prompts 
            WHERE server_id = ? AND DATE(created_at) = DATE('now')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (server_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# SETTINGS FUNCTIONS
# =============================================================================

async def get_settings(server_id: str) -> dict:
    """
    Get settings for a server, creating defaults if needed.
    
    This is called for every message to get current configuration.
    If the server has never been configured, creates default settings.
    
    Args:
        server_id: The Discord server ID
        
    Returns:
        Dict with all settings:
        - server_id
        - channel_id (or None)
        - post_time (default "09:00")
        - timezone (default "America/New_York")
        - current_theme (or None)
        - theme_days_remaining (default 0)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM settings WHERE server_id = ?",
            (server_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            return dict(row)
        
        # ----- CREATE DEFAULT SETTINGS -----
        # First time this server is seen, create a row with defaults
        await db.execute(
            "INSERT INTO settings (server_id) VALUES (?)",
            (server_id,)
        )
        await db.commit()
        
        # Return the default values
        return {
            "server_id": server_id,
            "channel_id": None,
            "post_time": "09:00",
            "timezone": "America/New_York",
            "current_theme": None,
            "theme_days_remaining": 0
        }


async def update_settings(server_id: str, **kwargs) -> None:
    """
    Update settings for a server.
    
    Uses **kwargs so you can update any combination of fields:
    - await update_settings(server_id, post_time="10:00")
    - await update_settings(server_id, current_theme="space", theme_days_remaining=7)
    
    Args:
        server_id: The Discord server ID
        **kwargs: Field names and values to update
        
    Valid fields:
        - channel_id: Channel ID for daily prompts
        - post_time: Time in HH:MM format
        - timezone: Timezone string
        - current_theme: Theme name or None
        - theme_days_remaining: Days left for current theme
    """
    # Ensure the server has a settings row first
    await get_settings(server_id)
    
    # Filter to only valid fields (security measure)
    valid_fields = ["channel_id", "post_time", "timezone", "current_theme", "theme_days_remaining"]
    updates = {k: v for k, v in kwargs.items() if k in valid_fields}
    
    if not updates:
        return  # Nothing to update
    
    # Build the SQL UPDATE statement dynamically
    # e.g., "UPDATE settings SET post_time = ?, current_theme = ? WHERE server_id = ?"
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [server_id]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE settings SET {set_clause} WHERE server_id = ?",
            values
        )
        await db.commit()


async def get_all_servers_for_posting() -> list[dict]:
    """
    Get all servers that have a channel configured for daily prompts.
    
    Used by the daily scheduler to know which servers need prompts posted.
    Only returns servers where channel_id is not NULL.
    
    Returns:
        List of settings dicts for servers with configured channels
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM settings WHERE channel_id IS NOT NULL"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def decrement_theme_days(server_id: str) -> None:
    """
    Decrement the theme_days_remaining counter.
    
    Called after each prompt is generated when using a themed week.
    When days reach 0, the theme is automatically cleared.
    
    Example flow:
    - User sets "space" theme for 3 days
    - Day 1: Generate space prompt, decrement to 2
    - Day 2: Generate space prompt, decrement to 1
    - Day 3: Generate space prompt, decrement to 0, clear theme
    - Day 4: Generate random prompt (no theme)
    
    Args:
        server_id: The Discord server ID
    """
    settings = await get_settings(server_id)
    days = settings.get("theme_days_remaining", 0)
    
    if days > 1:
        # Still have days left, just decrement
        await update_settings(server_id, theme_days_remaining=days - 1)
    elif days == 1:
        # Last day! Clear the theme entirely
        await update_settings(server_id, current_theme=None, theme_days_remaining=0)
    # If days is 0, do nothing


# =============================================================================
# CONVERSATION FUNCTIONS
# =============================================================================

async def save_message(server_id: str, user_id: str, role: str, content: str) -> None:
    """
    Save a message to conversation history.
    
    Called after every interaction to build up context.
    Both user messages and Mai's responses are saved.
    
    Args:
        server_id: The Discord server ID
        user_id: The Discord user ID
        role: "user" or "assistant"
        content: The message text
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (server_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (server_id, user_id, role, content)
        )
        await db.commit()


async def get_recent_conversation(server_id: str, limit: int = 10) -> list[dict]:
    """
    Get recent conversation history for GPT context.
    
    This is passed to GPT so Mai can remember recent interactions.
    Returns messages in chronological order (oldest first).
    
    Args:
        server_id: The Discord server ID
        limit: How many messages to retrieve (default 10)
        
    Returns:
        List of dicts with role, content, and created_at
        Ordered chronologically (oldest to newest)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT role, content, created_at
            FROM conversations
            WHERE server_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (server_id, limit)
        )
        rows = await cursor.fetchall()
        # Reverse to get chronological order (oldest first)
        # This is important for GPT to understand the conversation flow
        return [dict(row) for row in reversed(rows)]
