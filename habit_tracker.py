"""
habit_tracker.py — Habit management, streak calculation, and weekly summary.
"""

import json
import os
from datetime import datetime, timedelta
import pytz

HABITS_FILE = "habits.json"


# ── Storage helpers ───────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(HABITS_FILE):
        return {}
    with open(HABITS_FILE) as f:
        return json.load(f)


def _save(data: dict):
    with open(HABITS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Habit CRUD ────────────────────────────────────────────────────────────────

def add_habit(name: str) -> bool:
    """Add a new habit. Returns False if it already exists."""
    data = _load()
    key  = name.strip().lower()
    if key in data:
        return False
    data[key] = {
        "name":    name.strip(),
        "created": datetime.now().strftime("%Y-%m-%d"),
        "log":     {},          # {"YYYY-MM-DD": true/false}
    }
    _save(data)
    return True


def remove_habit(name: str) -> bool:
    """Remove a habit by name. Returns False if not found."""
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return False
    del data[key]
    _save(data)
    return True


def list_habits() -> list:
    """Return list of habit dicts sorted by name."""
    data = _load()
    return sorted(data.values(), key=lambda h: h["name"].lower())


# ── Daily logging ─────────────────────────────────────────────────────────────

def mark_habit(name: str, done: bool, date: str = None):
    """Mark a habit done/undone for a given date (default today)."""
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return False
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    data[key]["log"][date] = done
    _save(data)
    return True


def get_habits_for_date(date: str) -> list:
    """Return list of (habit_name, done_bool) for a given date."""
    data   = _load()
    result = []
    for habit in data.values():
        done = habit["log"].get(date, None)  # None = not yet logged
        result.append({"name": habit["name"], "done": done, "date": date})
    return sorted(result, key=lambda h: h["name"].lower())


# ── Streak calculation ────────────────────────────────────────────────────────

def get_streak(name: str, timezone: str = "Asia/Tokyo") -> dict:
    """
    Calculate current streak and best streak for a habit.
    Streak = consecutive days ending today (or yesterday if today not yet logged).
    """
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return {"current": 0, "best": 0}

    log      = data[key]["log"]
    tz       = pytz.timezone(timezone)
    today    = datetime.now(tz).strftime("%Y-%m-%d")
    
    # Walk backwards from today
    current_streak = 0
    check_date     = datetime.now(tz)

    # If today not yet logged, start check from yesterday
    if today not in log:
        check_date = check_date - timedelta(days=1)

    while True:
        date_str = check_date.strftime("%Y-%m-%d")
        if log.get(date_str) is True:
            current_streak += 1
            check_date = check_date - timedelta(days=1)
        else:
            break

    # Best streak ever
    best_streak   = 0
    run           = 0
    sorted_dates  = sorted(log.keys())
    for i, d in enumerate(sorted_dates):
        if log[d] is True:
            run += 1
            # Check if consecutive with previous date
            if i > 0:
                prev = datetime.strptime(sorted_dates[i - 1], "%Y-%m-%d")
                curr = datetime.strptime(d, "%Y-%m-%d")
                if (curr - prev).days != 1:
                    run = 1  # gap — restart
            best_streak = max(best_streak, run)
        else:
            run = 0

    return {"current": current_streak, "best": best_streak}


def streak_emoji(streak: int) -> str:
    if streak >= 30: return "🏆"
    if streak >= 14: return "⚡"
    if streak >= 7:  return "🔥"
    if streak >= 3:  return "✨"
    return "🌱"


# ── Weekly summary ────────────────────────────────────────────────────────────

def get_weekly_summary(timezone: str = "Asia/Tokyo") -> dict:
    """
    Return a summary of the past 7 days for all habits.
    Returns dict: {habit_name: {"days": [...bool/None x7], "rate": float, "streak": int}}
    """
    data    = _load()
    tz      = pytz.timezone(timezone)
    today   = datetime.now(tz)
    dates   = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    summary = {}
    for habit in data.values():
        log  = habit["log"]
        days = [log.get(d) for d in dates]          # True/False/None per day
        done = [d for d in days if d is True]
        rate = len(done) / 7 * 100
        streak = get_streak(habit["name"], timezone)["current"]
        summary[habit["name"]] = {
            "days":   days,
            "dates":  dates,
            "rate":   rate,
            "streak": streak,
        }

    return {"habits": summary, "dates": dates}
