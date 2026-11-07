"""Shared fixtures: a fresh app and database per test."""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import DEMO_PASSWORDS, TANK_REEF
from app.timeutil import iso, utcnow


@pytest.fixture
def make_client(tmp_path):
    def _make(ai_provider=None, **overrides):
        settings = Settings(database_path=str(tmp_path / f"{uuid.uuid4()}.db"), token_secret="test-secret",
                            ai_deadline_seconds=overrides.pop("deadline", 1.0), **overrides)
        return TestClient(create_app(settings, ai_provider=ai_provider))
    return _make


@pytest.fixture
def client(make_client):
    return make_client()


def login(client, username):
    r = client.post("/api/v1/auth/token", json={"username": username, "password": DEMO_PASSWORDS[username]})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def reading(minutes_ago=0.0, temp=25.0, ph=8.1, level=95.0, rid=None):
    return {"reading_id": rid or str(uuid.uuid4()), "observed_at": iso(utcnow() - timedelta(minutes=minutes_ago)),
            "temperature_c": temp, "ph": ph, "water_level_pct": level}


def load_series(client, temps, tank=TANK_REEF, step=1.0):
    sim = login(client, "sim-a")
    n = len(temps)
    for i, t in enumerate(temps):
        r = client.post(f"/api/v1/tanks/{tank}/readings", json=reading((n - 1 - i) * step, t), headers=sim)
        assert r.status_code == 201, r.text
