import discord
from discord.ext import tasks
import os
from datetime import datetime
from dotenv import load_dotenv
import pytz

import database as db
import gpt

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  # Required for reading messages

bot = discord.Client(intents=intents)

EST = pytz.timezone("America/New_York")


@bot.event
async def on_ready():
    """Called when bot is ready."""
    await db.init_db()
    daily_prompt_check.start()
    print(f"✨ {bot.user} is now online!")
    print(f"🎨 Mai-san is ready to help with your art channel!")


@bot.event
async def on_message(message: discord.Message):
    """Handle incoming messages."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Only respond if bot is mentioned
    if bot.user not in message.mentions:
        return
    
    # Remove the mention from the message content
    user_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
    
    if not user_message and not message.attachments:
        user_message = "hi"
    
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    user_id = str(message.author.id)
    
    # Get current settings and conversation history
    settings = await db.get_settings(server_id)
    conversation_history = await db.get_recent_conversation(server_id)
    
    # Handle image attachments (for grading drawings)
    image_urls = []
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            # Download and convert to base64 for GPT-4o vision
            base64_url = await gpt.download_image_as_base64(attachment.url)
            if base64_url:
                image_urls.append(base64_url)
    
    async with message.channel.typing():
        # Chat with Mai
        response_text, function_call = await gpt.chat_with_mai(
            user_message=user_message,
            conversation_history=conversation_history,
            current_settings=settings,
            image_urls=image_urls if image_urls else None
        )
        
        # If GPT wants to call a function, execute it
        if function_call:
            function_result = await execute_function(
                function_call["name"],
                function_call["args"],
                message,
                settings
            )
            
            # Get Mai's natural response after function execution
            response_text = await gpt.get_mai_response_after_function(
                function_name=function_call["name"],
                function_result=function_result,
                tool_call_id=function_call["tool_call_id"],
                original_messages=conversation_history,
                user_message=user_message,
                current_settings=await db.get_settings(server_id)  # Refresh settings
            )
        
        # Save conversation
        await db.save_message(server_id, user_id, "user", user_message)
        await db.save_message(server_id, user_id, "assistant", response_text)
        
        # Send response
        await message.reply(response_text)


async def execute_function(name: str, args: dict, message: discord.Message, settings: dict) -> str:
    """Execute a function called by GPT and return the result."""
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    
    if name == "generate_prompt":
        theme = args.get("theme") or settings.get("current_theme")
        prompt = await gpt.generate_creative_prompt(theme)
        await db.save_prompt(server_id, prompt, theme)
        
        # Decrement theme days if using a theme
        if settings.get("theme_days_remaining", 0) > 0:
            await db.decrement_theme_days(server_id)
        
        return f"Generated prompt: {prompt}"
    
    elif name == "set_theme":
        theme = args["theme"]
        days = args.get("days", 7)
        await db.update_settings(server_id, current_theme=theme, theme_days_remaining=days)
        return f"Theme set to '{theme}' for {days} days"
    
    elif name == "set_schedule":
        time = args["time"]
        await db.update_settings(server_id, post_time=time)
        return f"Daily prompt time set to {time} EST"
    
    elif name == "set_channel":
        channel_name = args["channel_name"].lower().replace("#", "")
        
        # Find the channel
        guild = message.guild
        if guild:
            channel = discord.utils.find(
                lambda c: c.name.lower() == channel_name, 
                guild.text_channels
            )
            if channel:
                await db.update_settings(server_id, channel_id=str(channel.id))
                return f"Daily prompts will now be posted to #{channel.name}"
            else:
                return f"Could not find channel '{channel_name}'"
        return "Could not set channel (not in a server)"
    
    elif name == "get_history":
        days = args.get("days", 7)
        history = await db.get_prompt_history(server_id, days)
        
        if not history:
            return "No prompts found in history"
        
        history_text = "\n".join([
            f"- {p['created_at'][:10]}: {p['prompt_text']}" + 
            (f" (theme: {p['theme']})" if p['theme'] else "")
            for p in history
        ])
        return f"Recent prompts:\n{history_text}"
    
    elif name == "get_current_settings":
        return f"""Current settings:
- Daily prompt time: {settings.get('post_time', '09:00')} EST
- Current theme: {settings.get('current_theme') or 'None (random prompts)'}
- Theme days remaining: {settings.get('theme_days_remaining', 0)}
- Prompt channel: {'Set' if settings.get('channel_id') else 'Not configured yet'}"""
    
    return "Function not recognized"


@tasks.loop(minutes=1)
async def daily_prompt_check():
    """Check if it's time to post daily prompts for any server."""
    now = datetime.now(EST)
    current_time = now.strftime("%H:%M")
    
    servers = await db.get_all_servers_for_posting()
    
    for server_settings in servers:
        if server_settings["post_time"] == current_time:
            # Check if we already posted today
            server_id = server_settings["server_id"]
            todays_prompt = await db.get_todays_prompt(server_id)
            
            if todays_prompt:
                continue  # Already posted today
            
            # Generate and post prompt
            channel_id = server_settings["channel_id"]
            channel = bot.get_channel(int(channel_id))
            
            if channel:
                theme = server_settings.get("current_theme")
                prompt = await gpt.generate_creative_prompt(theme)
                await db.save_prompt(server_id, prompt, theme)
                
                # Decrement theme days
                if server_settings.get("theme_days_remaining", 0) > 0:
                    await db.decrement_theme_days(server_id)
                
                # Format the message
                embed = discord.Embed(
                    title="🎨 Today's Drawing Prompt",
                    description=prompt,
                    color=discord.Color.from_rgb(255, 182, 193)  # Soft pink
                )
                if theme:
                    embed.set_footer(text=f"Theme: {theme}")
                
                await channel.send(embed=embed)


@daily_prompt_check.before_loop
async def before_daily_check():
    """Wait for bot to be ready before starting the loop."""
    await bot.wait_until_ready()


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Error: DISCORD_TOKEN not found in .env file")
        exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in .env file")
        exit(1)
    
    bot.run(token)
