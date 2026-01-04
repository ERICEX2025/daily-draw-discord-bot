"""
chat/generator.py — GPT Response Generator

Builds messages and calls GPT to generate Mai's response.
"""

import json
from typing import Optional
from datetime import datetime
import pytz

from bot.services.openai import client
from bot.services.langfuse import observe
from bot.mai import CHARACTER, FUNCTIONS
from bot.config import MODEL, MAX_SHORT_TERM_MESSAGES, MAX_CHAT_TOKENS


@observe(name="chat_with_mai", capture_input=False, capture_output=False)
async def chat_with_mai(
    user_message: str,
    username: str,
    conversation_history: list[dict],
    current_settings: dict,
    image_urls: Optional[list[str]] = None,
    function_result: Optional[dict] = None,
    long_term_memories: Optional[list[str]] = None,
    server_id: Optional[str] = None,
    channel_id: Optional[str] = None
) -> tuple[str, Optional[dict]]:
    """
    Main function to chat with Mai-san.
    
    Returns:
        Tuple of (response_text, function_calls)
    """
    # Build context
    server_tz_name = current_settings.get('timezone', 'America/New_York')
    try:
        server_tz = pytz.timezone(server_tz_name)
    except pytz.UnknownTimeZoneError:
        server_tz = pytz.timezone('America/New_York')
        server_tz_name = 'America/New_York'
    
    now = datetime.now(server_tz)
    tz_abbrev = now.strftime('%Z')
    
    paused_until = current_settings.get('paused_until')
    pause_status = f"Paused until {paused_until[:10]}" if paused_until else "Active"
    
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
    
    # Build messages array
    messages = [
        {"role": "system", "content": f"{CHARACTER}\n\n{context}"}
    ]
    
    # Add conversation history
    for msg in conversation_history[-MAX_SHORT_TERM_MESSAGES:]:
        msg_username = msg.get("username", "Unknown")
        if msg.get("role") == "user":
            content_with_name = f"{msg_username}: {msg['content']}"
        else:
            content_with_name = msg["content"]
        
        if msg.get("images"):
            content = [{"type": "text", "text": content_with_name}]
            for img_url in msg["images"]:
                content.append({"type": "image_url", "image_url": {"url": img_url}})
            messages.append({"role": msg["role"], "content": content})
        else:
            messages.append({"role": msg["role"], "content": content_with_name})
    
    # Add current user message
    user_message_with_name = f"{username}: {user_message}"
    
    if image_urls:
        content = [{"type": "text", "text": user_message_with_name}]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_message_with_name})
    
    # If post-function: Add tool calls + results
    if function_result:
        results = function_result if isinstance(function_result, list) else [function_result]
        
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
        
        for r in results:
            messages.append({
                "role": "tool",
                "tool_call_id": r["tool_call_id"],
                "content": r["result"]
            })
    
    # Call GPT
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[{"type": "function", "function": f} for f in FUNCTIONS],
        tool_choice="auto",
        max_completion_tokens=MAX_CHAT_TOKENS,
    )
    
    message = response.choices[0].message
    
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

