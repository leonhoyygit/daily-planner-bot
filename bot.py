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
from google_calendar import create_tasks, get_todays_tasks, mark_task_complete
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

# ── Config — supports both local config.json and Railway env vars ─────────────
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


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi " + NAME + "! I'm your personal productivity assistant.\n\n"
        "I'll help you plan your day, track your habits, and celebrate your wins!\n\n"
        "TASK COMMANDS\n"
        "/plan          - Set today's tasks\n"
        "/review        - Evening task check-in\n\n"
        "HABIT COMMANDS\n"
        "/addhabit      - Add a recurring habit\n"
        "/setreward     - Set a monthly reward for a habit\n"
        "/removehabit   - Remove a habit\n"
        "/habits        - View habits + streaks\n"
        "/habitcheck    - Log today's habits\n"
        "/weeklyhabits  - Weekly habit summary\n"
        "/monthlyhabits - Monthly progress + rewards\n\n"
        "Your Chat ID: " + str(update.effective_chat.id),
    )


# ── /plan ─────────────────────────────────────────────────────────────────────
async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Good morning, " + NAME + "! What do you want to achieve?\n\n"
        "Send your tasks one per line. You can include a time and/or date:\n\n"
        "9am - Team standup              (today, timed)\n"
        "3pm tomorrow - Dentist          (tomorrow, timed)\n"
        "Friday 2pm - Team dinner        (next Friday, timed)\n"
        "2026-05-15 10am - Flight        (specific date, timed)\n"
        "Go for a walk                   (today, all-day)\n"
        "Buy groceries tomorrow          (tomorrow, all-day)\n\n"
        "Tasks with no date default to TODAY."
    )
    context.user_data["waiting_for_tasks"] = True


