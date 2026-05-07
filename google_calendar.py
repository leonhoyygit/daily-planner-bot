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

# ── Time parsing ──────────────────────────────────────────────────────────────
TIME_PATTERN = re.compile(
    r"(?:^|\s|-)(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{2}:\d{2})(?:\s*-\s*|\s+|$)",
    re.IGNORECASE,
)

def parse_task_line(line: str):
    """Parse a task line into (title, time_str_or_None)."""
    line  = line.strip()
    match = TIME_PATTERN.search(line)
    if not match:
        return line, None
    time_str = match.group(1).strip()
    title    = TIME_PATTERN.sub(" ", line).strip(" -–—").strip()
    if not title:
        title = line
    return title, time_str


def parse_time_str(time_str: str, date: datetime, tz):
    """Convert '9am', '2:30pm', '14:00' into a localized datetime."""
    time_str = time_str.strip().lower().replace(" ", "")
    for fmt in ["%I:%M%p", "%I%p", "%H:%M"]:
        try:
            t = datetime.strptime(time_str, fmt)
            return tz.localize(date.replace(
                hour=t.hour, minute=t.minute, second=0, microsecond=0
            ))
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
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


# ── Create tasks ──────────────────────────────────────────────────────────────
def create_tasks(task_lines: list, timezone: str = "Asia/Tokyo"):
    """
    Create Google Calendar events.
    Lines with a time  → 1-hour timed event + 10-min popup reminder.
    Lines without time → all-day event.
    Returns list of (title, time_str_or_None, event_link).
    """
    service = get_calendar_service()
    tz      = pytz.timezone(timezone)
    today   = datetime.now(tz).replace(tzinfo=None)
    results = []

    for line in task_lines:
        title, time_str = parse_task_line(line)

        if time_str:
            start_dt = parse_time_str(time_str, today, tz)
            if start_dt:
                end_dt = start_dt + timedelta(hours=1)
                event  = {
                    "summary": f"📝 {title}",
                    "start":   {"dateTime": start_dt.isoformat(), "timeZone": timezone},
                    "end":     {"dateTime": end_dt.isoformat(),   "timeZone": timezone},
                    "description": "Added by Daily Planner Bot",
                    "colorId": "5",
                    "reminders": {
                        "useDefault": False,
                        "overrides": [{"method": "popup", "minutes": 10}],
                    },
                }
                result = service.events().insert(calendarId="primary", body=event).execute()
                results.append((title, time_str, result.get("htmlLink")))
                continue

        # All-day fallback
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        event = {
            "summary":     f"📝 {title}",
            "start":       {"date": today_str},
            "end":         {"date": today_str},
            "description": "Added by Daily Planner Bot",
            "colorId":     "5",
        }
        result = service.events().insert(calendarId="primary", body=event).execute()
        results.append((title, None, result.get("htmlLink")))

    return results


# ── Fetch today's tasks ───────────────────────────────────────────────────────
def get_todays_tasks(timezone: str = "Asia/Tokyo"):
    service = get_calendar_service()
    tz      = pytz.timezone(timezone)
    today   = datetime.now(tz)
    time_min = today.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
    time_max = today.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    result   = service.events().list(
        calendarId="primary", timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy="startTime",
    ).execute()
    return result.get("items", [])


# ── Mark complete ─────────────────────────────────────────────────────────────
def mark_task_complete(event_id: str):
    service = get_calendar_service()
    event   = service.events().get(calendarId="primary", eventId=event_id).execute()
    if not event["summary"].startswith("✅"):
        event["summary"] = "✅ " + event["summary"].replace("📝 ", "")
        service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
