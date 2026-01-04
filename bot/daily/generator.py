"""
daily/generator.py — Prompt Generator

Have Mai generate and present a drawing prompt.
"""

import json
from typing import Optional

from bot.services.openai import client
from bot.services.langfuse import observe
from bot.daily.daily_prompt import build_daily_system_prompt, build_daily_user_prompt
from bot.config import MODEL, MAX_PROMPT_TOKENS


@observe(name="generate_daily_prompt", capture_input=False, capture_output=False)
async def generate_daily_prompt(
    recent_prompts: Optional[list[dict]] = None,
    theme: str = "anime and video game inspired",
    memories: Optional[list[str]] = None,
    recent_messages: Optional[list[dict]] = None,
    server_id: Optional[str] = None,
    hint: Optional[str] = None
) -> tuple[str, str]:
    """
    Have Mai generate and present a drawing prompt.
    
    Returns:
        Tuple of (raw_prompt, mai_message)
    """
    # Build context
    if recent_prompts:
        prompt_list = "\n".join(f"- {p['date']}: {p['prompt']}" for p in recent_prompts)
        recent_context = f"\n\nRecent prompts (avoid repeating these):\n{prompt_list}"
    else:
        recent_context = ""
    
    memories_context = ""
    if memories:
        memories_list = "\n".join(f"- {m}" for m in memories)
        memories_context = f"\n\nThings you remember about this server:\n{memories_list}"
    
    conversation_context = ""
    if recent_messages:
        convo_list = "\n".join(f"- {m.get('username', 'Someone')}: {m['content']}" for m in recent_messages)
        conversation_context = f"\n\nRecent conversations (feel free to reference or play off these):\n{convo_list}"
    
    hint_context = ""
    if hint:
        hint_context = f"\n\nUser requested: {hint}. Incorporate this into the prompt."
    
    # Call OpenAI
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": build_daily_system_prompt()},
            {"role": "user", "content": build_daily_user_prompt(
                theme=theme,
                recent_context=recent_context,
                memories_context=memories_context,
                conversation_context=conversation_context,
                hint_context=hint_context
            )}
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=MAX_PROMPT_TOKENS,
    )
    
    content = response.choices[0].message.content.strip()
    
    try:
        data = json.loads(content)
        raw_prompt = data["prompt"]
        mai_message = data["message"]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️ JSON parse error in generate_daily_prompt: {e}")
        raw_prompt = "cozy cafe scene"
        mai_message = "today's prompt: 'cozy cafe scene.' had some trouble thinking, but here you go."
    
    return raw_prompt, mai_message

