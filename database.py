import aiosqlite
from datetime import datetime
from typing import Optional
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "mai_san.db")


async def init_db():
    """Initialize the database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Prompts table - stores all generated prompts
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                theme TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Settings table - per-server configuration
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                server_id TEXT PRIMARY KEY,
                channel_id TEXT,
                post_time TEXT DEFAULT '09:00',
                timezone TEXT DEFAULT 'America/New_York',
                current_theme TEXT,
                theme_days_remaining INTEGER DEFAULT 0
            )
        """)
        
        # Conversation history for context
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()


# ============ PROMPT FUNCTIONS ============

async def save_prompt(server_id: str, prompt_text: str, theme: Optional[str] = None) -> int:
    """Save a new prompt to the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO prompts (server_id, prompt_text, theme) VALUES (?, ?, ?)",
            (server_id, prompt_text, theme)
        )
        await db.commit()
        return cursor.lastrowid


async def get_prompt_history(server_id: str, days: int = 7) -> list[dict]:
    """Get recent prompts for a server."""
    async with aiosqlite.connect(DB_PATH) as db:
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
    """Get today's prompt if one exists."""
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


# ============ SETTINGS FUNCTIONS ============

async def get_settings(server_id: str) -> dict:
    """Get settings for a server, creating defaults if needed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM settings WHERE server_id = ?",
            (server_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            return dict(row)
        
        # Create default settings
        await db.execute(
            "INSERT INTO settings (server_id) VALUES (?)",
            (server_id,)
        )
        await db.commit()
        
        return {
            "server_id": server_id,
            "channel_id": None,
            "post_time": "09:00",
            "timezone": "America/New_York",
            "current_theme": None,
            "theme_days_remaining": 0
        }


async def update_settings(server_id: str, **kwargs) -> None:
    """Update settings for a server."""
    # Get current settings first to ensure row exists
    await get_settings(server_id)
    
    valid_fields = ["channel_id", "post_time", "timezone", "current_theme", "theme_days_remaining"]
    updates = {k: v for k, v in kwargs.items() if k in valid_fields}
    
    if not updates:
        return
    
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [server_id]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE settings SET {set_clause} WHERE server_id = ?",
            values
        )
        await db.commit()


async def get_all_servers_for_posting() -> list[dict]:
    """Get all servers that have a channel configured for daily prompts."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM settings WHERE channel_id IS NOT NULL"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def decrement_theme_days(server_id: str) -> None:
    """Decrement theme days remaining, clearing theme if done."""
    settings = await get_settings(server_id)
    days = settings.get("theme_days_remaining", 0)
    
    if days > 1:
        await update_settings(server_id, theme_days_remaining=days - 1)
    elif days == 1:
        await update_settings(server_id, current_theme=None, theme_days_remaining=0)


# ============ CONVERSATION FUNCTIONS ============

async def save_message(server_id: str, user_id: str, role: str, content: str) -> None:
    """Save a message to conversation history."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (server_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (server_id, user_id, role, content)
        )
        await db.commit()


async def get_recent_conversation(server_id: str, limit: int = 10) -> list[dict]:
    """Get recent conversation history for context."""
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
        # Reverse to get chronological order
        return [dict(row) for row in reversed(rows)]

