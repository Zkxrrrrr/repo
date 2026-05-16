# afly

Affiliate signup automation. Spins up disposable identities, temp emails, and stealth browser contexts to sign up under your referral links on per-signup-payout sites, then either:
- verifies via the email link inside the run, **or**
- waits for the affiliate network to fire a postback at the built-in webhook listener and marks the row verified asynchronously.

Pings Discord when a payout lands.

## Layout

```
afly/
  cli.py            CLI: once / daemon / webhook / stats / targets
  config.py         loads config.yml + .env
  db.py             SQLite (signups table)
  identity.py       Faker-based persona generator
  email_provider.py mail.tm temp inbox + link extractor
  sms_provider.py   5sim wrapper (pluggable)
  captcha.py        2captcha / capsolver / anti-captcha + fallback chain
  proxies.py        round-robin proxy pool with health
  fingerprint.py    UA / viewport / tz / locale randomizer
  browser.py        stealth Playwright context
  runner.py         single signup pipeline
  scheduler.py      async queue with cooldowns + daily caps
  notify.py         Discord webhook
  webhook.py        FastAPI postback listener (subid -> verified)
  adapters/
    base.py         SignupAdapter ABC + SubID-aware referral helpers
    template.py     copy-paste starter
    swagbucks.py
    inboxdollars.py
    freecash.py
    idle_empire.py
    timebucks.py
    paidviewpoint.py
    ysense.py
    prizerebel.py
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env                 # fill captcha chain / sms / proxies / discord
cp config.example.yml config.yml     # paste referral codes, toggle targets, set webhook secret
```

## Use

```bash
python run.py targets    # show what's enabled
python run.py once       # single pass over enabled targets
python run.py daemon     # forever loop, respects cooldowns + caps
python run.py webhook    # run the postback listener (port from config.yml)
python run.py stats      # totals by target
```

## Captcha fallback chain

Set `CAPTCHA_CHAIN` in `.env` as comma-separated `provider:key` pairs:

```
CAPTCHA_CHAIN=2captcha:KEY_A,capsolver:KEY_B,anti-captcha:KEY_C
```

`captcha.CaptchaChain` tries them in order, logs the failure, falls through. If
`CAPTCHA_CHAIN` is empty, the legacy single-provider knobs `CAPTCHA_PROVIDER` /
`CAPTCHA_API_KEY` are used.

## Postback listener

Each signup row in the DB is given a unique id; the runner appends
`&subid=afly_<id>` to every referral URL it visits. When the affiliate
network confirms the conversion and pings the postback URL:

```
GET /postback?subid=afly_42&payout=5.00&secret=YOUR_SECRET&target=swagbucks
```

the listener:
1. validates the secret (if configured),
2. looks up signup #42,
3. flips its status to `verified`, sets `payout_usd`,
4. pings Discord.

Run it alongside the daemon:

```bash
python run.py daemon &
python run.py webhook
```

Networks usually have a "Global Postback URL" field in the affiliate
dashboard with macros like `{subid}` / `{amount}` — paste them into the
URL above.

## Adding a new target

1. Copy `afly/adapters/template.py` to `afly/adapters/<site>.py`.
2. Set `target_id`, `landing_url`, swap selectors in the `SELECTORS` dict.
3. Use `self.referral_url_with_subid(...)` so postbacks attribute correctly.
4. Add `from . import <site>` to `afly/adapters/__init__.py`.
5. Add a block under `targets:` in `config.yml`.

That's it — the scheduler picks it up automatically.

## Tuning knobs (`config.yml -> global`)

- `max_concurrency` — parallel signups across all targets
- `per_target_cooldown_sec` — min seconds between two signups on same target
- `jitter_sec: [lo, hi]` — random pre-run delay window
- `daily_cap_per_target` — circuit-breaker so one target doesn't get hammered
- `retries` — exponential backoff retry count
