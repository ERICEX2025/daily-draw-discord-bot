"""
character/tools.py — GPT Tool Definitions

What Mai-san can do:
1. Function enum - All callable function names
2. FUNCTIONS - Tool definitions for OpenAI API

The actual execution happens in tools/handlers.py.
"""

from enum import Enum


class Function(str, Enum):
    SET_CHANNEL = "set_channel"
    SET_SCHEDULE = "set_schedule"
    SET_THEME = "set_theme"
    PAUSE_SCHEDULE = "pause_schedule"
    RESUME_SCHEDULE = "resume_schedule"
    GET_HISTORY = "get_history"
    REROLL_PROMPT = "reroll_prompt"
    SAVE_MEMORY = "save_memory"
    RECALL_MEMORIES = "recall_memories"
    SEARCH_IMAGES = "search_images"
    WEB_SEARCH = "web_search"


# These are the "tools" that GPT can decide to call.
# GPT reads the descriptions and decides when to use them based on user requests.

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
    {
        "name": Function.REROLL_PROMPT,
        "description": "Generate a new daily prompt, replacing today's prompt. Use when users ask to reroll, get a different prompt, or don't like today's prompt. If they ask for something specific (e.g., 'reroll with a JJK character'), pass that as the hint.",
        "parameters": {
            "type": "object",
            "properties": {
                "hint": {
                    "type": "string",
                    "description": "Optional guidance for the new prompt, e.g., 'JJK character', 'something cozy', 'a scene instead'. Leave empty for no preference."
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
    },
    # --- Search ---
    {
        "name": Function.SEARCH_IMAGES,
        "description": "Search for reference images of characters, objects, or art styles. Images will be sent as embeds automatically—do NOT include URLs in your response text. Default is 1 image; only request more if user asks for multiple references.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for, e.g., 'Snorlax pokemon', 'Hori from Horimiya', 'art nouveau style'"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of images to return (1-5). Default is 1. Only use more if user specifically asks for multiple references."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": Function.WEB_SEARCH,
        "description": "Search the web for information. Use for looking up anime/game info, art techniques, or anything you don't know.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for, e.g., 'trending anime 2026', 'what is isekai genre', 'how to draw dynamic poses'"
                }
            },
            "required": ["query"]
        }
    }
]

