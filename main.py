"""
main.py — Bot Entry Point & Discord Event Handlers

This is the main file that runs Mai-san. It handles:
1. Connecting to Discord
2. Listening for @mentions
3. Processing messages and images
4. Executing functions that GPT requests
5. Running the daily prompt scheduler

Startup Flow:
    1. load_dotenv() loads DISCORD_TOKEN and OPENAI_API_KEY from .env
    2. Discord client is created with message_content intent enabled
    3. __main__ validates that both env vars exist, then calls bot.run(token)
    4. on_ready() fires once connected:
       - Initializes SQLite database (creates tables if needed)
       - Starts daily_prompt_check background loop (runs every minute)
       - Prints confirmation message

Message Flow:
    User @mentions bot → on_message() → gpt.chat_with_mai() → 
    execute_function() (if needed) → reply to user
"""

import discord
import os
import atexit
import json
from dotenv import load_dotenv

from bot import database as db
from bot import gpt
from bot import utils
from bot import scheduler
from bot.memory import get_conversation_history, add_to_history
from bot.config import MAX_FUNCTION_CHAIN_ITERATIONS, MEMORIES_FOR_CONTEXT

# Import Langfuse for tracing (if configured and Python < 3.13)
import sys
_langfuse_enabled = (
    bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    and sys.version_info < (3, 13)  # Disable on Python 3.13+ due to serialization bug
)
if _langfuse_enabled:
    try:
        from langfuse import observe
    except ImportError:
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        _langfuse_enabled = False
else:
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Load environment variables from .env file (DISCORD_TOKEN, OPENAI_API_KEY)
load_dotenv()


# =============================================================================
# DISCORD CLIENT SETUP
# =============================================================================

# Intents are permissions that tell Discord what events we want to receive
# We need message_content to read what users type (required for @mention detection)
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message text

# Create the Discord client (this is our bot instance)
bot = discord.Client(intents=intents)


# =============================================================================
# EVENT: BOT READY
# =============================================================================

@bot.event
async def on_ready():
    """
    Called automatically when the bot successfully connects to Discord.
    
    This runs once at startup and:
    1. Initializes the database (creates tables if they don't exist)
    2. Starts the APScheduler-based daily prompt scheduler
    3. Prints a confirmation message
    """
    await db.init_db()  # Create database tables if needed
    
    # Initialize and start APScheduler
    scheduler.init(bot)
    await scheduler.start_scheduler()
    
    print(f"✨ {bot.user} is now online!")
    print(f"🎨 Mai-san is ready to help with your art channel!")




# =============================================================================
# EVENT: MESSAGE RECEIVED
# =============================================================================

