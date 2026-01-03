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

from bot.personality import CHARACTER, FUNCTIONS, Function
from bot.config import MODEL, MAX_PROMPT_TOKENS, MAX_CHAT_TOKENS, MAX_SHORT_TERM_MESSAGES


# Load environment variables (specifically OPENAI_API_KEY)
# This MUST happen before creating the client
load_dotenv()

# =============================================================================
# OPENAI CLIENT SETUP
# =============================================================================

# Create the async OpenAI client
# AsyncOpenAI is used because Discord.py is async (non-blocking)
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =============================================================================
# PROMPT GENERATION
# =============================================================================

async def generate_daily_prompt(
    recent_prompts: Optional[list[dict]] = None,
    theme: str = "anime and video game inspired",
    memories: Optional[list[str]] = None,
    recent_messages: Optional[list[dict]] = None
) -> tuple[str, str]:
    """
    Have Mai generate and present a drawing prompt.
    
    Mai creates the prompt herself (influenced by her taste) and presents it
    in her voice. Returns both the raw prompt (for database) and her full message.
    
    Args:
        recent_prompts: List of dicts with {"date": "YYYY-MM-DD", "prompt": "..."}
        theme: The theme/style for prompts
        memories: Long-term memories about the server/users
        recent_messages: Recent conversation messages for context
        
    Returns:
        Tuple of (raw_prompt, mai_message)
        - raw_prompt: Just the prompt text (for saving to database)
        - mai_message: Mai's full presentation (for sending to Discord)
    """
    # Build context about recent prompts to avoid repeats (with dates)
    if recent_prompts:
        prompt_list = "\n".join(f"- {p['date']}: {p['prompt']}" for p in recent_prompts)
        recent_context = f"\n\nRecent prompts (avoid repeating these):\n{prompt_list}"
    else:
        recent_context = ""
    
    # Build memories context
    memories_context = ""
    if memories:
        memories_list = "\n".join(f"- {m}" for m in memories)
        memories_context = f"\n\nThings you remember about this server:\n{memories_list}"
    
    # Build recent conversation context
    conversation_context = ""
    if recent_messages:
        convo_list = "\n".join(f"- {m.get('username', 'Someone')}: {m['content']}" for m in recent_messages)
        conversation_context = f"\n\nRecent conversations (feel free to reference or play off these):\n{convo_list}"
    
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": CHARACTER
            },
            {
                "role": "user",
                "content": f"""It's time to post today's daily drawing prompt! The theme is: {theme}.

Come up with a SHORT, simple prompt — just a fun concept in a few words. Examples:
- "Snorlax as an ice cream"
- "Hori from Horimiya"
- "A mage who's bad at magic"
- "Pikachu in a hoodie"

Keep the prompt simple and open to interpretation. Don't over-describe or add too many details.

Present it with a short message in YOUR voice — dry, slightly teasing, maybe a little sarcastic. Something like:
- "today's prompt: 'a tired swordsman.' ...no, drawing me doesn't count."
- "here's today's prompt. try not to disappoint me."
- "prompt's up. 'cozy dragon.' don't overthink it."

Keep it brief (1-2 sentences). Don't be overly enthusiastic or use lots of exclamation points. You're too cool for that.{recent_context}{memories_context}{conversation_context}

Respond with JSON in this exact format:
{{
    "prompt": "The short, simple prompt",
    "message": "Your brief message including the prompt"
}}"""
            }
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=MAX_PROMPT_TOKENS
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
    image_urls: Optional[list[str]] = None,
    function_result: Optional[dict] = None,  # For post-function responses
    long_term_memories: Optional[list[str]] = None  # Recent memories to inject
) -> tuple[str, Optional[dict]]:
    """
    Main function to chat with Mai-san.
    
    This sends the user's message to GPT-5.2 along with:
    - Mai-san's personality (system prompt)
    - Current context (date, settings)
    - Recent conversation history
    - Any images the user uploaded
    - Available functions (tools) — unless responding to a function result
    
    Two modes:
    1. Normal chat (function_result=None): Can return function calls
    2. Post-function (function_result provided): Just responds to the results
    
    Args:
        user_message: What the user said
        username: The display name of the user (e.g., "Alice")
        conversation_history: Recent messages for context
        current_settings: Server settings (theme, post time, etc.)
        image_urls: Optional list of base64 image URLs for vision
        function_result: Optional dict or list of dicts with {name, result, tool_call_id}
        
    Returns:
        Tuple of (response_text, function_calls)
        - If function_calls is None, use response_text directly
        - If function_calls is a list, execute each function first
    """
    
    # ----- BUILD CONTEXT -----
    now = datetime.now()
    
    paused_until = current_settings.get('paused_until')
    pause_status = f"Paused until {paused_until[:10]}" if paused_until else "Active"
    
    # Build memories section if any exist
    memories_section = ""
    if long_term_memories:
        memories_text = "\n".join(f"- {m}" for m in long_term_memories[:10])
        memories_section = f"\n\nThings you remember:\n{memories_text}"
    
    context = f"""
Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} EST
Current settings:
- Daily prompt time: {current_settings.get('post_time', '09:00')} EST
- Prompt channel: {'Configured' if current_settings.get('channel_id') else 'Not set yet'}
- Theme: {current_settings.get('theme', 'anime and video game inspired')}
- Status: {pause_status}{memories_section}
"""
    
    # ----- BUILD MESSAGES ARRAY -----
    messages = [
        {"role": "system", "content": f"{CHARACTER}\n\n{context}"}
    ]
    
    # Add conversation history (with images if present)
    for msg in conversation_history[-MAX_SHORT_TERM_MESSAGES:]:
        msg_username = msg.get("username", "Unknown")
        # Only prefix usernames for user messages.
        # Prefixing assistant messages with "Mai:" teaches the model to emit name prefixes.
        if msg.get("role") == "user":
            content_with_name = f"{msg_username}: {msg['content']}"
        else:
            content_with_name = msg["content"]
        
        # Check if this message has images attached
        if msg.get("images"):
            content = [{"type": "text", "text": content_with_name}]
            for img_url in msg["images"]:
                content.append({"type": "image_url", "image_url": {"url": img_url}})
            messages.append({"role": msg["role"], "content": content})
        else:
            messages.append({"role": msg["role"], "content": content_with_name})
    
    # ----- ADD CURRENT USER MESSAGE -----
    user_message_with_name = f"{username}: {user_message}"
    
    if image_urls:
        content = [{"type": "text", "text": user_message_with_name}]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_message_with_name})
    
    # ----- IF POST-FUNCTION: Add tool calls + results -----
    # function_result can be a single dict or a list of dicts (for multiple calls)
    if function_result:
        # Normalize to list
        results = function_result if isinstance(function_result, list) else [function_result]
        
        # Add the assistant's tool calls (all at once)
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": r["tool_call_id"],
                    "type": "function",
                    "function": {"name": r["name"], "arguments": json.dumps(r.get("args", {}))}
                }
                for r in results
            ]
        })
        
        # Add each function result
        for r in results:
            messages.append({
                "role": "tool",
                "tool_call_id": r["tool_call_id"],
                "content": r["result"]
            })
    
    # ----- CALL GPT (with tools so Mai can chain calls) -----
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
        tool_choice="auto",
        max_completion_tokens=MAX_CHAT_TOKENS
    )
    
    message = response.choices[0].message
    
    # Check for function calls (can be multiple, or chained after previous calls)
    if message.tool_calls:
        return None, [
            {
                "name": tc.function.name,
                "args": json.loads(tc.function.arguments),
                "tool_call_id": tc.id
            }
            for tc in message.tool_calls
        ]
    
    return message.content, None
