"""Single-signup pipeline: identity -> inbox -> browser -> adapter -> persist."""
from __future__ import annotations

from typing import Optional

from loguru import logger

from .adapters import get_adapter
from .adapters.base import SignupContext, SignupResult
from .browser import fresh_context
from .captcha import build_chain
from .config import Settings, Target
from .db import DB
from .email_provider import MailTm
from .fingerprint import random_fingerprint
from .identity import generate as gen_identity
from .notify import discord
from .proxies import ProxyPool, Proxy
from .sms_provider import get_provider as get_sms


async def run_signup(
    target: Target,
    settings: Settings,
    db: DB,
    proxies: ProxyPool,
) -> SignupResult:
    fp = random_fingerprint()
    proxy: Optional[Proxy] = proxies.acquire()
    identity = gen_identity()

    mail = MailTm()
    captcha_solver = build_chain(
        [{"provider": e.provider, "api_key": e.api_key} for e in settings.captcha_chain]
    )
    sms_provider = get_sms(settings.sms_provider, settings.sms_api_key)

    sid = None
    try:
        inbox = await mail.create()
        adapter_cls = get_adapter(target.id)
        adapter = adapter_cls()

        sid = db.record(
            target_id=target.id,
            status="pending",
            email=inbox.address,
            username=identity.username,
            password=identity.password,
            proxy=(proxy.uri if proxy else None),
            user_agent=fp.user_agent,
        ).id

        async with fresh_context(fp, proxy=proxy, headless=settings.headless) as (
            _pw, _br, _ctx, page,
        ):
            ctx = SignupContext(
                target=target,
                identity=identity,
                inbox=inbox,
                mail=mail,
                captcha_solver=captcha_solver,
                sms_provider=sms_provider,
                signup_id=sid,
            )
            try:
                result = await adapter.run(page, ctx)
            except Exception as e:
                logger.exception(f"[{target.id}] adapter raised")
                result = SignupResult(ok=False, note=f"exception: {e}")

        # persist outcome
        if result.ok:
            payout = target.payout_per_signup_usd if result.verified else 0.0
            db.update(
                sid,
                status="verified" if result.verified else "ok",
                note=result.note,
                payout_usd=payout,
            )
            proxies.report(proxy, ok=True)
            await discord(
                settings.discord_webhook,
                f":moneybag: **{target.id}** signup -> {inbox.address} "
                f"({'verified' if result.verified else 'submitted'}, ${payout:.2f})",
            )
        else:
            db.update(sid, status="failed", note=result.note)
            proxies.report(proxy, ok=False)

        return result
    finally:
        await mail.close()
        if captcha_solver and hasattr(captcha_solver, "close"):
            try:
                await captcha_solver.close()
            except Exception:
                pass
        if sms_provider and hasattr(sms_provider, "close"):
            try:
                await sms_provider.close()
            except Exception:
                pass
