"""Feedback module: ratings on assistant answers, queued for offline human review."""
import sqlite3
import uuid

from .errors import ApiError
from .timeutil import iso, utcnow


class Feedback:
    def __init__(self, repo):
        self.repo = repo

    def submit(self, principal: dict, message_id: str, body: dict) -> tuple[int, dict]:
        row = self.repo.one("SELECT m.author, v.user_id FROM messages m JOIN conversations v "
                            "ON v.conversation_id = m.conversation_id WHERE m.message_id = ?", (message_id,))
        if row is None or row["user_id"] != principal["user_id"]:
            raise ApiError(404, "not_found", "Resource not found")
        if row["author"] != "assistant":
            raise ApiError(422, "validation_error", "Feedback must target an assistant message",
                           [{"field": "message_id", "issue": "not an assistant message"}])
        feedback_id = str(uuid.uuid4())
        try:
            with self.repo.transaction() as db:
                db.execute("INSERT INTO feedback VALUES (?,?,?,?,?,?,?)",
                           (feedback_id, message_id, principal["user_id"], int(body["helpful"]),
                            body.get("comment", ""), "pending", iso(utcnow())))
        except sqlite3.IntegrityError as exc:
            raise ApiError(409, "duplicate_feedback", "Feedback already submitted") from exc
        return 201, {"feedback_id": feedback_id, "review_status": "pending"}

    def export_pending(self) -> list[dict]:
        """De-identified export for the offline review loop (no user IDs or names)."""
        rows = self.repo.all("SELECT f.feedback_id, f.helpful, f.comment, m.text AS answer FROM feedback f "
                             "JOIN messages m ON m.message_id = f.message_id WHERE f.review_status = 'pending'")
        return [dict(r) for r in rows]
