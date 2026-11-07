# Installation guide

## Requirements

- Python 3.11 or newer (CI tests 3.11 and 3.13)
- pip; a modern browser for the dashboard
- No database server: the alpha uses an SQLite file created on first start

## Steps

```bash
git clone https://github.com/texascoder254/aquaguard-capstone.git
cd aquaguard-capstone
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt  # runtime only: requirements.txt
```

## Configure (optional)

All settings are environment variables read once at startup (`app/config.py`).

| Variable | Default | Meaning |
| --- | --- | --- |
| `AQUAGUARD_DB` | `aquaguard.db` | SQLite file path |
| `AQUAGUARD_SECRET` | `dev-only-change-me` | Token signing secret. **Set a long random value outside development.** |
| `AQUAGUARD_TOKEN_TTL` | `1800` | Token lifetime in seconds |
| `AQUAGUARD_AI_DEADLINE` | `8` | Seconds before the assistant falls back to a human |
| `AQUAGUARD_CHAT_LIMIT` | `6` | Chat messages per user per minute |

## Run

```bash
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the dashboard and http://127.0.0.1:8000/docs for interactive API docs.
The first start creates the schema and seeds demo clients, tanks, and users (`app/seed.py`).

## Load demo data

```bash
# 30 minutes of a stuck-heater rise on the reef tank, then exit
python -m scripts.simulator --scenario gradual_rise --backfill 30 --seed 12
# a stable freshwater tank
python -m scripts.simulator --tank aaaaaaaa-0000-4000-8000-000000000002 --scenario stable --backfill 30 --ph 7.0
# live mode: one reading per minute until Ctrl+C
python -m scripts.simulator --scenario stable
```

## Verify

```bash
ruff check app tests scripts
pytest -q --cov=app --cov-fail-under=85
python -m scripts.evaluate_detector && python -m scripts.benchmark && python -m scripts.check_metrics
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `404 not_found` when posting readings | Use a tank id from `app/seed.py`; simulators may only post to tanks they are assigned |
| `422 validation_error` on `observed_at` | Timestamps must be RFC 3339 UTC within the last 24 hours (and at most 60 s in the future) |
| `409 configuration_required` | The tank has no safe limits yet (the seeded Quarantine 20L tank is deliberately unconfigured) |
| Dashboard shows "No data" | Run the simulator with `--backfill` |
| `429 rate_limited` in chat | Wait 10 seconds (6 messages/minute per user) |
| Assistant says "insufficient data" | The trend check needs 20 readings within 30 minutes |
