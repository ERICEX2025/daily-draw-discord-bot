"""
services/ — External Service Clients

Connections to external services (Supabase, OpenAI, Langfuse, HTTP).
"""

# Re-export db module for convenience (e.g., `from bot.services import db`)
from bot.services import db

__all__ = ["db"]
