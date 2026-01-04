"""
chat/handlers.py — Function Handlers

Each handler implements a tool that GPT can call.
"""

import re
import discord
from datetime import datetime, timedelta, timezone as tz

from bot.services import db
from bot import daily
from bot.config import (
    RECENT_PROMPTS_FOR_GENERATION,
    DAILY_PROMPT_MEMORIES,
    DAILY_PROMPT_RECENT_MESSAGES,
)
from bot.daily import generate_daily_prompt
from bot.services.db import get_prompt_history, delete_todays_prompt, save_prompt
from bot.memory import save_memory, get_memories, get_conversation_history, add_to_history
from bot.config import MEMORIES_RECALL_LIMIT
from bot.mai import Function
from bot.services.search import search_reference_images, web_search


# =============================================================================
# SETTINGS HANDLERS
# =============================================================================

async def handle_set_schedule(server_id: str, args: dict, **_) -> str:
    """Set the daily posting time."""
    time = args["time"]
    timezone = args.get("timezone")
    
    tz_aliases = {
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
    }
    
    if timezone:
        timezone = tz_aliases.get(timezone.upper(), timezone)
        await db.update_settings(server_id, post_time=time, timezone=timezone)
    else:
        await db.update_settings(server_id, post_time=time)
    
    settings = await db.get_settings(server_id)
    tz_name = settings.get("timezone", "America/New_York")
    daily.add_or_update_job(server_id, time, tz_name)
    
    tz_display = timezone if timezone else settings.get("timezone", "America/New_York")
    await save_memory(
        server_id,
        f"Schedule changed to {time} ({tz_display})",
        category="event",
        importance=4
    )
    
    return f"Daily prompt time set to {time} ({tz_display})"


async def handle_set_channel(server_id: str, args: dict, message: discord.Message, **_) -> str:
    """Set which channel daily prompts should be posted to."""
    raw_input = args["channel_name"]
    guild = message.guild
    
    if guild:
        channel = None
        
        mention_match = re.match(r'<#(\d+)>', raw_input)
        if mention_match:
            channel_id = int(mention_match.group(1))
            channel = guild.get_channel(channel_id)
        elif raw_input.isdigit():
            channel = guild.get_channel(int(raw_input))
        else:
            channel_name = raw_input.lower().replace("#", "").strip()
            channel = discord.utils.find(
                lambda c: c.name.lower() == channel_name,
                guild.text_channels
            )
        
        if channel:
            await db.update_settings(server_id, channel_id=str(channel.id))
            
            settings = await db.get_settings(server_id)
            daily.add_or_update_job(
                server_id,
                settings["post_time"],
                settings.get("timezone", "America/New_York")
            )
            
            await save_memory(
                server_id,
                f"Daily prompts channel set to #{channel.name}",
                category="event",
                importance=5
            )
            
            return f"Daily prompts will now be posted to #{channel.name}"
        else:
            return f"Could not find channel '{raw_input}'"
    
    return "Could not set channel (not in a server)"


async def handle_set_theme(server_id: str, args: dict, **_) -> str:
    """Set the theme for daily prompts."""
    theme = args["theme"]
    await db.update_settings(server_id, theme=theme)
    
    await save_memory(
        server_id,
        f"Theme changed to: {theme}",
        category="event",
        importance=4
    )
    
    return f"Theme set to: {theme}"


async def handle_pause_schedule(server_id: str, args: dict, **_) -> str:
    """Pause daily prompts."""
    days = args["days"]
    resume_at = datetime.now(tz.utc) + timedelta(days=days)
    await db.update_settings(server_id, paused_until=resume_at.isoformat())
    
    return f"Daily prompts paused for {days} days (until {resume_at.strftime('%B %d, %Y')})"


async def handle_resume_schedule(server_id: str, **_) -> str:
    """Resume daily prompts."""
    await db.update_settings(server_id, paused_until=None)
    return "Daily prompts resumed! The next prompt will post at the scheduled time."


# =============================================================================
# PROMPT HANDLERS
# =============================================================================

async def handle_get_history(server_id: str, args: dict, **_) -> str:
    """Get recent prompt history."""
    count = args.get("days", 7)
    history = await get_prompt_history(server_id, limit=count)
    
    if not history:
        return "No prompts found in history"
    
    history_text = "\n".join([
        f"- {p['created_at'][:10]}: {p['prompt_text']}"
        for p in history
    ])
    
    return f"Recent prompts:\n{history_text}"


