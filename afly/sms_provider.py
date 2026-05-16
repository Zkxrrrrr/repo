"""Pluggable SMS-verification provider. Default impl is 5sim.net."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx


@dataclass
class SmsOrder:
    id: str
    phone: str


class SmsProvider(Protocol):
    async def order(self, service: str, country: str = "usa") -> SmsOrder: ...
    async def wait_code(self, order: SmsOrder, timeout: float = 180.0) -> Optional[str]: ...
    async def finish(self, order: SmsOrder, success: bool = True) -> None: ...


class FiveSim:
    """Thin wrapper around 5sim.net REST API."""

    BASE = "https://5sim.net/v1"

    def __init__(self, api_key: str, timeout: float = 20.0):
        self._client = httpx.AsyncClient(
            base_url=self.BASE,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )

    async def close(self):
        await self._client.aclose()

    async def order(self, service: str, country: str = "usa") -> SmsOrder:
        # operator "any" lets the provider pick whatever's cheapest/available
        r = await self._client.get(f"/user/buy/activation/{country}/any/{service}")
        r.raise_for_status()
        data = r.json()
        return SmsOrder(id=str(data["id"]), phone=data["phone"])

    async def wait_code(self, order: SmsOrder, timeout: float = 180.0) -> Optional[str]:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            r = await self._client.get(f"/user/check/{order.id}")
            if r.status_code == 200:
                sms_list = r.json().get("sms") or []
                if sms_list:
                    # take latest code-bearing message
                    code = sms_list[-1].get("code")
                    if code:
                        return code
            await asyncio.sleep(5.0)
        return None

    async def finish(self, order: SmsOrder, success: bool = True) -> None:
        path = "finish" if success else "cancel"
        try:
            await self._client.get(f"/user/{path}/{order.id}")
        except Exception:
            pass


def get_provider(name: str, api_key: Optional[str]) -> Optional[SmsProvider]:
    if not api_key:
        return None
    if name.lower() == "5sim":
        return FiveSim(api_key)
    raise ValueError(f"Unknown SMS provider: {name}")
