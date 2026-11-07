"""Persistence layer. All SQL lives here and uses parameterized queries.

SQLite is the local prototype store; the schema mirrors the PostgreSQL target.
"""
import sqlite3
import threading
from contextlib import contextmanager

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, name TEXT NOT NULL,
    service_tier TEXT NOT NULL, timezone TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('customer','simulator','agent')),
    client_id TEXT REFERENCES clients(client_id));
CREATE TABLE IF NOT EXISTS agent_scopes (user_id TEXT REFERENCES users(user_id),
    client_id TEXT REFERENCES clients(client_id), PRIMARY KEY (user_id, client_id));
CREATE TABLE IF NOT EXISTS tanks (tank_id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(client_id),
    name TEXT NOT NULL, temp_min REAL, temp_max REAL, ph_min REAL, ph_max REAL, level_min REAL, level_max REAL,
    simulator_user_id TEXT REFERENCES users(user_id));
CREATE TABLE IF NOT EXISTS readings (reading_id TEXT PRIMARY KEY, tank_id TEXT NOT NULL REFERENCES tanks(tank_id),
    observed_at TEXT NOT NULL, temperature_c REAL NOT NULL, ph REAL NOT NULL, water_level_pct REAL NOT NULL,
    stored_at TEXT NOT NULL, threshold_status TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_readings_tank_time ON readings(tank_id, observed_at DESC, reading_id DESC);
CREATE TABLE IF NOT EXISTS conversations (conversation_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
    client_id TEXT NOT NULL REFERENCES clients(client_id), tank_id TEXT NOT NULL REFERENCES tanks(tank_id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    author TEXT NOT NULL CHECK (author IN ('customer','assistant','agent')), text TEXT NOT NULL, created_at TEXT NOT NULL,
    request_hash TEXT, response_json TEXT);
CREATE INDEX IF NOT EXISTS ix_messages_conv_time ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    reason TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('open','closed')), created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_one_open_case ON cases(conversation_id) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS ix_cases_status_time ON cases(status, created_at, case_id);
CREATE TABLE IF NOT EXISTS replies (reply_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
    message_id TEXT NOT NULL REFERENCES messages(message_id), request_hash TEXT NOT NULL, case_status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feedback (feedback_id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(message_id),
    user_id TEXT NOT NULL REFERENCES users(user_id), helpful INTEGER NOT NULL, comment TEXT NOT NULL,
    review_status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (message_id, user_id));
"""


class Repository:
    """Thin transactional wrapper around one SQLite connection."""

    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self):
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def one(self, sql: str, params: tuple = ()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self):
        self._conn.close()
