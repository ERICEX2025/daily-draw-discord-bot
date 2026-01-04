"""
daily/executor.py — Daily Prompt Executor

Orchestrates daily prompt flow: generate → save → post to Discord.
"""

from datetime import datetime

import pytz

from bot.services import db
from bot.services.db import get_prompt_history, get_todays_prompt, save_prompt
from bot.services.langfuse import observe, propagate_attributes
from bot.memory import get_memories
from bot.config import (
    RECENT_PROMPTS_FOR_GENERATION,
    DAILY_PROMPT_MEMORIES,
    DAILY_PROMPT_RECENT_MESSAGES,
)
from bot.daily.generator import generate_daily_prompt


@observe(name="post_daily_prompt")
async def post_daily_prompt(server_id: str):
    """Post the daily prompt for a server."""
    from bot.memory import get_conversation_history, add_to_history
    from bot.daily.scheduler import get_bot
    
    _bot = get_bot()
    
    try:
        settings = await db.get_settings(server_id)
        
        # Check pause status
        paused_until = settings.get("paused_until")
        if paused_until:
            if isinstance(paused_until, str):
                pause_time = datetime.fromisoformat(paused_until.replace("Z", "+00:00"))
            else:
                pause_time = paused_until
            
            if datetime.now(pause_time.tzinfo or pytz.UTC) < pause_time:
                print(f"⏸️ Skipping server {server_id}: Paused until {paused_until}")
                return
        
        # Check if already posted today
        server_tz = settings.get("timezone", "America/New_York")
        todays_prompt = await get_todays_prompt(server_id, timezone=server_tz)
        if todays_prompt:
            print(f"⏭️ Skipping server {server_id}: Already posted today")
            return
        
        channel_id = settings.get("channel_id")
        if not channel_id:
            print(f"⚠️ Server {server_id} has no channel configured")
            return
        
        channel = _bot.get_channel(int(channel_id))
        if not channel:
            print(f"⚠️ Could not find channel {channel_id} for server {server_id}")
            return
        
        # Get context
        recent_history = await get_prompt_history(server_id, limit=RECENT_PROMPTS_FOR_GENERATION)
        past_prompts = [
            {"date": p["created_at"][:10], "prompt": p["prompt_text"]}
            for p in recent_history
        ]
        
        memories_raw = await get_memories(server_id, limit=DAILY_PROMPT_MEMORIES)
        memories = [m["memory"] for m in memories_raw]
        
        recent_messages = get_conversation_history(server_id, limit=DAILY_PROMPT_RECENT_MESSAGES)
        theme = settings.get("theme", "anime and video game inspired")
        
        # Generate prompt
        with propagate_attributes(
            user_id="scheduler",
            session_id=f"daily-prompt-{server_id}",
            metadata={"server_id": server_id, "channel_id": channel_id}
        ):
            raw_prompt, mai_message = await generate_daily_prompt(
                past_prompts,
                theme=theme,
                memories=memories if memories else None,
                recent_messages=recent_messages if recent_messages else None,
                server_id=server_id
            )
        
        await save_prompt(server_id, raw_prompt)
        
        # Get reference images
        from bot.services.search import search_reference_images
        from bot.services.http import download_image_as_base64, download_image_as_file
        reference_urls = await search_reference_images(raw_prompt, max_results=2)
        
        base64_images = []
        for url in reference_urls:
            b64 = await download_image_as_base64(url)
            if b64:
                base64_images.append(b64)
        
        # Send to Discord
        if reference_urls:
            files = []
            for i, url in enumerate(reference_urls):
                file = await download_image_as_file(url, f"reference_{i}.jpg")
                if file:
                    files.append(file)
            
            if files:
                await channel.send(mai_message, files=files)
            else:
                await channel.send(mai_message)
        else:
            await channel.send(mai_message)
        
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

