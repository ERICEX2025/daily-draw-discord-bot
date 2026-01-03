"""
scheduler.py — APScheduler-based Daily Prompt Scheduler

This module manages the background scheduling of daily prompts using APScheduler.
It provides a clean interface for:
1. Starting the scheduler on bot ready
2. Adding/updating jobs when users change their post time
3. Removing jobs if needed

Benefits over the polling approach:
- Efficient: Sleeps until the exact time instead of checking every minute
- Robust: Handles DST, missed jobs, timezone edge cases
- Dynamic: Easy to add/remove/reschedule jobs at runtime
"""

import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime

import discord
from bot import database as db
from bot import gpt

# Import Langfuse for tracing (if configured)
_langfuse_enabled = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
if _langfuse_enabled:
    from langfuse.decorators import observe, langfuse_context
else:
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    langfuse_context = None

# Timezone for scheduling (can be made per-server in the future)
EST = pytz.timezone("America/New_York")

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone=EST)

# Reference to the Discord bot (set during init)
_bot: "discord.Client" = None


def init(bot: "discord.Client"):
    """
    Initialize the scheduler with a reference to the Discord bot.
    
    Must be called before start_scheduler().
    """
    global _bot
    _bot = bot


async def start_scheduler():
    """
    Start the scheduler and load all existing jobs from the database.
    
    Call this in on_ready() after init().
    """
    # Load all servers with configured channels
    servers = await db.get_all_servers_for_posting()
    
    for server in servers:
        add_or_update_job(
            server_id=server["server_id"],
            post_time=server["post_time"],
            timezone=server["timezone"]
        )
    
    # Add weekly memory cleanup job (runs every Sunday at 3am EST)
    scheduler.add_job(
        cleanup_expired_memories,
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=EST),
        id="memory_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    print("🧹 Scheduled weekly memory cleanup (Sundays 3am EST)")
    
    scheduler.start()
    print(f"📅 Scheduler started with {len(servers)} daily prompt job(s)")


