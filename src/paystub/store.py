"""Paystub keeps its state in SQLite: intents, events, webhook deliveries and settings."""

import json
import secrets
import sqlite3
import threading
import time
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS intents (
    id TEXT PRIMARY KEY, amount INTEGER NOT NULL, currency TEXT NOT NULL, status TEXT NOT NULL,
    metadata TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, type TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL REFERENCES events(id),
    status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
    next_at REAL NOT NULL, last_result TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str) -> None:
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _all(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def _run(self, sql: str, *args: Any) -> int:
        with self._lock:
            return self._db.execute(sql, args).rowcount

    def setting(self, key: str) -> str | None:
        rows = self._all("SELECT value FROM settings WHERE key = ?", key)
        return rows[0]["value"] if rows else None

    def set_setting(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            key,
            value,
        )

    def create_intent(self, amount: int, currency: str, metadata: dict[str, str]) -> dict[str, Any]:
        intent_id = f"pi_{secrets.token_hex(12)}"
        self._run(
            "INSERT INTO intents VALUES (?, ?, ?, 'requires_payment', ?, ?)",
            intent_id,
            amount,
            currency,
            json.dumps(metadata),
            time.time(),
        )
        intent = self.intent(intent_id)
        assert intent is not None
        return intent

    def intent(self, intent_id: str) -> dict[str, Any] | None:
        rows = self._all("SELECT id, amount, currency, status, metadata FROM intents WHERE id = ?", intent_id)
        if not rows:
            return None
        row = rows[0]
        return {**row, "metadata": json.loads(row["metadata"])}

    def set_intent_status(self, intent_id: str, status: str) -> None:
        self._run("UPDATE intents SET status = ? WHERE id = ?", status, intent_id)

    def add_event(self, event_id: str, event_type: str, body: str) -> None:
        self._run("INSERT INTO events VALUES (?, ?, ?, ?)", event_id, event_type, body, time.time())
        self.add_delivery(event_id)

    def add_delivery(self, event_id: str) -> bool:
        if not self._all("SELECT 1 FROM events WHERE id = ?", event_id):
            return False
        self._run("INSERT INTO deliveries(event_id, next_at) VALUES (?, ?)", event_id, time.time())
        return True

    def due_deliveries(self) -> list[dict[str, Any]]:
        return self._all(
            "SELECT d.id, d.event_id, d.attempts, e.body FROM deliveries d JOIN events e ON e.id = d.event_id "
            "WHERE d.status = 'pending' AND d.next_at <= ? ORDER BY d.next_at LIMIT 20",
            time.time(),
        )

    def finish_delivery(self, delivery_id: int, status: str, result: str, attempts: int) -> None:
        self._run(
            "UPDATE deliveries SET status = ?, last_result = ?, attempts = ? WHERE id = ?",
            status,
            result,
            attempts,
            delivery_id,
        )

    def retry_delivery(self, delivery_id: int, result: str, attempts: int, delay: float) -> None:
        self._run(
            "UPDATE deliveries SET last_result = ?, attempts = ?, next_at = ? WHERE id = ?",
            result,
            attempts,
            time.time() + delay,
            delivery_id,
        )

    def deliveries(self, status: str | None, limit: int) -> list[dict[str, Any]]:
        sql = (
            "SELECT d.id, d.event_id, e.type, d.status, d.attempts, d.last_result FROM deliveries d "
            "JOIN events e ON e.id = d.event_id"
        )
        if status:
            return self._all(sql + " WHERE d.status = ? ORDER BY d.id DESC LIMIT ?", status, limit)
        return self._all(sql + " ORDER BY d.id DESC LIMIT ?", limit)

    def requeue_failed(self) -> int:
        """Retry now every delivery that failed or is waiting between retries ("Resend failed" in the dashboard)."""
        return self._run(
            "UPDATE deliveries SET status = 'pending', attempts = 0, next_at = ? "
            "WHERE status = 'failed' OR (status = 'pending' AND attempts > 0)",
            time.time(),
        )
