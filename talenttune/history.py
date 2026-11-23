"""Tiny SQLite store for past runs. One table, no ORM, good enough for a local tool."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

DB_PATH = os.environ.get("TALENTTUNE_DB", "talenttune.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    job_title TEXT,
    mode TEXT,
    score_before REAL,
    score_after REAL,
    faithfulness REAL,
    payload TEXT
)
"""


class History:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        with closing(self._conn()) as c:
            c.execute(_SCHEMA)
            c.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, job_title: str, mode: str, before: float, after: float, faithfulness: float,
            payload: dict) -> str:
        run_id = uuid.uuid4().hex[:12]
        with closing(self._conn()) as c:
            c.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), job_title[:200], mode,
                 before, after, faithfulness, json.dumps(payload)),
            )
            c.commit()
        return run_id

    def list(self, limit: int = 50) -> list[dict]:
        with closing(self._conn()) as c:
            rows = c.execute(
                "SELECT id, created_at, job_title, mode, score_before, score_after, faithfulness "
                "FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get(self, run_id: str) -> dict | None:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload"] or "{}")
        return d

    def delete(self, run_id: str) -> bool:
        with closing(self._conn()) as c:
            cur = c.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            c.commit()
        return cur.rowcount > 0
