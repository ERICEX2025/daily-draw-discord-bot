"""
personality.py — Mai-san's Character & Available Functions

This file defines WHO Mai-san is and WHAT she can do:
1. Function enum - All callable functions
2. SYSTEM_PROMPT - Mai's personality and behavior rules
3. FUNCTIONS - Tool definitions for OpenAI API

Separating this from gpt.py makes it easy to:
- Tweak Mai's personality without touching API code
- Add new functions in one place
- Keep the character definition readable
"""

from enum import Enum


# =============================================================================
# FUNCTION NAMES (for GPT tool calls)
# =============================================================================

class Function(str, Enum):
    SET_CHANNEL = "set_channel"
    SET_SCHEDULE = "set_schedule"
    SET_THEME = "set_theme"
    PAUSE_SCHEDULE = "pause_schedule"
    RESUME_SCHEDULE = "resume_schedule"
    GET_HISTORY = "get_history"
    SAVE_MEMORY = "save_memory"
    RECALL_MEMORIES = "recall_memories"


# =============================================================================
# MAI-SAN'S IDENTITY
# =============================================================================

CHARACTER = (
    "You are Sakurajima Mai from 'Rascal Does Not Dream of Bunny Girl Senpai,' "
    "running an art discord server for a daily drawing challenge."
)

# =============================================================================
# TOOL BEHAVIOR
# =============================================================================

TOOL_INSTRUCTIONS = (
    "You have tools to manage the art channel: set up the prompt channel, change the schedule, "
    "set the theme, pause/resume prompts, check history, and manage your long-term memory. "
    "Use them whenever it would help — whether the user asks directly or you think it'd be useful. "
    "You can call multiple tools at once. "
    "Use save_memory to remember important things about users or the server (preferences, fun facts, milestones). "
    "Use recall_memories when you need context about a user or want to personalize your response."
)


# =============================================================================
# FUNCTION DEFINITIONS (TOOLS)
# =============================================================================

# These are the "tools" that GPT can decide to call.
# GPT reads the descriptions and decides when to use them based on user requests.
# The actual execution happens in handlers.py

FUNCTIONS = [
    # --- Daily prompt setup ---
    {
        "name": Function.SET_CHANNEL,
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
        "name": Function.SET_SCHEDULE,
        "description": "Set the daily prompt posting time and optionally the timezone.",
        "parameters": {
            "type": "object",
            "properties": {
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM format (24-hour), e.g., '09:00' or '21:30'"
                },
                "timezone": {
                    "type": "string",
                    "description": "Timezone for the schedule. Common values: 'EST' or 'America/New_York', 'PST' or 'America/Los_Angeles', 'CST' or 'America/Chicago', 'MST' or 'America/Denver', 'UTC'. If user says 'EST', 'PST', etc., convert to the full timezone name."
                }
            },
            "required": ["time"]
        }
    },
    # --- Theme ---
    {
        "name": Function.SET_THEME,
        "description": "Set the theme/style for daily drawing prompts (e.g., 'fantasy', 'sci-fi', 'slice of life', 'horror').",
        "parameters": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "The theme for prompts, e.g., 'fantasy adventure', 'cozy slice of life', 'dark gothic', 'mecha and robots'"
                }
            },
            "required": ["theme"]
        }
    },
    # --- Pause/Resume ---
    {
        "name": Function.PAUSE_SCHEDULE,
        "description": "Temporarily pause daily prompts for a specified duration.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to pause. e.g., 7 for a week, 14 for two weeks."
                }
            },
            "required": ["days"]
        }
    },
    {
        "name": Function.RESUME_SCHEDULE,
        "description": "Resume daily prompts immediately if they were paused.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    # --- Info ---
    {
        "name": Function.GET_HISTORY,
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
    # --- Memory ---
    {
        "name": Function.SAVE_MEMORY,
        "description": "Save something important to long-term memory. Use this to remember user facts, preferences, events, or conversations.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory": {
                    "type": "string",
                    "description": "What to remember, e.g., 'Alice loves drawing dragons', 'Eric prefers fantasy themes', 'Server hit 100 prompts'"
                },
                "about_user": {
                    "type": "string",
                    "description": "Optional: the username this memory is about. Leave empty for server-wide memories."
                },
                "category": {
                    "type": "string",
                    "enum": ["user_fact", "preference", "event", "conversation", "general"],
                    "description": "Memory category: user_fact (permanent), preference (permanent), event (permanent), conversation (30 days), general (60 days)"
                },
                "importance": {
                    "type": "integer",
                    "description": "1-5, how important is this? 5=critical/permanent, 1=minor. Defaults based on category."
                }
            },
            "required": ["memory"]
        }
    },
    {
        "name": Function.RECALL_MEMORIES,
        "description": "Recall memories from long-term storage. Use this to remember things about a user or the server.",
        "parameters": {
            "type": "object",
            "properties": {
                "about_user": {
                    "type": "string",
                    "description": "Optional: filter to memories about a specific user."
                },
                "category": {
                    "type": "string",
                    "enum": ["user_fact", "preference", "event", "conversation", "general"],
                    "description": "Optional: filter to a specific category of memories."
                }
            },
            "required": []
        }
    }
]

