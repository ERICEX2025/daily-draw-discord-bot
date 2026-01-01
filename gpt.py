import os
import json
import base64
import httpx
from openai import AsyncOpenAI
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load env vars before creating client
load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-5.2"

# Mai-san's personality system prompt (optimized for GPT-5.2)
# Reference: https://cookbook.openai.com/examples/gpt-5/gpt-5-2_prompting_guide
SYSTEM_PROMPT = """You are Sakurajima Mai from "Rascal Does Not Dream of Bunny Girl Senpai," helping run an art channel for a daily drawing challenge.

<persona>
- Composed, elegant, mature actress
- Sarcastic and teasing, but genuinely caring underneath
- Confident but humble — encourage people in your own cool way
- Blunt with feedback but always constructive
- Slightly tsundere — "It's not like I'm impressed or anything" while clearly being impressed
- Occasionally reference your acting career or the bunny girl outfit incident with mild exasperation
- Never break character
</persona>

<output_verbosity_spec>
- Default: 2-4 sentences for typical responses
- Simple questions (yes/no, confirmations): 1-2 sentences
- Art feedback: 1 short paragraph covering strengths, then improvements
- Avoid long narrative paragraphs; prefer natural conversational flow
- Use emojis sparingly (🎨 ✨ at most 1-2 per message)
</output_verbosity_spec>

<tool_calling_spec>
- Use provided functions when users ask about prompts, schedules, themes, history, or settings
- Execute tool calls without explaining that you're using tools
- After function results, respond naturally in character — don't narrate the process
- For ambiguous requests, choose the most likely interpretation rather than asking clarifying questions
</tool_calling_spec>

<art_feedback_spec>
When reviewing artwork:
1. Start with what works well (composition, colors, mood, technique)
2. Then suggest 1-2 specific improvements
3. Give an overall score or encouragement in your tsundere style
4. Be honest but constructive — never harsh without reason
</art_feedback_spec>

<uncertainty_handling>
- If a request is ambiguous, choose the most reasonable interpretation and proceed
- For schedule/setting changes, confirm what you understood before executing
- Never fabricate specific dates or history you don't have in context
</uncertainty_handling>

Current date/time context will be provided for temporal references."""


# Function definitions for GPT to call
FUNCTIONS = [
    {
        "name": "generate_prompt",
        "description": "Generate a new creative drawing prompt. Call this when someone asks for today's prompt, a new prompt, or drawing ideas.",
        "parameters": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "Optional theme category for the prompt (e.g., 'food', 'fantasy', 'nature', 'sci-fi', 'cozy'). If not specified, generate freely."
                }
            },
            "required": []
        }
    },
    {
        "name": "set_theme",
        "description": "Set a drawing theme for upcoming prompts for a number of days.",
        "parameters": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "The theme category (e.g., 'space', 'food', 'nature', 'fantasy')"
                },
                "days": {
                    "type": "integer",
                    "description": "How many days to use this theme. Default is 7."
                }
            },
            "required": ["theme"]
        }
    },
    {
        "name": "set_schedule",
        "description": "Set the daily prompt posting time.",
        "parameters": {
            "type": "object",
            "properties": {
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM format (24-hour), e.g., '09:00' or '21:30'"
                }
            },
            "required": ["time"]
        }
    },
    {
        "name": "set_channel",
        "description": "Set which channel daily prompts should be posted to.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel_name": {
                    "type": "string",
                    "description": "The name of the channel to post daily prompts to"
                }
            },
            "required": ["channel_name"]
        }
    },
    {
        "name": "get_history",
        "description": "Retrieve past drawing prompts.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many past prompts to retrieve. Default is 7."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_current_settings",
        "description": "Get the current settings for the art channel (posting time, theme, etc.).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


async def generate_creative_prompt(theme: Optional[str] = None) -> str:
    """Generate a creative drawing prompt using GPT-5.2."""
    theme_instruction = f"Theme: {theme}" if theme else "Theme: Any creative theme"
    
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a creative art prompt generator. Output ONLY the prompt itself, 1-2 sentences. Be specific, evocative, and inspiring. No preamble or explanation."
            },
            {
                "role": "user",
                "content": f"Generate a drawing prompt. {theme_instruction}"
            }
        ],
        max_tokens=100
    )
    
    return response.choices[0].message.content.strip()


async def chat_with_mai(
    user_message: str,
    conversation_history: list[dict],
    current_settings: dict,
    image_urls: Optional[list[str]] = None
) -> tuple[str, Optional[dict]]:
    """
    Chat with Mai-san. Returns (response_text, function_call_if_any).
    
    If GPT wants to call a function, returns the function details for the bot to execute.
    """
    
    # Build context about current state
    now = datetime.now()
    context = f"""
Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} EST
Current settings:
- Daily prompt time: {current_settings.get('post_time', '09:00')} EST
- Current theme: {current_settings.get('current_theme') or 'None (random)'}
- Theme days remaining: {current_settings.get('theme_days_remaining', 0)}
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
"""
    
    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}
    ]
    
    # Add conversation history
    for msg in conversation_history[-10:]:  # Last 10 messages for context
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current message (with images if present)
    if image_urls:
        content = [{"type": "text", "text": user_message}]
        for url in image_urls:
            # Handle both URLs and base64
            if url.startswith("data:"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url}
                })
            else:
                content.append({
                    "type": "image_url", 
                    "image_url": {"url": url}
                })
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_message})
    
    # Call GPT-5.2 with function calling
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
        tool_choice="auto",
        max_tokens=500
    )
    
    message = response.choices[0].message
    
    # Check if GPT wants to call a function
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        return None, {
            "name": function_name,
            "args": function_args,
            "tool_call_id": tool_call.id
        }
    
    # Regular response
    return message.content, None


async def get_mai_response_after_function(
    function_name: str,
    function_result: str,
    tool_call_id: str,
    original_messages: list[dict],
    user_message: str,
    current_settings: dict
) -> str:
    """Get Mai's natural response after a function has been executed."""
    
    now = datetime.now()
    context = f"""
Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} EST
Current settings:
- Daily prompt time: {current_settings.get('post_time', '09:00')} EST
- Current theme: {current_settings.get('current_theme') or 'None (random)'}
- Theme days remaining: {current_settings.get('theme_days_remaining', 0)}
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}
    ]
    
    # Add conversation history
    for msg in original_messages[-8:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    messages.append({"role": "user", "content": user_message})
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {"name": function_name, "arguments": "{}"}
        }]
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": function_result
    })
    
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=500
    )
    
    return response.choices[0].message.content


async def download_image_as_base64(url: str) -> Optional[str]:
    """Download an image and convert to base64 data URL."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/png")
                base64_data = base64.b64encode(response.content).decode("utf-8")
                return f"data:{content_type};base64,{base64_data}"
    except Exception as e:
        print(f"Error downloading image: {e}")
    return None

