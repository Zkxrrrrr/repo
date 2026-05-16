"""Async scheduler: spreads signups across targets with cooldowns + daily caps."""
from __future__ import annotations

import asyncio
import datetime as dt
import random
from typing import List

from loguru import logger
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from .config import Settings, Target
from .db import DB
from .proxies import ProxyPool
from .runner import run_signup


def _eligible(target: Target, settings: Settings, db: DB) -> bool:
    if not target.enabled:
        return False
    if db.count_today(target.id) >= settings.global_cfg.daily_cap_per_target:
        logger.info(f"[{target.id}] daily cap reached, skipping")
        return False
    last = db.last_attempt(target.id)
    if last is not None:
        delta = (dt.datetime.utcnow() - last).total_seconds()
        if delta < settings.global_cfg.per_target_cooldown_sec:
            return False
    return True


async def _run_one(target: Target, settings: Settings, db: DB, proxies: ProxyPool, sem: asyncio.Semaphore):
    async with sem:
        lo, hi = settings.global_cfg.jitter_sec
        await asyncio.sleep(random.uniform(lo, hi))
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.global_cfg.retries + 1),
                wait=wait_exponential(multiplier=2, min=2, max=30),
                reraise=True,
            ):
                with attempt:
                    result = await run_signup(target, settings, db, proxies)
                    if not result.ok:
                        raise RuntimeError(result.note or "signup failed")
                    logger.success(f"[{target.id}] OK ({result.note})")
        except (RetryError, Exception) as e:
            logger.error(f"[{target.id}] gave up: {e}")


async def run_once(settings: Settings, db: DB) -> None:
    """Single pass: fire one signup attempt per eligible target."""
    proxies = ProxyPool.from_uris(settings.proxies)
    sem = asyncio.Semaphore(settings.global_cfg.max_concurrency)

    todo: List[Target] = [t for t in settings.targets if _eligible(t, settings, db)]
    if not todo:
        logger.info("nothing eligible right now")
        return

    await asyncio.gather(*(_run_one(t, settings, db, proxies, sem) for t in todo))


async def run_forever(settings: Settings, db: DB, loop_sleep: int = 60) -> None:
    """Daemon loop — keeps cycling through targets respecting cooldowns + caps."""
    logger.info("afly daemon up")
    while True:
        try:
            await run_once(settings, db)
        except Exception as e:
            logger.exception(f"loop iteration crashed: {e}")
        await asyncio.sleep(loop_sleep)
