"""Temporary email via mail.tm — free, public API, no key needed."""
from __future__ import annotations

import asyncio
import random
import string
from dataclasses import dataclass
from typing import List, Optional

import httpx

MAILTM = "https://api.mail.tm"


@dataclass
class TempInbox:
    address: str
    password: str
    token: str


class MailTm:
    def __init__(self, timeout: float = 20.0):
        self._client = httpx.AsyncClient(base_url=MAILTM, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def _domains(self) -> List[str]:
        r = await self._client.get("/domains")
        r.raise_for_status()
        return [d["domain"] for d in r.json().get("hydra:member", [])]

    async def create(self) -> TempInbox:
        domains = await self._domains()
        if not domains:
            raise RuntimeError("mail.tm returned no domains")
        local = "".join(random.choices(string.ascii_lowercase + string.digits, k=14))
        addr = f"{local}@{random.choice(domains)}"
        pw = "".join(random.choices(string.ascii_letters + string.digits, k=18))

        r = await self._client.post("/accounts", json={"address": addr, "password": pw})
        r.raise_for_status()
        r = await self._client.post("/token", json={"address": addr, "password": pw})
        r.raise_for_status()
        token = r.json()["token"]
        return TempInbox(address=addr, password=pw, token=token)

    async def wait_for_link(
        self,
        inbox: TempInbox,
        contains: Optional[str] = None,
        timeout: float = 180.0,
        poll_interval: float = 5.0,
    ) -> Optional[str]:
        """Poll the inbox until a message arrives; pull the first http(s) link."""
        deadline = asyncio.get_event_loop().time() + timeout
        headers = {"Authorization": f"Bearer {inbox.token}"}
        while asyncio.get_event_loop().time() < deadline:
            r = await self._client.get("/messages", headers=headers)
            if r.status_code == 200:
                msgs = r.json().get("hydra:member", [])
                for m in msgs:
                    mid = m["id"]
                    full = await self._client.get(f"/messages/{mid}", headers=headers)
                    if full.status_code != 200:
                        continue
                    body = full.json()
                    text = (body.get("text") or "") + " " + " ".join(body.get("html", []))
                    link = self._extract_link(text, contains)
                    if link:
                        return link
            await asyncio.sleep(poll_interval)
        return None

    @staticmethod
    def _extract_link(text: str, contains: Optional[str]) -> Optional[str]:
        import re
        urls = re.findall(r"https?://[^\s\"'<>]+", text)
        for u in urls:
            if contains is None or contains in u:
                return u
        return None
