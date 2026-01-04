"""
services/search.py — DuckDuckGo Search

Image and web search using DuckDuckGo.
"""

import asyncio

from ddgs import DDGS

from bot.services.openai import client
from bot.config import MODEL


async def optimize_search_query(prompt: str) -> str:
    """Use GPT to generate an optimized image search query."""
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You generate optimized image search queries. Given a drawing prompt, output a search query that will find good anime/game character reference images. Add the source (anime/game name) if you know it. Keep it short (3-6 words). Output ONLY the search query, nothing else."
                },
                {"role": "user", "content": f"Drawing prompt: {prompt}"}
            ],
            max_completion_tokens=30,
        )
        
        optimized = response.choices[0].message.content.strip().strip('"')
        print(f"🔍 Search query: '{prompt}' → '{optimized}'")
        return optimized
        
    except Exception as e:
        print(f"⚠️ Query optimization failed: {e}")
        return prompt


async def search_reference_images(query: str, max_results: int = 3) -> list[str]:
    """Search for reference images using DuckDuckGo."""
    try:
        search_query = await optimize_search_query(query)
        
        def do_search():
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    search_query,
                    max_results=max_results,
                    safesearch="moderate"
                ))
                return [r["image"] for r in results if r.get("image")]
        
        loop = asyncio.get_running_loop()
        urls = await loop.run_in_executor(None, do_search)
        return urls[:max_results]
        
    except Exception as e:
        print(f"Error searching for images '{query}': {e}")
        return []


async def web_search(query: str, max_results: int = 3) -> list[dict]:
    """Search the web using DuckDuckGo."""
    try:
        def do_search():
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    safesearch="moderate"
                ))
                return [
                    {"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")}
                    for r in results
                ]
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, do_search)
        
    except Exception as e:
        print(f"Error searching web for '{query}': {e}")
        return []

