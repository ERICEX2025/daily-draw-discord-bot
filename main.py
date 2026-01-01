"""
main.py — Bot Entry Point & Discord Event Handlers

This is the main file that runs Mai-san. It handles:
1. Connecting to Discord
2. Listening for @mentions
3. Processing messages and images
4. Executing functions that GPT requests
5. Running the daily prompt scheduler

Flow:
    User @mentions bot → on_message() → gpt.chat_with_mai() → 
    execute_function() (if needed) → reply to user
"""

import discord
from discord.ext import tasks
import os
from datetime import datetime
from dotenv import load_dotenv
import pytz

import database as db
import gpt

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

# Timezone for daily prompt scheduling (Eastern Standard Time)
EST = pytz.timezone("America/New_York")


# =============================================================================
# EVENT: BOT READY
# =============================================================================

@bot.event
async def on_ready():
    """
    Called automatically when the bot successfully connects to Discord.
    
    This runs once at startup and:
    1. Initializes the database (creates tables if they don't exist)
    2. Starts the daily prompt scheduler loop
    3. Prints a confirmation message
    """
    await db.init_db()  # Create database tables if needed
    daily_prompt_check.start()  # Start the scheduler loop
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
    user_id = str(message.author.id)
    
    # Fetch current settings (post time, theme, etc.) and recent conversation history
    settings = await db.get_settings(server_id)
    conversation_history = await db.get_recent_conversation(server_id)
    
    # ----- STEP 4: Handle image attachments -----
    
    # If user uploaded images (for art grading), download and convert to base64
    # GPT-5.2 vision can see these images and provide feedback
    image_urls = []
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            # Download the image and convert to base64 for GPT vision
            base64_url = await gpt.download_image_as_base64(attachment.url)
            if base64_url:
                image_urls.append(base64_url)
    
    # ----- STEP 5: Call GPT and get response -----
    
    # Show "typing..." indicator while processing
    async with message.channel.typing():
        # Send message to GPT-5.2 (Mai-san's brain)
        response_text, function_call = await gpt.chat_with_mai(
            user_message=user_message,
            conversation_history=conversation_history,
            current_settings=settings,
            image_urls=image_urls if image_urls else None
        )
        
        # ----- STEP 6: Execute function if GPT requested one -----
        
        # GPT might decide to call a function like "generate_prompt" or "set_theme"
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
        
        # ----- STEP 7: Save conversation and reply -----
        
        # Save both messages to database for conversation history
        await db.save_message(server_id, user_id, "user", user_message)
        await db.save_message(server_id, user_id, "assistant", response_text)
        
        # Send the response back to Discord
        await message.reply(response_text)


# =============================================================================
# FUNCTION EXECUTOR
# =============================================================================

