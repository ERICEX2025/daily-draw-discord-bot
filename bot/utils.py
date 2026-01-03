"""
utils.py — Utility Functions

General-purpose helper functions used across the bot.
"""

import base64
import httpx
import asyncio
from typing import Optional
from ddgs import DDGS


async def search_reference_images(query: str, max_results: int = 3) -> list[str]:
    """
    Search for reference images using DuckDuckGo.
    
    Args:
        query: Search term (e.g., "Snorlax", "Hori from Horimiya")
        max_results: Maximum number of image URLs to return
        
    Returns:
        List of image URLs
    """
    try:
        # Run the sync DuckDuckGo search in a thread pool
        def do_search():
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    query,
                    max_results=max_results,
                    safesearch="moderate"
                ))
                return [r["image"] for r in results if r.get("image")]
        
        # Run synchronous search in executor to not block async loop
        loop = asyncio.get_running_loop()
        urls = await loop.run_in_executor(None, do_search)
        return urls[:max_results]
        
    except Exception as e:
        print(f"Error searching for images '{query}': {e}")
        return []


async def web_search(query: str, max_results: int = 3) -> list[dict]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search term (e.g., "trending anime 2026", "what is isekai")
        max_results: Maximum number of results to return
        
    Returns:
        List of dicts with 'title', 'url', 'body' keys
    """
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


async def download_image_as_base64(url: str) -> Optional[str]:
    """
    Download an image from a URL and convert it to a base64 data URL.
    
    Discord image URLs expire after a while, so we download the image
    immediately and convert it to base64. This ensures GPT can see the
    image even if there's a delay in processing.
    
    Args:
        url: The Discord CDN URL for the image
        
    Returns:
        A base64 data URL (e.g., "data:image/png;base64,...")
        or None if download failed
        
    Example:
        >>> await download_image_as_base64("https://cdn.discord.com/.../image.png")
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA..."
    """
    try:
        # Use httpx for async HTTP requests
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url)
            
            if response.status_code == 200:
                # Get the content type (e.g., "image/png")
                content_type = response.headers.get("content-type", "image/png")
                
                # Convert binary image data to base64
                base64_data = base64.b64encode(response.content).decode("utf-8")
                
                # Return as data URL that GPT can use
                return f"data:{content_type};base64,{base64_data}"
                
    except Exception as e:
        print(f"Error downloading image: {e}")
    
    return None

