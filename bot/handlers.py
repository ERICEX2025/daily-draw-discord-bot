"""
handlers.py — Function Handlers for GPT Tool Calls

This module contains the implementation of each function that GPT can call.
Each handler is a standalone async function that performs one specific action.

The HANDLERS dict maps Function enum values to their handler functions,
allowing execute_function in main.py to be a simple dispatcher.
"""

import discord
from datetime import datetime, timedelta, timezone as tz
from bot import database as db
from bot import scheduler
from bot.personality import Function
from bot.config import MEMORIES_RECALL_LIMIT


# =============================================================================
# HANDLER FUNCTIONS
# =============================================================================

async def handle_set_schedule(server_id: str, args: dict, **_) -> str:
    """
    Set the daily posting time for prompts.
    
    Time should be in HH:MM format (24-hour clock).
    Timezone is optional (defaults to America/New_York).
    Also updates the APScheduler job to fire at the new time.
    """
    time = args["time"]  # Expected format: "HH:MM" (24-hour)
    timezone = args.get("timezone")  # Optional timezone
    
    # Map common abbreviations to full timezone names
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
    
    # Get the current timezone for the scheduler
    settings = await db.get_settings(server_id)
    tz = settings.get("timezone", "America/New_York")
    
    # Update the scheduler job to use the new time and timezone
    scheduler.add_or_update_job(server_id, time, tz)
    
    # Auto-save this as an event memory
    tz_display = timezone if timezone else settings.get("timezone", "America/New_York")
    await db.save_memory(
        server_id,
        f"Schedule changed to {time} ({tz_display})",
        category="event",
        importance=4
    )
    
    return f"Daily prompt time set to {time} ({tz_display})"


async def handle_set_channel(server_id: str, args: dict, message: discord.Message, **_) -> str:
    """
    Set which channel daily prompts should be posted to.
    
    Looks up the channel by name or ID in the current guild.
    Handles Discord channel mentions like <#123456789>.
    Also creates a scheduler job if this is the first channel setup.
    """
    import re
    
    raw_input = args["channel_name"]
    
    guild = message.guild
    if guild:
        channel = None
        
        # Check if it's a channel mention format: <#123456789>
        mention_match = re.match(r'<#(\d+)>', raw_input)
        if mention_match:
            channel_id = int(mention_match.group(1))
            channel = guild.get_channel(channel_id)
        # Check if it's just a raw ID
        elif raw_input.isdigit():
            channel = guild.get_channel(int(raw_input))
        # Otherwise, treat it as a channel name
        else:
            channel_name = raw_input.lower().replace("#", "").strip()
            channel = discord.utils.find(
                lambda c: c.name.lower() == channel_name, 
                guild.text_channels
            )
        if channel:
            await db.update_settings(server_id, channel_id=str(channel.id))
            
            # Ensure a scheduler job exists for this server
            settings = await db.get_settings(server_id)
            scheduler.add_or_update_job(
                server_id, 
                settings["post_time"], 
                settings.get("timezone", "America/New_York")
            )
            
            # Auto-save this as an event memory
            await db.save_memory(
                server_id,
                f"Daily prompts channel set to #{channel.name}",
                category="event",
                importance=5  # Important setup event
            )
            
            return f"Daily prompts will now be posted to #{channel.name}"
        else:
            return f"Could not find channel '{raw_input}'"
    
    return "Could not set channel (not in a server)"


async def handle_get_history(server_id: str, args: dict, **_) -> str:
    """
    Retrieve recent prompt history for the server.
    
    Returns a formatted list of prompts from the past N days.
    """
    count = args.get("days", 7)  # "days" is really count for backwards compat
    
    history = await db.get_prompt_history(server_id, limit=count)
    
    if not history:
        return "No prompts found in history"
    
    # Format the history as a readable list
    history_text = "\n".join([
        f"- {p['created_at'][:10]}: {p['prompt_text']}"
        for p in history
    ])
    
    return f"Recent prompts:\n{history_text}"


