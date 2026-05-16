"""Discord webhook ping for successful signups."""
from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger


async def discord(webhook: Optional[str], content: str) -> None:
    if not webhook:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook, json={"content": content})
    except Exception as e:
        logger.warning(f"discord notify failed: {e}")
