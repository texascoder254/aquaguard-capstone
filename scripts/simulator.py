"""Tank sensor simulator: posts synthetic readings to a running AquaGuard server.

Usage:
  python -m scripts.simulator --url http://127.0.0.1:8000 --scenario gradual_rise --backfill 25
  python -m scripts.simulator --scenario stable --interval 60          # live, one reading per minute
"""
from __future__ import annotations

import argparse
import random
import time
import uuid
from datetime import timedelta

import httpx

from app.seed import DEMO_PASSWORDS, TANK_REEF
from app.timeutil import iso, utcnow
from scripts.scenarios import KINDS, generate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--tank", default=TANK_REEF)
    ap.add_argument("--user", default="sim-a")
    ap.add_argument("--scenario", choices=KINDS, default="stable")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--backfill", type=int, default=0, help="post N past readings one minute apart, then exit")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--ph", type=float, default=8.1, help="mean pH (use ~7.0 for freshwater planted tanks)")
    a = ap.parse_args()
    with httpx.Client(base_url=a.url, timeout=5) as c:
        login = c.post("/api/v1/auth/token", json={"username": a.user, "password": DEMO_PASSWORDS[a.user]})
        if login.status_code != 200:
            raise SystemExit(f"Login failed for {a.user}: HTTP {login.status_code} {login.text}")
        tok = login.json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        rng = random.Random(a.seed)

        def send(ts, temp):
            body = {"reading_id": str(uuid.uuid4()), "observed_at": iso(ts), "temperature_c": temp,
                    "ph": round(a.ph + rng.gauss(0, 0.02), 2), "water_level_pct": round(95 - rng.random(), 1)}
            r = c.post(f"/api/v1/tanks/{a.tank}/readings", json=body, headers=h)
            print(r.status_code, body["observed_at"], temp)

        if a.backfill:
            temps = generate(a.scenario, a.seed, n=a.backfill)
            now = utcnow()
            for i, t in enumerate(temps):
                send(now - timedelta(minutes=a.backfill - 1 - i), t)
            return
        i = 0
        while True:
            send(utcnow(), generate(a.scenario, a.seed, n=i + 1)[-1])
            i += 1
            time.sleep(a.interval)


if __name__ == "__main__":
    main()
