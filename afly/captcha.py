"""Captcha solver providers + a fallback chain that tries them in order.

Supported providers: 2captcha, capsolver, anti-captcha.
All three expose: recaptcha_v2(sitekey, page_url), hcaptcha(...), turnstile(...).
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, Protocol

import httpx
from loguru import logger


class CaptchaSolver(Protocol):
    async def recaptcha_v2(self, sitekey: str, page_url: str) -> str: ...
    async def hcaptcha(self, sitekey: str, page_url: str) -> str: ...
    async def turnstile(self, sitekey: str, page_url: str) -> str: ...
    async def close(self) -> None: ...


# ---------- 2captcha ----------------------------------------------------------

class TwoCaptcha:
    BASE = "https://2captcha.com"
    name = "2captcha"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._key = api_key
        self._client = httpx.AsyncClient(base_url=self.BASE, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def _submit(self, params: dict) -> str:
        params = {**params, "key": self._key, "json": 1}
        r = await self._client.post("/in.php", data=params)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != 1:
            raise RuntimeError(f"2captcha submit failed: {data}")
        return data["request"]

    async def _poll(self, cap_id: str, timeout: float = 180.0) -> str:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            r = await self._client.get(
                "/res.php",
                params={"key": self._key, "action": "get", "id": cap_id, "json": 1},
            )
            data = r.json()
            if data.get("status") == 1:
                return data["request"]
            if data.get("request") not in ("CAPCHA_NOT_READY",):
                raise RuntimeError(f"2captcha error: {data}")
            await asyncio.sleep(5.0)
        raise TimeoutError("2captcha solve timed out")

    async def recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        cid = await self._submit({"method": "userrecaptcha", "googlekey": sitekey, "pageurl": page_url})
        return await self._poll(cid)

    async def hcaptcha(self, sitekey: str, page_url: str) -> str:
        cid = await self._submit({"method": "hcaptcha", "sitekey": sitekey, "pageurl": page_url})
        return await self._poll(cid)

    async def turnstile(self, sitekey: str, page_url: str) -> str:
        cid = await self._submit({"method": "turnstile", "sitekey": sitekey, "pageurl": page_url})
        return await self._poll(cid)


# ---------- capsolver ---------------------------------------------------------

class CapSolver:
    BASE = "https://api.capsolver.com"
    name = "capsolver"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._key = api_key
        self._client = httpx.AsyncClient(base_url=self.BASE, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def _solve(self, task: dict, timeout: float = 180.0) -> str:
        r = await self._client.post(
            "/createTask", json={"clientKey": self._key, "task": task}
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errorId"):
            raise RuntimeError(f"capsolver createTask: {data}")
        task_id = data["taskId"]

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            r = await self._client.post(
                "/getTaskResult", json={"clientKey": self._key, "taskId": task_id}
            )
            data = r.json()
            if data.get("errorId"):
                raise RuntimeError(f"capsolver getTaskResult: {data}")
            if data.get("status") == "ready":
                sol = data.get("solution", {})
                return (
                    sol.get("gRecaptchaResponse")
                    or sol.get("token")
                    or sol.get("captchaToken")
                    or ""
                )
            await asyncio.sleep(4.0)
        raise TimeoutError("capsolver timed out")

    async def recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        return await self._solve({
            "type": "ReCaptchaV2TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })

    async def hcaptcha(self, sitekey: str, page_url: str) -> str:
        return await self._solve({
            "type": "HCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })

    async def turnstile(self, sitekey: str, page_url: str) -> str:
        return await self._solve({
            "type": "AntiTurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })


# ---------- anti-captcha ------------------------------------------------------

class AntiCaptcha:
    BASE = "https://api.anti-captcha.com"
    name = "anti-captcha"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self._key = api_key
        self._client = httpx.AsyncClient(base_url=self.BASE, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def _solve(self, task: dict, timeout: float = 180.0) -> str:
        r = await self._client.post(
            "/createTask", json={"clientKey": self._key, "task": task}
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errorId"):
            raise RuntimeError(f"anti-captcha createTask: {data}")
        task_id = data["taskId"]

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            r = await self._client.post(
                "/getTaskResult", json={"clientKey": self._key, "taskId": task_id}
            )
            data = r.json()
            if data.get("errorId"):
                raise RuntimeError(f"anti-captcha getTaskResult: {data}")
            if data.get("status") == "ready":
                sol = data.get("solution", {})
                return (
                    sol.get("gRecaptchaResponse")
                    or sol.get("token")
                    or ""
                )
            await asyncio.sleep(4.0)
        raise TimeoutError("anti-captcha timed out")

    async def recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        return await self._solve({
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })

    async def hcaptcha(self, sitekey: str, page_url: str) -> str:
        return await self._solve({
            "type": "HCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })

    async def turnstile(self, sitekey: str, page_url: str) -> str:
        return await self._solve({
            "type": "TurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        })


# ---------- chain -------------------------------------------------------------

class CaptchaChain:
    """Tries each underlying solver in order; falls back on failure."""

    def __init__(self, solvers: List[CaptchaSolver]):
        self._solvers = solvers

    async def close(self):
        for s in self._solvers:
            try:
                await s.close()
            except Exception:
                pass

    async def _run(self, method: str, *args) -> str:
        last_err: Optional[Exception] = None
        for s in self._solvers:
            try:
                fn = getattr(s, method)
                token = await fn(*args)
                if token:
                    return token
                raise RuntimeError("empty token")
            except Exception as e:
                logger.warning(f"captcha [{getattr(s, 'name', '?')}] failed: {e}")
                last_err = e
        raise RuntimeError(f"all captcha solvers failed: {last_err}")

    async def recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        return await self._run("recaptcha_v2", sitekey, page_url)

    async def hcaptcha(self, sitekey: str, page_url: str) -> str:
        return await self._run("hcaptcha", sitekey, page_url)

    async def turnstile(self, sitekey: str, page_url: str) -> str:
        return await self._run("turnstile", sitekey, page_url)


_FACTORIES = {
    "2captcha": TwoCaptcha,
    "capsolver": CapSolver,
    "anti-captcha": AntiCaptcha,
    "anticaptcha": AntiCaptcha,
}


def _build(name: str, key: str) -> Optional[CaptchaSolver]:
    cls = _FACTORIES.get(name.lower().strip())
    if cls is None or not key:
        return None
    return cls(key)


def get_solver(provider: str, api_key: Optional[str]) -> Optional[CaptchaSolver]:
    """Build a single solver. Kept for back-compat with single-provider configs."""
    if not api_key:
        return None
    s = _build(provider, api_key)
    if s is None:
        raise ValueError(f"Unknown captcha provider: {provider}")
    return s


def build_chain(spec: List[dict]) -> Optional[CaptchaChain]:
    """spec = [{provider: '2captcha', api_key: '...'}, ...] in fallback order."""
    solvers: List[CaptchaSolver] = []
    for entry in spec or []:
        s = _build(entry.get("provider", ""), entry.get("api_key", ""))
        if s is not None:
            solvers.append(s)
    if not solvers:
        return None
    return CaptchaChain(solvers)
