"""
services/langfuse.py — Langfuse Observability

Centralized Langfuse setup. Import from here instead of duplicating setup.
"""

import os
from contextlib import nullcontext

# Check if Langfuse is configured
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
)

if LANGFUSE_ENABLED:
    try:
        from langfuse import observe as _observe, get_client, propagate_attributes
        print("🔍 Langfuse observability enabled")
        
        # Re-export the real implementations
        observe = _observe
        
    except ImportError as e:
        print(f"⚠️ Langfuse import failed: {e}")
        LANGFUSE_ENABLED = False

# Provide no-op fallbacks if Langfuse is not available
if not LANGFUSE_ENABLED:
    def observe(name=None, capture_input=True, capture_output=True):
        """No-op decorator when Langfuse is disabled."""
        def decorator(func):
            return func
        return decorator
    
    def get_client():
        """No-op client when Langfuse is disabled."""
        return None
    
    def propagate_attributes(**kwargs):
        """No-op context manager when Langfuse is disabled."""
        return nullcontext()


def update_span(input=None, output=None, name=None, metadata=None):
    """
    Safely update the current Langfuse span.
    No-op if Langfuse is disabled or fails.
    """
    if not LANGFUSE_ENABLED:
        return
    
    try:
        client = get_client()
        if client:
            kwargs = {}
            if input is not None:
                kwargs["input"] = input
            if output is not None:
                kwargs["output"] = output
            if name is not None:
                kwargs["name"] = name
            if metadata is not None:
                kwargs["metadata"] = metadata
            client.update_current_span(**kwargs)
    except Exception:
        pass

