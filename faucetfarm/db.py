"""SQLite-backed state: claims, cooldowns, balances. Async via aiosqlite."""
import aiosqlite
import time
from contextlib import asynccontextmanager

DB_PATH = "faucetfarm.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_label TEXT NOT NULL,
    site TEXT NOT NULL,
    amount_usd REAL DEFAULT 0,
    amount_native TEXT DEFAULT '',
    success INTEGER NOT NULL,
    note TEXT DEFAULT '',
    ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_account_site ON claims(account_label, site);
CREATE INDEX IF NOT EXISTS idx_claims_ts ON claims(ts);

CREATE TABLE IF NOT EXISTS cooldowns (
    account_label TEXT NOT NULL,
    site TEXT NOT NULL,
    next_run_ts INTEGER NOT NULL,
    PRIMARY KEY (account_label, site)
);

CREATE TABLE IF NOT EXISTS balances (
    account_label TEXT NOT NULL,
    site TEXT NOT NULL,
    balance_native TEXT DEFAULT '',
    balance_usd REAL DEFAULT 0,
    updated_ts INTEGER NOT NULL,
    PRIMARY KEY (account_label, site)
);
"""


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    async with get_db() as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def record_claim(account: str, site: str, amount_usd: float,
                       amount_native: str, success: bool, note: str = ""):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO claims(account_label, site, amount_usd, amount_native, success, note, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account, site, amount_usd, amount_native, 1 if success else 0, note, int(time.time())),
        )
        await db.commit()


async def set_cooldown(account: str, site: str, seconds: int):
    next_ts = int(time.time()) + seconds
    async with get_db() as db:
        await db.execute(
            "INSERT INTO cooldowns(account_label, site, next_run_ts) VALUES (?, ?, ?) "
            "ON CONFLICT(account_label, site) DO UPDATE SET next_run_ts = excluded.next_run_ts",
            (account, site, next_ts),
        )
        await db.commit()


async def get_cooldown(account: str, site: str) -> int:
    async with get_db() as db:
        async with db.execute(
            "SELECT next_run_ts FROM cooldowns WHERE account_label=? AND site=?",
            (account, site),
        ) as cur:
            row = await cur.fetchone()
            return row["next_run_ts"] if row else 0


async def update_balance(account: str, site: str, balance_native: str, balance_usd: float):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO balances(account_label, site, balance_native, balance_usd, updated_ts) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(account_label, site) DO UPDATE SET "
            "balance_native=excluded.balance_native, "
            "balance_usd=excluded.balance_usd, "
            "updated_ts=excluded.updated_ts",
            (account, site, balance_native, balance_usd, int(time.time())),
        )
        await db.commit()


async def total_earnings_usd() -> float:
    async with get_db() as db:
        async with db.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) AS total FROM claims WHERE success=1"
        ) as cur:
            row = await cur.fetchone()
            return float(row["total"] or 0)
