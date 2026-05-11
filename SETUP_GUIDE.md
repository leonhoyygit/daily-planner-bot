# 🤖 Daily Planner Bot — Complete Setup Guide

A personal Telegram bot that greets you by name, plans your day with flexible date/time input, syncs to Google Calendar, tracks habits with streaks, and rewards you for monthly consistency.

---

## 📁 Project Files

```
daily_planner_bot/
├── bot.py              ← Main bot logic
├── google_calendar.py  ← Google Calendar sync with date/time parsing
├── scheduler.py        ← Morning & evening automation
├── storage.py          ← Local task storage
├── habit_tracker.py    ← Habit streaks & rewards
├── config.json         ← Your tokens, name & settings (local only)
├── requirements.txt    ← Python dependencies
├── Procfile            ← Railway deployment config
├── runtime.txt         ← Python version for Railway
├── .gitignore          ← Keeps secrets off GitHub
└── credentials.json    ← (You add this — Google API key, never commit)
```

---

## STEP 1 — Create Your Telegram Bot

1. Open Telegram and search for @BotFather
2. Send /newbot
3. Give it a name e.g. Leon's Daily Planner
4. Give it a username ending in bot e.g. leonplanner_bot
5. Copy the token: 7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx

---

## STEP 2 — Get Your Telegram Chat ID

1. Search for @userinfobot in Telegram
2. Send it any message
3. Copy your Chat ID (a number like 987654321)

---

## STEP 3 — Configure config.json

```json
{
  "telegram_token": "7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx",
  "your_chat_id": 987654321,
  "timezone": "Asia/Tokyo",
  "name": "Leon"
}
```

---

## STEP 4 — Set Up Google Calendar API

1. Go to https://console.cloud.google.com
2. New Project → Name it DailyPlannerBot → Create
3. APIs & Services → Library → Search "Google Calendar API" → Enable
4. APIs & Services → Credentials → + Create Credentials → OAuth client ID
5. Configure consent screen if prompted:
   - User type: External
   - App name: Daily Planner Bot
   - Add your Gmail as a Test user (OAuth consent screen → scroll to bottom → + Add Users)
6. Application type: Desktop app → Create
7. Download JSON → rename to credentials.json → move to project folder

---

## STEP 5 — Install Python & Dependencies

```bash
cd ~/GeminiProject/Daily_Planner_Bot

# Create virtual environment with Python 3.11
python3.11 -m venv venv

# If python3.11 not found:
# brew install python@3.11

# Activate venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## STEP 6 — First Run & Google Auth

```bash
python bot.py
```

Seeing 200 OK lines means the bot is running. The Google sign-in browser window appears the first time you submit tasks via /plan. After signing in, token.json is saved automatically.

---

## STEP 7 — Test Your Bot in Telegram

Search your bot username in Telegram → tap Start or type /start

| Command | What to expect |
|---------|---------------|
| /start | Welcome message |
| /plan | Bot asks for today's tasks |
| /review | Evening task check-in |
| /siri_summary | Text summary of achieved vs. pending tasks |
| /addhabit Exercise | Adds a recurring habit |
| /setreward Exercise | Buy new shoes — Sets monthly reward |
| /habits | All habits with streaks |
| /habitcheck | Tap to mark today's habits |
| /delete | PERMANENTLY delete today's events from Google Calendar |
| /weeklyhabits | 7-day habit grid |
| /monthlyhabits | Monthly progress + rewards |

---

## STEP 8 — Achievement-Based Summaries

The bot uses a progress-focused format for daily summaries (both in Telegram via `/siri_summary` and via the Siri integration endpoint). Instead of a simple chronological list, it separates your day into:

1.  **✅ What you've achieved:** A list of all tasks you've marked as done today.
2.  **⏳ Tasks pending to complete:** A list of remaining tasks yet to be finished.
3.  **❌ Tasks missed:** Any tasks that remained unticked after your evening review will automatically be marked with a ❌ in Google Calendar for accountability.

This format is designed to give you a clear sense of accomplishment while keeping you focused on what's left to do.

---

## STEP 9 — Cross-Day Event Support

The bot now correctly handles events that span across midnight. If you enter a time range where the end time is numerically smaller than the start time (e.g., in 24-hour format), the bot automatically assumes the event ends on the following day.

**Examples:**
- `2200-0000 - Movie night` (10 PM tonight to 12 AM tomorrow)
- `23:30-01:30 - Late project` (11:30 PM tonight to 1:30 AM tomorrow)
- `11pm-1am - Night shift` (11 PM tonight to 1 AM tomorrow)

---

## STEP 10 — Enhanced Input & Implicit Planning

### 10A — 24-Hour Time Support
You no longer need to type "am" or "pm". The bot recognizes 24-hour formats:
- `2130 - Deep work` (9:30 PM)
- `14:00-16:00 - Meeting` (2 PM to 4 PM)
- `14 - Quick call` (2 PM)
- `2200-0000 - Cross-day event` (See Step 9)

### 10B — Implicit Task Adding
You don't even need to type `/plan`. Just send any text message to the bot, and it will automatically parse it as a task and sync it to your Google Calendar.

---

## ⚠️ IMPORTANT REMARKS & REMINDERS

1. **No Concurrent Running:** NEVER run the bot locally on your Mac (via terminal) while it is also running on Railway. This causes a **Conflict Error (409)** and the bot will stop working. Always stop the local bot before deploying to Railway.
2. **Privacy Mode:** If adding the bot to a group, use **@BotFather** -> `/setprivacy` -> **Disable**. This allows the bot to see messages and sync them automatically.
3. **Robot Icon (🤖):** Events added by this bot are marked with a 🤖 icon to distinguish them from your personal calendar entries.
4. **Full Review:** The `/review` command now fetches **all** your Google Calendar activities for today, allowing you to tick off items directly in Telegram.

---

## STEP 11 — Deploy to Railway (Run 24/7 Without Your Mac)

$5 free credit to start. A lightweight bot costs roughly $0.50-2/month after that.

### 11A — Push code to GitHub

```bash
cd ~/GeminiProject/Daily_Planner_Bot

