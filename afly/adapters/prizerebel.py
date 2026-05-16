"""PrizeRebel signup adapter."""
from __future__ import annotations

from playwright.async_api import Page

from ..browser import fill_human
from .base import SignupAdapter, SignupContext, SignupResult
from . import register


SELECTORS = {
    # VERIFY against current prizerebel signup page
    "username": "input[name=username]",
    "email": "input[name=email], input[type=email]",
    "password": "input[name=password], input[type=password]",
    "submit": "button[type=submit], button:has-text('Sign Up')",
    "cookie_accept": "button:has-text('Accept'), #onetrust-accept-btn-handler",
}


@register
class PrizeRebelAdapter(SignupAdapter):
    target_id = "prizerebel"
    landing_url = "https://www.prizerebel.com/index.php?r="

    async def run(self, page: Page, ctx: SignupContext) -> SignupResult:
        base = f"{self.landing_url}{ctx.target.referral_code}"
        url = f"{base}&subid=afly_{ctx.signup_id}" if ctx.signup_id else base
        await page.goto(url, wait_until="domcontentloaded")
        await self.click_if_present(page, SELECTORS["cookie_accept"])

        try:
            await fill_human(page, SELECTORS["username"], ctx.identity.username)
            await fill_human(page, SELECTORS["email"], ctx.inbox.address)
            await fill_human(page, SELECTORS["password"], ctx.identity.password)
        except Exception as e:
            return SignupResult(ok=False, note=f"form fill failed: {e}")

        try:
            await page.click(SELECTORS["submit"])
        except Exception as e:
            return SignupResult(ok=False, note=f"submit failed: {e}")

        if ctx.target.requires_email_verify:
            link = await ctx.mail.wait_for_link(ctx.inbox, contains="prizerebel")
            if not link:
                return SignupResult(ok=False, note="no prizerebel verification email")
            verify_page = await page.context.new_page()
            await verify_page.goto(link, wait_until="domcontentloaded")
            await verify_page.close()
            return SignupResult(ok=True, verified=True, note="verified via email link")

        return SignupResult(ok=True, note="submitted")
