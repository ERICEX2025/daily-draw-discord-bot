"""
gpt.py — OpenAI GPT-5.2 Integration

This file handles all AI-related functionality:
1. OpenAI client setup
2. Chat completions with function calling
3. Prompt generation

The personality and function definitions live in personality.py.
Image utilities live in utils.py.

Reference: https://cookbook.openai.com/examples/gpt-5/gpt-5-2_prompting_guide
"""

import os
import json
from openai import AsyncOpenAI
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from bot.personality import CHARACTER, TOOL_INSTRUCTIONS, FUNCTIONS, Function


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
# PROMPT GENERATION
# =============================================================================

async def generate_daily_prompt(
    recent_prompts: Optional[list[dict]] = None,
    theme: str = "anime and video game inspired"
) -> tuple[str, str]:
    """
    Have Mai generate and present a drawing prompt.
    
    Mai creates the prompt herself (influenced by her taste) and presents it
    in her voice. Returns both the raw prompt (for database) and her full message.
    
    Args:
        recent_prompts: List of dicts with {"date": "YYYY-MM-DD", "prompt": "..."}
        
    Returns:
        Tuple of (raw_prompt, mai_message)
        - raw_prompt: Just the prompt text (for saving to database)
        - mai_message: Mai's full presentation (for sending to Discord)
    """
    # Build context about recent prompts to avoid repeats (with dates)
    if recent_prompts:
        prompt_list = "\n".join(f"- {p['date']}: {p['prompt']}" for p in recent_prompts)
        recent_context = f"\n\nRecent prompts (don't repeat these):\n{prompt_list}"
    else:
        recent_context = ""
    
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": CHARACTER
            },
            {
                "role": "user",
                "content": f"""It's time to post today's daily drawing prompt for the art channel! The theme is: {theme}. Pick something fun and creative that fits!

Come up with a creative prompt (1-2 sentences, specific and evocative).
Present it to everyone in your voice — maybe add some encouragement or a comment.
Keep it to 2-4 sentences total.{recent_context}

Respond with JSON in this exact format:
{{
    "prompt": "The drawing prompt itself (just the prompt, no fluff)",
    "message": "Your full message to post in Discord (including the prompt, with your personality)"
}}"""
            }
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=300
    )
    
    # Parse the JSON response
    content = response.choices[0].message.content.strip()
    data = json.loads(content)
    
    raw_prompt = data["prompt"]
    mai_message = data["message"]
    
    return raw_prompt, mai_message


# =============================================================================
# MAIN CHAT FUNCTION
# =============================================================================

async def chat_with_mai(
    user_message: str,
    username: str,
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
        username: The display name of the user (e.g., "Alice")
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
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
"""
    
    # ----- BUILD MESSAGES ARRAY -----
    messages = [
        # System message: Mai's personality + current context
        {"role": "system", "content": f"{CHARACTER}\n\n{TOOL_INSTRUCTIONS}\n\n{context}"}
    ]
    
    # Add recent conversation history (last 10 messages for context)
    # This helps Mai remember what was just discussed
    # Include username so Mai knows who said what (e.g., "Alice: give me a prompt")
    for msg in conversation_history[-10:]:
        # Prefix content with username so GPT knows who's speaking
        msg_username = msg.get("username", "Unknown")
        content_with_name = f"{msg_username}: {msg['content']}"
        messages.append({
            "role": msg["role"],  # "user" or "assistant"
            "content": content_with_name
        })
    
    # ----- ADD CURRENT MESSAGE -----
    # Include username so GPT knows who's asking
    user_message_with_name = f"{username}: {user_message}"
    
    # If user uploaded images, use the vision format
    if image_urls:
        # Vision messages have a special format with text and images
        content = [{"type": "text", "text": user_message_with_name}]
        for url in image_urls:
            content.append({
                "type": "image_url",
                "image_url": {"url": url}  # base64 data URL
            })
        messages.append({"role": "user", "content": content})
    else:
        # Simple text message
        messages.append({"role": "user", "content": user_message_with_name})
    
    # ----- CALL GPT-5.2 -----
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        # Provide the functions as "tools" that GPT can call
        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
        tool_choice="auto",  # Let GPT decide whether to call a function
        max_completion_tokens=500
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
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
"""
    
    # Build the message sequence that led to this point
    messages = [
        {"role": "system", "content": f"{CHARACTER}\n\n{TOOL_INSTRUCTIONS}\n\n{context}"}
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
        max_completion_tokens=500
    )
    
    return response.choices[0].message.content

