"""Shared error type and the JSON error envelope from the design (Section 4)."""
import uuid
from typing import Optional


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 fields: Optional[list] = None, headers: Optional[dict] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or []
        self.headers = headers or {}


def envelope(code: str, message: str, fields=None) -> dict:
    return {"error": {"code": code, "message": message, "fields": fields or []},
            "request_id": str(uuid.uuid4())}
