"""
faucetfarm entry point.

Usage:
    python run.py                 # runs all accounts, all enabled sites, forever
    python run.py --once          # one pass, then exit (for cron / testing)
    python run.py --site firefaucet  # only run a specific adapter
"""
import argparse
import asyncio
import logging
import sys

from faucetfarm.config import load_config
from faucetfarm.scheduler import Scheduler


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.json")
    p.add_argument("--once", action="store_true",
                   help="Run a single pass then exit")
    p.add_argument("--site", default=None,
                   help="Only run this adapter (e.g. firefaucet)")
    p.add_argument("--account", default=None,
                   help="Only run this account label")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("faucetfarm.log"),
        ],
    )
    cfg = load_config(args.config)
    sched = Scheduler(cfg, only_site=args.site, only_account=args.account)
    try:
        if args.once:
            asyncio.run(sched.run_once())
        else:
            asyncio.run(sched.run_forever())
    except KeyboardInterrupt:
        print("\n[!] Stopped by user.")


if __name__ == "__main__":
    main()
