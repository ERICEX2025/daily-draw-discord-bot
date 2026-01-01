"""
gpt.py — OpenAI GPT-5.2 Integration

This file handles all AI-related functionality:
1. Mai-san's personality (system prompt)
2. Function definitions (tools GPT can call)
3. Chat completions with function calling
4. Image vision for art grading
5. Prompt generation

Key Concepts:
- System Prompt: Defines Mai-san's personality and behavior rules
- Function Calling: GPT can decide to call functions like "set_theme" or "generate_prompt"
- Vision: GPT-5.2 can see images and provide feedback on artwork

Reference: https://cookbook.openai.com/examples/gpt-5/gpt-5-2_prompting_guide
"""

import os
import json
import base64
import httpx
from openai import AsyncOpenAI
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (specifically OPENAI_API_KEY)
# This MUST happen before creating the client
load_dotenv()

# =============================================================================
# OPENAI CLIENT SETUP
# =============================================================================

# Create the async OpenAI client
# AsyncOpenAI is used because Discord.py is async (non-blocking)
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# The model to use for all requests
# GPT-5.2 is OpenAI's flagship model (as of Dec 2025)
MODEL = "gpt-5.2"


# =============================================================================
# MAI-SAN'S PERSONALITY (SYSTEM PROMPT)
# =============================================================================

# This system prompt defines who Mai-san is and how she behaves.
# It uses XML-style tags for clear section boundaries (GPT-5.2 best practice).
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


# =============================================================================
# FUNCTION DEFINITIONS (TOOLS)
# =============================================================================

# These are the "tools" that GPT can decide to call.
# GPT reads the descriptions and decides when to use them based on user requests.
# The actual execution happens in main.py's execute_function()

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
            "required": []  # Theme is optional
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
            "required": ["theme"]  # Theme is required, days has a default
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
            "properties": {},  # No parameters needed
            "required": []
        }
    }
]


# =============================================================================
# PROMPT GENERATION
# =============================================================================

async def generate_creative_prompt(theme: Optional[str] = None) -> str:
    """
    Generate a creative drawing prompt using GPT-5.2.
    
    This is a simple, focused API call just for generating prompts.
    It uses a minimal system prompt to get concise, creative output.
    
    Args:
        theme: Optional theme to guide the prompt (e.g., "food", "fantasy")
        
    Returns:
        A creative drawing prompt string (1-2 sentences)
        
    Example:
        >>> await generate_creative_prompt("food")
        "A chef discovering a secret ingredient in grandma's recipe book"
    """
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
        max_tokens=100  # Prompts should be short
    )
    
    return response.choices[0].message.content.strip()


# =============================================================================
# MAIN CHAT FUNCTION
# =============================================================================

async def chat_with_mai(
    user_message: str,
    conversation_history: list[dict],
    current_settings: dict,
    image_urls: Optional[list[str]] = None
) -> tuple[str, Optional[dict]]:
    """
    Main function to chat with Mai-san.
    
    This sends the user's message to GPT-5.2 along with:
    - Mai-san's personality (system prompt)
    - Current context (date, settings)
    - Recent conversation history
    - Any images the user uploaded
    - Available functions (tools)
    
    GPT can respond in two ways:
    1. Direct text response → returns (response_text, None)
    2. Function call request → returns (None, function_details)
    
    Args:
        user_message: What the user said
        conversation_history: Recent messages for context
        current_settings: Server settings (theme, post time, etc.)
        image_urls: Optional list of base64 image URLs for vision
        
    Returns:
        Tuple of (response_text, function_call)
        - If function_call is None, use response_text directly
        - If function_call is not None, execute the function first
    """
    
    # ----- BUILD CONTEXT -----
    # Add current date/time and settings so Mai knows the context
    now = datetime.now()
    context = f"""
Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} EST
Current settings:
- Daily prompt time: {current_settings.get('post_time', '09:00')} EST
- Current theme: {current_settings.get('current_theme') or 'None (random)'}
- Theme days remaining: {current_settings.get('theme_days_remaining', 0)}
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
"""
    
    # ----- BUILD MESSAGES ARRAY -----
    messages = [
        # System message: Mai's personality + current context
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}
    ]
    
    # Add recent conversation history (last 10 messages for context)
    # This helps Mai remember what was just discussed
    for msg in conversation_history[-10:]:
        messages.append({
            "role": msg["role"],  # "user" or "assistant"
            "content": msg["content"]
        })
    
    # ----- ADD CURRENT MESSAGE -----
    # If user uploaded images, use the vision format
    if image_urls:
        # Vision messages have a special format with text and images
        content = [{"type": "text", "text": user_message}]
        for url in image_urls:
            content.append({
                "type": "image_url",
                "image_url": {"url": url}  # base64 data URL
            })
        messages.append({"role": "user", "content": content})
    else:
        # Simple text message
        messages.append({"role": "user", "content": user_message})
    
    # ----- CALL GPT-5.2 -----
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        # Provide the functions as "tools" that GPT can call
        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
        tool_choice="auto",  # Let GPT decide whether to call a function
        max_tokens=500
    )
    
    message = response.choices[0].message
    
    # ----- CHECK FOR FUNCTION CALL -----
    # GPT might decide to call a function instead of responding directly
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        # Return function details for main.py to execute
        return None, {
            "name": function_name,
            "args": function_args,
            "tool_call_id": tool_call.id  # Needed for the follow-up response
        }
    
    # ----- DIRECT RESPONSE -----
    # No function call, just return Mai's response
    return message.content, None


