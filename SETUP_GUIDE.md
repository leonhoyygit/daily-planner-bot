# 🤖 Daily Planner Bot — Complete Setup Guide

A personal Telegram bot that greets you by name, plans your day, syncs to Google Calendar, tracks habits with streaks, and rewards you for monthly consistency.

---

## 📁 Project Files

```
daily_planner_bot/
├── bot.py              ← Main bot logic
├── google_calendar.py  ← Google Calendar sync
├── scheduler.py        ← Morning & evening automation
├── storage.py          ← Local task storage
├── habit_tracker.py    ← Habit streaks & rewards
├── config.json         ← Your tokens, name & settings
├── requirements.txt    ← Python dependencies
└── credentials.json    ← (You'll add this — Google API key)
```

---

## STEP 1 — Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g. `Leon's Daily Planner`)
4. Give it a username ending in `bot` (e.g. `leonplanner_bot`)
5. BotFather gives you a **token** like:
   ```
   7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx
   ```
6. Copy this token — you'll need it in Step 3

---

## STEP 2 — Get Your Telegram Chat ID

1. Search for **@userinfobot** in Telegram
2. Send it any message
3. It replies with your **Chat ID** (a number like `987654321`)
4. Copy this number

---

## STEP 3 — Configure `config.json`

Open `config.json` and fill in your details:

```json
{
  "telegram_token": "7123456789:AAFxxxxxxxxxxxxxxxxxxxxxx",
  "your_chat_id": 987654321,
  "timezone": "Asia/Tokyo",
  "name": "Leon"
}
```

> **Timezone options:** `Asia/Tokyo`, `America/New_York`, `Europe/London`, `Asia/Singapore`
> Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

---

## STEP 4 — Set Up Google Calendar API

1. Go to https://console.cloud.google.com
2. Click **"New Project"** → Name it `DailyPlannerBot` → Click **Create**
3. In the left menu go to **APIs & Services → Library**
4. Search for **Google Calendar API** → Click it → Click **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **"+ Create Credentials" → OAuth client ID**
7. If prompted, configure the consent screen:
   - User type: **External**
   - App name: `Daily Planner Bot`
   - Add your Gmail as a test user
8. Back at Create Credentials:
   - Application type: **Desktop app**
   - Name: `Daily Planner`
   - Click **Create**
9. Click **Download JSON**
10. Rename the downloaded file to `credentials.json`
11. Move it into the `daily_planner_bot/` folder

---

## STEP 5 — Install Python & Dependencies (Using Virtual Environment)

Using a virtual environment avoids conflicts with Anaconda or system Python.

```bash
# Navigate to the project folder
cd ~/daily_planner_bot

# Check what Python 3.9+ versions you have
python3.11 --version   # try this first
python3.10 --version   # or this

# If none found, install via Homebrew
brew install python@3.11

# Create a virtual environment
python3.11 -m venv venv

# Activate it (you'll see (venv) appear in your terminal)
source venv/bin/activate

# Install dependencies inside the venv
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ **Important:** Every time you open a new Terminal window to run the bot,
> you must activate the venv first:
> ```bash
> cd ~/daily_planner_bot && source venv/bin/activate
> ```

---

## STEP 6 — First Run & Google Auth

```bash
python3 bot.py
```

**What you'll see in Terminal (this is normal and means it's working!):**
```
2026-05-07 21:59:09 – httpx – INFO – HTTP Request: POST https://api.telegram.org/...getUpdates "HTTP/1.1 200 OK"
2026-05-07 21:59:19 – httpx – INFO – HTTP Request: POST https://api.telegram.org/...getUpdates "HTTP/1.1 200 OK"
```
These `200 OK` lines mean your bot is **successfully running** and listening for messages. ✅

**When does the Google browser window appear?**
The Google sign-in window does NOT appear immediately — it opens the **first time you send a task** via `/plan`. Once you submit your task list, a browser window will ask you to sign in and allow access to Google Calendar. After that, a `token.json` file is saved and you won't be asked again.

> Do NOT close the Terminal while the bot is running — this stops the bot.

---

## STEP 7 — Activate & Test Your Bot in Telegram

1. Open Telegram on your **phone or Mac**
2. In the search bar, type your bot's username (e.g. `@leonplanner_bot`)
3. Tap the bot and press **Start**, or type `/start`
4. You should receive the welcome message immediately!

**Test all features:**

| Command | What to expect |
|---------|---------------|
| `/start` | Welcome message with all commands listed |
| `/plan` | Bot asks what you want to achieve today |
| _(reply with tasks)_ | Tasks synced to Google Calendar (triggers Google sign-in on first use) |
| `/review` | Evening task check-in with tap-to-complete buttons |
| `/addhabit Exercise` | Adds a new daily habit |
| `/setreward Exercise \| Buy new shoes` | Sets a monthly reward for a habit |
| `/habits` | Shows all habits with streaks |
| `/habitcheck` | Tap to mark today's habits done |
| `/weeklyhabits` | 7-day habit grid with completion % |
| `/monthlyhabits` | Monthly progress bars + reward status |

---

## STEP 8 — Do You Need Your Mac On All the Time?

**Yes, while running locally — but you have options:**

### Option A: Keep Mac running (simplest)
Use the launchd setup below so the bot auto-starts when your Mac boots. Your Mac just needs to stay on and awake.

Create `~/Library/LaunchAgents/com.dailyplanner.bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dailyplanner.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/leonlee/daily_planner_bot/venv/bin/python</string>
        <string>/Users/leonlee/daily_planner_bot/bot.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/leonlee/daily_planner_bot</string>
    <key>StandardOutPath</key>
    <string>/Users/leonlee/daily_planner_bot/bot.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/leonlee/daily_planner_bot/bot_error.log</string>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.dailyplanner.bot.plist
