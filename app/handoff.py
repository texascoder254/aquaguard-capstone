"""Handoff module: durable cases, the agent queue, and agent replies."""
import hashlib
import json
import sqlite3
import uuid

from .errors import ApiError
from .timeutil import iso, utcnow


class Handoff:
    def __init__(self, repo, policy):
        self.repo, self.policy = repo, policy

    def conversation(self, conversation_id: str) -> dict:
        row = self.repo.one("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,))
        if row is None:
            raise ApiError(404, "not_found", "Resource not found")
        return dict(row)

    @staticmethod
    def open_in(db, conversation_id: str, reason: str) -> tuple[int, dict]:
        """Idempotently find or create the single open case (inside a caller transaction)."""
        row = db.execute("SELECT case_id FROM cases WHERE conversation_id = ? AND status = 'open'",
                         (conversation_id,)).fetchone()
        if row:
            return 200, {"case_id": row["case_id"], "status": "open"}
        case_id = str(uuid.uuid4())
        db.execute("INSERT INTO cases VALUES (?,?,?,?,?)", (case_id, conversation_id, reason, "open", iso(utcnow())))
        return 201, {"case_id": case_id, "status": "open"}

    def open(self, principal: dict, conversation_id: str, reason: str) -> tuple[int, dict]:
        conv = self.conversation(conversation_id)
        if conv["user_id"] != principal["user_id"]:
            raise ApiError(404, "not_found", "Resource not found")
        with self.repo.transaction() as db:
            return self.open_in(db, conversation_id, reason)

    def queue(self, principal: dict, status: str, limit: int) -> dict:
        if principal["role"] != "agent":
            raise ApiError(403, "forbidden", "Role not permitted")
        scopes = principal.get("scopes", [])
        if not scopes:
            return {"items": []}
        marks = ",".join("?" * len(scopes))
        rows = self.repo.all(
            f"SELECT c.case_id, c.conversation_id, v.tank_id, c.reason, c.status, c.created_at FROM cases c "
            f"JOIN conversations v ON v.conversation_id = c.conversation_id WHERE c.status = ? AND v.client_id IN ({marks}) "
            f"ORDER BY c.created_at ASC, c.case_id ASC LIMIT ?", (status, *scopes, limit))
        return {"items": [dict(r) for r in rows]}

    def transcript(self, principal: dict, conversation_id: str, limit: int) -> dict:
        conv = self.conversation(conversation_id)
        if principal["role"] == "customer" and conv["user_id"] != principal["user_id"]:
            raise ApiError(404, "not_found", "Resource not found")
        self.policy.require(principal, "transcript:read", conv)
        rows = self.repo.all("SELECT message_id, author, text, created_at FROM messages WHERE conversation_id = ? "
                             "ORDER BY created_at DESC, rowid DESC LIMIT ?", (conversation_id, limit))
        return {"items": [dict(r) for r in reversed(rows)]}

    def reply(self, principal: dict, case_id: str, body: dict) -> tuple[int, dict]:
        if principal["role"] != "agent":
            raise ApiError(403, "forbidden", "Role not permitted")
        case = self.repo.one("SELECT c.*, v.client_id FROM cases c JOIN conversations v "
                             "ON v.conversation_id = c.conversation_id WHERE c.case_id = ?", (case_id,))
        if case is None:
            raise ApiError(404, "not_found", "Resource not found")
        self.policy.require(principal, "cases:reply", dict(case))
        req_hash = hashlib.sha256(json.dumps([case_id, body], sort_keys=True).encode()).hexdigest()
        with self.repo.transaction() as db:
            prior = db.execute("SELECT * FROM replies WHERE reply_id = ?", (body["reply_id"],)).fetchone()
            if prior:
                if prior["request_hash"] != req_hash:
                    raise ApiError(409, "duplicate_conflict", "reply_id already used with different data")
                return 200, {"reply_id": prior["reply_id"], "case_status": prior["case_status"],
                             "created_at": prior["created_at"]}
            current = db.execute("SELECT status FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if current["status"] == "closed":
                raise ApiError(409, "case_closed", "Case is already closed")
            now = iso(utcnow())
            message_id = str(uuid.uuid4())
            db.execute("INSERT INTO messages (message_id, conversation_id, author, text, created_at) VALUES (?,?,?,?,?)",
                       (message_id, case["conversation_id"], "agent", body["text"], now))
            status = "closed" if body["close_case"] else "open"
            db.execute("UPDATE cases SET status = ? WHERE case_id = ?", (status, case_id))
            try:
                db.execute("INSERT INTO replies VALUES (?,?,?,?,?,?)",
                           (body["reply_id"], case_id, message_id, req_hash, status, now))
            except sqlite3.IntegrityError as exc:
                raise ApiError(409, "duplicate_conflict", "reply conflict") from exc
        return 201, {"reply_id": body["reply_id"], "case_status": status, "created_at": now}
