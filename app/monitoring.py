"""Monitoring module: reading ingestion, threshold status, and paginated history."""
import base64
import json
import math
from datetime import timedelta

from .errors import ApiError
from .timeutil import iso, parse, utcnow

BOUNDS = {"temperature_c": (0.0, 50.0), "ph": (0.0, 14.0), "water_level_pct": (0.0, 100.0)}
LIMITS = {"temperature_c": ("temp_min", "temp_max"), "ph": ("ph_min", "ph_max"),
          "water_level_pct": ("level_min", "level_max")}


class Monitoring:
    def __init__(self, repo, policy):
        self.repo, self.policy = repo, policy

    def tank(self, tank_id: str) -> dict:
        row = self.repo.one("SELECT * FROM tanks WHERE tank_id = ?", (tank_id,))
        if row is None:
            raise ApiError(404, "not_found", "Resource not found")
        return dict(row)

    @staticmethod
    def validate(body: dict) -> list:
        issues = []
        for field, (lo, hi) in BOUNDS.items():
            value = body[field]
            if not math.isfinite(value) or not lo <= value <= hi:
                issues.append({"field": field, "issue": f"must be between {lo:g} and {hi:g}"})
        try:
            observed = parse(body["observed_at"])
            now = utcnow()
            if observed < now - timedelta(hours=24) or observed > now + timedelta(seconds=60):
                issues.append({"field": "observed_at", "issue": "must be within the last 24 hours"})
        except ValueError:
            issues.append({"field": "observed_at", "issue": "must be an RFC 3339 UTC timestamp"})
        return issues

    @staticmethod
    def threshold_status(tank: dict, body: dict) -> str:
        for field, (lo_col, hi_col) in LIMITS.items():
            lo, hi = tank[lo_col], tank[hi_col]
            if lo is None or hi is None:
                raise ApiError(409, "configuration_required", "Tank safe limits are not configured")
            if not lo <= body[field] <= hi:
                return "alert"
        return "normal"

    def ingest(self, principal: dict, tank_id: str, body: dict) -> tuple[int, dict]:
        tank = self.tank(tank_id)
        self.policy.require(principal, "readings:write", tank)
        issues = self.validate(body)
        if issues:
            raise ApiError(422, "validation_error", "Invalid input", issues)
        with self.repo.transaction() as db:
            existing = db.execute("SELECT * FROM readings WHERE reading_id = ?", (body["reading_id"],)).fetchone()
            if existing:
                same = (existing["tank_id"] == tank_id and existing["observed_at"] == body["observed_at"]
                        and all(existing[f] == body[f] for f in BOUNDS))
                if not same:
                    raise ApiError(409, "duplicate_conflict", "reading_id already used with different data")
                return 200, self._out(dict(existing))
            status = self.threshold_status(tank, body)
            row = dict(body, tank_id=tank_id, stored_at=iso(utcnow()), threshold_status=status)
            db.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,?)",
                       (row["reading_id"], tank_id, row["observed_at"], row["temperature_c"], row["ph"],
                        row["water_level_pct"], row["stored_at"], status))
        return 201, {"reading_id": row["reading_id"], "stored_at": row["stored_at"], "threshold_status": status}

    @staticmethod
    def _out(row: dict) -> dict:
        return {"reading_id": row["reading_id"], "stored_at": row["stored_at"],
                "threshold_status": row["threshold_status"]}

    @staticmethod
    def encode_cursor(row: dict) -> str:
        raw = json.dumps({"observed_at": row["observed_at"], "reading_id": row["reading_id"]}).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def decode_cursor(cursor: str) -> tuple[str, str]:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
            parse(data["observed_at"])
            return data["observed_at"], str(data["reading_id"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ApiError(422, "validation_error", "Malformed cursor", [{"field": "cursor", "issue": "malformed"}]) from exc

    def history(self, principal: dict, tank_id: str, limit: int, cursor: str | None) -> dict:
        tank = self.tank(tank_id)
        self.policy.require(principal, "readings:read", tank)
        sql = "SELECT * FROM readings WHERE tank_id = ?"
        params: list = [tank_id]
        if cursor:
            obs, rid = self.decode_cursor(cursor)
            sql += " AND (observed_at < ? OR (observed_at = ? AND reading_id < ?))"
            params += [obs, obs, rid]
        sql += " ORDER BY observed_at DESC, reading_id DESC LIMIT ?"
        rows = [dict(r) for r in self.repo.all(sql, tuple(params) + (limit + 1,))]
        more = len(rows) > limit
        rows = rows[:limit]
        items = [{k: r[k] for k in ("reading_id", "observed_at", "temperature_c", "ph", "water_level_pct",
                                    "stored_at", "threshold_status")} for r in rows]
        return {"items": items, "next_cursor": self.encode_cursor(rows[-1]) if more and rows else None}

    def recent(self, tank_id: str, count: int = 20) -> list[dict]:
        rows = self.repo.all("SELECT observed_at, temperature_c, ph, water_level_pct FROM readings WHERE tank_id = ? "
                             "ORDER BY observed_at DESC, reading_id DESC LIMIT ?", (tank_id, count))
        return [dict(r) for r in reversed(rows)]
