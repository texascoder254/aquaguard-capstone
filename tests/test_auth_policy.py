from app.seed import TANK_OTHER, TANK_REEF
from tests.conftest import login, reading


def test_login_success_returns_bearer(client):
    r = client.post("/api/v1/auth/token", json={"username": "maya", "password": "reef-demo-1"})
    body = r.json()
    assert r.status_code == 200 and body["token_type"] == "bearer" and body["expires_in"] == 1800


def test_login_bad_password_401(client):
    r = client.post("/api/v1/auth/token", json={"username": "maya", "password": "nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


def test_missing_and_tampered_token_401(client):
    assert client.get(f"/api/v1/tanks/{TANK_REEF}/readings").status_code == 401
    h = login(client, "maya")
    bad = {"Authorization": h["Authorization"][:-2] + "xx"}
    assert client.get(f"/api/v1/tanks/{TANK_REEF}/readings", headers=bad).status_code == 401


def test_cross_client_tank_hidden_404(client):
    h = login(client, "maya")
    assert client.get(f"/api/v1/tanks/{TANK_OTHER}/readings", headers=h).status_code == 404


def test_customer_cannot_ingest(client):
    h = login(client, "maya")
    assert client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=reading(), headers=h).status_code == 404


def test_policy_outage_fails_closed_503(client):
    h = login(client, "maya")
    client.app.state.policy.available = False
    r = client.get(f"/api/v1/tanks/{TANK_REEF}/readings", headers=h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "policy_unavailable"


def test_error_envelope_shape(client):
    r = client.post("/api/v1/auth/token", content=b"{not json", headers={"Content-Type": "application/json"})
    body = r.json()
    assert r.status_code == 400 and set(body) == {"error", "request_id"} and body["error"]["fields"] == []
