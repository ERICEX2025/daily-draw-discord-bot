"""
daily/scheduler.py — Daily Prompt Scheduler

Handles scheduling and job management for daily prompts.
"""

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord

from bot.services import db
from bot.memory import cleanup_expired_memories

EST = pytz.timezone("America/New_York")
scheduler = AsyncIOScheduler(timezone=EST)
_bot: "discord.Client" = None


def init(bot: "discord.Client"):
    """Initialize scheduler with Discord bot reference."""
    global _bot
    _bot = bot


def get_bot() -> "discord.Client":
    """Get the Discord bot reference."""
    return _bot


async def start_scheduler():
    """Start scheduler and load existing jobs."""
    from bot.daily.executor import post_daily_prompt
    
    servers = await db.get_all_servers_for_posting()
    
    for server in servers:
        add_or_update_job(
            server_id=server["server_id"],
            post_time=server["post_time"],
            timezone=server["timezone"]
        )
    
    scheduler.add_job(
        _cleanup_expired_memories,
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=EST),
        id="memory_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    print("🧹 Scheduled weekly memory cleanup (Sundays 3am EST)")
    
    scheduler.start()
    print(f"📅 Scheduler started with {len(servers)} daily prompt job(s)")


def add_or_update_job(server_id: str, post_time: str, timezone: str = "America/New_York"):
    """Add or update a daily prompt job."""
    from bot.daily.executor import post_daily_prompt
    
    job_id = f"daily_prompt_{server_id}"
    hour, minute = map(int, post_time.split(":"))
    
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        print(f"⚠️ Unknown timezone '{timezone}', defaulting to America/New_York")
        tz = EST
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    scheduler.add_job(
        post_daily_prompt,
        CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[server_id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    
    print(f"📅 Scheduled daily prompt for server {server_id} at {post_time} ({timezone})")


def remove_job(server_id: str):
    """Remove a server's daily prompt job."""
    job_id = f"daily_prompt_{server_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        print(f"📅 Removed daily prompt job for server {server_id}")


def shutdown():
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        print("📅 Scheduler shut down gracefully")


async def _cleanup_expired_memories():
    """Clean up expired memories."""
    try:
        deleted_count = await cleanup_expired_memories()
        print(f"🧹 Memory cleanup: deleted {deleted_count} expired memories")
    except Exception as e:
        print(f"❌ Error during memory cleanup: {e}")

