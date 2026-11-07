"""Ingestion and assistant latency benchmark (in-process, no network).

Measures POST /readings request latency (validate -> policy -> persist -> visible on GET)
against the design target: 95% of valid readings visible within 2 seconds.

Usage: python -m scripts.benchmark [--n 1000] [--out docs/metrics/benchmark.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import DEMO_PASSWORDS, TANK_REEF
from app.timeutil import iso, utcnow


def pct(values, p):
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(p / 100 * len(values)) - 1))
    return values[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--out", default="docs/metrics/benchmark.json")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as d:
        settings = Settings(database_path=f"{d}/bench.db", token_secret="bench", chat_limit_per_minute=10_000)
        c = TestClient(create_app(settings))
        def tok(user):
            r = c.post("/api/v1/auth/token", json={"username": user, "password": DEMO_PASSWORDS[user]})
            return {"Authorization": "Bearer " + r.json()["access_token"]}
        sim, cust = tok("sim-a"), tok("maya")
        ingest, visible = [], []
        start = utcnow() - timedelta(minutes=a.n)
        for i in range(a.n):
            body = {"reading_id": str(uuid.uuid4()), "observed_at": iso(start + timedelta(minutes=i)),
                    "temperature_c": 25.0 + (i % 7) * 0.1, "ph": 8.1, "water_level_pct": 95.0}
            t0 = time.perf_counter()
            r = c.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=body, headers=sim)
            t1 = time.perf_counter()
            assert r.status_code == 201, r.text
            ingest.append((t1 - t0) * 1000)
            if i % 50 == 0:
                g = c.get(f"/api/v1/tanks/{TANK_REEF}/readings?limit=1", headers=cust)
                visible.append((time.perf_counter() - t0) * 1000)
                assert g.json()["items"][0]["reading_id"] == body["reading_id"]
        chat = []
        for _ in range(50):
            t0 = time.perf_counter()
            r = c.post(f"/api/v1/tanks/{TANK_REEF}/messages", headers=cust,
                       json={"message_id": str(uuid.uuid4()), "conversation_id": str(uuid.uuid4()), "text": "How is my tank temperature?"})
            chat.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 201, r.text
    res = {
        "readings": a.n,
        "ingest_ms": {"p50": round(pct(ingest, 50), 2), "p95": round(pct(ingest, 95), 2), "p99": round(pct(ingest, 99), 2),
                      "mean": round(statistics.mean(ingest), 2)},
        "ingest_to_visible_ms_p95": round(pct(visible, 95), 2),
        "within_2s_rate": round(sum(v < 2000 for v in ingest) / len(ingest), 4),
        "assistant_ms": {"p50": round(pct(chat, 50), 2), "p95": round(pct(chat, 95), 2)},
        "throughput_readings_per_s": round(1000 * a.n / sum(ingest), 1),
        "target": "95% of valid readings visible within 2000 ms",
    }
    with open(a.out, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
