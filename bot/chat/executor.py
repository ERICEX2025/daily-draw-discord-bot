"""
chat/executor.py — Chat Loop & Function Execution

Main entry point for chat: run_chat_loop()
"""

import json
from typing import Optional
import discord

from bot.chat.handlers import HANDLERS
from bot.chat.generator import chat_with_mai
from bot.services.langfuse import observe, update_span
from bot.services import db
from bot.memory import get_memories_for_context
from bot.config import MAX_FUNCTION_CHAIN_ITERATIONS, MEMORIES_FOR_CONTEXT


# =============================================================================
# CHAT LOOP (main entry point)
# =============================================================================

@observe(name="chat_loop", capture_input=False, capture_output=False)
async def run_chat_loop(
    user_message: str,
    username: str,
    conversation_history: list,
    settings: dict,
    message: discord.Message,
    image_urls: Optional[list] = None,
    long_term_memories: Optional[list] = None,
    server_id: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> tuple[str, list]:
    """
    Run the full chat + function execution loop.
    
    Flow:
      1. Call GPT with user message + context
      2. If GPT requests tool calls → execute them
      3. Feed results back to GPT, repeat until final response
      4. Return (response_text, pending_images)
    """
    server_id = server_id or (str(message.guild.id) if message.guild else str(message.author.id))
    
    # -------------------------------------------------------------------------
    # Initial GPT call
    # -------------------------------------------------------------------------
    response_text, function_calls = await chat_with_mai(
        user_message=user_message,
        username=username,
        conversation_history=conversation_history,
        current_settings=settings,
        image_urls=image_urls,
        long_term_memories=long_term_memories,
        server_id=server_id,
        channel_id=channel_id
    )
    
    # -------------------------------------------------------------------------
    # Function execution loop
    # GPT may chain multiple tool calls before giving a final response
    # -------------------------------------------------------------------------
    all_results = []
    pending_images = []
    
    for _ in range(MAX_FUNCTION_CHAIN_ITERATIONS):
        if not function_calls:
            break
        
        # Execute each requested function
        for fc in function_calls:
            result = await _execute_function(
                fc["name"],
                fc["args"],
                message,
                settings
            )
            
            # Check for special result flags
            try:
                result_data = json.loads(result)
                if result_data.get("ok") and result_data.get("data"):
                    data = result_data["data"]
                    
                    # Tool wants to send images after the response
                    if data.get("_pending_images"):
                        pending_images.append(data["_pending_images"])
                    
                    # Tool wants to short-circuit with a direct response
                    if data.get("_direct_response"):
                        return data["_direct_response"], pending_images
                        
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
            
            all_results.append({
                "name": fc["name"],
                "args": fc.get("args", {}),
                "result": result,
                "tool_call_id": fc["tool_call_id"]
            })
        
        # Refresh memories (tools may have added new ones) and call GPT again
        memories_raw = await get_memories_for_context(
            server_id,
            current_user=username,
            limit=MEMORIES_FOR_CONTEXT
        )
        long_term_memories = [m["memory"] for m in memories_raw]
        
        response_text, function_calls = await chat_with_mai(
            user_message=user_message,
            username=username,
            conversation_history=conversation_history,
            current_settings=await db.get_settings(server_id),
            image_urls=image_urls,
            function_result=all_results,
            long_term_memories=long_term_memories,
            server_id=server_id,
            channel_id=channel_id
        )
    
    return response_text, pending_images


# =============================================================================
# FUNCTION EXECUTOR (helper)
# =============================================================================

@observe(name="execute_tool", capture_input=False, capture_output=False)
async def _execute_function(
    name: str,
    args: dict,
    message: discord.Message,
    settings: dict
) -> str:
    """
    Execute a single tool call that GPT requested.
    
    Returns JSON string: {"ok": true, "data": ...} or {"ok": false, "error": ...}
    """
    server_id = str(message.guild.id) if message.guild else str(message.author.id)
    
    update_span(
        name=f"tool:{name}",
        input={"function": name, "args": args},
        metadata={"server_id": server_id}
    )
    
    # Look up the handler for this function
    handler = HANDLERS.get(name)
    if not handler:
        return json.dumps({"ok": False, "error": f"Function '{name}' not recognized"})

    # Execute the handler
    result = await handler(
        server_id=server_id,
        args=args,
        settings=settings,
        message=message,
    )

    # Wrap result in standard format
    if isinstance(result, (dict, list)):
        output = json.dumps({"ok": True, "data": result})
    else:
        output = json.dumps({"ok": True, "message": str(result)})
    
    update_span(output=output)
    return output
