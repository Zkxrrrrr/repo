"""Async scheduler: wakes up every minute, picks accounts whose cooldowns
have elapsed, runs the next adapter for them, respects max_concurrent_browsers.
"""
import asyncio
import logging
import time
from typing import Optional

from .adapters import get_adapter
from .browser import make_context
from .config import Account, Config
from .db import (init_db, record_claim, set_cooldown, get_cooldown,
                 update_balance, total_earnings_usd)
from .notify import telegram_send

log = logging.getLogger("scheduler")


class Scheduler:
    def __init__(self, cfg: Config, only_site: Optional[str] = None,
                 only_account: Optional[str] = None):
        self.cfg = cfg
        self.only_site = only_site
        self.only_account = only_account
        self.sem = asyncio.Semaphore(cfg.max_concurrent_browsers)
        self._last_alert_total = 0.0

    def _payout_addrs(self) -> dict:
        return {
            "btc": self.cfg.btc_payout_address,
            "ltc": self.cfg.ltc_payout_address,
            "doge": self.cfg.doge_payout_address,
        }

    async def _run_adapter(self, account: Account, site_name: str):
        async with self.sem:
            cd = await get_cooldown(account.label, site_name)
            if cd > time.time():
                return
            try:
                AdapterCls = get_adapter(site_name)
            except KeyError:
                log.warning(f"unknown site '{site_name}' for {account.label}, skipping")
                return

            adapter = AdapterCls(
                account_label=account.label,
                email=account.email,
                password=account.password,
                payout_addresses=self._payout_addrs(),
            )

            log.info(f"[{account.label}] running {site_name}")
            try:
                async with make_context(account.label,
                                        headless=self.cfg.headless,
                                        use_proxy=self.cfg.use_proxies) as ctx:
                    result = await adapter.run_once(ctx)
            except Exception as e:
                log.exception(f"[{account.label}] {site_name} crashed")
                await set_cooldown(account.label, site_name, 60 * 30)
                return

            await record_claim(account.label, site_name, result.amount_usd,
                               result.amount_native, result.success, result.note)
            if result.balance_native or result.balance_usd:
                await update_balance(account.label, site_name,
                                     result.balance_native, result.balance_usd)
            await set_cooldown(account.label, site_name, result.cooldown_seconds)
            log.info(f"[{account.label}] {site_name} -> "
                     f"{'OK' if result.success else 'FAIL'} "
                     f"{result.amount_native} (${result.amount_usd:.4f}) | "
                     f"next in {result.cooldown_seconds//60}m | {result.note}")

            await self._maybe_alert()

    async def _maybe_alert(self):
        if not self.cfg.telegram.enabled:
            return
        total = await total_earnings_usd()
        threshold = self.cfg.withdrawal_threshold_usd
        if total - self._last_alert_total >= threshold:
            await telegram_send(self.cfg.telegram.bot_token,
                                self.cfg.telegram.chat_id,
                                f"[faucetfarm] total earnings: ${total:.2f}")
            self._last_alert_total = total

    async def run_once(self):
        await init_db()
        tasks = []
        for acc in self.cfg.accounts:
            if self.only_account and acc.label != self.only_account:
                continue
            for site in acc.sites:
                if self.only_site and site != self.only_site:
                    continue
                tasks.append(asyncio.create_task(self._run_adapter(acc, site)))
        if not tasks:
            log.warning("no tasks scheduled")
            return
        await asyncio.gather(*tasks)
        total = await total_earnings_usd()
        log.info(f"pass complete. lifetime earnings: ${total:.4f}")

    async def run_forever(self):
        await init_db()
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("scheduler pass crashed")
            # sleep 60s between passes; cooldowns prevent repeat work
            await asyncio.sleep(60)
