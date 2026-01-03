# Mai-san Memory System

A visual guide to how Mai remembers things.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MAI'S BRAIN                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐│
│  │   SHORT-TERM MEMORY     │    │       LONG-TERM MEMORY          ││
│  │   (In-RAM Dictionary)   │    │       (Supabase Table)          ││
│  │                         │    │                                 ││
│  │  "What just happened"   │    │  "What I'll remember forever"   ││
│  │                         │    │                                 ││
│  │  • Last 20 messages     │    │  • User facts & preferences     ││
│  │  • Lost on restart      │    │  • Important events             ││
│  │  • Per-server           │    │  • Survives restarts            ││
│  └─────────────────────────┘    └─────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Short-Term Memory

### What it is

A Python dictionary that lives in `main.py`. Stores recent conversation messages.

### Structure

```python
short_term_memory = {
    "server_123": [
        {"role": "user", "content": "set theme to fantasy", "username": "Alice"},
        {"role": "assistant", "content": "Done! Switched to fantasy~", "username": "Mai"},
        {"role": "user", "content": "what's today's prompt?", "username": "Bob"},
        {"role": "assistant", "content": "Today's prompt is...", "username": "Mai"},
        # ... up to 20 messages
    ],
    "server_456": [
        # ... different server's messages
    ]
}
```

### Lifecycle

```
Bot starts         User sends message       Bot restarts
    │                     │                      │
    ▼                     ▼                      ▼
┌────────┐          ┌──────────┐           ┌────────┐
│ Empty  │ ──────▶  │ Message  │ ──────▶   │ Empty  │
│   {}   │          │  saved   │           │   {}   │
└────────┘          └──────────┘           └────────┘
                         │
                         ▼
                    (if > 20 messages,
                     oldest dropped)
```

### Where it's used

```
main.py (on_message)
    │
    ├── get_conversation_history(server_id)  ─────▶  Returns last 20 messages
    │
    └── After reply: add_to_history(...)  ─────────▶  Saves user msg + Mai's reply
                                                             │
                                                             ▼
                                                    Passed to gpt.chat_with_mai()
                                                    as "conversation_history"

scheduler.py (post_daily_prompt)
    │
    └── After posting: add_to_history(...)  ─────────▶  Saves Mai's daily prompt
                                                               │
                                                               ▼
                                                      So when users reply to the prompt,
                                                      Mai knows what she just posted
```

---

## Long-Term Memory

### What it is

A Supabase database table. Stores facts worth remembering permanently.

### Database Schema

```sql
memories (
    id              BIGSERIAL PRIMARY KEY,
    server_id       TEXT NOT NULL,           -- Which Discord server
    user_id         TEXT,                    -- Who it's about (optional)
    memory          TEXT NOT NULL,           -- The actual memory
    category        TEXT DEFAULT 'general',  -- Type of memory
    importance      INTEGER DEFAULT 3,       -- 1-5, higher = more important
    expires_at      TIMESTAMPTZ,             -- When to delete (NULL = never)
    created_at      TIMESTAMPTZ DEFAULT NOW()
)
```

### Memory Categories

```
┌────────────────┬─────────────┬────────────┬─────────────────────────────────┐
│   Category     │   Expires   │ Importance │           Example               │
├────────────────┼─────────────┼────────────┼─────────────────────────────────┤
│  user_fact     │   Never     │     4      │ "Alice loves drawing dragons"   │
│  preference    │   Never     │     4      │ "Eric prefers 9am prompts"      │
│  event         │   Never     │     5      │ "Server hit 100 prompts"        │
│  conversation  │  30 days    │     2      │ "Discussed shading techniques"  │
│  general       │  60 days    │     3      │ "Bob mentioned he's busy"       │
└────────────────┴─────────────┴────────────┴─────────────────────────────────┘
```

### How Memories Are Created

```
                    ┌─────────────────────────────────────┐
                    │         MEMORY CREATION             │
                    └─────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
    ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
    │  MAI DECIDES  │      │  AUTO-SAVED   │      │   SCHEDULED   │
    │   (Tool Call) │      │   (Events)    │      │   (Future)    │
    └───────┬───────┘      └───────┬───────┘      └───────────────┘
            │                      │
            ▼                      ▼
    Mai calls save_memory()   Handlers auto-save:
    when she thinks            • Theme changed
    something is worth         • Schedule changed
    remembering                • Channel set up
            │                      │
            └──────────┬───────────┘
                       ▼
              ┌─────────────────┐
              │    Supabase     │
              │   memories      │
              │     table       │
              └─────────────────┘
```

