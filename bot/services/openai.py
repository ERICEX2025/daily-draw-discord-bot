"""
services/openai.py — OpenAI Client

Shared OpenAI client with optional Langfuse observability.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Import Langfuse-wrapped or regular OpenAI based on config
from bot.services.langfuse import LANGFUSE_ENABLED

if LANGFUSE_ENABLED:
    try:
        from langfuse.openai import AsyncOpenAI
    except ImportError:
        from openai import AsyncOpenAI
else:
    from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