git init
git add .
git commit -m "Initial bot setup"

# Create repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/daily-planner-bot.git
git branch -M main
git push -u origin main
```

The .gitignore ensures credentials.json, token.json, and config.json are never pushed to GitHub.

### 11B — Create Railway project

1. Go to railway.app → sign up with GitHub
2. New Project → Deploy from GitHub repo
3. Select your daily-planner-bot repo
4. Railway detects the Procfile and starts building automatically

### 11C — Set Environment Variables on Railway

Project → Variables tab → Add these:

| Variable | Value |
|----------|-------|
| TELEGRAM_TOKEN | Your bot token from BotFather |
| YOUR_CHAT_ID | Your chat ID number |
| TIMEZONE | Asia/Tokyo |
| NAME | Leon |

DO I NEED TO ADD GOOGLE CREDENTIALS AS A VARIABLE?
Yes — but not as a plain variable. credentials.json is a multi-line JSON file so you need to encode it first.

In Terminal on your Mac:
```bash
base64 -i credentials.json | tr -d '\n'
```
Copy the entire output and add it as a Railway env var called GOOGLE_CREDENTIALS_B64.

Do the same for token.json:
```bash
base64 -i token.json | tr -d '\n'
```
Add as GOOGLE_TOKEN_B64.

Then add this block at the very top of google_calendar.py (already included in the latest version):
```python
import base64, os
for fname, env_key in [("credentials.json","GOOGLE_CREDENTIALS_B64"),("token.json","GOOGLE_TOKEN_B64")]:
    val = os.environ.get(env_key)
    if val and not os.path.exists(fname):
        with open(fname,"w") as f:
            f.write(base64.b64decode(val).decode())
```

This means Railway env vars needed are:

| Variable | Value |
|----------|-------|
| TELEGRAM_TOKEN | Bot token |
| YOUR_CHAT_ID | Chat ID |
| TIMEZONE | Asia/Tokyo |
| NAME | Leon |
| GOOGLE_CREDENTIALS_B64 | base64 encoded credentials.json |
| GOOGLE_TOKEN_B64 | base64 encoded token.json |

### 11D — Confirm Bot is Running

Railway dashboard → your project → Deployments tab → View Logs
You should see the same 200 OK lines as on your Mac.

---

## STEP 12 — Updating the Bot After Code Changes

```bash
cd ~/GeminiProject/Daily_Planner_Bot
source venv/bin/activate

# Test locally first
python bot.py

# Push to GitHub — Railway auto-deploys
git add .
git commit -m "describe your change here"
git push origin main
```

Railway auto-deploys within 1-2 minutes of every push.

---

## Daily Schedule

| Time | What happens |
|------|-------------|
| 8:30 AM | Bot asks: Good morning Leon! What do you want to achieve? |
| You reply | Tasks synced to Google Calendar with correct dates and times |
| 9:00 PM | Task check-in + habit check-in sent together |
| Sunday 8 PM | Weekly habit summary auto-sent |
| 1st of month | Bot announces any earned rewards from last month |

---

## Habit & Reward System

```
/addhabit Exercise
/setreward Exercise | Buy new running shoes
```

| Streak | Emoji |
|--------|-------|
| 1-2 days | Seedling - just starting |
| 3-6 days | Sparkles - building momentum |
| 7-13 days | Fire - on fire |
| 14-29 days | Lightning - unstoppable |
| 30+ days | Trophy - champion |

Complete every day of the month → reward earned. Miss one day → streak resets to 0.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ImportError: cannot import name 'get_monthly_progress' | Railway cached old file. Run: git add . && git commit -m "fix" && git push |
| AttributeError: module 'anyio' | Using Anaconda Python 3.8. Follow Step 5 with venv + Python 3.11 |
| ModuleNotFoundError | Activate venv: source venv/bin/activate |
| Google Error 403: access_denied | Add Gmail as test user in Google Cloud Console → OAuth consent screen → Test users |
| Google browser window never appeared | Opens only on first /plan task submission |
| Bot stops when Mac sleeps | Deploy to Railway (Step 9) |
| Railway bot not responding after deploy | Check Variables tab — all 6 env vars must be set |
| Tasks going to wrong date | Check phrasing — "friday 3pm" and "3pm friday" both work |
