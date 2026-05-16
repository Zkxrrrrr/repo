"""Idle-Empire signup adapter."""
from __future__ import annotations

from playwright.async_api import Page

from ..browser import fill_human
from .base import SignupAdapter, SignupContext, SignupResult
from . import register


SELECTORS = {
    # VERIFY against current idle-empire signup page
    "email": "input[name=email], input[type=email]",
    "password": "input[name=password], input[type=password]",
    "username": "input[name=username]",
    "submit": "button[type=submit], button:has-text('Sign Up')",
    "cookie_accept": "button:has-text('Accept'), button:has-text('Agree')",
}


@register
class IdleEmpireAdapter(SignupAdapter):
    target_id = "idle_empire"
    landing_url = "https://idle-empire.com/register"

    async def run(self, page: Page, ctx: SignupContext) -> SignupResult:
        url = self.referral_url_with_subid(
            self.landing_url, ctx.target.referral_code, ctx.signup_id, ref_param="rid"
        )
        await page.goto(url, wait_until="domcontentloaded")
        await self.click_if_present(page, SELECTORS["cookie_accept"])

        try:
            try:
                await fill_human(page, SELECTORS["username"], ctx.identity.username)
            except Exception:
                pass
            await fill_human(page, SELECTORS["email"], ctx.inbox.address)
            await fill_human(page, SELECTORS["password"], ctx.identity.password)
        except Exception as e:
            return SignupResult(ok=False, note=f"form fill failed: {e}")

        try:
            await page.click(SELECTORS["submit"])
        except Exception as e:
            return SignupResult(ok=False, note=f"submit failed: {e}")

        if ctx.target.requires_email_verify:
            link = await ctx.mail.wait_for_link(ctx.inbox, contains="idle-empire")
            if not link:
                return SignupResult(ok=False, note="no idle-empire verification email")
            verify_page = await page.context.new_page()
            await verify_page.goto(link, wait_until="domcontentloaded")
            await verify_page.close()
            return SignupResult(ok=True, verified=True, note="verified via email link")

        return SignupResult(ok=True, note="submitted")
