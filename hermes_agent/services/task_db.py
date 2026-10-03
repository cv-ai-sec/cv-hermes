"""Local SQLite task database — Backlog -> In Progress -> Completed/Failed.

Deliberately not a real AppFlowy/Affine integration: a single lightweight
table is enough for this bot's own task tracking, with no dependency on
either app actually being installed/running. If real AppFlowy/Affine
integration is ever needed later, this class's interface (create_task/
update_status/get_task) is the seam to swap out for a real adapter against
that app's schema.

Shared, not owned: both hermes-agent and the task-dashboard service (see
`task_dashboard/`) open this same SQLite file concurrently — the dashboard
so a task can be added/edited from a browser instead of only via a Discord
command. WAL mode + a busy_timeout are enabled below specifically to make
that safe: WAL lets one writer and multiple readers proceed without
blocking each other, and the timeout makes a brief write/write collision
retry instead of raising "database is locked". This is an accepted,
bounded tradeoff rather than a real multi-writer database — at this
task volume (a handful of personal tasks, not concurrent multi-user
writes) WAL's last-writer-wins semantics on the same row are good enough,
and the alternative (a client/server DB) isn't justified for this scale.
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
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "description" not in existing_cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN description TEXT")
            if "source" not in existing_cols:
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN source TEXT NOT NULL DEFAULT 'discord'"
                )

    def create_task(
        self, title: str, description: str | None = None, source: str = "discord"
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, description, source) VALUES (?, ?, ?)",
                (title, description, source),
            )
            return int(cursor.lastrowid)

    def list_tasks(self, status: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
            return [dict(row) for row in rows]

    def delete_task(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

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
