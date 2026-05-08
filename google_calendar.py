"""
google_calendar.py — Google Calendar sync with flexible date, time, and time-range parsing.

Supported task formats:
  "9am - Team standup"                  → today, 9:00-10:00am
  "9am-11am - Deep work"                → today, 9:00-11:00am (2 hours)
  "9:00-10:30 - Meeting"                → today, 9:00-10:30am
  "3pm tomorrow - Dentist"              → tomorrow, 3:00-4:00pm
  "Friday 2pm-4pm - Team dinner"        → next Friday, 2:00-4:00pm
  "2026-05-15 10am-12pm - Flight prep"  → May 15, 10:00am-12:00pm
  "Go for a walk"                       → today, all-day
  "Buy groceries tomorrow"              → tomorrow, all-day
"""

import os
import re
import base64
from datetime import datetime, timedelta
import pytz
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Decode Google credentials from Railway env vars ───────────────────────────
for _fname, _env_key in [
    ("credentials.json", "GOOGLE_CREDENTIALS_B64"),
    ("token.json",       "GOOGLE_TOKEN_B64"),
]:
    _val = os.environ.get(_env_key)
    if _val and not os.path.exists(_fname):
        with open(_fname, "w") as _f:
            _f.write(base64.b64decode(_val).decode())

SCOPES     = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "token.json"
CREDS_FILE = "credentials.json"

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Timezone aliases for easy switching
TIMEZONE_ALIASES = {
    "hk":      "Asia/Hong_Kong",
    "hongkong": "Asia/Hong_Kong",
    "japan":   "Asia/Tokyo",
    "tokyo":   "Asia/Tokyo",
    "jp":      "Asia/Tokyo",
    "us":      "America/New_York",
    "ny":      "America/New_York",
    "nyc":     "America/New_York",
    "la":      "America/Los_Angeles",
    "sf":      "America/Los_Angeles",
    "london":  "Europe/London",
    "uk":      "Europe/London",
    "sg":      "Asia/Singapore",
    "singapore": "Asia/Singapore",
}

TIMEZONE_DISPLAY = {
    "Asia/Hong_Kong":      "🇭🇰 Hong Kong (HKT)",
    "Asia/Tokyo":          "🇯🇵 Japan (JST)",
    "America/New_York":    "🇺🇸 US East (ET)",
    "America/Los_Angeles": "🇺🇸 US West (PT)",
    "Europe/London":       "🇬🇧 London (GMT/BST)",
    "Asia/Singapore":      "🇸🇬 Singapore (SGT)",
}


def resolve_timezone(tz_input: str) -> str:
    """Resolve a timezone alias or name to a valid pytz timezone string."""
    key = tz_input.strip().lower()
    if key in TIMEZONE_ALIASES:
        return TIMEZONE_ALIASES[key]
    # Try direct pytz lookup
    try:
        pytz.timezone(tz_input)
        return tz_input
    except pytz.UnknownTimeZoneError:
        return None


# ── Time range pattern — matches "9am-11am", "9:00-10:30", "14:00-16:00", "14-16" ─────
TIME_RANGE_PATTERN = re.compile(
    r"(\d{1,4}(?::\d{2})?\s*(?:am|pm)?)\s*[-–]\s*(\d{1,4}(?::\d{2})?\s*(?:am|pm)?)",
    re.IGNORECASE,
)

# Single time pattern
TIME_PATTERN = re.compile(
    r"(\d{1,4}(?::\d{2})?\s*(?:am|pm)|\d{2}:\d{2}|\b\d{1,2}\b(?!\s*[-–]))",
    re.IGNORECASE,
)


