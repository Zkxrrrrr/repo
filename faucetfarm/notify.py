"""Telegram alerts when balance hits withdrawal threshold or something breaks."""
import logging
import aiohttp

log = logging.getLogger("notify")


async def telegram_send(bot_token: str, chat_id: str, text: str):
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=10) as r:
                if r.status != 200:
                    log.warning(f"telegram failed: {r.status}")
    except Exception as e:
        log.warning(f"telegram error: {e}")
