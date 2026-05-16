"""Cointiply — hourly faucet roll + offerwall + survey routing.

Roll only here. Offerwalls and surveys require human-shaped behavior and
device fingerprints; gate those behind a flag if you want to expand.
"""
import asyncio
import logging
import os
import re

from .base import Adapter, ClaimResult

log = logging.getLogger("cointiply")

LOGIN_URL = "https://cointiply.com/login"
FAUCET_URL = "https://cointiply.com/faucet"
DASH_URL = "https://cointiply.com/dashboard"

TWO_CAPTCHA_KEY = os.environ.get("TWOCAPTCHA_KEY", "")


class CointiplyAdapter(Adapter):
    name = "cointiply"
    default_cooldown = 60 * 60 + 60  # 1h + slack

    async def login_if_needed(self, page):
        await page.goto(DASH_URL, wait_until="domcontentloaded")
        if "login" in page.url:
            log.info(f"[{self.account_label}] cointiply: logging in")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            await page.fill('input[name="email"]', self.email)
            await page.fill('input[name="password"]', self.password)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(5000)

    async def fetch_balance(self, page) -> tuple[str, float]:
        try:
            await page.goto(DASH_URL, wait_until="domcontentloaded")
            txt = await page.inner_text("body")
            m = re.search(r"([\d,]+)\s*coins", txt, re.I)
            if m:
                coins = float(m.group(1).replace(",", ""))
                # 100 coins ~ $0.01
                usd = coins * 0.0001
                return f"{coins:.0f} coins", usd
        except Exception:
            pass
        return "", 0.0

    async def run_once(self, context) -> ClaimResult:
        page = await context.new_page()
        try:
            await self.login_if_needed(page)
            await page.goto(FAUCET_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            roll = await page.query_selector("#roll-button, button:has-text('Roll')")
            if not roll:
                return ClaimResult(success=False, note="no roll (cooldown)",
                                   cooldown_seconds=self.default_cooldown)

            # Captcha gate (hCaptcha)
            if await page.query_selector(".h-captcha"):
                if not TWO_CAPTCHA_KEY:
                    return ClaimResult(success=False, note="captcha; set TWOCAPTCHA_KEY",
                                       cooldown_seconds=60 * 30)
                # plug in your solver here

            await roll.click()
            await page.wait_for_timeout(4000)

            bal_native, bal_usd = await self.fetch_balance(page)
            return ClaimResult(
                success=True,
                amount_native="roll",
                amount_usd=0.0005,
                cooldown_seconds=self.default_cooldown,
                balance_native=bal_native,
                balance_usd=bal_usd,
                note="rolled",
            )
        except Exception as e:
            log.exception("cointiply error")
            return ClaimResult(success=False, note=str(e),
                               cooldown_seconds=60 * 30)
        finally:
            await page.close()
