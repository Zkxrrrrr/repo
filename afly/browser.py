"""Stealth Playwright launcher — fresh context per signup."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import BrowserContext, async_playwright

try:
    from playwright_stealth import stealth_async  # type: ignore
except ImportError:  # pragma: no cover
    stealth_async = None

from .fingerprint import Fingerprint
from .proxies import Proxy


@asynccontextmanager
async def fresh_context(
    fingerprint: Fingerprint,
    proxy: Optional[Proxy] = None,
    headless: bool = True,
):
    """Yield a (playwright, browser, context, page) tuple. Closes everything on exit."""
    pw = await async_playwright().start()
    launch_kwargs = {"headless": headless, "args": ["--disable-blink-features=AutomationControlled"]}
    if proxy is not None:
        launch_kwargs["proxy"] = {"server": proxy.uri}

    browser = await pw.chromium.launch(**launch_kwargs)
    context = await browser.new_context(
        user_agent=fingerprint.user_agent,
        viewport={"width": fingerprint.viewport[0], "height": fingerprint.viewport[1]},
        timezone_id=fingerprint.timezone,
        locale=fingerprint.locale,
    )
    # block obvious telemetry / heavy assets to keep it snappy
    await context.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in {"media", "font"}
        else route.continue_(),
    )
    page = await context.new_page()
    if stealth_async is not None:
        try:
            await stealth_async(page)
        except Exception:
            pass

    try:
        yield pw, browser, context, page
    finally:
        try:
            await context.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass


async def fill_human(page, selector: str, text: str, delay_ms: int = 60):
    """Type with per-key delay to look less robotic."""
    await page.click(selector)
    await page.fill(selector, "")
    await page.type(selector, text, delay=delay_ms)
