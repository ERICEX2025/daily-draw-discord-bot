"""
bot/config.py — All Configuration

Tunable settings for the entire bot.
"""

# =============================================================================
# MODEL
# =============================================================================

MODEL = "gpt-5.2"

# =============================================================================
# CHAT RESPONSES
# =============================================================================

MAX_CHAT_TOKENS = 500                 # Max GPT tokens for chat responses
MAX_FUNCTION_CHAIN_ITERATIONS = 10    # Max tool calls GPT can chain

# =============================================================================
# DAILY PROMPT GENERATION
# =============================================================================

MAX_PROMPT_TOKENS = 400               # Max GPT tokens for prompt generation
RECENT_PROMPTS_FOR_GENERATION = 30    # Past prompts shown (to avoid repeats)

# =============================================================================
# SHORT-TERM MEMORY (RAM, lost on restart)
# =============================================================================
# Stores recent conversation history per server.

MAX_SHORT_TERM_MESSAGES = 20          # Max messages stored per server
DAILY_PROMPT_RECENT_MESSAGES = 6      # How many used for daily prompt generation

# Usage:
#   - Chat: uses all 20
#   - Daily Prompt: uses 6

# =============================================================================
# LONG-TERM MEMORY (Supabase, persistent)
# =============================================================================
# Stores facts, preferences, and events permanently.
# Sorted by: importance (desc), then recency (desc) as tiebreaker
#
# Example for chat (Alice sends a message):
#   1. Fetch 12 server-wide memories (sorted by importance → recency)
#   2. Fetch up to 5 memories about Alice specifically
#   3. Put Alice's memories first, then fill with server-wide, cap at 12
#   Result: [Alice's 3 memories] + [9 server-wide] = 12 total

# For chat messages:
MEMORIES_FOR_CONTEXT = 12             # Total memories shown to Mai per message
MEMORIES_USER_SPECIFIC = 5            # Max user-specific memories to prioritize first

# For daily prompts:
DAILY_PROMPT_MEMORIES = 8             # Memories shown when generating daily prompt

# For explicit recall tool:
MEMORIES_RECALL_LIMIT = 15            # Max memories when Mai explicitly recalls

