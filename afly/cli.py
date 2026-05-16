"""afly CLI."""
from __future__ import annotations

import asyncio
import sys

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from .config import load_settings
from .db import DB
from .scheduler import run_forever, run_once

app = typer.Typer(add_completion=False, help="afly — affiliate signup automation")
console = Console()


def _setup_logging():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<level>{level:<8}</level> | {message}")


@app.command()
def once(
    config: str = typer.Option("config.yml", "--config", "-c"),
    env: str = typer.Option(".env", "--env", "-e"),
):
    """Run one pass over every eligible target, then exit."""
    _setup_logging()
    settings = load_settings(config, env)
    db = DB()
    asyncio.run(run_once(settings, db))


@app.command()
def daemon(
    config: str = typer.Option("config.yml", "--config", "-c"),
    env: str = typer.Option(".env", "--env", "-e"),
    loop_sleep: int = typer.Option(60, "--loop-sleep"),
):
    """Run forever, cycling targets with cooldowns + caps."""
    _setup_logging()
    settings = load_settings(config, env)
    db = DB()
    asyncio.run(run_forever(settings, db, loop_sleep=loop_sleep))


@app.command()
def webhook(
    config: str = typer.Option("config.yml", "--config", "-c"),
    env: str = typer.Option(".env", "--env", "-e"),
):
    """Run the postback listener (FastAPI + uvicorn)."""
    _setup_logging()
    from .webhook import serve  # local import — fastapi/uvicorn optional install

    settings = load_settings(config, env)
    db = DB()
    serve(settings, db)


@app.command()
def stats():
    """Show per-target totals from the local DB."""
    db = DB()
    rows = db.totals()
    t = Table(title="afly totals")
    t.add_column("target")
    t.add_column("signups", justify="right")
    t.add_column("payout (USD)", justify="right")
    grand = 0.0
    for target_id, count, payout in rows:
        payout = float(payout or 0.0)
        grand += payout
        t.add_row(target_id, str(count), f"${payout:,.2f}")
    t.add_row("[bold]TOTAL[/bold]", "", f"[bold]${grand:,.2f}[/bold]")
    console.print(t)


@app.command()
def targets(config: str = typer.Option("config.yml", "--config", "-c"),
            env: str = typer.Option(".env", "--env", "-e")):
    """List configured targets."""
    settings = load_settings(config, env)
    t = Table(title="targets")
    for col in ("id", "enabled", "payout/$", "email_verify", "sms"):
        t.add_column(col)
    for tgt in settings.targets:
        t.add_row(
            tgt.id,
            "✓" if tgt.enabled else "·",
            f"{tgt.payout_per_signup_usd:.2f}",
            "✓" if tgt.requires_email_verify else "·",
            "✓" if tgt.requires_sms else "·",
        )
    console.print(t)


def main():
    app()


if __name__ == "__main__":
    main()
