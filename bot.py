import logging
import json
import os
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from google_calendar import (
    create_tasks, get_todays_tasks, mark_task_complete,
    resolve_timezone, TIMEZONE_DISPLAY,
)
from scheduler import setup_scheduler
from storage import save_tasks, load_tasks, update_task_status
from habit_tracker import (
    add_habit, set_reward, remove_habit, list_habits,
    mark_habit, get_habits_for_date,
    get_streak, streak_emoji,
    get_weekly_summary, get_monthly_progress, check_month_complete,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
if os.path.exists("config.json"):
    with open("config.json") as f:
        config = json.load(f)
    TELEGRAM_TOKEN = config["telegram_token"]
    YOUR_CHAT_ID   = int(config["your_chat_id"])
    TIMEZONE       = config.get("timezone", "Asia/Tokyo")
    NAME           = config.get("name", "friend")
else:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    YOUR_CHAT_ID   = int(os.environ["YOUR_CHAT_ID"])
    TIMEZONE       = os.environ.get("TIMEZONE", "Asia/Tokyo")
    NAME           = os.environ.get("NAME", "friend")

# Active timezone — can be changed at runtime with /settimezone
_active_timezone = TIMEZONE


def get_timezone() -> str:
    return _active_timezone


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz_display = TIMEZONE_DISPLAY.get(get_timezone(), get_timezone())
    await update.message.reply_text(
        "Hi " + NAME + "! I'm your personal productivity assistant.\n\n"
        "TASK COMMANDS\n"
        "/plan          - Set today's tasks\n"
        "/review        - Evening task check-in\n\n"
        "HABIT COMMANDS\n"
        "/addhabit      - Add a recurring habit\n"
        "/setreward     - Set a monthly reward\n"
        "/removehabit   - Remove a habit\n"
        "/habits        - View habits + streaks\n"
        "/habitcheck    - Log today's habits\n"
        "/weeklyhabits  - Weekly habit summary\n"
        "/monthlyhabits - Monthly progress + rewards\n\n"
        "SETTINGS\n"
        "/settimezone   - Switch timezone (HK/Japan/US etc.)\n"
        "/timezone      - Show current timezone\n\n"
        "Current timezone: " + tz_display + "\n"
        "Chat ID: " + str(update.effective_chat.id),
    )


# ── /timezone ─────────────────────────────────────────────────────────────────
async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz_display = TIMEZONE_DISPLAY.get(get_timezone(), get_timezone())
    tz         = pytz.timezone(get_timezone())
    now        = datetime.now(tz).strftime("%I:%M %p, %A %d %b %Y")
    await update.message.reply_text(
        "Current timezone: " + tz_display + "\n"
        "Local time now: " + now + "\n\n"
        "To switch, use:\n"
        "/settimezone hk\n"
        "/settimezone japan\n"
        "/settimezone us\n"
        "/settimezone la\n"
        "/settimezone london\n"
        "/settimezone singapore"
    )


# ── /settimezone ──────────────────────────────────────────────────────────────
async def cmd_settimezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _active_timezone

    if not context.args:
        await update.message.reply_text(
            "Usage: /settimezone <zone>\n\n"
            "Available shortcuts:\n"
            "hk / hongkong   → 🇭🇰 Hong Kong\n"
            "japan / tokyo   → 🇯🇵 Japan\n"
            "us / ny / nyc   → 🇺🇸 US East\n"
            "la / sf         → 🇺🇸 US West\n"
            "london / uk     → 🇬🇧 London\n"
            "sg / singapore  → 🇸🇬 Singapore\n\n"
            "Or use full name: /settimezone Asia/Hong_Kong"
        )
        return

    tz_input   = " ".join(context.args)
    resolved   = resolve_timezone(tz_input)

    if not resolved:
        await update.message.reply_text(
            "I didn't recognise '" + tz_input + "', " + NAME + ".\n\n"
            "Try: hk, japan, us, la, london, singapore\n"
            "Or full name like: Asia/Hong_Kong"
        )
        return

    _active_timezone = resolved
    tz         = pytz.timezone(resolved)
    now        = datetime.now(tz).strftime("%I:%M %p, %A %d %b %Y")
    tz_display = TIMEZONE_DISPLAY.get(resolved, resolved)

    await update.message.reply_text(
        "Timezone updated, " + NAME + "!\n\n"
        "Now using: " + tz_display + "\n"
        "Local time: " + now + "\n\n"
        "All your tasks and schedules will use this timezone."
    )


# ── /plan ─────────────────────────────────────────────────────────────────────
async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz_display = TIMEZONE_DISPLAY.get(get_timezone(), get_timezone())
    await update.message.reply_text(
        "Good morning, " + NAME + "! What do you want to achieve?\n\n"
        "Send your tasks one per line.\n"
        "You can include a time range, time, and/or date:\n\n"
        "9am-11am - Deep work session      (2 hours)\n"
        "9am-10:30am - Team meeting        (1.5 hours)\n"
        "3pm - Quick call                  (1 hour default)\n"
        "3pm tomorrow - Dentist            (tomorrow)\n"
        "Friday 2pm-4pm - Team dinner      (next Friday)\n"
        "2026-05-15 10am-12pm - Flight     (specific date)\n"
        "Go for a walk                     (today, all-day)\n\n"
        "Current timezone: " + tz_display + "\n"
        "Use /settimezone to switch (hk/japan/us/london)"
    )
    context.user_data["waiting_for_tasks"] = True


# ── Receive tasks ─────────────────────────────────────────────────────────────
async def receive_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [l.strip() for l in update.message.text.strip().split("\n") if l.strip()]
    if not lines:
        return

    # Clear the manual /plan flag if it was set
    context.user_data["waiting_for_tasks"] = False

    tz    = pytz.timezone(get_timezone())
    today = datetime.now(tz).strftime("%Y-%m-%d")
    save_tasks(today, [{"title": t, "done": False} for t in lines])

    await update.message.reply_text("Syncing to Google Calendar...")
    try:
        results   = create_tasks(lines, get_timezone())
        task_list = ""
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        for title, date_str, time_label, _ in results:
            date_label = "today" if date_str == today_str else date_str
            if time_label:
                task_list += "- " + time_label + " " + date_label + " — " + title + "\n"
            else:
                task_list += "- " + title + " (" + date_label + ", all day)\n"

        await update.message.reply_text(
            "Got it, " + NAME + "! " + str(len(results)) + " tasks added:\n\n" +
            task_list + "\nCrush it! 💪"
        )
    except Exception as e:
        logger.error("Calendar sync error: " + str(e))
        await update.message.reply_text(
            "Tasks saved locally " + NAME + ", but Calendar sync failed.\nError: " + str(e)
        )


# ── /review ───────────────────────────────────────────────────────────────────
async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_evening_review(context.application, update.effective_chat.id)


async def send_evening_review(app, chat_id: int):
    tz    = pytz.timezone(get_timezone())
    today = datetime.now(tz).strftime("%Y-%m-%d")
    
    try:
        events = get_todays_tasks(get_timezone())
    except Exception as e:
        logger.error("Failed to fetch calendar for review: " + str(e))
        await app.bot.send_message(chat_id, "Couldn't reach Google Calendar for your review, " + NAME + ".")
        return

    if not events:
        await app.bot.send_message(chat_id, "Good evening, " + NAME + "! No calendar events found for today.")
        return

    # Store events in user_data for callback access
    app.user_data[chat_id]["review_events"] = events

    keyboard = []
    for i, event in enumerate(events):
        summary = event.get("summary", "Untitled")
        icon    = "✅" if summary.startswith("✅") else "⬜"
        keyboard.append([InlineKeyboardButton(icon + " " + summary, callback_data="toggle_" + str(i))])
    keyboard.append([InlineKeyboardButton("Save & Close", callback_data="save_done")])

    done_count = sum(1 for e in events if e.get("summary", "").startswith("✅"))
    await app.bot.send_message(
        chat_id,
        "Good evening, " + NAME + "! Time to wrap up.\n\n"
        "Calendar Check-In - " + today + "\n"
        "Completed " + str(done_count) + "/" + str(len(events)) + " activities.\n"
        "Tap each to mark it done:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── /addhabit ─────────────────────────────────────────────────────────────────
async def cmd_addhabit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /addhabit <habit name>\n\n"
            "Examples:\n/addhabit Exercise\n/addhabit Read 20 pages\n\n"
            "Then use /setreward to add a monthly reward!"
        )
        return
    name = " ".join(context.args)
    if add_habit(name):
        await update.message.reply_text(
            "Love it, " + NAME + "! Habit added: " + name + "\n\n"
            "Want a monthly reward? Use:\n"
            "/setreward " + name + " | your reward here"
        )
    else:
        await update.message.reply_text("You already have a habit called '" + name + "', " + NAME + "!")


# ── /setreward ────────────────────────────────────────────────────────────────
async def cmd_setreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or "|" not in " ".join(context.args):
        await update.message.reply_text(
            "Usage: /setreward <habit name> | <your reward>\n\n"
            "Example:\n/setreward Exercise | Buy new running shoes"
        )
        return
    full   = " ".join(context.args)
    parts  = full.split("|", 1)
    name   = parts[0].strip()
    reward = parts[1].strip()
    if set_reward(name, reward):
        await update.message.reply_text(
            "Perfect motivation, " + NAME + "!\n\n"
            "Habit: " + name + "\n"
            "Reward: " + reward + "\n\n"
            "Complete every day this month and you'll earn it! 🎁"
        )
    else:
        await update.message.reply_text("Couldn't find habit '" + name + "'. Use /habits to check.")


# ── /removehabit ──────────────────────────────────────────────────────────────
async def cmd_removehabit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removehabit <habit name>")
        return
    name = " ".join(context.args)
    if remove_habit(name):
        await update.message.reply_text("Done, " + NAME + ". Habit '" + name + "' removed.")
    else:
        await update.message.reply_text("Couldn't find habit '" + name + "'.")


# ── /habits ───────────────────────────────────────────────────────────────────
async def cmd_habits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    habits = list_habits()
    if not habits:
        await update.message.reply_text("No habits yet, " + NAME + "! Use /addhabit <name>")
        return

    tz    = pytz.timezone(get_timezone())
    today = datetime.now(tz).strftime("%Y-%m-%d")
    lines = []
    for h in habits:
        s          = get_streak(h["name"], get_timezone())
        emoji      = streak_emoji(s["current"])
        done       = h.get("log", {}).get(today)
        check      = "✅" if done else ("⬜" if done is False else "❓")
        reward_tag = " 🎁" if h.get("reward") else ""
        lines.append(check + " " + h["name"] + reward_tag + " - " + emoji + " " + str(s["current"]) + "d streak (best: " + str(s["best"]) + "d)")

    await update.message.reply_text(
        "Here are your habits, " + NAME + ":\n\n" + "\n".join(lines) + "\n\n"
        "🎁 = has a monthly reward\nUse /habitcheck to log today"
    )


# ── /habitcheck ───────────────────────────────────────────────────────────────
async def cmd_habitcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz    = pytz.timezone(get_timezone())
    today = datetime.now(tz).strftime("%Y-%m-%d")
    await send_habit_checkin(context.application, update.effective_chat.id, today)


async def send_habit_checkin(app, chat_id: int, date: str):
    habits = get_habits_for_date(date)
    if not habits:
        await app.bot.send_message(chat_id, "No habits set up yet! Use /addhabit <name>")
        return

    keyboard = []
    for i, h in enumerate(habits):
        icon  = "✅" if h["done"] else "⬜"
        s     = get_streak(h["name"], get_timezone())
        label = icon + " " + h["name"] + " (" + streak_emoji(s["current"]) + " " + str(s["current"]) + "d)"
        keyboard.append([InlineKeyboardButton(label, callback_data="habit_" + str(i) + "_" + date)])
    keyboard.append([InlineKeyboardButton("Save Habits", callback_data="habits_save_" + date)])

    done_count = sum(1 for h in habits if h["done"] is True)
    await app.bot.send_message(
        chat_id,
        "Habit Check-In - " + date + "\n\n"
        "How did you do today, " + NAME + "?\n" +
        str(done_count) + "/" + str(len(habits)) + " habits completed",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── /weeklyhabits ─────────────────────────────────────────────────────────────
async def cmd_weeklyhabits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_weekly_habit_summary(context.application, update.effective_chat.id)


async def send_weekly_habit_summary(app, chat_id: int):
    summary = get_weekly_summary(get_timezone())
    habits  = summary["habits"]
    dates   = summary["dates"]

    if not habits:
        await app.bot.send_message(chat_id, "No habits tracked yet! Use /addhabit to start.")
        return

    day_labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%a") for d in dates]
    rows = [NAME + "'s Weekly Habit Summary\n"]
    for name, data in habits.items():
        dots = ["🟢" if d is True else ("🔴" if d is False else "⚪") for d in data["days"]]
        rows.append(streak_emoji(data["streak"]) + " " + name + (" 🎁" if data.get("reward") else ""))
        rows.append(" ".join(dots) + "  " + str(int(data["rate"])) + "% - " + str(data["streak"]) + "d streak")
        rows.append("")

    rows.append("  ".join(day_labels))
    rows.append("\n🟢 Done  🔴 Missed  ⚪ Not logged")
    await app.bot.send_message(chat_id, "\n".join(rows))


# ── /monthlyhabits ────────────────────────────────────────────────────────────
async def cmd_monthlyhabits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_monthly_habit_summary(context.application, update.effective_chat.id)


async def send_monthly_habit_summary(app, chat_id: int):
    habits = list_habits()
    if not habits:
        await app.bot.send_message(chat_id, "No habits yet! Use /addhabit to start.")
        return

    tz         = pytz.timezone(get_timezone())
    month_name = datetime.now(tz).strftime("%B %Y")
    rows       = [NAME + "'s Monthly Progress - " + month_name + "\n"]

    for h in habits:
        progress = get_monthly_progress(h["name"], timezone=get_timezone())
        done     = progress["days_done"]
        elapsed  = progress["days_elapsed"]
        rate     = progress["completion_rate"]
        reward   = progress.get("reward")
        streak   = get_streak(h["name"], get_timezone())["current"]
        filled   = int(rate / 10)
        bar      = "█" * filled + "░" * (10 - filled)

        rows.append(streak_emoji(streak) + " " + h["name"])
        rows.append("[" + bar + "] " + str(done) + "/" + str(elapsed) + " days (" + str(int(rate)) + "%)")

        if reward:
            if progress["reward_earned"]:
                rows.append("🎁 Reward EARNED: " + reward + " - Go enjoy it, " + NAME + "!")
            else:
                rows.append("🎁 Reward: " + reward + " (" + str(progress["days_in_month"] - done) + " days left!)")
        rows.append("")

    await app.bot.send_message(chat_id, "\n".join(rows))


async def send_month_end_rewards(app, chat_id: int):
    earned = check_month_complete(get_timezone())
    if not earned:
        return
    rows = ["Congratulations, " + NAME + "! Full month of habits complete!\n"]
    for p in earned:
        rows.append("🏆 " + p["name"])
        rows.append("Reward earned: " + p["reward"] + " - Go enjoy it!\n")
    await app.bot.send_message(chat_id, "\n".join(rows))


# ── Button callbacks ──────────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tz    = pytz.timezone(get_timezone())
    today = datetime.now(tz).strftime("%Y-%m-%d")

    if query.data.startswith("toggle_"):
        idx    = int(query.data.split("_")[1])
        events = context.user_data.get("review_events", [])
        if not events or idx >= len(events):
            await query.edit_message_text("Session expired. Please use /review again.")
            return

        event   = events[idx]
        summary = event.get("summary", "")
        is_done = summary.startswith("✅")
        
        # Toggle on Google Calendar
        try:
            mark_task_complete(event["id"], not is_done)
            # Update local list
            if not is_done:
                event["summary"] = "✅ " + summary.replace("🤖 ", "").replace("📝 ", "")
            else:
                event["summary"] = "🤖 " + summary.replace("✅ ", "")
        except Exception as e:
            logger.error("Failed to toggle calendar event: " + str(e))
            await query.message.reply_text("Failed to update Google Calendar.")
            return

        keyboard = []
        for i, e in enumerate(events):
            s    = e.get("summary", "Untitled")
            icon = "✅" if s.startswith("✅") else "⬜"
            keyboard.append([InlineKeyboardButton(icon + " " + s, callback_data="toggle_" + str(i))])
        keyboard.append([InlineKeyboardButton("Save & Close", callback_data="save_done")])

        done_count = sum(1 for e in events if e.get("summary", "").startswith("✅"))
        await query.edit_message_text(
            "Calendar Check-In - " + today + "\n"
            "Completed " + str(done_count) + "/" + str(len(events)) + " activities, " + NAME + ".\n"
            "Tap to mark done:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "save_done":
        events      = context.user_data.get("review_events", [])
        if not events:
            await query.edit_message_text("Review complete.")
            return

        done_count  = sum(1 for e in events if e.get("summary", "").startswith("✅"))
        total_count = len(events)
        undone      = [e.get("summary", "") for e in events if not e.get("summary", "").startswith("✅")]

        if done_count == total_count:
            msg = "Amazing work, " + NAME + "! You completed ALL " + str(total_count) + " activities! 🎉"
        else:
            msg = "Day Summary - " + today + "\n\nCompleted: " + str(done_count) + "/" + str(total_count)
            if undone:
                msg += "\n\nRemaining:\n" + "\n".join("- " + t for t in undone)
            msg += "\n\nGood effort, " + NAME + ". Tomorrow is a new chance!"
        
        context.user_data["review_events"] = []
        await query.edit_message_text(msg)

    elif query.data.startswith("habit_"):
        parts  = query.data.split("_")
        idx    = int(parts[1])
        date   = parts[2]
        habits = get_habits_for_date(date)
        mark_habit(habits[idx]["name"], not (habits[idx]["done"] is True), date)

        habits   = get_habits_for_date(date)
        keyboard = []
        for i, h in enumerate(habits):
            icon  = "✅" if h["done"] else "⬜"
            s     = get_streak(h["name"], get_timezone())
            label = icon + " " + h["name"] + " (" + streak_emoji(s["current"]) + " " + str(s["current"]) + "d)"
            keyboard.append([InlineKeyboardButton(label, callback_data="habit_" + str(i) + "_" + date)])
        keyboard.append([InlineKeyboardButton("Save Habits", callback_data="habits_save_" + date)])

        done_count = sum(1 for h in habits if h["done"] is True)
        await query.edit_message_text(
            "Habit Check-In - " + date + "\n\n"
            "How did you do today, " + NAME + "?\n" +
            str(done_count) + "/" + str(len(habits)) + " habits completed",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data.startswith("habits_save_"):
        date   = query.data.replace("habits_save_", "")
        habits = get_habits_for_date(date)
        lines  = []
        for h in habits:
            s    = get_streak(h["name"], get_timezone())
            icon = "✅" if h["done"] is True else "❌"
            reward_note = ""
            if h.get("reward") and h["done"] is True:
                p = get_monthly_progress(h["name"], timezone=get_timezone())
                reward_note = " - Reward earned! 🎁" if p.get("reward_earned") else " - " + str(p["days_in_month"] - p["days_done"]) + " days left!"
            lines.append(icon + " " + h["name"] + " - " + streak_emoji(s["current"]) + " " + str(s["current"]) + "d" + reward_note)

        msg = "Habits saved - " + date + "\n\n" + "\n".join(lines)
        msg += "\n\nPerfect habit day, " + NAME + "! 🔥" if all(h["done"] is True for h in habits) else "\n\nEvery day counts, " + NAME + ". See you tomorrow!"
        await query.edit_message_text(msg)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",         start))
    app.add_handler(CommandHandler("plan",          plan))
    app.add_handler(CommandHandler("review",        review))
    app.add_handler(CommandHandler("timezone",      cmd_timezone))
    app.add_handler(CommandHandler("settimezone",   cmd_settimezone))
    app.add_handler(CommandHandler("addhabit",      cmd_addhabit))
    app.add_handler(CommandHandler("setreward",     cmd_setreward))
    app.add_handler(CommandHandler("removehabit",   cmd_removehabit))
    app.add_handler(CommandHandler("habits",        cmd_habits))
    app.add_handler(CommandHandler("habitcheck",    cmd_habitcheck))
    app.add_handler(CommandHandler("weeklyhabits",  cmd_weeklyhabits))
    app.add_handler(CommandHandler("monthlyhabits", cmd_monthlyhabits))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tasks))

    setup_scheduler(app, YOUR_CHAT_ID, TIMEZONE)

    logger.info("Bot is running for " + NAME + " (" + TIMEZONE + ")...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
