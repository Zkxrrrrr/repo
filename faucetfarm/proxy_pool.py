"""Free-proxy harvester + validator. Refreshes from public lists every N minutes.

For real scale, replace with a paid residential pool (BrightData, IPRoyal,
Smartproxy). The interface stays the same: get_proxy() -> dict for Playwright.
"""
import asyncio
import logging
import random
import time
from typing import List, Optional

import aiohttp

log = logging.getLogger("proxy_pool")

FREE_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
]

VALIDATE_URL = "https://httpbin.org/ip"
VALIDATE_TIMEOUT = 6
REFRESH_EVERY = 30 * 60  # seconds


class ProxyPool:
    def __init__(self):
        self._proxies: List[str] = []
        self._last_refresh = 0
        self._lock = asyncio.Lock()

    async def _fetch_lists(self) -> List[str]:
        out: List[str] = []
        async with aiohttp.ClientSession() as s:
            for url in FREE_PROXY_SOURCES:
                try:
                    async with s.get(url, timeout=15) as r:
                        if r.status == 200:
                            txt = await r.text()
                            for line in txt.splitlines():
                                line = line.strip()
                                if line and ":" in line:
                                    out.append(line)
                except Exception as e:
                    log.debug(f"source {url} failed: {e}")
        # de-dup
        return list(set(out))

    async def _validate(self, proxy: str) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=VALIDATE_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(VALIDATE_URL, proxy=f"http://{proxy}") as r:
                    return r.status == 200
        except Exception:
            return False

    async def refresh(self, max_keep: int = 200):
        async with self._lock:
            log.info("refreshing proxy pool...")
            candidates = await self._fetch_lists()
            log.info(f"got {len(candidates)} candidate proxies, validating...")
            random.shuffle(candidates)
            candidates = candidates[:600]  # cap validation work

            sem = asyncio.Semaphore(60)

            async def check(p):
                async with sem:
                    if await self._validate(p):
                        return p
                    return None

            results = await asyncio.gather(*(check(p) for p in candidates))
            valid = [p for p in results if p]
            self._proxies = valid[:max_keep]
            self._last_refresh = int(time.time())
            log.info(f"proxy pool: {len(self._proxies)} valid proxies")

    async def get(self) -> Optional[str]:
        if not self._proxies or (time.time() - self._last_refresh) > REFRESH_EVERY:
            await self.refresh()
        if not self._proxies:
            return None
        return random.choice(self._proxies)

    def to_playwright(self, proxy: str) -> dict:
        return {"server": f"http://{proxy}"}


# module-level singleton
pool = ProxyPool()
