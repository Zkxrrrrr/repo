# faucetfarm — setup & ops

## What this is
Async bot that runs accounts across crypto faucets, ad-view sites, and
microtask sites in parallel through rotating proxies. SQLite tracks
cooldowns and earnings. Telegram alerts when balance crosses threshold.

## Currently wired adapters
- **firefaucet** — autofaucet (passive, no captcha) — fast win
- **coinpayu** — paid-to-click ads (no captcha on ad clicks)
- **freebitco** — hourly roll (captcha-gated; needs 2captcha key)
- **cointiply** — hourly faucet roll (captcha-gated; needs 2captcha key)

## Install (Ubuntu / Debian VPS)

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone <your-fork> faucetfarm && cd faucetfarm
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

## Configure

```bash
cp config.example.json config.json
nano config.json
```

Fill in:
- `accounts[*].email` / `password` — sign up on each faucet manually first (with throwaway protonmail), then put creds here.
- `btc_payout_address` / `ltc_payout_address` — your withdrawal wallets (Trust Wallet, Exodus, whatever).
- `telegram.bot_token` + `chat_id` if you want alerts.
- `max_concurrent_browsers` — start at 2 on a 1GB VPS, 4-6 on a 4GB box.

For captcha-gated sites (freebitco, cointiply):
```bash
export TWOCAPTCHA_KEY=your_key_here
```

## Run

```bash
# one pass (good for testing)
python run.py --once

# only one site
python run.py --once --site firefaucet

# only one account
python run.py --once --account rig01

# forever
python run.py
```

## Run as a service (systemd)

```ini
# /etc/systemd/system/faucetfarm.service
[Unit]
Description=faucetfarm
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/faucetfarm
Environment="TWOCAPTCHA_KEY=xxx"
ExecStart=/home/ubuntu/faucetfarm/.venv/bin/python run.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now faucetfarm
sudo journalctl -u faucetfarm -f
```

## Scaling playbook

1. **Day 1**: 1 account, 4 sites, headless=true, on your laptop. Verify earnings logged.
2. **Day 3**: Move to a $4/mo VPS (Contabo, Hetzner, RackNerd). Add 2 more accounts.
3. **Week 2**: Add residential proxies (IPRoyal pay-as-you-go is cheapest start) so accounts don't share IP.
4. **Week 4**: Add 2captcha key. freebitco + cointiply start contributing.
5. **Month 2**: Spin up 5–10 accounts across 2 VPSes. ~$20–80/day realistic.

## Add a new site (adapter)

1. Create `faucetfarm/adapters/yoursite.py` subclassing `Adapter`.
2. Implement `login_if_needed`, `fetch_balance`, `run_once`.
3. Register in `faucetfarm/adapters/__init__.py` REGISTRY.
4. Add the site name to an account's `sites` list in config.json.

## Withdrawal flow

Most faucets pay out via FaucetPay or direct on-chain when balance crosses a threshold (usually $1–5). Watch the `balances` table:

```bash
sqlite3 faucetfarm.db "SELECT account_label, site, balance_native, balance_usd FROM balances ORDER BY balance_usd DESC;"
```

When a site hits its withdrawal min, log in manually and click withdraw. (Auto-withdraw is a future adapter method — easy add.)

## Troubleshooting

- **"login_form not found"** → site changed selectors. Inspect manually, update the adapter.
- **Captcha errors everywhere** → set TWOCAPTCHA_KEY or disable captcha-gated adapters.
- **Proxy pool empty** → free proxies die fast; either accept lower validation count or pay for residential.
- **Account banned** → faucets aggressively ban shared IPs / VPN datacenters. Use residential proxies and 1 account per IP.