def parse_time_str(time_str: str, base_date: datetime, tz, fallback_period: str = None) -> datetime:
    """
    Convert time strings into localized datetime.
    Supports: 9am, 9:30am, 10:30, 14:00, 14, 9, etc.
    """
    time_str = time_str.strip().lower().replace(" ", "")
    naive    = base_date.replace(tzinfo=None)

    # Normalise 4-digit compact times: 1030am -> 10:30am, 930pm -> 9:30pm
    compact = re.match(r"^(\d{3,4})(am|pm)$", time_str)
    if compact:
        digits  = compact.group(1)
        period  = compact.group(2)
        if len(digits) == 3:
            # 930 -> 9:30
            time_str = digits[0] + ":" + digits[1:] + period
        else:
            # 1030 -> 10:30
            time_str = digits[:2] + ":" + digits[2:] + period

    for fmt in ["%I:%M%p", "%I%p", "%H:%M", "%H"]:
        try:
            t = datetime.strptime(time_str, fmt)
            return tz.localize(naive.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0))
        except ValueError:
            continue

    # Bare number like "11" — try with fallback period
    if fallback_period and re.match(r"^\d{1,2}$", time_str):
        try:
            t = datetime.strptime(time_str + fallback_period, "%I%p")
            return tz.localize(naive.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0))
        except ValueError:
            pass

    return None


def parse_time_range(line: str, base_date: datetime, tz) -> tuple:
    """
    Detect and parse a time range like '9am-11am' or '14:00-16:00'.
    Returns (start_dt, end_dt, cleaned_line) or (None, None, line).
    """
    match = TIME_RANGE_PATTERN.search(line)
    if not match:
        return None, None, line

    start_str = match.group(1).strip()
    end_str   = match.group(2).strip()

    # Infer am/pm for end time from start time if missing
    start_has_period = bool(re.search(r"am|pm", start_str, re.IGNORECASE))
    end_has_period   = bool(re.search(r"am|pm", end_str,   re.IGNORECASE))

    fallback = None
    if start_has_period and not end_has_period:
        fallback = "am" if "am" in start_str.lower() else "pm"

    start_dt = parse_time_str(start_str, base_date, tz)
    end_dt   = parse_time_str(end_str,   base_date, tz, fallback_period=fallback)

    if not start_dt or not end_dt:
        return None, None, line

    # If end time is earlier than start (e.g. 11pm-1am), add a day
    if end_dt <= start_dt:
        end_dt += timedelta(hours=12)

    cleaned = TIME_RANGE_PATTERN.sub("", line, count=1).strip(" -–—,").strip()
    if not cleaned:
        cleaned = line

    return start_dt, end_dt, cleaned


def parse_single_time(line: str, base_date: datetime, tz) -> tuple:
    """
    Extract a single time from a line.
    Returns (start_dt, cleaned_line) or (None, line).
    """
    match = TIME_PATTERN.search(line)
    if not match:
        return None, line

    time_str = match.group(1).strip()
    start_dt = parse_time_str(time_str, base_date, tz)
    if not start_dt:
        return None, line

    cleaned = TIME_PATTERN.sub("", line, count=1).strip(" -–—,").strip()
    if not cleaned:
        cleaned = line

    return start_dt, cleaned


