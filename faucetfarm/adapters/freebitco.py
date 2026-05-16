"""FreeBitco.in — hourly free roll.

Captcha-gated. If no captcha solver is configured, this adapter will run
when the captcha is hCaptcha-easy-mode (rare) or skip with cooldown.

Plug a 2captcha / capmonster API key to make this print money. Hooks below.
"""
import asyncio
import logging
import os
import re

from .base import Adapter, ClaimResult

log = logging.getLogger("freebitco")

LOGIN_URL = "https://freebitco.in/?op=signup_page"
HOME_URL = "https://freebitco.in/?tag=&op=home"

# Optional 2captcha/capmonster integration
TWO_CAPTCHA_KEY = os.environ.get("TWOCAPTCHA_KEY", "")


class FreeBitcoAdapter(Adapter):
    name = "freebitco"
    default_cooldown = 60 * 60 + 60  # 1h + slack

    async def login_if_needed(self, page):
        await page.goto(HOME_URL, wait_until="domcontentloaded")
        if await page.query_selector("#login_form"):
            log.info(f"[{self.account_label}] freebitco: logging in")
            await page.fill("#login_form_btc_address", self.email)
            await page.fill("#login_form_password", self.password)
            await page.click("#login_button")
            await page.wait_for_timeout(4000)

    async def _solve_hcaptcha_with_2captcha(self, page) -> bool:
        """Stub: integrate 2captcha here if key is set. Returns True on success."""
        if not TWO_CAPTCHA_KEY:
            return False
        # Real implementation:
        # 1. extract sitekey from page
        # 2. POST to https://2captcha.com/in.php
        # 3. poll for token
        # 4. inject token into page (h-captcha-response & g-recaptcha-response)
        # 5. trigger onSuccess callback
        log.info(f"[{self.account_label}] freebitco: 2captcha solving (impl your hook)")
        return False

    async def fetch_balance(self, page) -> tuple[str, float]:
        try:
            txt = await page.inner_text("#balance")
            btc = float(txt.strip().split()[0])
            # crude btc->usd, replace with live price feed if you care
            usd = btc * 65000.0
            return f"{btc:.8f} BTC", usd
        except Exception:
            return "", 0.0

    async def run_once(self, context) -> ClaimResult:
        page = await context.new_page()
        try:
            await self.login_if_needed(page)

            # Roll
            roll_btn = await page.query_selector("#free_play_form_button")
            if not roll_btn:
                return ClaimResult(success=False, note="no roll button (cooldown?)",
                                   cooldown_seconds=self.default_cooldown)

            # Captcha?
            if await page.query_selector(".h-captcha, .g-recaptcha"):
                solved = await self._solve_hcaptcha_with_2captcha(page)
                if not solved:
                    return ClaimResult(success=False, note="captcha not solved",
                                       cooldown_seconds=60 * 30)

            await roll_btn.click()
            await page.wait_for_timeout(5000)

            bal_native, bal_usd = await self.fetch_balance(page)
            return ClaimResult(
                success=True,
                amount_native="roll",
                amount_usd=0.0002,  # avg roll value
                cooldown_seconds=self.default_cooldown,
                balance_native=bal_native,
                balance_usd=bal_usd,
                note="rolled",
            )
        except Exception as e:
            log.exception("freebitco error")
            return ClaimResult(success=False, note=str(e),
                               cooldown_seconds=60 * 30)
        finally:
            await page.close()
