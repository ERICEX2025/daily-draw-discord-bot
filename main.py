"""
main.py — Bot Entry Point & Discord Event Handlers
"""

import discord
import os
import atexit
from dotenv import load_dotenv

from bot.services import db
from bot.services.langfuse import observe, propagate_attributes, update_span
from bot.services.http import download_image_as_base64, download_image_as_file
from bot.chat.executor import run_chat_loop
from bot.memory import get_conversation_history, add_to_history, get_memories_for_context
from bot.config import MEMORIES_FOR_CONTEXT
from bot import daily

load_dotenv()

# =============================================================================
# DISCORD CLIENT SETUP
# =============================================================================

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


# =============================================================================
# EVENT: BOT READY
# =============================================================================

@bot.event
async def on_ready():
    """Initialize database and start scheduler."""
    await db.init_db()
    daily.init(bot)
    await daily.start_scheduler()
    
    print(f"✨ {bot.user} is now online!")
    print(f"🎨 Mai-san is ready to help with your art channel!")


# =============================================================================
# EVENT: MESSAGE RECEIVED
# =============================================================================

@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages."""
    if message.author == bot.user:
        return
    
    # Check if bot user is mentioned directly
    if bot.user in message.mentions:
        await _handle_mention(message)
        return
    
    # Check if bot's role is mentioned (people sometimes tag the role instead of the user)
    if message.guild:
        bot_member = message.guild.get_member(bot.user.id)
        if bot_member:
            for role in bot_member.roles:
                if role in message.role_mentions:
                    await _handle_mention(message)
                    return


@observe(name="handle_mention", capture_input=False, capture_output=False)
async def _handle_mention(message: discord.Message):
    """
    Handle a mention of Mai.
    
    Flow:
      1. Parse the message and extract user text
      2. Gather context (settings, history, images, memories)
      3. Run the chat loop (GPT + tool execution)
      4. Save conversation and send response
    """
    
    # -------------------------------------------------------------------------
    # 1. PARSE MESSAGE
    #    Strip the @mention, default to "hi" if empty
    # -------------------------------------------------------------------------
    user_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not user_message and not message.attachments:
        user_message = "hi"
    
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    username = message.author.display_name
    channel_id = str(message.channel.id)
    
    update_span(input=user_message)
    
    # -------------------------------------------------------------------------
    # 2. GATHER CONTEXT
    #    Fetch everything Mai needs to respond intelligently
    # -------------------------------------------------------------------------
    
    # Server settings (theme, timezone, prompt time, etc.)
    settings = await db.get_settings(server_id)
    
    # Recent conversation history (in-memory, lost on restart)
    conversation_history = get_conversation_history(server_id)
    
    # Convert any attached images to base64 for GPT vision
    image_urls = []
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            base64_url = await download_image_as_base64(attachment.url)
            if base64_url:
                image_urls.append(base64_url)
    
    # Fetch relevant long-term memories from database
    memories_raw = await get_memories_for_context(
        server_id,
        current_user=username,
        limit=MEMORIES_FOR_CONTEXT
    )
    long_term_memories = [m["memory"] for m in memories_raw]
    
    # -------------------------------------------------------------------------
    # 3. RUN CHAT LOOP
    #    Call GPT, execute any tools it requests, loop until final response
    # -------------------------------------------------------------------------
    async with message.channel.typing():
        with propagate_attributes(
            user_id=username,
            session_id=f"server-{server_id}-channel-{channel_id}",
            metadata={"server_id": server_id, "channel_id": channel_id}
        ):
            response_text, pending_images = await run_chat_loop(
                user_message=user_message,
                username=username,
                conversation_history=conversation_history,
                settings=settings,
                message=message,
                image_urls=image_urls if image_urls else None,
                long_term_memories=long_term_memories,
                server_id=server_id,
                channel_id=channel_id
            )
            
        # ---------------------------------------------------------------------
        # 4. SAVE & RESPOND
        #    Store conversation in short-term memory, send reply to user
        # ---------------------------------------------------------------------
        
        # Save both sides of conversation to short-term memory
        add_to_history(server_id, "user", user_message, username=username, images=image_urls if image_urls else None)
        add_to_history(server_id, "assistant", response_text, username="Mai")
        
        update_span(output=response_text or "[error: no response]")
        
        # Download any pending images first (so we can send text + images together)
        all_files = []
        for img_data in pending_images:
            urls = img_data.get("urls", [])
            for i, url in enumerate(urls):
                try:
                    file = await download_image_as_file(url, f"reference_{i}.jpg")
                    if file:
                        all_files.append(file)
                except Exception as e:
                    print(f"Failed to download image: {e}")
        
        # Send Mai's response (with images if any)
        try:
            if response_text:
                await message.reply(response_text, files=all_files if all_files else None)
            else:
                await message.reply("ah, something went wrong on my end... try again?")
        except Exception as e:
            print(f"Failed to send reply: {e}")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Error: DISCORD_TOKEN not found in .env file")
        exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in .env file")
        exit(1)
    
    atexit.register(daily.shutdown)
    bot.run(token)
