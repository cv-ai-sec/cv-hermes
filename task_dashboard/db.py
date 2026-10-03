"""Read/write access to the same tasks.db SQLite file hermes-agent owns.

Deliberately a standalone copy of the schema/pragmas in
`hermes_agent/services/task_db.py`, not an import of that module — the two
services ship in separate Docker build contexts (see the two Dockerfiles),
and the only thing that actually needs to be shared is the on-disk file,
not Python code. If the `tasks` table schema changes in
`hermes_agent/services/task_db.py`, mirror the change here too.
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
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'Backlog',
                    source TEXT NOT NULL DEFAULT 'discord',
                    note_path TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def list_tasks(self, status: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def create_task(self, title: str, description: str | None, source: str = "dashboard") -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, description, source) VALUES (?, ?, ?)",
                (title, description, source),
            )
            return int(cursor.lastrowid)

    def update_task(
        self, task_id: int, title: str | None = None, description: str | None = None
    ) -> None:
        with self._connect() as conn:
            if title is not None:
                conn.execute(
                    "UPDATE tasks SET title = ?, updated_at = datetime('now') WHERE id = ?",
                    (title, task_id),
                )
            if description is not None:
                conn.execute(
                    "UPDATE tasks SET description = ?, updated_at = datetime('now') WHERE id = ?",
                    (description, task_id),
                )

    def update_status(self, task_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, task_id),
            )

    def delete_task(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
