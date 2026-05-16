"""Playwright browser factory with stealth + optional proxy + per-account profile dir."""
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext
from fake_useragent import UserAgent

from .proxy_pool import pool

log = logging.getLogger("browser")
ua = UserAgent()
PROFILE_ROOT = "profiles"
os.makedirs(PROFILE_ROOT, exist_ok=True)


@asynccontextmanager
async def make_context(account_label: str, headless: bool = True,
                       use_proxy: bool = True, proxy_override: Optional[str] = None):
    """Yields a persistent BrowserContext per account so cookies survive runs."""
    profile_dir = os.path.join(PROFILE_ROOT, account_label)
    os.makedirs(profile_dir, exist_ok=True)

    proxy_cfg = None
    if use_proxy:
        proxy = proxy_override or await pool.get()
        if proxy:
            proxy_cfg = pool.to_playwright(proxy)
            log.debug(f"[{account_label}] proxy={proxy}")

    user_agent = ua.chrome
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            user_agent=user_agent,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            proxy=proxy_cfg,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        # Light stealth patches
        await ctx.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = { runtime: {} };
            """
        )

        try:
            yield ctx
        finally:
            await ctx.close()