```

### Option B: Deploy to Railway (free, runs 24/7 without your Mac) ⭐ Recommended

This is the best long-term solution — your bot runs in the cloud even when your Mac is off.

1. Go to https://railway.app and sign up (free)
2. Install the Railway CLI:
   ```bash
   brew install railway
   ```
3. In your project folder:
   ```bash
   cd ~/daily_planner_bot
   source venv/bin/activate
   railway login
   railway init
   railway up
   ```
4. Add your environment variables in the Railway dashboard:
   - `TELEGRAM_TOKEN` — your bot token
   - `YOUR_CHAT_ID` — your chat ID
5. Upload your `credentials.json` and `token.json` via the Railway dashboard under Files

> After deploying to Railway, you can close your Mac and the bot keeps running 24/7!

---

## 📅 How It Works Daily

| Time | What happens |
|------|-------------|
| **8:30 AM** | Bot messages you: *"Good morning, Leon! What do you want to achieve today?"* |
| **You reply** | Type tasks one per line, optionally with times like `9am - Standup` |
| **Instantly** | Tasks appear in Google Calendar as timed or all-day events |
| **9:00 PM** | Bot sends task check-in + habit check-in together |
| **You tap** | Mark tasks ✅ and habits 🟢 done |
| **Sunday 8 PM** | Weekly habit summary with 7-day grid automatically sent |
| **End of month** | Bot announces any earned habit rewards 🎁 |

---

## 🏃 Habit & Reward System

### Adding habits
```
/addhabit Exercise
/addhabit Read 20 pages
/addhabit No coffee after 3pm
```

### Setting monthly rewards
```
/setreward Exercise | Buy new running shoes
/setreward Read 20 pages | Buy that book you've been eyeing
/setreward No coffee after 3pm | Fancy dinner night
```

### Streak levels
| Streak | Emoji | Milestone |
|--------|-------|-----------|
| 1–2 days | 🌱 | Getting started |
| 3–6 days | ✨ | Building momentum |
| 7–13 days | 🔥 | On fire! |
| 14–29 days | ⚡ | Unstoppable |
| 30+ days | 🏆 | Champion |

### Monthly rewards
- Complete a habit **every single day** of the month → reward is earned
- At end of month, bot sends a congratulations message with your reward
- Miss even one day → streak resets to 0 and reward is not earned

---

## ⚙️ Customizing Schedule

Edit `scheduler.py` to change the times:

```python
CronTrigger(hour=8, minute=30, timezone=tz)   # Morning prompt
CronTrigger(hour=21, minute=0, timezone=tz)    # Evening check-in
CronTrigger(day_of_week="sun", hour=20, ...)   # Weekly summary
```

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| `AttributeError: module 'anyio'...` | You're using Anaconda Python 3.8. Follow Step 5 to create a venv with Python 3.11 |
| `ModuleNotFoundError` | Make sure venv is activated: `source venv/bin/activate` |
| Terminal shows `200 OK` but bot doesn't respond | Check you searched the correct bot username in Telegram |
| Google browser window never appeared | It only opens on your first `/plan` → task submission |
| Google auth fails | Delete `token.json` and re-run `python3 bot.py` |
| Bot stops when Mac sleeps | Use launchd (Step 8A) or deploy to Railway (Step 8B) |
| Wrong timezone | Update `timezone` in `config.json` |
