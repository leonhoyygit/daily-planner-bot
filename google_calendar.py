"""
google_calendar.py — Google Calendar sync with flexible date and time parsing.

Task line formats supported:
  "9am - Team standup"
  "Team standup at 9am"
  "11:30am - Review proposal"
  "14:00 - Meeting"
  "Go for a walk"                        → all-day event for TODAY
  "Go for a walk tomorrow"               → all-day event for TOMORROW
  "Go for a walk on Friday"              → all-day event for next Friday
  "Go for a walk on 2026-05-10"          → all-day event for that date
  "9am tomorrow - Dentist"               → timed event on tomorrow
  "Friday 3pm - Team dinner"             → timed event on next Friday
"""

import os
import re
from datetime import datetime, timedelta
import pytz
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES     = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "token.json"
CREDS_FILE = "credentials.json"

# ── Time pattern ──────────────────────────────────────────────────────────────
TIME_PATTERN = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{2}:\d{2})",
    re.IGNORECASE,
)

# ── Date keywords ─────────────────────────────────────────────────────────────
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_date_from_line(line: str, tz) -> tuple:
    """
    Extract a target date and cleaned line from natural language.
    Returns (target_date: datetime, cleaned_line: str)

    Supports:
      - "tomorrow"
      - "day after tomorrow"
      - Day names: "friday", "next monday"
      - ISO dates: "2026-05-10", "05/10", "10 May"
      - Default: today
    """
    lower = line.lower()
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # ── ISO date: 2026-05-10 ──────────────────────────────────────────────────
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", line)
    if iso_match:
        try:
            target = tz.localize(datetime.strptime(iso_match.group(1), "%Y-%m-%d"))
            cleaned = line.replace(iso_match.group(1), "").strip(" -–—,")
            return target, cleaned
        except ValueError:
            pass

    # ── Slash date: 05/10 or 10/05 ───────────────────────────────────────────
    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", line)
    if slash_match:
        try:
            m, d = int(slash_match.group(1)), int(slash_match.group(2))
            year = today.year
            target = tz.localize(datetime(year, m, d))
            if target < today:
                target = tz.localize(datetime(year + 1, m, d))
            cleaned = line.replace(slash_match.group(0), "").strip(" -–—,")
            return target, cleaned
        except ValueError:
            pass

    # ── Written date: "10 May" or "May 10" ───────────────────────────────────
    month_names = ["jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    for fmt, pattern in [
        ("%d %B", r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))\b"),
        ("%B %d", r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2})\b"),
    ]:
        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            try:
                target = tz.localize(datetime.strptime(m.group(1) + " " + str(today.year), fmt + " %Y"))
                if target < today:
                    target = target.replace(year=today.year + 1)
                cleaned = line.replace(m.group(1), "").strip(" -–—,")
                return target, cleaned
            except ValueError:
                pass

    # ── "day after tomorrow" ──────────────────────────────────────────────────
    if "day after tomorrow" in lower:
        cleaned = re.sub(r"day after tomorrow", "", line, flags=re.IGNORECASE).strip(" -–—,")
        return today + timedelta(days=2), cleaned

    # ── "tomorrow" ────────────────────────────────────────────────────────────
    if "tomorrow" in lower:
        cleaned = re.sub(r"tomorrow", "", line, flags=re.IGNORECASE).strip(" -–—,")
        return today + timedelta(days=1), cleaned

    # ── Day names: "friday", "next monday" ───────────────────────────────────
    day_match = re.search(r"\b(?:next\s+)?(" + "|".join(DAY_NAMES) + r")\b", lower)
    if day_match:
        day_name   = day_match.group(1)
        target_dow = DAY_NAMES.index(day_name)
        current_dow = today.weekday()
        days_ahead  = (target_dow - current_dow) % 7
        if days_ahead == 0:
            days_ahead = 7  # always next occurrence
        target  = today + timedelta(days=days_ahead)
        cleaned = re.sub(r"\b(?:next\s+)?" + day_name + r"\b", "", line, flags=re.IGNORECASE).strip(" -–—,")
        return target, cleaned

    # ── Default: today ────────────────────────────────────────────────────────
    return today, line


def parse_time_from_line(line: str) -> tuple:
    """
    Extract time string from a line.
    Returns (time_str_or_None, cleaned_line)
    """
    match = TIME_PATTERN.search(line)
    if not match:
        return None, line
    time_str = match.group(1).strip()
    cleaned  = TIME_PATTERN.sub("", line, count=1).strip(" -–—,").strip()
    if not cleaned:
        cleaned = line
    return time_str, cleaned


def parse_time_str(time_str: str, base_date: datetime, tz) -> datetime:
    """Convert '9am', '2:30pm', '14:00' into a localized datetime."""
    time_str = time_str.strip().lower().replace(" ", "")
    naive    = base_date.replace(tzinfo=None)
    for fmt in ["%I:%M%p", "%I%p", "%H:%M"]:
        try:
            t = datetime.strptime(time_str, fmt)
            return tz.localize(naive.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0))
        except ValueError:
            continue
    return None


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


# ── Create tasks ──────────────────────────────────────────────────────────────

def create_tasks(task_lines: list, timezone: str = "Asia/Tokyo") -> list:
    """
    Parse and create Google Calendar events from task lines.

    Each line is parsed for:
      1. A date (tomorrow / friday / 2026-05-10 / default: today)
      2. A time (9am / 14:00 / default: all-day)

    Returns list of (title, date_str, time_str_or_None, event_link).
    """
    service = get_calendar_service()
    tz      = pytz.timezone(timezone)
    results = []

    for raw_line in task_lines:
        line = raw_line.strip()
        if not line:
            continue

        # Step 1: extract date
        target_date, line_after_date = parse_date_from_line(line, tz)

        # Step 2: extract time
        time_str, title = parse_time_from_line(line_after_date)
        if not title:
            title = raw_line.strip()

        date_str = target_date.strftime("%Y-%m-%d")

        if time_str:
            start_dt = parse_time_str(time_str, target_date, tz)
            if start_dt:
                end_dt = start_dt + timedelta(hours=1)
                event  = {
                    "summary":     "📝 " + title,
                    "start":       {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                    "end":         {"dateTime": end_dt.isoformat(),   "timeZone": timezone},
                    "description": "Added by Daily Planner Bot",
                    "colorId":     "5",
                    "reminders":   {
                        "useDefault": False,
                        "overrides":  [{"method": "popup", "minutes": 10}],
                    },
                }
                result = service.events().insert(calendarId="primary", body=event).execute()
                results.append((title, date_str, time_str, result.get("htmlLink")))
                continue

        # All-day event
        event = {
            "summary":     "📝 " + title,
            "start":       {"date": date_str},
            "end":         {"date": date_str},
            "description": "Added by Daily Planner Bot",
            "colorId":     "5",
        }
        result = service.events().insert(calendarId="primary", body=event).execute()
        results.append((title, date_str, None, result.get("htmlLink")))

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_todays_tasks(timezone: str = "Asia/Tokyo") -> list:
    service  = get_calendar_service()
    tz       = pytz.timezone(timezone)
    today    = datetime.now(tz)
    time_min = today.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
    time_max = today.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    result   = service.events().list(
        calendarId="primary", timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy="startTime",
    ).execute()
    return result.get("items", [])


def mark_task_complete(event_id: str):
    service = get_calendar_service()
    event   = service.events().get(calendarId="primary", eventId=event_id).execute()
    if not event["summary"].startswith("✅"):
        event["summary"] = "✅ " + event["summary"].replace("📝 ", "")
        service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