async def handle_reroll_prompt(server_id: str, args: dict, **_) -> dict:
    """
    Reroll today's daily prompt.
    
    Deletes the current prompt for today (if any) and generates a new one.
    Returns _direct_response so main.py sends this instead of asking GPT.
    """
    from bot import gpt
    from bot.config import (
        RECENT_PROMPTS_FOR_GENERATION,
        DAILY_PROMPT_MEMORIES,
        DAILY_PROMPT_RECENT_MESSAGES,
    )
    from bot.memory import get_recent_messages, add_to_history
    from bot.utils import search_reference_images
    
    # Get optional hint from user (e.g., "JJK character", "something cozy")
    hint = args.get("hint")
    
    # Get server settings
    settings = await db.get_settings(server_id)
    server_tz = settings.get("timezone", "America/New_York")
    channel_id = settings.get("channel_id")
    theme = settings.get("theme", "anime and video game inspired")
    
    if not channel_id:
        return {"error": "No channel configured for daily prompts. Set one first."}
    
    # Delete today's prompt
    await db.delete_todays_prompt(server_id, server_tz)
    
    # Get recent prompts to avoid repeats
    recent_history = await db.get_prompt_history(server_id, limit=RECENT_PROMPTS_FOR_GENERATION)
    past_prompts = [
        {"date": p["created_at"][:10], "prompt": p["prompt_text"]}
        for p in recent_history
    ]
    
    # Get memories and recent messages for context
    memories_raw = await db.get_memories(server_id, limit=DAILY_PROMPT_MEMORIES)
    memories = [m["memory"] for m in memories_raw]
    recent_messages = get_recent_messages(server_id, limit=DAILY_PROMPT_RECENT_MESSAGES)
    
    # Generate the prompt (with optional hint)
    raw_prompt, mai_message = await gpt.generate_daily_prompt(
        past_prompts,
        theme=theme,
        memories=memories if memories else None,
        recent_messages=recent_messages if recent_messages else None,
        server_id=server_id,
        hint=hint
    )
    
    # Save to database
    await db.save_prompt(server_id, raw_prompt)
    
    # Add to conversation history
    add_to_history(server_id, "assistant", mai_message, username="Mai")
    
    # Get reference images
    reference_urls = await search_reference_images(raw_prompt, max_results=2)
    
    # Return direct response — main.py will send this instead of calling GPT
    return {
        "_direct_response": mai_message,
        "_pending_images": {"query": raw_prompt, "urls": reference_urls} if reference_urls else None
    }


async def handle_pause_schedule(server_id: str, args: dict, **_) -> str:
    """
    Pause daily prompts for a specified number of days.
    
    Sets paused_until to a future datetime. The scheduler will skip
    posting until that time passes.
    """
    days = args["days"]
    
    # Calculate the resume datetime (UTC)
    resume_at = datetime.now(tz.utc) + timedelta(days=days)
    resume_at_iso = resume_at.isoformat()
    
    await db.update_settings(server_id, paused_until=resume_at_iso)
    
    # Format a nice date for the response
    resume_date = resume_at.strftime("%B %d, %Y")
    
    return f"Daily prompts paused for {days} days (until {resume_date})"


async def handle_resume_schedule(server_id: str, **_) -> str:
    """
    Resume daily prompts immediately.
    
    Clears the paused_until field so prompts will post at the next scheduled time.
    """
    await db.update_settings(server_id, paused_until=None)
    
    return "Daily prompts resumed! The next prompt will post at the scheduled time."


async def handle_set_theme(server_id: str, args: dict, **_) -> str:
    """
    Set the theme/style for daily drawing prompts.
    
    This affects what kind of prompts Mai generates.
    """
    theme = args["theme"]
    
    await db.update_settings(server_id, theme=theme)
    
    # Auto-save this as an event memory
    await db.save_memory(
        server_id,
        f"Theme changed to: {theme}",
        category="event",
        importance=4
    )
    
    return f"Theme set to: {theme}"


async def handle_save_memory(server_id: str, args: dict, **_) -> str:
    """
    Save a long-term memory with category and importance.
    
    Mai can use this to remember things about users or the server.
    Categories: user_fact, preference, event, conversation, general
    """
    memory = args["memory"]
    about_user = args.get("about_user")
    category = args.get("category", "general")
    importance = args.get("importance")  # None = use default for category
    
    user_id = about_user if about_user else None
    
    await db.save_memory(
        server_id,
        memory,
        user_id=user_id,
        category=category,
        importance=importance
    )
    
    if about_user:
        return f"Remembered about {about_user} [{category}]: {memory}"
    return f"Remembered [{category}]: {memory}"


async def handle_recall_memories(server_id: str, args: dict, **_) -> str:
    """
    Recall memories from long-term storage.
    """
    about_user = args.get("about_user")
    category = args.get("category")
    
    memories = await db.get_memories(
        server_id,
        user_id=about_user,
        category=category,
        limit=MEMORIES_RECALL_LIMIT
    )
    
    if not memories:
        if about_user:
            return f"No memories found about {about_user}"
        return "No memories saved yet"
    
    # Format memories with category and importance
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

async def handle_search_images(server_id: str, args: dict, settings: dict, message) -> dict:
    """Search for reference images using DuckDuckGo. Returns URLs to be sent as attachments after Mai's response."""
    from bot import utils
    
    query = args.get("query", "")
    if not query:
        return {"error": "No search query provided"}
    
    count = args.get("count", 1)  # Default to 1, but can request more
    count = max(1, min(count, 5))  # Clamp between 1-5
    
    urls = await utils.search_reference_images(query, max_results=count)
    
    if not urls:
        return {"message": f"No images found for '{query}'"}
    
    # Return images with special flag - main.py will send them as attachments after Mai's text
    img_word = "image" if len(urls) == 1 else "images"
    return {
        "message": f"Found {len(urls)} reference {img_word} for '{query}'. Will be attached after your message—don't include URLs.",
        "_pending_images": {"query": query, "urls": urls}
    }


async def handle_web_search(server_id: str, args: dict, settings: dict, message) -> dict:
    """Search the web using DuckDuckGo."""
    from bot import utils
    
    query = args.get("query", "")
    if not query:
        return {"error": "No search query provided"}
    
    results = await utils.web_search(query, max_results=3)
    
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

