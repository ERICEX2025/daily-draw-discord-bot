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
    
    # Format nice response
    tz_display = timezone if timezone else settings.get("timezone", "America/New_York")
    return f"Daily prompt time set to {time} ({tz_display})"


async def handle_set_channel(server_id: str, args: dict, message: discord.Message, **_) -> str:
    """
    Set which channel daily prompts should be posted to.
    
    Looks up the channel by name in the current guild.
    Also creates a scheduler job if this is the first channel setup.
    """
    channel_name = args["channel_name"].lower().replace("#", "")
    
    guild = message.guild
    if guild:
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
            
            return f"Daily prompts will now be posted to #{channel.name}"
        else:
            return f"Could not find channel '{channel_name}'"
    
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
    
    return f"Theme set to: {theme}"


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
}