def parse_date_from_line(line: str, tz) -> tuple:
    """
    Extract a target date from natural language.
    Returns (target_date: datetime, cleaned_line: str)
    """
    lower = line.lower()
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # ISO date: 2026-05-10
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", line)
    if iso_match:
        try:
            target  = tz.localize(datetime.strptime(iso_match.group(1), "%Y-%m-%d"))
            cleaned = line.replace(iso_match.group(1), "").strip(" -–—,")
            return target, cleaned
        except ValueError:
            pass

    # Slash date: 05/10
    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", line)
    if slash_match:
        try:
            m, d   = int(slash_match.group(1)), int(slash_match.group(2))
            target = tz.localize(datetime(today.year, m, d))
            if target < today:
                target = tz.localize(datetime(today.year + 1, m, d))
            cleaned = line.replace(slash_match.group(0), "").strip(" -–—,")
            return target, cleaned
        except ValueError:
            pass

    # Written date: "10 May" or "May 10"
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

    # "day after tomorrow"
    if "day after tomorrow" in lower:
        cleaned = re.sub(r"day after tomorrow", "", line, flags=re.IGNORECASE).strip(" -–—,")
        return today + timedelta(days=2), cleaned

    # "tomorrow"
    if "tomorrow" in lower:
        cleaned = re.sub(r"tomorrow", "", line, flags=re.IGNORECASE).strip(" -–—,")
        return today + timedelta(days=1), cleaned

    # Day names: "friday", "next monday"
    day_match = re.search(r"\b(?:next\s+)?(" + "|".join(DAY_NAMES) + r")\b", lower)
    if day_match:
        day_name    = day_match.group(1)
        target_dow  = DAY_NAMES.index(day_name)
        days_ahead  = (target_dow - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target  = today + timedelta(days=days_ahead)
        cleaned = re.sub(r"\b(?:next\s+)?" + day_name + r"\b", "", line, flags=re.IGNORECASE).strip(" -–—,")
        return target, cleaned

    return today, line


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
    Parse and create Google Calendar events.
    Returns list of (title, date_str, time_label, event_link).
    time_label examples: "9am-11am", "9am", None (all-day)
    """
    service = get_calendar_service()
    tz      = pytz.timezone(timezone)
    results = []

    for raw_line in task_lines:
        line = raw_line.strip()
        if not line:
            continue

        # 1. Extract date
        target_date, line_after_date = parse_date_from_line(line, tz)
        date_str = target_date.strftime("%Y-%m-%d")

        # 2. Try time range first (9am-11am)
        start_dt, end_dt, title = parse_time_range(line_after_date, target_date, tz)

        if start_dt and end_dt:
            duration_hrs = (end_dt - start_dt).seconds / 3600
            time_label   = start_dt.strftime("%I:%M%p").lstrip("0").lower() + "-" + end_dt.strftime("%I:%M%p").lstrip("0").lower()
            event = {
                "summary":     "🤖 " + title,
                "start":       {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                "end":         {"dateTime": end_dt.isoformat(),   "timeZone": timezone},
                "description": "Added by Daily Planner Bot (" + str(duration_hrs) + "h)",
                "colorId":     "5",
                "reminders":   {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
            }
            result = service.events().insert(calendarId="primary", body=event).execute()
            results.append((title, date_str, time_label, result.get("htmlLink")))
            continue

        # 3. Try single time (9am → 9am-10am default 1 hour)
        start_dt, title = parse_single_time(line_after_date, target_date, tz)

        if start_dt:
            end_dt     = start_dt + timedelta(hours=1)
            time_label = start_dt.strftime("%I:%M%p").lstrip("0").lower()
            event = {
                "summary":     "🤖 " + title,
                "start":       {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                "end":         {"dateTime": end_dt.isoformat(),   "timeZone": timezone},
                "description": "Added by Daily Planner Bot (1h)",
                "colorId":     "5",
                "reminders":   {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
            }
            result = service.events().insert(calendarId="primary", body=event).execute()
            results.append((title, date_str, time_label, result.get("htmlLink")))
            continue

        # 4. All-day event
        if not title:
            title = raw_line.strip()
        event = {
            "summary":     "🤖 " + title,
            "start":       {"date": date_str},
            "end":         {"date": date_str},
            "description": "Added by Daily Planner Bot",
            "colorId":     "5",
        }
        result = service.events().insert(calendarId="primary", body=event).execute()
        results.append((title, date_str, None, result.get("htmlLink")))

    return results


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


def mark_task_complete(event_id: str, done: bool = True):
    service = get_calendar_service()
    event   = service.events().get(calendarId="primary", eventId=event_id).execute()
    summary = event["summary"]
    
    if done and not summary.startswith("✅"):
        event["summary"] = "✅ " + summary.replace("🤖 ", "").replace("📝 ", "")
    elif not done and summary.startswith("✅"):
        event["summary"] = "🤖 " + summary.replace("✅ ", "")
    
    service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
