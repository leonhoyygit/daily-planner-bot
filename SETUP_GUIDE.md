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
cd ~/daily_planner_bot

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
| /addhabit Exercise | Adds a recurring habit |
| /setreward Exercise | Buy new shoes — Sets monthly reward |
| /habits | All habits with streaks |
| /habitcheck | Tap to mark today's habits |
| /weeklyhabits | 7-day habit grid |
| /monthlyhabits | Monthly progress + rewards |

---

## STEP 8 — Flexible Task Date Input

When sending tasks, include a date and/or time in natural language:

| What you type | What happens |
|---------------|-------------|
| 9am - Team standup | Today, timed 9-10am |
| 3pm tomorrow - Dentist | Tomorrow, timed 3-4pm |
| Friday 2pm - Team dinner | Next Friday, timed 2-3pm |
| 2026-05-15 10am - Flight | May 15, timed 10-11am |
| Buy groceries tomorrow | Tomorrow, all-day |
| Go for a walk | Today, all-day |

Tasks with no date default to today. Tasks with no time are all-day events.

---

## STEP 9 — Deploy to Railway (Run 24/7 Without Your Mac)

$5 free credit to start. A lightweight bot costs roughly $0.50-2/month after that.

### 9A — Push code to GitHub

```bash
cd ~/daily_planner_bot

git init
git add .
git commit -m "Initial bot setup"

# Create repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/daily-planner-bot.git
git branch -M main
git push -u origin main
```

The .gitignore ensures credentials.json, token.json, and config.json are never pushed to GitHub.

### 9B — Create Railway project

1. Go to railway.app → sign up with GitHub
2. New Project → Deploy from GitHub repo
3. Select your daily-planner-bot repo
4. Railway detects the Procfile and starts building automatically

### 9C — Set Environment Variables on Railway

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

### 9D — Confirm Bot is Running

Railway dashboard → your project → Deployments tab → View Logs
You should see the same 200 OK lines as on your Mac.

---

## STEP 10 — Updating the Bot After Code Changes

```bash
cd ~/daily_planner_bot
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
