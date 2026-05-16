"""Per-session fingerprint randomization (UA / viewport / timezone / locale)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Tuple


_USER_AGENTS = [
    # rotated, kept current-ish — extend freely
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    (1920, 1080), (1536, 864), (1440, 900), (1366, 768), (1680, 1050), (2560, 1440),
]

_TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Toronto", "Europe/London",
]

_LOCALES = ["en-US", "en-GB", "en-CA"]


@dataclass
class Fingerprint:
    user_agent: str
    viewport: Tuple[int, int]
    timezone: str
    locale: str


def random_fingerprint() -> Fingerprint:
    return Fingerprint(
        user_agent=random.choice(_USER_AGENTS),
        viewport=random.choice(_VIEWPORTS),
        timezone=random.choice(_TIMEZONES),
        locale=random.choice(_LOCALES),
    )