# =============================================================================
# POST-FUNCTION RESPONSE
# =============================================================================

async def get_mai_response_after_function(
    function_name: str,
    function_result: str,
    tool_call_id: str,
    original_messages: list[dict],
    user_message: str,
    current_settings: dict
) -> str:
    """
    Get Mai's natural language response after a function has been executed.
    
    When GPT calls a function, we need to:
    1. Execute the function (done in main.py)
    2. Send the result back to GPT
    3. Get a natural response from Mai
    
    This function handles step 2-3. It reconstructs the conversation
    with the tool call and result, then gets Mai's response.
    
    Args:
        function_name: Name of the function that was called
        function_result: The string result from executing the function
        tool_call_id: ID from the original tool call (required by API)
        original_messages: Conversation history
        user_message: What the user originally said
        current_settings: Updated server settings
        
    Returns:
        Mai's natural language response
        
    Example:
        User: "give me a fantasy prompt"
        GPT calls: generate_prompt(theme="fantasy")
        Result: "Generated prompt: A dragon librarian..."
        Mai says: "Here's today's prompt: 'A dragon librarian...' 🐉📚 
                   Now get drawing, I expect to see something impressive."
    """
    
    # Build context (same as chat_with_mai)
    now = datetime.now()
    context = f"""
Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} EST
Current settings:
- Daily prompt time: {current_settings.get('post_time', '09:00')} EST
- Current theme: {current_settings.get('current_theme') or 'None (random)'}
- Theme days remaining: {current_settings.get('theme_days_remaining', 0)}
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
"""
    
    # Build the message sequence that led to this point
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}
    ]
    
    # Add conversation history
    for msg in original_messages[-8:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add the user's message that triggered the function call
    messages.append({"role": "user", "content": user_message})
    
    # Add the assistant's decision to call a function
    # This is the format GPT expects to see its own tool call
    messages.append({
        "role": "assistant",
        "content": None,  # No text content when calling a tool
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {"name": function_name, "arguments": "{}"}
        }]
    })
    
    # Add the function result
    # This tells GPT what happened when the function was executed
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": function_result
    })
    
    # Get Mai's response incorporating the function result
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=500
    )
    
    return response.choices[0].message.content


# =============================================================================
# IMAGE UTILITIES
# =============================================================================

async def download_image_as_base64(url: str) -> Optional[str]:
    """
    Download an image from a URL and convert it to a base64 data URL.
    
    Discord image URLs expire after a while, so we download the image
    immediately and convert it to base64. This ensures GPT can see the
    image even if there's a delay in processing.
    
    Args:
        url: The Discord CDN URL for the image
        
    Returns:
        A base64 data URL (e.g., "data:image/png;base64,...")
        or None if download failed
        
    Example:
        >>> await download_image_as_base64("https://cdn.discord.com/.../image.png")
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA..."
    """
    try:
        # Use httpx for async HTTP requests
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url)
            
            if response.status_code == 200:
                # Get the content type (e.g., "image/png")
                content_type = response.headers.get("content-type", "image/png")
                
                # Convert binary image data to base64
                base64_data = base64.b64encode(response.content).decode("utf-8")
                
                # Return as data URL that GPT can use
                return f"data:{content_type};base64,{base64_data}"
                
    except Exception as e:
        print(f"Error downloading image: {e}")
    
    return None
