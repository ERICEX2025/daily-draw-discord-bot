"""
config.py — Centralized Configuration

All tunable constants in one place for easy editing.
"""

# =============================================================================
# MODEL SETTINGS
# =============================================================================

# OpenAI model to use for all requests
MODEL = "gpt-5.2"

# Max tokens for different response types
MAX_PROMPT_TOKENS = 400      # Daily prompt generation
MAX_CHAT_TOKENS = 500        # Regular conversation

# =============================================================================
# DAILY PROMPTS
# =============================================================================

# How many past prompts to show GPT when generating new ones (to avoid repeats)
RECENT_PROMPTS_FOR_GENERATION = 30

# Context for personalized daily prompts
DAILY_PROMPT_MEMORIES = 8         # Long-term memories to inject
DAILY_PROMPT_RECENT_MESSAGES = 6  # Recent conversation messages to reference

# =============================================================================
# SHORT-TERM MEMORY (in-memory, per-server)
# =============================================================================

# How many messages to keep in conversation history
MAX_SHORT_TERM_MESSAGES = 20

# Safety limit for function call chains (prevents infinite loops)
MAX_FUNCTION_CHAIN_ITERATIONS = 10

# =============================================================================
# LONG-TERM MEMORY (Supabase)
# =============================================================================

# Memories injected into context for each message
MEMORIES_FOR_CONTEXT = 12

# User-specific memories to prioritize
MEMORIES_USER_SPECIFIC = 5

# Memories returned when Mai explicitly recalls
MEMORIES_RECALL_LIMIT = 15

# Default limit for get_memories queries
MEMORIES_DEFAULT_LIMIT = 20

