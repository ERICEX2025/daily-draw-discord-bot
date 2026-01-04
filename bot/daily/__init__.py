"""
daily/ — Daily Prompt Feature

Handles daily prompt generation, scheduling, and posting.
"""

from bot.daily.generator import generate_daily_prompt
from bot.daily.executor import post_daily_prompt
from bot.daily.scheduler import (
    init,
    start_scheduler,
    add_or_update_job,
    remove_job,
    shutdown,
)

__all__ = [
    # Generator
    "generate_daily_prompt",
    # Poster
    "post_daily_prompt",
    # Scheduler
    "init",
    "start_scheduler",
    "add_or_update_job",
    "remove_job",
    "shutdown",
]