### How Memories Are Retrieved

```
User sends message to Mai
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    get_memories_for_context()                   │
│                                                                 │
│   1. Get memories about CURRENT USER (up to 5)                  │
│      └── Prioritizes personalization                            │
│                                                                 │
│   2. Get HIGH IMPORTANCE memories (sorted by importance desc)   │
│      └── Important stuff always visible                         │
│                                                                 │
│   3. Combine, dedupe, return top 12                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
    Injected into Mai's context:

    "Things you remember:
     - Alice loves drawing dragons
     - Theme changed to: horror
     - Eric prefers 9am prompts"
```

### Memory Cleanup

```
Every Sunday at 3am EST
           │
           ▼
┌─────────────────────────────────┐
│   cleanup_expired_memories()    │
│                                 │
│   DELETE FROM memories          │
│   WHERE expires_at < NOW()      │
│   AND expires_at IS NOT NULL    │
│                                 │
└─────────────────────────────────┘
           │
           ▼
   Keeps database clean,
   removes stale conversation/general memories
```

---

## Complete Message Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER SENDS MESSAGE                                │
│                          "@Mai set theme to horror"                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Load Context                                                        │
│                                                                             │
│   ┌─────────────────────┐    ┌─────────────────────────────────────────┐   │
│   │  Short-Term Memory  │    │         Long-Term Memory                │   │
│   │  (last 20 messages) │    │  (prioritized by user + importance)     │   │
│   └──────────┬──────────┘    └────────────────────┬────────────────────┘   │
│              │                                    │                         │
│              └───────────────┬────────────────────┘                         │
│                              ▼                                              │
│                    Combined into GPT context                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: GPT Processes                                                       │
│                                                                             │
│   Mai sees:                                                                 │
│   - System prompt (her personality)                                         │
│   - Current settings (theme, schedule, etc.)                                │
│   - Things she remembers (long-term memories)                               │
│   - Recent conversation (short-term memory)                                 │
│   - Current message                                                         │
│                                                                             │
│   Mai decides to call: set_theme(theme="horror")                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Function Executed                                                   │
│                                                                             │
│   handle_set_theme():                                                       │
│     1. Update settings in database                                          │
│     2. AUTO-SAVE memory: "Theme changed to: horror" (category: event)       │
│     3. Return result to GPT                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Mai Responds                                                        │
│                                                                             │
│   "Switched to horror~ 🎃 Prepare for some spooky prompts!"                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Save to Short-Term Memory                                           │
│                                                                             │
│   add_to_history(server_id, "user", "set theme to horror", username)        │
│   add_to_history(server_id, "assistant", "Switched to horror~...", "Mai")   │
│                                                                             │
│   Now if user says "what did I just ask?", Mai can see it in history        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration (config.py)

```python
# Short-Term Memory
MAX_SHORT_TERM_MESSAGES = 20          # Messages kept in RAM
MAX_FUNCTION_CHAIN_ITERATIONS = 10    # Safety limit for function chains

# Long-Term Memory
MEMORIES_FOR_CONTEXT = 12             # Memories shown to Mai each message
MEMORIES_USER_SPECIFIC = 5            # User-specific memories prioritized
MEMORIES_RECALL_LIMIT = 15            # When Mai explicitly recalls
MEMORIES_DEFAULT_LIMIT = 20           # Default DB query limit
```

---

## Key Files

| File               | Purpose                                      |
| ------------------ | -------------------------------------------- |
| `main.py`          | Short-term memory dict, message handling     |
| `bot/memory.py`    | Short-term memory helper functions           |
| `bot/database.py`  | Long-term memory (Supabase queries)          |
| `bot/handlers.py`  | Auto-saves events, handles save/recall tools |
| `bot/scheduler.py` | Weekly memory cleanup job                    |
| `bot/config.py`    | All tunable memory constants                 |

---

## Future: Conversation Summaries (Not Yet Implemented)

The idea: At end of each day, summarize conversations and save as a memory.

**Why it's complex:**

```
Short-term memory is in RAM
           │
           ▼
   Lost on restart! 😱
           │
           ▼
To summarize, we'd need to:
  1. Persist messages to a "conversations" table
  2. Run a daily GPT call to summarize
  3. Save summary as "conversation" memory
           │
           ▼
   More DB writes + GPT costs
```

Current workaround: Mai can manually `save_memory` notable things during conversation.
