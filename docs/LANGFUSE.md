# 🔍 Langfuse Integration Architecture

This document explains how Langfuse observability is integrated into the Mai-san Discord bot.

## Overview

Langfuse provides full visibility into every AI interaction:

- What messages are sent to OpenAI
- What responses come back
- Tool calls and their results
- Token usage and cost
- User and session tracking

## 1. Configuration

**Files:** `gpt.py` lines 33-55, `main.py` lines 38-53

```
┌─────────────────────────────────────────────────────────────┐
│  ENV VARS: LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY        │
│                         ↓                                    │
│  _langfuse_enabled = True/False                              │
│                         ↓                                    │
│  If enabled: import wrapped AsyncOpenAI + @observe           │
│  If disabled: use standard OpenAI + no-op @observe           │
└─────────────────────────────────────────────────────────────┘
```

**Environment Variables Required:**

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## 2. Auto-Tracing OpenAI Calls

**Files:** `gpt.py` lines 38, 59

```python
from langfuse.openai import AsyncOpenAI  # Wrapped client (with spying!)
client = AsyncOpenAI(...)  # All API calls auto-traced
```

Every `client.chat.completions.create()` call automatically logs:

- ✅ Full messages array (system prompt, user message, history)
- ✅ Tools/functions available
- ✅ Model response (content or tool_calls)
- ✅ Token usage & cost

**How it works:** The import `from langfuse.openai import AsyncOpenAI` replaces
the standard OpenAI client with a wrapped version that intercepts all API calls
and sends the data to your Langfuse dashboard automatically.

## 3. Function Decorators

| File          | Function                                 | Purpose                           |
| ------------- | ---------------------------------------- | --------------------------------- |
| `gpt.py:66`   | `@observe(name="generate_daily_prompt")` | Daily prompt generation           |
| `gpt.py:163`  | `@observe(name="chat_with_mai")`         | Main chat function                |
| `main.py:137` | `@observe(name="handle_mention")`        | Parent trace for Discord messages |
| `main.py:298` | `@observe(name="execute_tool")`          | Tool execution                    |

All decorators use `capture_input=False, capture_output=False` to prevent
serializing Discord objects (which have circular references and cause errors).

## 4. Propagating Attributes (Best Practice)

**File:** `main.py`

### User & Session via `propagate_attributes` (lines 205-212)

Using `propagate_attributes()` ensures `user_id`, `session_id`, and `metadata`
are applied to ALL child observations (not just the trace). This is the
Langfuse-recommended approach for future-proof analytics.

```python
from langfuse import propagate_attributes

with propagate_attributes(
    user_id=username,
    session_id=f"server-{server_id}-channel-{channel_id}",
    metadata={"server_id": server_id, "channel_id": channel_id}
):
    # All GPT calls and tool executions inside here inherit these attributes
    response = await gpt.chat_with_mai(...)
```

### Setting Input/Output Manually

```python
from langfuse import get_client
langfuse = get_client()

langfuse.update_current_span(input=user_message)   # on entry
langfuse.update_current_span(output=response_text) # on exit
```

### Tool Execution (lines 320-335)

```python
langfuse.update_current_span(
    name=f"tool:{name}",
    input={"function": name, "args": args},
    output=result
)
```

## 5. Trace Hierarchy

When a user sends a message, Langfuse creates this nested trace structure:

```
handle_mention (parent)                    ← input, output set manually
│
└── [propagate_attributes context]         ← user_id, session_id, metadata
    │                                         inherited by ALL children below
    │
    ├── chat_with_mai                      ← @observe wrapper
    │   └── OpenAI-generation              ← auto-traced, inherits user/session
    │
    ├── tool:get_history                   ← tool execution span
    │   └── (database calls)                  inherits user/session
    │
    └── chat_with_mai                      ← second call with tool results
        └── OpenAI-generation              ← auto-traced, inherits user/session
```

## 6. Files Summary

| File               | Langfuse Usage                                     |
| ------------------ | -------------------------------------------------- |
| `requirements.txt` | `langfuse>=2.0.0` dependency                       |
| `bot/gpt.py`       | Wrapped OpenAI client, `@observe` on GPT functions |
| `main.py`          | `@observe` on handlers, manual trace updates       |
| `DEPLOYMENT.md`    | Env var setup instructions                         |

## 7. Python Version Compatibility

⚠️ **Langfuse requires Python 3.12 or lower.** Python 3.14+ is not supported
due to Pydantic V1 compatibility issues in the Langfuse SDK.

## 8. Graceful Fallback

If Langfuse is not configured (missing env vars) or import fails:

- Bot continues to work normally
- `@observe` becomes a no-op decorator (does nothing)
- Regular `openai.AsyncOpenAI` is used instead of the wrapped version
- Console shows: `📊 Langfuse not configured - set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY`
