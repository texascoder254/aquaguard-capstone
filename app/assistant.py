"""Assistant module: builds scoped context, calls the AI adapter, applies escalation."""
import hashlib
import json
import threading
import uuid

from .ai import AIUnavailable
from .errors import ApiError
from .handoff import Handoff
from .timeutil import iso, utcnow

FALLBACK_REPLY = "AI is unavailable; a human will review."


class Assistant:
    def __init__(self, repo, policy, monitoring, ai, customers):
        self.repo, self.policy, self.monitoring = repo, policy, monitoring
        self.ai, self.customers = ai, customers
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    def respond(self, principal: dict, tank_id: str, body: dict) -> tuple[int, dict]:
        tank = self.monitoring.tank(tank_id)
        self.policy.require(principal, "messages:write", tank)
        text = body["text"].strip()
        if not 1 <= len(text) <= 2000:
            raise ApiError(422, "validation_error", "Invalid input", [{"field": "text", "issue": "1-2000 characters"}])
        req_hash = hashlib.sha256(json.dumps([tank_id, body["conversation_id"], text]).encode()).hexdigest()
        prior = self.repo.one("SELECT request_hash, response_json FROM messages WHERE message_id = ?", (body["message_id"],))
        if prior:
            if prior["request_hash"] != req_hash or prior["response_json"] is None:
                raise ApiError(409, "duplicate_conflict", "message_id already used with different data")
            return 200, json.loads(prior["response_json"])
        with self._lock:
            if body["message_id"] in self._inflight:
                raise ApiError(409, "request_in_progress", "This message is already being processed")
            self._inflight.add(body["message_id"])
        try:
            return self._respond(principal, tank, text, body, req_hash)
        finally:
            with self._lock:
                self._inflight.discard(body["message_id"])

    def _conversation(self, principal, tank, conversation_id):
        conv = self.repo.one("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,))
        if conv is None:
            return None
        if conv["user_id"] != principal["user_id"]:
            raise ApiError(404, "not_found", "Resource not found")
        if conv["tank_id"] != tank["tank_id"]:
            raise ApiError(409, "conversation_mismatch", "Conversation belongs to another tank")
        return conv

    def _respond(self, principal, tank, text, body, req_hash):
        conv_id = body["conversation_id"]
        conv = self._conversation(principal, tank, conv_id)
        history = []
        if conv:
            rows = self.repo.all("SELECT author, text FROM messages WHERE conversation_id = ? "
                                 "ORDER BY created_at DESC, rowid DESC LIMIT 10", (conv_id,))
            history = [{"role": r["author"], "text": r["text"]} for r in reversed(rows)]
        context = {"question": text, "history": history,
                   "readings": self.monitoring.recent(tank["tank_id"], 20),
                   "service_context": self.customers.get(tank["client_id"])}
        try:
            result = self.ai.analyze(context)
            reply, status, version = result.answer, result.anomaly_status, result.model_version
            handoff = not result.resolved
        except AIUnavailable:
            reply, status, version, handoff = FALLBACK_REPLY, "unavailable", "fallback", True
        now = iso(utcnow())
        assistant_id = str(uuid.uuid4())
        response = {"message_id": body["message_id"], "assistant_message_id": assistant_id, "reply": reply,
                    "anomaly_status": status, "model_version": version, "handoff_required": handoff}
        with self.repo.transaction() as db:
            if conv is None:
                db.execute("INSERT INTO conversations VALUES (?,?,?,?,?)",
                           (conv_id, principal["user_id"], tank["client_id"], tank["tank_id"], now))
            if handoff:
                _, case = Handoff.open_in(db, conv_id, "AI escalation: " + text[:450])
                response["case_id"] = case["case_id"]
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
                       (body["message_id"], conv_id, "customer", text, now, req_hash, json.dumps(response)))
            db.execute("INSERT INTO messages (message_id, conversation_id, author, text, created_at) VALUES (?,?,?,?,?)",
                       (assistant_id, conv_id, "assistant", reply, now))
        return 201, response
