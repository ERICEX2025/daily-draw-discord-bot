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
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from bot.personality import CHARACTER, FUNCTIONS, Function
from bot.config import MODEL, MAX_PROMPT_TOKENS, MAX_CHAT_TOKENS, MAX_SHORT_TERM_MESSAGES


# Load environment variables (specifically OPENAI_API_KEY)
# This MUST happen before creating the client
load_dotenv()

# =============================================================================
# OPENAI CLIENT SETUP (with Langfuse Observability)
# =============================================================================

# Check if Langfuse is configured
_langfuse_enabled = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

if _langfuse_enabled:
    try:
        from langfuse.openai import AsyncOpenAI  # Wrapped client for auto-tracing
        from langfuse import observe
        print("🔍 Langfuse observability enabled")
    except ImportError as e:
        print(f"⚠️ Langfuse import failed: {e}")
        from openai import AsyncOpenAI
        def observe(name=None, capture_input=True, capture_output=True):
            def decorator(func):
                return func
            return decorator
        _langfuse_enabled = False
else:
    from openai import AsyncOpenAI
    def observe(name=None, capture_input=True, capture_output=True):
        def decorator(func):
            return func
        return decorator
    print("📊 Langfuse not configured - set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")

# Create the async OpenAI client
# AsyncOpenAI is used because Discord.py is async (non-blocking)
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =============================================================================
# PROMPT GENERATION
# =============================================================================

@observe(name="generate_daily_prompt", capture_input=False, capture_output=False)
async def generate_daily_prompt(
    recent_prompts: Optional[list[dict]] = None,
    theme: str = "anime and video game inspired",
    memories: Optional[list[str]] = None,
    recent_messages: Optional[list[dict]] = None,
    server_id: Optional[str] = None,  # For Langfuse session tracking
    hint: Optional[str] = None  # User guidance like "JJK character", "something cozy"
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
        hint: Optional user guidance for the prompt (e.g., "JJK character")
        
    Returns:
        Tuple of (raw_prompt, mai_message)
        - raw_prompt: Just the prompt text (for saving to database)
        - mai_message: Mai's full presentation (for sending to Discord)
    """
    # Session ID for daily prompts
    session_id = f"daily-prompt-{server_id}" if server_id else "daily-prompt"
    
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
    
    # Build hint context
    hint_context = ""
    if hint:
        hint_context = f"\n\nUser requested: {hint}. Incorporate this into the prompt."
    
    # Simpler system prompt for prompt generation (no tools mentioned)
    prompt_system = """You are Mai Sakurajima, running an art Discord server. Your voice is dry, deadpan, slightly teasing. You're cool and composed—no excessive enthusiasm or exclamation points. Just generate the prompt and a short message. No tool calls, no extra output—just the JSON."""
    
    # Call OpenAI - wrapped client auto-traces when Langfuse is enabled
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": prompt_system
            },
            {
                "role": "user",
                "content": f"""Generate today's daily drawing prompt. Theme: {theme}.

Come up with a SHORT, simple prompt that's FUN to draw. Stick to one of these categories:

1. A REAL character from anime/games/manga (most common): "Link", "Tifa", "Hori from Horimiya", "Gojo", "2B"
2. A character + simple twist: "Pikachu in a hoodie", "Snorlax as an ice cream", "chibi Sephiroth"
3. A cozy scene or vibe: "sunset at a ramen shop", "rainy convenience store at night"
4. A simple concept: "two rivals sharing an umbrella", "a sword that's too big"

AVOID:
- Random/weird combinations like "tsundere android" or "villain in pajamas"
- Abstract/non-visual modifiers like "(short break)", "(thinking)", "(sad)" — these aren't drawable
- Parentheticals in general — if you add a twist, make it part of the phrase naturally

GOOD modifiers (visual, drawable): "in streetwear", "as a chibi", "holding coffee", "in pajamas"
BAD modifiers (abstract, not drawable): "(resting)", "(on break)", "(contemplating)"

Keep it clean. When in doubt, just say the character name alone.

IMPORTANT: 
- Don't repeat characters from recent prompts or conversations. Pick someone NEW.
- Vary the format. Rotate between: just a character name, character + outfit/twist, a scene, a simple concept. Don't do the same pattern twice in a row.

Present it with a short message in YOUR voice — dry, slightly teasing, maybe a little sarcastic. Something like:
- "today's prompt: 'a tired swordsman.' ...no, drawing me doesn't count."
- "here's today's prompt. try not to disappoint me."
- "prompt's up. 'cozy dragon.' don't overthink it."

Keep it brief (1-2 sentences). Don't be overly enthusiastic or use lots of exclamation points. You're too cool for that.{recent_context}{memories_context}{conversation_context}{hint_context}

Respond with JSON in this exact format:
{{
    "prompt": "The short, simple prompt",
    "message": "Your brief message including the prompt"
}}"""
            }
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=MAX_PROMPT_TOKENS,
    )
    
    # Parse the JSON response
    content = response.choices[0].message.content.strip()
    
    try:
        data = json.loads(content)
        raw_prompt = data["prompt"]
        mai_message = data["message"]
    except (json.JSONDecodeError, KeyError) as e:
        # Fallback if JSON parsing fails
        print(f"⚠️ JSON parse error in generate_daily_prompt: {e}")
        print(f"   Raw content: {content[:200]}")
        # Try to extract something usable
        raw_prompt = "cozy cafe scene"
        mai_message = "today's prompt: 'cozy cafe scene.' had some trouble thinking, but here you go."
    
    return raw_prompt, mai_message


# =============================================================================
# MAIN CHAT FUNCTION
# =============================================================================

@observe(name="chat_with_mai", capture_input=False, capture_output=False)
async def chat_with_mai(
    user_message: str,
    username: str,
    conversation_history: list[dict],
    current_settings: dict,
    image_urls: Optional[list[str]] = None,
    function_result: Optional[dict] = None,  # For post-function responses
    long_term_memories: Optional[list[str]] = None,  # Recent memories to inject
    server_id: Optional[str] = None,  # For Langfuse session tracking
    channel_id: Optional[str] = None  # For Langfuse session tracking
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
    # Session ID for grouping conversations
    session_id = f"server-{server_id}-channel-{channel_id}" if server_id and channel_id else None
    
    # ----- BUILD CONTEXT -----
    # Use the server's configured timezone for accurate time display
    import pytz
    server_tz_name = current_settings.get('timezone', 'America/New_York')
    try:
        server_tz = pytz.timezone(server_tz_name)
    except pytz.UnknownTimeZoneError:
        server_tz = pytz.timezone('America/New_York')
        server_tz_name = 'America/New_York'
    
    now = datetime.now(server_tz)
    
    # Format timezone for display (e.g., "America/New_York" -> "EST" or "EDT")
    tz_abbrev = now.strftime('%Z')  # Gets "EST", "PST", "EDT", etc.
    
    paused_until = current_settings.get('paused_until')
    pause_status = f"Paused until {paused_until[:10]}" if paused_until else "Active"
    
    # Build memories section if any exist
    memories_section = ""
    if long_term_memories:
        memories_text = "\n".join(f"- {m}" for m in long_term_memories[:10])
        memories_section = f"\n\nThings you remember:\n{memories_text}"
    
    context = f"""
Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} {tz_abbrev}
Current settings:
- Daily prompt time: {current_settings.get('post_time', '09:00')} {tz_abbrev}
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
    # Note: When Langfuse is enabled (Python < 3.13), the wrapped client
    # automatically traces this call with input/output/tokens/cost
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
        tool_choice="auto",
        max_completion_tokens=MAX_CHAT_TOKENS,
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
