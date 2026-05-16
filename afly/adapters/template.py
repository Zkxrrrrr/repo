"""Copy this file to add a new target. Steps are commented for clarity."""
from __future__ import annotations

from playwright.async_api import Page

from ..browser import fill_human
from .base import SignupAdapter, SignupContext, SignupResult
from . import register


# @register   # uncomment after renaming target_id
class TemplateAdapter(SignupAdapter):
    target_id = "template"
    landing_url = "https://example.com/signup"

    async def run(self, page: Page, ctx: SignupContext) -> SignupResult:
        # 1) load referral landing
        url = self.referral_url(self.landing_url, ctx.target.referral_code)
        await page.goto(url, wait_until="domcontentloaded")

        # 2) optional: dismiss cookie banners
        await self.click_if_present(page, "button:has-text('Accept')")

        # 3) fill the form
        await fill_human(page, "input[name=email]", ctx.inbox.address)
        await fill_human(page, "input[name=password]", ctx.identity.password)
        await fill_human(page, "input[name=username]", ctx.identity.username)

        # 4) (optional) solve captcha — example reCAPTCHA v2
        # token = await ctx.captcha_solver.recaptcha_v2(SITEKEY, page.url)
        # await page.evaluate(f"document.getElementById('g-recaptcha-response').value='{token}'")

        # 5) submit
        await page.click("button[type=submit]")

        # 6) (optional) email verification
        if ctx.target.requires_email_verify:
            link = await ctx.mail.wait_for_link(ctx.inbox, contains="example.com")
            if not link:
                return SignupResult(ok=False, note="no verification email")
            verify_page = await page.context.new_page()
            await verify_page.goto(link, wait_until="domcontentloaded")
            await verify_page.close()
            return SignupResult(ok=True, verified=True)

        return SignupResult(ok=True)
