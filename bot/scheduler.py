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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

from bot import database as db
from bot import gpt

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


async def post_daily_prompt(server_id: str):
    """
    Post the daily prompt for a single server.
    
    This is the job function that APScheduler calls at the scheduled time.
    """
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
        
        # Generate the prompt
        # Include dates so GPT knows when each prompt was used
        all_history = await db.get_prompt_history(server_id)
        past_prompts = [
            {"date": p["created_at"][:10], "prompt": p["prompt_text"]}
            for p in all_history
        ]
        
        # Get theme from settings (defaults to "anime and video game inspired")
        theme = settings.get("theme", "anime and video game inspired")
        
        raw_prompt, mai_message = await gpt.generate_daily_prompt(past_prompts, theme=theme)
        
        # Save to database
        await db.save_prompt(server_id, raw_prompt)
        
        # Send to Discord
        await channel.send(mai_message)
        
        print(f"✅ Posted daily prompt to server {server_id}")
        
    except Exception as e:
        print(f"❌ Error posting daily prompt to server {server_id}: {e}")