@bot.event
async def on_message(message: discord.Message):
    """
    Called automatically every time a message is sent in any channel the bot can see.
    
    This is the main handler for user interactions. It:
    1. Ignores messages from the bot itself (prevents infinite loops)
    2. Only responds when the bot is @mentioned
    3. Extracts the message text and any image attachments
    4. Sends everything to GPT for processing
    5. Executes any functions GPT wants to call
    6. Sends the response back to Discord
    
    Args:
        message: The Discord message object containing author, content, attachments, etc.
    """
    # ----- STEP 1: Filter out irrelevant messages -----
    
    # Don't respond to our own messages (prevents bot talking to itself)
    if message.author == bot.user:
        return
    
    # Only respond if the bot is @mentioned
    # This means users must type @Mai-san to trigger the bot
    if bot.user not in message.mentions:
        return
    
    # ----- STEP 2: Extract the user's message -----
    
    # Remove the @mention from the message to get just the text
    # e.g., "@Mai-san what should I draw?" → "what should I draw?"
    user_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
    
    # If user just @mentioned without any text (and no attachments), default to "hi"
    if not user_message and not message.attachments:
        user_message = "hi"
    
    # ----- STEP 3: Get context from database -----
    
    # Get the server ID (or user ID for DMs) to look up settings
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    
    # Get the user's display name (what GPT will see, not the numeric ID)
    username = message.author.display_name
    
    # Fetch current settings (post time, channel, etc.)
    settings = await db.get_settings(server_id)
    
    # Get short-term conversation history
    conversation_history = get_conversation_history(server_id)
    
    # ----- STEP 4: Handle image attachments -----
    
    # If user uploaded images (for art grading), download and convert to base64
    # GPT-5.2 vision can see these images and provide feedback
    image_urls = []
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            # Download the image and convert to base64 for GPT vision
            base64_url = await utils.download_image_as_base64(attachment.url)
            if base64_url:
                image_urls.append(base64_url)
    
    # ----- STEP 5: Fetch long-term memories -----
    
    # Get relevant memories for context (prioritizes current user + high importance)
    memories_raw = await db.get_memories_for_context(
        server_id,
        current_user=username,
        limit=MEMORIES_FOR_CONTEXT
    )
    long_term_memories = [m["memory"] for m in memories_raw]
    
    # ----- STEP 6: Call GPT and get response -----
    
    # Get channel ID for session tracking
    channel_id = str(message.channel.id)
    
    # Show "typing..." indicator while processing
    async with message.channel.typing():
        # Send message to GPT-5.2 (Mai-san's brain)
        response_text, function_calls = await gpt.chat_with_mai(
            user_message=user_message,
            username=username,
            conversation_history=conversation_history,
            current_settings=settings,
            image_urls=image_urls if image_urls else None,
            long_term_memories=long_term_memories,
            server_id=server_id,
            channel_id=channel_id
        )
        
        # ----- STEP 7: Execute functions (loop for chained calls) -----
        
        # Mai might call functions, see results, then call more functions
        # e.g., "What was yesterday's prompt?" → get_history → "Make today's similar"
        # Keep looping until Mai responds with text instead of more function calls
        all_results = []  # Accumulate results across chains
        
        for _ in range(MAX_FUNCTION_CHAIN_ITERATIONS):
            if not function_calls:
                break
            
            # Execute each function and collect results
            for fc in function_calls:
                result = await execute_function(
                    fc["name"],
                    fc["args"],
                    message,
                    settings
                )
                all_results.append({
                    "name": fc["name"],
                    "args": fc.get("args", {}),
                    "result": result,
                    "tool_call_id": fc["tool_call_id"]
                })
            
            # Refresh memories (in case save_memory was just called)
            memories_raw = await db.get_memories_for_context(
                server_id,
                current_user=username,
                limit=MEMORIES_FOR_CONTEXT
            )
            long_term_memories = [m["memory"] for m in memories_raw]
            
            # Call GPT again with results — might return more function calls or text
            response_text, function_calls = await gpt.chat_with_mai(
                user_message=user_message,
                username=username,
                conversation_history=conversation_history,
                current_settings=await db.get_settings(server_id),  # Refresh settings
                image_urls=image_urls if image_urls else None,
                function_result=all_results,
                long_term_memories=long_term_memories,
                server_id=server_id,
                channel_id=channel_id
            )
        
        # ----- STEP 8: Save to short-term memory -----
        
        # Save user message to history (including any images they shared)
        add_to_history(server_id, "user", user_message, username=username, images=image_urls if image_urls else None)
        
        # Save Mai's response to history
        add_to_history(server_id, "assistant", response_text, username="Mai")
        
        # ----- STEP 9: Reply -----
        
        # Send the response back to Discord
        if response_text:
            await message.reply(response_text)
        else:
            # Edge case: GPT kept calling functions without responding
            await message.reply("...give me a second.")


# =============================================================================
# FUNCTION EXECUTOR
# =============================================================================

@observe(name="execute_function")
async def execute_function(name: str, args: dict, message: discord.Message, settings: dict) -> str:
    """
    Execute a function that GPT decided to call.
    
    Dispatches to the appropriate handler function based on the Function enum.
    All handler implementations live in bot/handlers.py for cleaner separation.
    
    Args:
        name: The function name GPT wants to call (matches Function enum values)
        args: The arguments GPT provided (parsed from JSON)
        message: The Discord message (for context like server/channel)
        settings: Current server settings
        
    Returns:
        A string describing the result (fed back to GPT for natural response)
    """
    from bot.handlers import HANDLERS
    
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    
    handler = HANDLERS.get(name)
    if not handler:
        return json.dumps({"ok": False, "error": f"Function '{name}' not recognized"})

    result = await handler(
        server_id=server_id,
        args=args,
        settings=settings,
        message=message,
    )

    # Always return machine-readable JSON to the model.
    # Handlers may return str (legacy) or dict/list (preferred).
    if isinstance(result, (dict, list)):
        return json.dumps({"ok": True, "data": result})

    return json.dumps({"ok": True, "message": str(result)})


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    This block runs when you execute: python main.py
    
    It:
    1. Validates that required environment variables exist
    2. Registers cleanup handlers for graceful shutdown
    3. Starts the bot and connects to Discord
    """
    # Get the Discord token from environment variables
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Error: DISCORD_TOKEN not found in .env file")
        exit(1)
    
    # Verify OpenAI API key exists
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in .env file")
        exit(1)
    
    # Register graceful shutdown handler
    # This runs when the program exits (Ctrl+C, errors, etc.)
    atexit.register(scheduler.shutdown)
    
    # Start the bot! This blocks forever (until you Ctrl+C)
    bot.run(token)
