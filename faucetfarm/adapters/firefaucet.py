"""FireFaucet — Auto Faucet (passive coin generation).

Flow:
- Login at https://firefaucet.win/login
- Open /autofaucet, click 'Start' to begin passive accrual
- Periodically claim accumulated balance to wallet
- No per-claim captcha when autofaucet is running
"""
import asyncio
import logging
import re

from .base import Adapter, ClaimResult

log = logging.getLogger("firefaucet")

LOGIN_URL = "https://firefaucet.win/login"
AUTOFAUCET_URL = "https://firefaucet.win/autofaucet"
DASHBOARD_URL = "https://firefaucet.win/dashboard"


class FireFaucetAdapter(Adapter):
    name = "firefaucet"
    default_cooldown = 60 * 60 * 4  # 4 hours

    async def login_if_needed(self, page):
        await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
        if "login" in page.url:
            log.info(f"[{self.account_label}] firefaucet: logging in")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            await page.fill('input[name="email"]', self.email)
            await page.fill('input[name="password"]', self.password)
            await page.click('button[type="submit"]')
            try:
                await page.wait_for_url("**/dashboard**", timeout=20000)
            except Exception:
                log.warning(f"[{self.account_label}] firefaucet: login redirect not detected")

    async def fetch_balance(self, page) -> tuple[str, float]:
        try:
            await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
            txt = await page.inner_text("body")
            m = re.search(r"([\d.,]+)\s*satoshi", txt, re.I)
            if m:
                sats = float(m.group(1).replace(",", ""))
                # rough sats -> usd; real value populated by withdraw screen
                usd = sats * 0.0006 / 1000  # placeholder
                return f"{sats:.0f} sats", usd
        except Exception as e:
            log.debug(f"firefaucet balance err: {e}")
        return "", 0.0

    async def run_once(self, context) -> ClaimResult:
        page = await context.new_page()
        try:
            await self.login_if_needed(page)

            # Open the autofaucet page and ensure 'Start' is clicked
            await page.goto(AUTOFAUCET_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)

            start_btn = await page.query_selector("button:has-text('Start')")
            if start_btn:
                try:
                    await start_btn.click()
                    log.info(f"[{self.account_label}] firefaucet: autofaucet started")
                except Exception:
                    pass

            # Let it accrue briefly so the next loop sees coins
            await page.wait_for_timeout(60_000)

            balance_native, balance_usd = await self.fetch_balance(page)

            return ClaimResult(
                success=True,
                amount_native="(passive)",
                amount_usd=0.0,
                cooldown_seconds=self.default_cooldown,
                balance_native=balance_native,
                balance_usd=balance_usd,
                note="autofaucet running",
            )
        except Exception as e:
            log.exception("firefaucet error")
            return ClaimResult(success=False, note=str(e),
                               cooldown_seconds=60 * 30)
        finally:
            await page.close()
