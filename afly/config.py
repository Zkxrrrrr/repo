"""Config loading: YAML for targets + .env for secrets."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Target(BaseModel):
    id: str
    enabled: bool = True
    referral_code: str
    payout_per_signup_usd: float = 0.0
    requires_sms: bool = False
    requires_email_verify: bool = True


class GlobalCfg(BaseModel):
    max_concurrency: int = 3
    per_target_cooldown_sec: int = 90
    jitter_sec: Tuple[int, int] = (15, 75)
    daily_cap_per_target: int = 25
    retries: int = 2


class CaptchaEntry(BaseModel):
    provider: str
    api_key: str


class WebhookCfg(BaseModel):
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    secret: Optional[str] = None  # if set, postbacks must include ?secret=...


class Settings(BaseModel):
    # secrets pulled from env
    captcha_provider: str = "2captcha"      # legacy single-provider knob
    captcha_api_key: Optional[str] = None   # legacy single-provider knob
    captcha_chain: List[CaptchaEntry] = Field(default_factory=list)
    sms_provider: str = "5sim"
    sms_api_key: Optional[str] = None
    email_provider: str = "mailtm"
    proxies: List[str] = Field(default_factory=list)
    discord_webhook: Optional[str] = None
    headless: bool = True

    # yaml side
    global_cfg: GlobalCfg = GlobalCfg()
    targets: List[Target] = Field(default_factory=list)
    webhook: WebhookCfg = WebhookCfg()


def _parse_proxies(raw: str) -> List[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(",", "\n").splitlines()]
    return [p for p in parts if p]


def _parse_captcha_chain() -> List[CaptchaEntry]:
    """Build chain from env: CAPTCHA_CHAIN='2captcha:KEY1,capsolver:KEY2'."""
    raw = os.getenv("CAPTCHA_CHAIN", "").strip()
    if not raw:
        return []
    out: List[CaptchaEntry] = []
    for item in [p.strip() for p in raw.split(",")]:
        if not item or ":" not in item:
            continue
        provider, key = item.split(":", 1)
        provider, key = provider.strip(), key.strip()
        if provider and key:
            out.append(CaptchaEntry(provider=provider, api_key=key))
    return out


def load_settings(config_path: str = "config.yml", env_path: str = ".env") -> Settings:
    if Path(env_path).exists():
        load_dotenv(env_path)

    yaml_data = {}
    if Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}

    global_cfg = GlobalCfg(**(yaml_data.get("global") or {}))
    targets = [Target(**t) for t in (yaml_data.get("targets") or [])]
    webhook = WebhookCfg(**(yaml_data.get("webhook") or {}))

    chain = _parse_captcha_chain()
    legacy_provider = os.getenv("CAPTCHA_PROVIDER", "2captcha")
    legacy_key = os.getenv("CAPTCHA_API_KEY")
    # if the chain isn't set explicitly, synthesize one from the legacy single provider
    if not chain and legacy_key:
        chain = [CaptchaEntry(provider=legacy_provider, api_key=legacy_key)]

    return Settings(
        captcha_provider=legacy_provider,
        captcha_api_key=legacy_key,
        captcha_chain=chain,
        sms_provider=os.getenv("SMS_PROVIDER", "5sim"),
        sms_api_key=os.getenv("SMS_API_KEY"),
        email_provider=os.getenv("EMAIL_PROVIDER", "mailtm"),
        proxies=_parse_proxies(os.getenv("PROXIES", "")),
        discord_webhook=os.getenv("DISCORD_WEBHOOK"),
        headless=os.getenv("HEADLESS", "true").lower() != "false",
        global_cfg=global_cfg,
        targets=targets,
        webhook=webhook,
    )
