"""Postback listener: payout networks ping us, we mark the signup verified.

Most affiliate dashboards let you paste a postback URL with macros, e.g.
    https://your.host/postback?subid={subid}&payout={amount}&tx={txid}

The runner stamps `subid=afly_<signup_id>` into every referral URL, so when
the network fires the postback we can find the row and mark it verified.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from loguru import logger

from .config import Settings
from .db import DB, Signup
from .notify import discord


_SUBID_RE = re.compile(r"^afly_(\d+)$")


def _extract_id(subid: str) -> Optional[int]:
    m = _SUBID_RE.match(subid or "")
    return int(m.group(1)) if m else None


def build_app(settings: Settings, db: DB) -> FastAPI:
    app = FastAPI(title="afly postback listener")

    @app.get("/health")
    async def health():
        return {"ok": True, "ts": dt.datetime.utcnow().isoformat()}

    async def _process(
        subid: str,
        payout: float,
        secret: Optional[str],
        target: Optional[str],
        txid: Optional[str],
    ):
        if settings.webhook.secret and secret != settings.webhook.secret:
            raise HTTPException(status_code=403, detail="bad secret")

        sid = _extract_id(subid)
        if sid is None:
            raise HTTPException(status_code=400, detail=f"unrecognized subid: {subid}")

        with db.Session() as s:
            row = s.get(Signup, sid)
            if not row:
                raise HTTPException(status_code=404, detail=f"no signup {sid}")
            if target and row.target_id != target:
                logger.warning(f"postback target mismatch: {row.target_id} != {target}")

            row.status = "verified"
            row.verified_at = dt.datetime.utcnow()
            row.payout_usd = float(payout) if payout else (row.payout_usd or 0.0)
            note = f"postback ok"
            if txid:
                note += f" tx={txid}"
            row.note = (row.note + " | " if row.note else "") + note
            s.commit()
            email = row.email
            target_id = row.target_id
            paid = row.payout_usd

        await discord(
            settings.discord_webhook,
            f":white_check_mark: postback **{target_id}** "
            f"-> {email} (${paid:.2f})",
        )
        return {"ok": True, "id": sid, "payout_usd": paid}

    @app.get("/postback")
    async def postback_get(
        subid: str = Query(...),
        payout: float = Query(0.0),
        secret: Optional[str] = Query(None),
        target: Optional[str] = Query(None),
        txid: Optional[str] = Query(None),
    ):
        return await _process(subid, payout, secret, target, txid)

    @app.post("/postback")
    async def postback_post(
        subid: str = Query(...),
        payout: float = Query(0.0),
        secret: Optional[str] = Query(None),
        target: Optional[str] = Query(None),
        txid: Optional[str] = Query(None),
    ):
        return await _process(subid, payout, secret, target, txid)

    return app


def serve(settings: Settings, db: DB) -> None:
    import uvicorn  # local import so it's only required when used

    app = build_app(settings, db)
    uvicorn.run(
        app,
        host=settings.webhook.host,
        port=settings.webhook.port,
        log_level="info",
    )
