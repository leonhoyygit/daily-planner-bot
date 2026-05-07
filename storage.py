import json
import os

STORAGE_FILE = "tasks_data.json"


def _load_all() -> dict:
    if not os.path.exists(STORAGE_FILE):
        return {}
    with open(STORAGE_FILE) as f:
        return json.load(f)


def _save_all(data: dict):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def save_tasks(date: str, tasks: list):
    """Save tasks for a given date. date format: YYYY-MM-DD"""
    data = _load_all()
    data[date] = tasks
    _save_all(data)


def load_tasks(date: str) -> list:
    """Load tasks for a given date."""
    data = _load_all()
    return data.get(date, [])


def update_task_status(date: str, index: int, done: bool):
    """Toggle a single task's done status."""
    data  = _load_all()
    tasks = data.get(date, [])
    if 0 <= index < len(tasks):
        tasks[index]["done"] = done
        data[date] = tasks
        _save_all(data)
