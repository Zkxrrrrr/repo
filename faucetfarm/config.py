"""Loads config.json into a typed object."""
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Account:
    label: str
    email: str
    password: str
    sites: List[str]


@dataclass
class TelegramCfg:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class Config:
    accounts: List[Account] = field(default_factory=list)
    telegram: TelegramCfg = field(default_factory=TelegramCfg)
    use_proxies: bool = True
    headless: bool = True
    max_concurrent_browsers: int = 4
    withdrawal_threshold_usd: float = 5.0
    btc_payout_address: str = ""
    ltc_payout_address: str = ""
    doge_payout_address: str = ""


def load_config(path: str = "config.json") -> Config:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Copy config.example.json -> config.json and fill it in."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = [Account(**a) for a in data.get("accounts", [])]
    tg = TelegramCfg(**data.get("telegram", {}))

    return Config(
        accounts=accounts,
        telegram=tg,
        use_proxies=data.get("use_proxies", True),
        headless=data.get("headless", True),
        max_concurrent_browsers=data.get("max_concurrent_browsers", 4),
        withdrawal_threshold_usd=data.get("withdrawal_threshold_usd", 5.0),
        btc_payout_address=data.get("btc_payout_address", ""),
        ltc_payout_address=data.get("ltc_payout_address", ""),
        doge_payout_address=data.get("doge_payout_address", ""),
    )
