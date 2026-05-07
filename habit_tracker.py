"""
habit_tracker.py — Habit management, streaks, weekly/monthly summaries and rewards.
"""

import json
import os
import calendar
from datetime import datetime, timedelta
import pytz

HABITS_FILE = "habits.json"

__all__ = [
    "add_habit", "set_reward", "remove_habit", "list_habits",
    "mark_habit", "get_habits_for_date",
    "get_streak", "streak_emoji",
    "get_weekly_summary", "get_monthly_progress",
    "check_month_complete",
]


# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(HABITS_FILE):
        return {}
    with open(HABITS_FILE) as f:
        return json.load(f)


def _save(data: dict):
    with open(HABITS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def add_habit(name: str, reward: str = None) -> bool:
    data = _load()
    key  = name.strip().lower()
    if key in data:
        return False
    data[key] = {
        "name":    name.strip(),
        "reward":  reward.strip() if reward else None,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "log":     {},
    }
    _save(data)
    return True


def set_reward(name: str, reward: str) -> bool:
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return False
    data[key]["reward"] = reward.strip()
    _save(data)
    return True


def remove_habit(name: str) -> bool:
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return False
    del data[key]
    _save(data)
    return True


def list_habits() -> list:
    data = _load()
    return sorted(data.values(), key=lambda h: h["name"].lower())


# ── Daily logging ─────────────────────────────────────────────────────────────

def mark_habit(name: str, done: bool, date: str = None):
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
    data = _load()
    result = []
    for habit in data.values():
        done = habit["log"].get(date, None)
        result.append({
            "name":   habit["name"],
            "done":   done,
            "date":   date,
            "reward": habit.get("reward"),
        })
    return sorted(result, key=lambda h: h["name"].lower())


# ── Streaks ───────────────────────────────────────────────────────────────────

def get_streak(name: str, timezone: str = "Asia/Tokyo") -> dict:
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return {"current": 0, "best": 0}

    log        = data[key]["log"]
    tz         = pytz.timezone(timezone)
    today      = datetime.now(tz).strftime("%Y-%m-%d")
    check_date = datetime.now(tz)

    if today not in log:
        check_date = check_date - timedelta(days=1)

    current_streak = 0
    while True:
        date_str = check_date.strftime("%Y-%m-%d")
        if log.get(date_str) is True:
            current_streak += 1
            check_date = check_date - timedelta(days=1)
        else:
            break

    best_streak  = 0
    run          = 0
    sorted_dates = sorted(log.keys())
    for i, d in enumerate(sorted_dates):
        if log[d] is True:
            run += 1
            if i > 0:
                prev = datetime.strptime(sorted_dates[i - 1], "%Y-%m-%d")
                curr = datetime.strptime(d, "%Y-%m-%d")
                if (curr - prev).days != 1:
                    run = 1
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


# ── Monthly progress & rewards ────────────────────────────────────────────────

def get_monthly_progress(name: str, year: int = None, month: int = None, timezone: str = "Asia/Tokyo") -> dict:
    data = _load()
    key  = name.strip().lower()
    if key not in data:
        return {}

    tz = pytz.timezone(timezone)
    if year is None or month is None:
        now   = datetime.now(tz)
        year  = now.year
        month = now.month

    days_in_month = calendar.monthrange(year, month)[1]
    log           = data[key]["log"]
    reward        = data[key].get("reward")

    days_done = 0
    for day in range(1, days_in_month + 1):
        date_str = "%04d-%02d-%02d" % (year, month, day)
        if log.get(date_str) is True:
            days_done += 1

    tz_now        = datetime.now(tz)
    days_elapsed  = min(tz_now.day, days_in_month) if (tz_now.year == year and tz_now.month == month) else days_in_month
    completion_rate = (days_done / days_elapsed * 100) if days_elapsed > 0 else 0
    reward_earned = (days_done >= days_in_month)

    return {
        "name":            name,
        "year":            year,
        "month":           month,
        "days_done":       days_done,
        "days_elapsed":    days_elapsed,
        "days_in_month":   days_in_month,
        "completion_rate": completion_rate,
        "reward":          reward,
        "reward_earned":   reward_earned,
    }


def check_month_complete(timezone: str = "Asia/Tokyo") -> list:
    tz  = pytz.timezone(timezone)
    now = datetime.now(tz)
    if now.day == 1:
        first_of_month = now.replace(day=1)
        last_month     = first_of_month - timedelta(days=1)
        year, month    = last_month.year, last_month.month
    else:
        year, month = now.year, now.month

    earned = []
    for habit in list_habits():
        progress = get_monthly_progress(habit["name"], year, month, timezone)
        if progress.get("reward_earned") and progress.get("reward"):
            earned.append(progress)
    return earned


# ── Weekly summary ────────────────────────────────────────────────────────────

def get_weekly_summary(timezone: str = "Asia/Tokyo") -> dict:
    data  = _load()
    tz    = pytz.timezone(timezone)
    today = datetime.now(tz)
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    summary = {}
    for habit in data.values():
        log    = habit["log"]
        days   = [log.get(d) for d in dates]
        done   = [d for d in days if d is True]
        rate   = len(done) / 7 * 100
        streak = get_streak(habit["name"], timezone)["current"]
        summary[habit["name"]] = {
            "days":   days,
            "dates":  dates,
            "rate":   rate,
            "streak": streak,
            "reward": habit.get("reward"),
        }

    return {"habits": summary, "dates": dates}