def add_or_update_job(server_id: str, post_time: str, timezone: str = "America/New_York"):
    """
    Add or update a daily prompt job for a server.
    
    Args:
        server_id: The Discord server ID
        post_time: Time in "HH:MM" format (24-hour)
        timezone: IANA timezone name (e.g., "America/New_York", "America/Los_Angeles")
    """
    job_id = f"daily_prompt_{server_id}"
    
    # Parse the time
    hour, minute = map(int, post_time.split(":"))
    
    # Get the timezone object
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        print(f"⚠️ Unknown timezone '{timezone}', defaulting to America/New_York")
        tz = EST
    
    # Remove existing job if it exists (to update the time)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    # Add the new job
    scheduler.add_job(
        post_daily_prompt,
        CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[server_id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,  # Allow running up to 1 hour late if missed
    )
    
    print(f"📅 Scheduled daily prompt for server {server_id} at {post_time} ({timezone})")


def remove_job(server_id: str):
    """
    Remove a server's daily prompt job.
    
    Call this if a server removes their channel configuration.
    """
    job_id = f"daily_prompt_{server_id}"
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        print(f"📅 Removed daily prompt job for server {server_id}")


def shutdown():
    """
    Gracefully shutdown the scheduler.
    
    Call this when the bot is stopping to:
    1. Stop accepting new jobs
    2. Wait for any currently running jobs to finish
    3. Clean up resources
    """
    if scheduler.running:
        scheduler.shutdown(wait=True)  # wait=True lets running jobs finish
        print("📅 Scheduler shut down gracefully")


@observe(name="post_daily_prompt")
async def post_daily_prompt(server_id: str):
    """
    Post the daily prompt for a single server.
    
    This is the job function that APScheduler calls at the scheduled time.
    """
    # Add Langfuse metadata for the scheduled job
    if _langfuse_enabled and langfuse_context:
        langfuse_context.update_current_trace(
            session_id=f"daily-prompt-{server_id}",
            metadata={
                "type": "scheduled_daily_prompt",
                "server_id": server_id,
            }
        )
    
    try:
        # Get server settings first to check pause status
        settings = await db.get_settings(server_id)
        
        # Check if prompts are paused for this server
        paused_until = settings.get("paused_until")
        if paused_until:
            # Parse the datetime string from database
            if isinstance(paused_until, str):
                pause_time = datetime.fromisoformat(paused_until.replace("Z", "+00:00"))
            else:
                pause_time = paused_until
            
            if datetime.now(pause_time.tzinfo or pytz.UTC) < pause_time:
                print(f"⏸️ Skipping server {server_id}: Paused until {paused_until}")
                return
        
        # Check if we already posted today (prevents duplicates on reschedule)
        # Pass the server's timezone so "today" is calculated correctly
        server_tz = settings.get("timezone", "America/New_York")
        todays_prompt = await db.get_todays_prompt(server_id, timezone=server_tz)
        if todays_prompt:
            print(f"⏭️ Skipping server {server_id}: Already posted today")
            return
        
        channel_id = settings.get("channel_id")
        
        if not channel_id:
            print(f"⚠️ Server {server_id} has no channel configured")
            return
        
        # Get the channel
        channel = _bot.get_channel(int(channel_id))
        if not channel:
            print(f"⚠️ Could not find channel {channel_id} for server {server_id}")
            return
        
        # Generate the prompt with full context
        from bot.config import (
            RECENT_PROMPTS_FOR_GENERATION,
            DAILY_PROMPT_MEMORIES,
            DAILY_PROMPT_RECENT_MESSAGES,
        )
        from bot.memory import get_recent_messages, add_to_history
        
        # Get recent prompts to avoid repeats
        recent_history = await db.get_prompt_history(server_id, limit=RECENT_PROMPTS_FOR_GENERATION)
        past_prompts = [
            {"date": p["created_at"][:10], "prompt": p["prompt_text"]}
            for p in recent_history
        ]
        
        # Get long-term memories for personalization
        memories_raw = await db.get_memories(server_id, limit=DAILY_PROMPT_MEMORIES)
        memories = [m["memory"] for m in memories_raw]
        
        # Get recent conversations for context
        recent_messages = get_recent_messages(server_id, limit=DAILY_PROMPT_RECENT_MESSAGES)
        
        # Get theme from settings (defaults to "anime and video game inspired")
        theme = settings.get("theme", "anime and video game inspired")
        
        raw_prompt, mai_message = await gpt.generate_daily_prompt(
            past_prompts,
            theme=theme,
            memories=memories if memories else None,
            recent_messages=recent_messages if recent_messages else None,
            server_id=server_id
        )
        
        # Save to database
        await db.save_prompt(server_id, raw_prompt)
        
        # Search for reference images based on the prompt
        from bot.utils import search_reference_images, download_image_as_base64
        reference_urls = await search_reference_images(raw_prompt, max_results=2)
        
        # Download images as base64 for GPT memory
        base64_images = []
        for url in reference_urls:
            b64 = await download_image_as_base64(url)
            if b64:
                base64_images.append(b64)
        
        # Send to Discord
        await channel.send(mai_message)
        
        # Send reference images as embeds (plain URLs don't auto-embed)
        if reference_urls:
            for url in reference_urls:
                embed = discord.Embed(color=0xE91E63)
                embed.set_image(url=url)
                await channel.send(embed=embed)
        
        # Add to short-term memory with actual images so Mai can see them
        add_to_history(
            server_id, 
            "assistant", 
            mai_message, 
            username="Mai",
            images=base64_images if base64_images else None
        )
        
        print(f"✅ Posted daily prompt to server {server_id} (with {len(reference_urls)} reference images)")
        
    except Exception as e:
        print(f"❌ Error posting daily prompt to server {server_id}: {e}")


async def cleanup_expired_memories():
    """
    Clean up expired memories from all servers.
    
    Runs weekly to remove memories that have passed their expiry date.
    This keeps the database clean and memory retrieval fast.
    """
    try:
        deleted_count = await db.cleanup_expired_memories()
        print(f"🧹 Memory cleanup: deleted {deleted_count} expired memories")
    except Exception as e:
        print(f"❌ Error during memory cleanup: {e}")

