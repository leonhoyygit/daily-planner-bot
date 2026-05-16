# Daily Planner Bot Project Context

## Architecture
- **Framework:** `python-telegram-bot` (v20+)
- **Calendar Sync:** Google Calendar API V3
- **Logic:** `google_calendar.py` handles natural language parsing of dates and times.
- **Automation:** `scheduler.py` handles morning prompts (8:30 AM) and evening reviews (9:00 PM).
- **Habit Tracking:** `habit_tracker.py` manages streaks and rewards.

## Authentication & Token Management
- **Security:** Tokens are stored in `token.json`.
- **Expiration Fix:** The Google Cloud project must be set to **"In Production"** to prevent the 7-day refresh token expiration.
- **Auto-Refresh:** The bot handles `RefreshError` and provides actionable re-authentication instructions via Telegram if an `invalid_grant` occurs.

## Deployment
- **Platform:** Railway (using `Procfile` and `runtime.txt`)
- **Credentials:** 
  - Telegram Token via `TELEGRAM_TOKEN` env var.
  - Chat ID via `YOUR_CHAT_ID` env var.
  - Google Cloud Credentials (base64) via `GOOGLE_CREDENTIALS_B64`.
  - Google Token (base64) via `GOOGLE_TOKEN_B64`.

## Key Features
- **Implicit Planning:** Any text sent to the bot (not a command) is parsed as a task.
- **Flexible Parsing:** Supports relative dates ("tomorrow", "friday") and 24h compact times ("2130").
- **Interactive Review:** Evening check-in via Inline Buttons to mark tasks as Done.
- **Siri Integration:** Specialized `/siri_summary` command and Flask endpoint for voice-based progress updates.
