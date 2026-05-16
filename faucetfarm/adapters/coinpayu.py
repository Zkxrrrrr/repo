"""CoinPayU — paid-to-click ad viewer.

Flow:
- Login at https://www.coinpayu.com/sign_in
- Open /surf_ads (or /quick_ads)
- For each available ad: click, wait the timer, claim, repeat
"""
import asyncio
import logging
import re

from .base import Adapter, ClaimResult

log = logging.getLogger("coinpayu")

LOGIN_URL = "https://www.coinpayu.com/sign_in"
ADS_URLS = [
    "https://www.coinpayu.com/quick_ads",
    "https://www.coinpayu.com/surf_ads",
    "https://www.coinpayu.com/active_ads",
]
DASH_URL = "https://www.coinpayu.com/dashboard"


class CoinpayuAdapter(Adapter):
    name = "coinpayu"
    default_cooldown = 60 * 60  # 1 hour, ads refresh frequently

    async def login_if_needed(self, page):
        await page.goto(DASH_URL, wait_until="domcontentloaded")
        if "sign_in" in page.url or "login" in page.url:
            log.info(f"[{self.account_label}] coinpayu: logging in")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            await page.fill('input[type="email"]', self.email)
            await page.fill('input[type="password"]', self.password)
            await page.click('button[type="submit"]')
            try:
                await page.wait_for_url("**/dashboard**", timeout=20000)
            except Exception:
                log.warning(f"[{self.account_label}] coinpayu: login redirect not detected")

    async def fetch_balance(self, page) -> tuple[str, float]:
        try:
            await page.goto(DASH_URL, wait_until="domcontentloaded")
            txt = await page.inner_text("body")
            m = re.search(r"\$\s?([\d.]+)", txt)
            if m:
                usd = float(m.group(1))
                return f"${usd:.4f}", usd
        except Exception:
            pass
        return "", 0.0

    async def _click_one_ad(self, page) -> bool:
        """Click an ad item, wait for the verification timer, claim. Returns True on success."""
        ad = await page.query_selector("a.btn-ad, .ads-row a.btn-success")
        if not ad:
            return False

        # Open in new tab via popup
        async with page.context.expect_page() as ad_page_info:
            await ad.click()
        ad_page = await ad_page_info.value

        # Wait for the "Verify code" or timer to complete (30-45s typical)
        await ad_page.wait_for_timeout(45_000)

        # Click the verify/claim button if visible
        try:
            btn = await ad_page.query_selector("button:has-text('Click to get reward'), button:has-text('Verify')")
            if btn:
                await btn.click()
                await ad_page.wait_for_timeout(3000)
        except Exception:
            pass

        await ad_page.close()
        return True

    async def run_once(self, context) -> ClaimResult:
        page = await context.new_page()
        ads_clicked = 0
        try:
            await self.login_if_needed(page)

            for url in ADS_URLS:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                # Burn through up to 10 ads per page per pass
                for _ in range(10):
                    ok = await self._click_one_ad(page)
                    if not ok:
                        break
                    ads_clicked += 1
                    await page.reload()
                    await page.wait_for_timeout(2000)

            bal_native, bal_usd = await self.fetch_balance(page)
            return ClaimResult(
                success=ads_clicked > 0,
                amount_native=f"{ads_clicked} ads",
                amount_usd=ads_clicked * 0.0008,  # rough avg
                cooldown_seconds=self.default_cooldown,
                balance_native=bal_native,
                balance_usd=bal_usd,
                note=f"clicked {ads_clicked} ads",
            )
        except Exception as e:
            log.exception("coinpayu error")
            return ClaimResult(success=False, note=str(e),
                               cooldown_seconds=60 * 30)
        finally:
            await page.close()
