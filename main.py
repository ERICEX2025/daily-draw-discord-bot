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
from dotenv import load_dotenv

from bot import database as db
from bot import gpt
from bot import utils
from bot import scheduler

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
    conversation_history = []  # MVP: no conversation memory
    
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
    
    # ----- STEP 5: Call GPT and get response -----
    
    # Show "typing..." indicator while processing
    async with message.channel.typing():
        # Send message to GPT-5.2 (Mai-san's brain)
        response_text, function_call = await gpt.chat_with_mai(
            user_message=user_message,
            username=username,
            conversation_history=conversation_history,
            current_settings=settings,
            image_urls=image_urls if image_urls else None
        )
        
        # ----- STEP 6: Execute function if GPT requested one -----
        
        # GPT might decide to call a function like "set_channel" or "set_schedule"
        # If so, we execute it here and then get GPT's natural language response
        if function_call:
            # Execute the function (e.g., save to database, generate prompt)
            function_result = await execute_function(
                function_call["name"],
                function_call["args"],
                message,
                settings
            )
            
            # Get Mai's natural response after the function executed
            # e.g., "Here's your prompt: ..." instead of just the raw data
            response_text = await gpt.get_mai_response_after_function(
                function_name=function_call["name"],
                function_result=function_result,
                tool_call_id=function_call["tool_call_id"],
                original_messages=conversation_history,
                user_message=user_message,
                current_settings=await db.get_settings(server_id)  # Refresh settings
            )
        
        # ----- STEP 7: Reply -----
        
        # Send the response back to Discord
        await message.reply(response_text)


# =============================================================================
# FUNCTION EXECUTOR
# =============================================================================

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
    if handler:
        return await handler(
            server_id=server_id,
            args=args,
            settings=settings,
            message=message,
        )
    
    return f"Function '{name}' not recognized"


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
