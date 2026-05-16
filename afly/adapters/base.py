"""SignupAdapter contract every target must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from playwright.async_api import Page

from ..config import Target
from ..email_provider import MailTm, TempInbox
from ..identity import Identity


@dataclass
class SignupContext:
    target: Target
    identity: Identity
    inbox: TempInbox
    mail: MailTm
    captcha_solver: Any = None     # CaptchaChain or None
    sms_provider: Any = None       # FiveSim or None
    signup_id: Optional[int] = None  # DB row id; used as SubID for postback attribution
    extra: dict = field(default_factory=dict)


@dataclass
class SignupResult:
    ok: bool
    note: str = ""
    verified: bool = False


class SignupAdapter(ABC):
    """One adapter per referral site."""
    target_id: str = "abstract"
    landing_url: str = ""

    @abstractmethod
    async def run(self, page: Page, ctx: SignupContext) -> SignupResult:
        """Drive the signup flow start-to-finish on `page`."""
        raise NotImplementedError

    # --- helpers child classes can call ------------------------------------

    @staticmethod
    def referral_url(base: str, code: str, param: str = "ref") -> str:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{param}={code}"

    @staticmethod
    def referral_url_with_subid(
        base: str, code: str, signup_id: Optional[int],
        ref_param: str = "ref", subid_param: str = "subid",
    ) -> str:
        url = SignupAdapter.referral_url(base, code, ref_param)
        if signup_id is not None:
            url = f"{url}&{subid_param}=afly_{signup_id}"
        return url

    @staticmethod
    async def click_if_present(page: Page, selector: str, timeout: int = 1500) -> bool:
        try:
            el = await page.wait_for_selector(selector, timeout=timeout)
            if el:
                await el.click()
                return True
        except Exception:
            return False
        return False
