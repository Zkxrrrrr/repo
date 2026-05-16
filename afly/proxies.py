"""Round-robin proxy pool with health tracking."""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Proxy:
    uri: str
    fails: int = 0
    last_used_at: float = 0.0


@dataclass
class ProxyPool:
    proxies: List[Proxy] = field(default_factory=list)
    _cycle: itertools.cycle = field(init=False, default=None)
    fail_threshold: int = 3

    def __post_init__(self):
        self._cycle = itertools.cycle(self.proxies) if self.proxies else None

    @classmethod
    def from_uris(cls, uris: List[str]) -> "ProxyPool":
        return cls(proxies=[Proxy(uri=u) for u in uris])

    def acquire(self) -> Optional[Proxy]:
        if not self.proxies:
            return None
        # try at most len(proxies) times to find a healthy one
        for _ in range(len(self.proxies)):
            p = next(self._cycle)
            if p.fails < self.fail_threshold:
                return p
        # everyone's burnt — pick the least bad
        return min(self.proxies, key=lambda p: p.fails)

    def report(self, proxy: Optional[Proxy], ok: bool) -> None:
        if proxy is None:
            return
        if ok:
            proxy.fails = max(0, proxy.fails - 1)
        else:
            proxy.fails += 1

    def random(self) -> Optional[Proxy]:
        return random.choice(self.proxies) if self.proxies else None
