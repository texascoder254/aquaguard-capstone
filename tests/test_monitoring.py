from app.seed import TANK_REEF, TANK_UNCONFIGURED
from tests.conftest import login, reading


def test_ingest_normal_then_history(client):
    sim, cust = login(client, "sim-a"), login(client, "maya")
    r = client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=reading(temp=25.5), headers=sim)
    assert r.status_code == 201 and r.json()["threshold_status"] == "normal"
    h = client.get(f"/api/v1/tanks/{TANK_REEF}/readings", headers=cust).json()
    assert len(h["items"]) == 1 and h["next_cursor"] is None


def test_out_of_limit_reading_alerts(client):
    sim = login(client, "sim-a")
    r = client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=reading(temp=29.0), headers=sim)
    assert r.json()["threshold_status"] == "alert"


def test_duplicate_identical_200_conflicting_409(client):
    sim = login(client, "sim-a")
    body = reading()
    assert client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=body, headers=sim).status_code == 201
    again = client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=body, headers=sim)
    assert again.status_code == 200
    changed = dict(body, temperature_c=26.0)
    assert client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=changed, headers=sim).status_code == 409


def test_bounds_and_unknown_fields_rejected(client):
    sim = login(client, "sim-a")
    bad = reading(ph=15)
    r = client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=bad, headers=sim)
    assert r.status_code == 422 and r.json()["error"]["fields"][0]["field"] == "ph"
    extra = dict(reading(), valve="open")
    assert client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=extra, headers=sim).status_code == 422


def test_stale_reading_rejected(client):
    sim = login(client, "sim-a")
    r = client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=reading(minutes_ago=25 * 60), headers=sim)
    assert r.status_code == 422


def test_missing_limits_409(client):
    sim = login(client, "sim-a")
    r = client.post(f"/api/v1/tanks/{TANK_UNCONFIGURED}/readings", json=reading(), headers=sim)
    assert r.status_code == 409 and r.json()["error"]["code"] == "configuration_required"


def test_cursor_pagination_and_malformed_cursor(client):
    sim, cust = login(client, "sim-a"), login(client, "maya")
    for i in range(5):
        client.post(f"/api/v1/tanks/{TANK_REEF}/readings", json=reading(minutes_ago=i), headers=sim)
    first = client.get(f"/api/v1/tanks/{TANK_REEF}/readings?limit=2", headers=cust).json()
    second = client.get(f"/api/v1/tanks/{TANK_REEF}/readings?limit=2&cursor={first['next_cursor']}", headers=cust).json()
    third = client.get(f"/api/v1/tanks/{TANK_REEF}/readings?limit=2&cursor={second['next_cursor']}", headers=cust).json()
    ids = [r["reading_id"] for r in first["items"] + second["items"] + third["items"]]
    assert len(ids) == len(set(ids)) == 5 and third["next_cursor"] is None
    assert client.get(f"/api/v1/tanks/{TANK_REEF}/readings?cursor=%%%", headers=cust).status_code == 422
    assert client.get(f"/api/v1/tanks/{TANK_REEF}/readings?limit=501", headers=cust).status_code == 422