# ── Receive tasks ─────────────────────────────────────────────────────────────
async def receive_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_tasks"):
        return

    lines = [l.strip() for l in update.message.text.strip().split("\n") if l.strip()]
    if not lines:
        await update.message.reply_text("I didn't catch any tasks, " + NAME + ". Please try again!")
        return

    context.user_data["waiting_for_tasks"] = False

    # Save tasks grouped by date
    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    tasks = [{"title": t, "done": False} for t in lines]
    save_tasks(today, tasks)

    await update.message.reply_text("Syncing to Google Calendar...")
    try:
        results   = create_tasks(lines, TIMEZONE)
        task_list = ""
        for title, date_str, time_str, _ in results:
            tz_obj   = pytz.timezone(TIMEZONE)
            today_str = datetime.now(tz_obj).strftime("%Y-%m-%d")
            date_label = "today" if date_str == today_str else date_str
            if time_str:
                task_list += "- " + time_str + " " + date_label + " — " + title + "\n"
            else:
                task_list += "- " + title + " (" + date_label + ", all day)\n"

        await update.message.reply_text(
            "You're all set, " + NAME + "! " + str(len(results)) + " tasks added:\n\n" +
            task_list + "\nCrush it today! 💪"
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
    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    tasks = load_tasks(today)

    if not tasks:
        await app.bot.send_message(chat_id, "Good evening, " + NAME + "! No tasks found for today.")
        return

    keyboard = []
    for i, task in enumerate(tasks):
        icon = "✅" if task["done"] else "⬜"
        keyboard.append([InlineKeyboardButton(icon + " " + task["title"], callback_data="toggle_" + str(i))])
    keyboard.append([InlineKeyboardButton("Save & Close", callback_data="save_done")])

    done_count = sum(1 for t in tasks if t["done"])
    await app.bot.send_message(
        chat_id,
        "Good evening, " + NAME + "! Time to wrap up the day.\n\n"
        "Task Check-In - " + today + "\n"
        "Completed " + str(done_count) + "/" + str(len(tasks)) + " tasks.\n"
        "Tap each task to mark it done:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── /addhabit ─────────────────────────────────────────────────────────────────
async def cmd_addhabit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /addhabit <habit name>\n\n"
            "Examples:\n"
            "/addhabit Exercise\n"
            "/addhabit Read 20 pages\n\n"
            "Then use /setreward to add a monthly reward!"
        )
        return
    name = " ".join(context.args)
    if add_habit(name):
        await update.message.reply_text(
            "Love it, " + NAME + "! Habit added: " + name + "\n\n"
            "Want to set a reward for completing it all month?\n"
            "Use: /setreward " + name + " | your reward here"
        )
    else:
        await update.message.reply_text("You already have a habit called '" + name + "', " + NAME + "!")


# ── /setreward ────────────────────────────────────────────────────────────────
async def cmd_setreward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or "|" not in " ".join(context.args):
        await update.message.reply_text(
            "Usage: /setreward <habit name> | <your reward>\n\n"
            "Examples:\n"
            "/setreward Exercise | Buy new running shoes\n"
            "/setreward Read 20 pages | Buy that book you've been eyeing"
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
            "Complete this habit every day this month and you'll earn it! 🎁"
        )
    else:
        await update.message.reply_text(
            "I couldn't find a habit called '" + name + "'. Use /habits to see your habits."
        )


# ── /removehabit ──────────────────────────────────────────────────────────────
async def cmd_removehabit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removehabit <habit name>")
        return
    name = " ".join(context.args)
    if remove_habit(name):
        await update.message.reply_text("Done, " + NAME + ". Habit '" + name + "' removed.")
    else:
        await update.message.reply_text("I couldn't find a habit called '" + name + "'.")


# ── /habits ───────────────────────────────────────────────────────────────────
async def cmd_habits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    habits = list_habits()
    if not habits:
        await update.message.reply_text("No habits set up yet, " + NAME + "! Use /addhabit <name>")
        return

    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    lines = []
    for h in habits:
        s          = get_streak(h["name"], TIMEZONE)
        emoji      = streak_emoji(s["current"])
        done       = h.get("log", {}).get(today)
        check      = "✅" if done else ("⬜" if done is False else "❓")
        reward_tag = " 🎁" if h.get("reward") else ""
        lines.append(
            check + " " + h["name"] + reward_tag + " - " +
            emoji + " " + str(s["current"]) + "d streak (best: " + str(s["best"]) + "d)"
        )

    await update.message.reply_text(
        "Here are your habits, " + NAME + ":\n\n" +
        "\n".join(lines) + "\n\n"
        "🎁 = has a monthly reward set\n"
        "Use /habitcheck to log today"
    )


# ── /habitcheck ───────────────────────────────────────────────────────────────
async def cmd_habitcheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz    = pytz.timezone(TIMEZONE)
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
        s     = get_streak(h["name"], TIMEZONE)
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
    summary = get_weekly_summary(TIMEZONE)
    habits  = summary["habits"]
    dates   = summary["dates"]

    if not habits:
        await app.bot.send_message(chat_id, "No habits tracked yet! Use /addhabit to start.")
        return

    day_labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%a") for d in dates]
    rows = [NAME + "'s Weekly Habit Summary\n"]

    for name, data in habits.items():
        dots = []
        for done in data["days"]:
            if done is True:    dots.append("🟢")
            elif done is False: dots.append("🔴")
            else:               dots.append("⚪")
        rate   = data["rate"]
        streak = data["streak"]
        rows.append(streak_emoji(streak) + " " + name + (" 🎁" if data.get("reward") else ""))
        rows.append(" ".join(dots) + "  " + str(int(rate)) + "% - " + str(streak) + "d streak")
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
        await app.bot.send_message(chat_id, "No habits set up yet! Use /addhabit to start.")
        return

    tz         = pytz.timezone(TIMEZONE)
    month_name = datetime.now(tz).strftime("%B %Y")
    rows       = [NAME + "'s Monthly Progress - " + month_name + "\n"]

    for h in habits:
        progress = get_monthly_progress(h["name"], timezone=TIMEZONE)
        done     = progress["days_done"]
        elapsed  = progress["days_elapsed"]
        total    = progress["days_in_month"]
        rate     = progress["completion_rate"]
        reward   = progress.get("reward")
        streak   = get_streak(h["name"], TIMEZONE)["current"]

        filled = int(rate / 10)
        bar    = "█" * filled + "░" * (10 - filled)

        rows.append(streak_emoji(streak) + " " + h["name"])
        rows.append("[" + bar + "] " + str(done) + "/" + str(elapsed) + " days (" + str(int(rate)) + "%)")

        if reward:
            days_left = total - done
            if progress["reward_earned"]:
                rows.append("🎁 Reward earned: " + reward + " - Go enjoy it, " + NAME + "!")
            else:
                rows.append("🎁 Reward: " + reward)
                rows.append("Keep going! " + str(days_left) + " more days to earn it.")
        rows.append("")

    await app.bot.send_message(chat_id, "\n".join(rows))


async def send_month_end_rewards(app, chat_id: int):
    earned = check_month_complete(TIMEZONE)
    if not earned:
        return
    rows = ["Congratulations, " + NAME + "!\n\nYou completed a full month of habits!\n"]
    for p in earned:
        rows.append("🏆 " + p["name"])
        rows.append("You earned your reward: " + p["reward"])
        rows.append("Go enjoy it - you deserve it!\n")
    await app.bot.send_message(chat_id, "\n".join(rows))


# ── Button callbacks ──────────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")

    if query.data.startswith("toggle_"):
        tasks = load_tasks(today)
        idx   = int(query.data.split("_")[1])
        tasks[idx]["done"] = not tasks[idx]["done"]
        save_tasks(today, tasks)

        keyboard = []
        for i, task in enumerate(tasks):
            icon = "✅" if task["done"] else "⬜"
            keyboard.append([InlineKeyboardButton(icon + " " + task["title"], callback_data="toggle_" + str(i))])
        keyboard.append([InlineKeyboardButton("Save & Close", callback_data="save_done")])

        done_count = sum(1 for t in tasks if t["done"])
        await query.edit_message_text(
            "Task Check-In - " + today + "\n"
            "Completed " + str(done_count) + "/" + str(len(tasks)) + " tasks, " + NAME + ".\n"
            "Tap each task to mark it done:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "save_done":
        tasks       = load_tasks(today)
        done_count  = sum(1 for t in tasks if t["done"])
        total_count = len(tasks)
        undone      = [t["title"] for t in tasks if not t["done"]]

        if done_count == total_count:
            msg = "Amazing work, " + NAME + "! You completed ALL " + str(total_count) + " tasks today! 🎉"
        else:
            msg = "Day Summary - " + today + "\n\nCompleted: " + str(done_count) + "/" + str(total_count) + " tasks"
            if undone:
                msg += "\n\nNot completed:\n" + "\n".join("- " + t for t in undone)
            msg += "\n\nGood effort today, " + NAME + ". Tomorrow is a new chance!"
        await query.edit_message_text(msg)

    elif query.data.startswith("habit_"):
        parts  = query.data.split("_")
        idx    = int(parts[1])
        date   = parts[2]
        habits = get_habits_for_date(date)
        h      = habits[idx]
        mark_habit(h["name"], not (h["done"] is True), date)

        habits   = get_habits_for_date(date)
        keyboard = []
        for i, h in enumerate(habits):
            icon  = "✅" if h["done"] else "⬜"
            s     = get_streak(h["name"], TIMEZONE)
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
            s    = get_streak(h["name"], TIMEZONE)
            icon = "✅" if h["done"] is True else "❌"
            reward_note = ""
            if h.get("reward") and h["done"] is True:
                p = get_monthly_progress(h["name"], timezone=TIMEZONE)
                if p.get("reward_earned"):
                    reward_note = " - Reward earned! 🎁"
                else:
                    days_left   = p["days_in_month"] - p["days_done"]
                    reward_note = " - " + str(days_left) + " days left for reward!"
            lines.append(icon + " " + h["name"] + " - " + streak_emoji(s["current"]) + " " + str(s["current"]) + "d streak" + reward_note)

        all_done = all(h["done"] is True for h in habits)
        msg = "Habits saved - " + date + "\n\n" + "\n".join(lines)
        if all_done:
            msg += "\n\nPerfect habit day, " + NAME + "! Keep that streak alive! 🔥"
        else:
            msg += "\n\nEvery day counts, " + NAME + ". See you tomorrow!"
        await query.edit_message_text(msg)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",         start))
    app.add_handler(CommandHandler("plan",          plan))
    app.add_handler(CommandHandler("review",        review))
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

    logger.info("Bot is running for " + NAME + "...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
