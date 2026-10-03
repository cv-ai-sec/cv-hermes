"""Minimal task board: view/add/edit/delete tasks in the shared SQLite DB.

No auth of its own — relies entirely on network-layer restriction (firewalld,
same pattern as Grafana) to keep this off the real internet. Do not publish
this port beyond LOCAL_SUBNET; see docs/INSTALL.md.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import TaskDB

VALID_STATUSES = {"Backlog", "In Progress", "Completed", "Failed"}

db = TaskDB(os.environ.get("TASK_DB_PATH", "/app/data/tasks.db"))

app = FastAPI(title="Hermes Task Dashboard")


class NewTask(BaseModel):
    title: str
    description: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class StatusUpdate(BaseModel):
    status: str


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/api/tasks")
def get_tasks(status: str | None = None) -> list[dict]:
    return db.list_tasks(status)


@app.post("/api/tasks")
def post_task(task: NewTask) -> dict:
    if not task.title.strip():
        raise HTTPException(400, "title is required")
    task_id = db.create_task(task.title.strip(), task.description, source="dashboard")
    return db.get_task(task_id)


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: int, update: TaskUpdate) -> dict:
    if db.get_task(task_id) is None:
        raise HTTPException(404, "task not found")
    db.update_task(task_id, title=update.title, description=update.description)
    return db.get_task(task_id)


@app.patch("/api/tasks/{task_id}/status")
def patch_task_status(task_id: int, update: StatusUpdate) -> dict:
    if update.status not in VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(VALID_STATUSES)}")
    if db.get_task(task_id) is None:
        raise HTTPException(404, "task not found")
    db.update_status(task_id, update.status)
    return db.get_task(task_id)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int) -> dict:
    if db.get_task(task_id) is None:
        raise HTTPException(404, "task not found")
    db.delete_task(task_id)
    return {"deleted": task_id}


_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
