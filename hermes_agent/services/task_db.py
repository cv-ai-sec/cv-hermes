"""Local SQLite task database — Backlog -> In Progress -> Completed/Failed.

Deliberately not a real AppFlowy/Affine integration: a single lightweight
table is enough for this bot's own task tracking, with no dependency on
either app actually being installed/running. If real AppFlowy/Affine
integration is ever needed later, this class's interface (create_task/
update_status/get_task) is the seam to swap out for a real adapter against
that app's schema.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class TaskDB:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Backlog',
                    note_path TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def create_task(self, title: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
            return int(cursor.lastrowid)

    def update_status(
        self, task_id: int, status: str, note_path: str | None = None
    ) -> None:
        with self._connect() as conn:
            if note_path is not None:
                conn.execute(
                    "UPDATE tasks SET status = ?, note_path = ?, updated_at = datetime('now') "
                    "WHERE id = ?",
                    (status, note_path, task_id),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
                    (status, task_id),
                )

    def get_task(self, task_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