async def execute_function(name: str, args: dict, message: discord.Message, settings: dict) -> str:
    """
    Execute a function that GPT decided to call.
    
    GPT can call these functions based on user requests:
    - generate_prompt: Create a new drawing prompt
    - set_theme: Set a theme for upcoming prompts
    - set_schedule: Change the daily posting time
    - set_channel: Set which channel gets daily prompts
    - get_history: Retrieve past prompts
    - get_current_settings: Show current configuration
    
    Args:
        name: The function name GPT wants to call
        args: The arguments GPT provided (parsed from JSON)
        message: The Discord message (for context like server/channel)
        settings: Current server settings
        
    Returns:
        A string describing the result (fed back to GPT for natural response)
    """
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    
    # ----- GENERATE A NEW DRAWING PROMPT -----
    if name == "generate_prompt":
        # Use theme from args, or fall back to current server theme
        theme = args.get("theme") or settings.get("current_theme")
        
        # Generate a creative prompt using GPT
        prompt = await gpt.generate_creative_prompt(theme)
        
        # Save the prompt to database
        await db.save_prompt(server_id, prompt, theme)
        
        # Decrement theme days if we're using a limited theme
        if settings.get("theme_days_remaining", 0) > 0:
            await db.decrement_theme_days(server_id)
        
        return f"Generated prompt: {prompt}"
    
    # ----- SET A THEME FOR UPCOMING PROMPTS -----
    elif name == "set_theme":
        theme = args["theme"]
        days = args.get("days", 7)  # Default to 7 days
        
        # Update server settings with new theme
        await db.update_settings(server_id, current_theme=theme, theme_days_remaining=days)
        
        return f"Theme set to '{theme}' for {days} days"
    
    # ----- SET THE DAILY POSTING TIME -----
    elif name == "set_schedule":
        time = args["time"]  # Expected format: "HH:MM" (24-hour)
        
        # Update the posting time
        await db.update_settings(server_id, post_time=time)
        
        return f"Daily prompt time set to {time} EST"
    
    # ----- SET THE CHANNEL FOR DAILY PROMPTS -----
    elif name == "set_channel":
        channel_name = args["channel_name"].lower().replace("#", "")
        
        # Find the channel by name in this server
        guild = message.guild
        if guild:
            channel = discord.utils.find(
                lambda c: c.name.lower() == channel_name, 
                guild.text_channels
            )
            if channel:
                # Save the channel ID to settings
                await db.update_settings(server_id, channel_id=str(channel.id))
                return f"Daily prompts will now be posted to #{channel.name}"
            else:
                return f"Could not find channel '{channel_name}'"
        return "Could not set channel (not in a server)"
    
    # ----- GET PROMPT HISTORY -----
    elif name == "get_history":
        days = args.get("days", 7)
        
        # Fetch recent prompts from database
        history = await db.get_prompt_history(server_id, days)
        
        if not history:
            return "No prompts found in history"
        
        # Format the history as a readable list
        history_text = "\n".join([
            f"- {p['created_at'][:10]}: {p['prompt_text']}" + 
            (f" (theme: {p['theme']})" if p['theme'] else "")
            for p in history
        ])
        return f"Recent prompts:\n{history_text}"
    
    # ----- GET CURRENT SETTINGS -----
    elif name == "get_current_settings":
        return f"""Current settings:
- Daily prompt time: {settings.get('post_time', '09:00')} EST
- Current theme: {settings.get('current_theme') or 'None (random prompts)'}
- Theme days remaining: {settings.get('theme_days_remaining', 0)}
- Prompt channel: {'Set' if settings.get('channel_id') else 'Not configured yet'}"""
    
    return "Function not recognized"


# =============================================================================
# DAILY PROMPT SCHEDULER
# =============================================================================

@tasks.loop(minutes=1)
async def daily_prompt_check():
    """
    Background task that runs every minute to check if it's time to post daily prompts.
    
    This loop:
    1. Gets the current time in EST
    2. Fetches all servers that have a channel configured
    3. For each server, checks if current time matches their post_time
    4. If it does AND we haven't posted today, generates and posts a prompt
    
    This ensures prompts are posted automatically without user interaction.
    """
    # Get current time in EST (e.g., "09:00")
    now = datetime.now(EST)
    current_time = now.strftime("%H:%M")
    
    # Get all servers that have configured a channel for daily prompts
    servers = await db.get_all_servers_for_posting()
    
    for server_settings in servers:
        # Check if it's time to post for this server
        if server_settings["post_time"] == current_time:
            server_id = server_settings["server_id"]
            
            # Check if we already posted today (prevents duplicate posts)
            todays_prompt = await db.get_todays_prompt(server_id)
            if todays_prompt:
                continue  # Already posted today, skip
            
            # Get the channel to post in
            channel_id = server_settings["channel_id"]
            channel = bot.get_channel(int(channel_id))
            
            if channel:
                # Generate a prompt (with current theme if set)
                theme = server_settings.get("current_theme")
                prompt = await gpt.generate_creative_prompt(theme)
                
                # Save the prompt to database
                await db.save_prompt(server_id, prompt, theme)
                
                # Decrement theme days if using a limited theme
                if server_settings.get("theme_days_remaining", 0) > 0:
                    await db.decrement_theme_days(server_id)
                
                # Create a pretty embed message
                embed = discord.Embed(
                    title="🎨 Today's Drawing Prompt",
                    description=prompt,
                    color=discord.Color.from_rgb(255, 182, 193)  # Soft pink
                )
                if theme:
                    embed.set_footer(text=f"Theme: {theme}")
                
                # Send the prompt to the channel
                await channel.send(embed=embed)


@daily_prompt_check.before_loop
async def before_daily_check():
    """
    Runs once before the daily_prompt_check loop starts.
    Waits until the bot is fully connected to Discord before starting.
    """
    await bot.wait_until_ready()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    This block runs when you execute: python main.py
    
    It:
    1. Validates that required environment variables exist
    2. Starts the bot and connects to Discord
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
    
    # Start the bot! This blocks forever (until you Ctrl+C)
    bot.run(token)
