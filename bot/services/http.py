"""
services/http.py — HTTP Utilities

Download and convert images via HTTP.
"""

import base64
from typing import Optional
from io import BytesIO

import httpx
import discord


async def download_image_as_base64(url: str) -> Optional[str]:
    """Download an image and convert to base64 data URL."""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url)
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "image/png")
                base64_data = base64.b64encode(response.content).decode("utf-8")
                return f"data:{content_type};base64,{base64_data}"
                
    except Exception as e:
        print(f"Error downloading image: {e}")
    
    return None


async def download_image_as_file(url: str, filename: str = "image.jpg") -> Optional[discord.File]:
    """Download an image and return as discord.File."""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url, timeout=10.0)
            
            if response.status_code == 200:
                return discord.File(BytesIO(response.content), filename=filename)
                
    except Exception as e:
        print(f"Error downloading image as file: {e}")
    
    return None

