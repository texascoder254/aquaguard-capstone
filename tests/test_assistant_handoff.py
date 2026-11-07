import time
import uuid

from app.seed import TANK_REEF
from tests.conftest import load_series, login


def ask(client, headers, text, conv=None, mid=None):
    body = {"message_id": mid or str(uuid.uuid4()), "conversation_id": conv or str(uuid.uuid4()), "text": text}
    return client.post(f"/api/v1/tanks/{TANK_REEF}/messages", json=body, headers=headers), body


def test_rising_temperature_answer_and_feedback(client):
    load_series(client, [25.0 + 0.05 * i for i in range(20)])
    cust = login(client, "maya")
    r, _ = ask(client, cust, "Why is the temperature rising?")
    out = r.json()
    assert r.status_code == 201 and out["anomaly_status"] == "warning" and out["handoff_required"] is False
    fb = client.post(f"/api/v1/messages/{out['assistant_message_id']}/feedback", json={"helpful": True}, headers=cust)
    assert fb.status_code == 201 and fb.json()["review_status"] == "pending"
    dup = client.post(f"/api/v1/messages/{out['assistant_message_id']}/feedback", json={"helpful": False}, headers=cust)
    assert dup.status_code == 409


def test_idempotent_message_retry(client):
    cust = login(client, "maya")
    r1, body = ask(client, cust, "How is my tank?")
    r2 = client.post(f"/api/v1/tanks/{TANK_REEF}/messages", json=body, headers=cust)
    assert r1.status_code == 201 and r2.status_code == 200 and r2.json() == r1.json()
    conflict = client.post(f"/api/v1/tanks/{TANK_REEF}/messages", json=dict(body, text="different"), headers=cust)
    assert conflict.status_code == 409


def test_explicit_human_request_creates_case_and_agent_replies(client):
    cust, agent = login(client, "maya"), login(client, "agent-lee")
    r, body = ask(client, cust, "Please have a human agent review this.")
    out = r.json()
    assert out["handoff_required"] is True and "case_id" in out
    queue = client.get("/api/v1/cases", headers=agent).json()["items"]
    assert [c["case_id"] for c in queue] == [out["case_id"]]
    reply = {"reply_id": str(uuid.uuid4()), "text": "Hi Maya, checking your heater now.", "close_case": True}
    rr = client.post(f"/api/v1/cases/{out['case_id']}/replies", json=reply, headers=agent)
    assert rr.status_code == 201 and rr.json()["case_status"] == "closed"
    assert client.post(f"/api/v1/cases/{out['case_id']}/replies", json=reply, headers=agent).status_code == 200
    again = dict(reply, reply_id=str(uuid.uuid4()))
    assert client.post(f"/api/v1/cases/{out['case_id']}/replies", json=again, headers=agent).status_code == 409
    transcript = client.get(f"/api/v1/conversations/{body['conversation_id']}/messages", headers=cust).json()["items"]
    assert [m["author"] for m in transcript] == ["customer", "assistant", "agent"]


def test_ai_timeout_falls_back_to_human(make_client):
    def slow(_):
        time.sleep(2)
        return {}
    client = make_client(ai_provider=slow, deadline=0.2)
    cust = login(client, "maya")
    out = ask(client, cust, "How is my tank?")[0].json()
    assert out["model_version"] == "fallback" and out["anomaly_status"] == "unavailable"
    assert out["handoff_required"] is True and out["case_id"]


def test_invalid_model_output_falls_back(make_client):
    client = make_client(ai_provider=lambda ctx: {"answer": 42})
    out = ask(client, login(client, "maya"), "How is my tank?")[0].json()
    assert out["model_version"] == "fallback"


def test_explicit_case_is_idempotent(client):
    load_series(client, [25.0] * 20)
    cust = login(client, "maya")
    _, body = ask(client, cust, "How is my tank?")
    url = f"/api/v1/conversations/{body['conversation_id']}/cases"
    first = client.post(url, json={"reason": "Please review"}, headers=cust)
    second = client.post(url, json={"reason": "Please review"}, headers=cust)
    assert first.status_code == 201 and second.status_code == 200 and first.json() == second.json()


def test_other_customer_cannot_read_transcript(client):
    _, body = ask(client, login(client, "maya"), "How is my tank?")
    other = login(client, "omar")
    assert client.get(f"/api/v1/conversations/{body['conversation_id']}/messages", headers=other).status_code == 404


def test_chat_rate_limit_429(make_client):
    client = make_client(chat_limit_per_minute=2)
    cust = login(client, "maya")
    codes = [ask(client, cust, "status?")[0].status_code for _ in range(3)]
    assert codes[:2] == [201, 201] and codes[2] == 429


def test_unanswerable_question_opens_case_automatically(client):
    cust = login(client, "maya")
    out = ask(client, cust, "Can you recommend a good restaurant?")[0].json()
    assert out["handoff_required"] is True and out["case_id"]
