"""Abstract adapter. One subclass per faucet/microtask site."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClaimResult:
    success: bool
    amount_native: str = ""           # e.g. "0.00000123 BTC", "5 sats"
    amount_usd: float = 0.0
    cooldown_seconds: int = 3600      # how long until we should try again
    balance_native: str = ""
    balance_usd: float = 0.0
    note: str = ""


class Adapter(ABC):
    name: str = "base"
    default_cooldown: int = 3600  # seconds

    def __init__(self, account_label: str, email: str, password: str,
                 payout_addresses: dict):
        self.account_label = account_label
        self.email = email
        self.password = password
        self.payout_addresses = payout_addresses  # {"btc": "...", "ltc": "..."}

    @abstractmethod
    async def run_once(self, context) -> ClaimResult:
        """Perform login if needed, do one claim/round of work, update balance.
        `context` is a Playwright BrowserContext.
        """
        ...

    async def login_if_needed(self, page):
        """Override per-site. Use cookies from persistent profile when possible."""
        pass

    async def fetch_balance(self, page) -> tuple[str, float]:
        """Return (balance_native_str, balance_usd_float). Override per site."""
        return "", 0.0