async def handle_reroll_prompt(server_id: str, args: dict, **_) -> dict:
    """Reroll today's prompt."""
    hint = args.get("hint")
    settings = await db.get_settings(server_id)
    server_tz = settings.get("timezone", "America/New_York")
    channel_id = settings.get("channel_id")
    theme = settings.get("theme", "anime and video game inspired")
    
    if not channel_id:
        return {"error": "No channel configured for daily prompts. Set one first."}
    
    await delete_todays_prompt(server_id, server_tz)
    
    recent_history = await get_prompt_history(server_id, limit=RECENT_PROMPTS_FOR_GENERATION)
    past_prompts = [
        {"date": p["created_at"][:10], "prompt": p["prompt_text"]}
        for p in recent_history
    ]
    
    memories_raw = await get_memories(server_id, limit=DAILY_PROMPT_MEMORIES)
    memories = [m["memory"] for m in memories_raw]
    recent_messages = get_conversation_history(server_id, limit=DAILY_PROMPT_RECENT_MESSAGES)
    
    raw_prompt, mai_message = await generate_daily_prompt(
        past_prompts,
        theme=theme,
        memories=memories if memories else None,
        recent_messages=recent_messages if recent_messages else None,
        server_id=server_id,
        hint=hint
    )
    
    await save_prompt(server_id, raw_prompt)
    add_to_history(server_id, "assistant", mai_message, username="Mai")
    
    reference_urls = await search_reference_images(raw_prompt, max_results=2)
    
    return {
        "_direct_response": mai_message,
        "_pending_images": {"query": raw_prompt, "urls": reference_urls} if reference_urls else None
    }


# =============================================================================
# MEMORY HANDLERS
# =============================================================================

async def handle_save_memory(server_id: str, args: dict, **_) -> str:
    """Save a long-term memory."""
    memory = args["memory"]
    about_user = args.get("about_user")
    category = args.get("category", "general")
    importance = args.get("importance")
    
    await save_memory(
        server_id,
        memory,
        user_id=about_user if about_user else None,
        category=category,
        importance=importance
    )
    
    if about_user:
        return f"Remembered about {about_user} [{category}]: {memory}"
    return f"Remembered [{category}]: {memory}"


async def handle_recall_memories(server_id: str, args: dict, **_) -> str:
    """Recall memories."""
    about_user = args.get("about_user")
    category = args.get("category")
    
    memories = await get_memories(
        server_id,
        user_id=about_user,
        category=category,
        limit=MEMORIES_RECALL_LIMIT
    )
    
    if not memories:
        if about_user:
            return f"No memories found about {about_user}"
        return "No memories saved yet"
    
    memory_list = []
    for m in memories:
        prefix = f"[{m.get('category', 'general')}]"
        if m.get("user_id"):
            memory_list.append(f"- {prefix} About {m['user_id']}: {m['memory']}")
        else:
            memory_list.append(f"- {prefix} {m['memory']}")
    
    return "Memories:\n" + "\n".join(memory_list)


# =============================================================================
# SEARCH HANDLERS
# =============================================================================

async def handle_search_images(server_id: str, args: dict, **_) -> dict:
    """Search for reference images."""
    query = args.get("query", "")
    if not query:
        return {"error": "No search query provided"}
    
    count = args.get("count", 1)
    count = max(1, min(count, 5))
    
    urls = await search_reference_images(query, max_results=count)
    
    if not urls:
        return {"message": f"No images found for '{query}'"}
    
    img_word = "image" if len(urls) == 1 else "images"
    return {
        "message": f"Found {len(urls)} reference {img_word} for '{query}'. Will be attached after your message—don't include URLs.",
        "_pending_images": {"query": query, "urls": urls}
    }


async def handle_web_search(server_id: str, args: dict, **_) -> dict:
    """Search the web."""
    query = args.get("query", "")
    if not query:
        return {"error": "No search query provided"}
    
    results = await web_search(query, max_results=3)
    
    if not results:
        return {"message": f"No results found for '{query}'"}
    
    return {"query": query, "results": results}


# =============================================================================
# HANDLER REGISTRY
# =============================================================================

HANDLERS = {
    Function.SET_SCHEDULE: handle_set_schedule,
    Function.SET_CHANNEL: handle_set_channel,
    Function.SET_THEME: handle_set_theme,
    Function.PAUSE_SCHEDULE: handle_pause_schedule,
    Function.RESUME_SCHEDULE: handle_resume_schedule,
    Function.GET_HISTORY: handle_get_history,
    Function.REROLL_PROMPT: handle_reroll_prompt,
    Function.SAVE_MEMORY: handle_save_memory,
    Function.RECALL_MEMORIES: handle_recall_memories,
    Function.SEARCH_IMAGES: handle_search_images,
    Function.WEB_SEARCH: handle_web_search,
}

