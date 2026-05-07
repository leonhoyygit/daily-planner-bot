import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)


def setup_scheduler(app, chat_id: int, timezone: str = "Asia/Tokyo"):
    """Set up morning and evening scheduled messages."""
    tz        = pytz.timezone(timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    # ── Morning prompt (8:00 AM) ──────────────────────────────────────────────
    async def morning_prompt():
        await app.bot.send_message(
            chat_id,
            "🌅 *Good morning!* ☀️\n\n"
            "What do you want to achieve today?\n\n"
            "Send me your tasks, one per line.\n"
            "You can optionally add a time — formats like `9am`, `2:30pm`, or `14:00` all work:\n\n"
            "```\n9am - Team standup call\n11:30am - Review project proposal\n1pm - Lunch with Sarah\n3pm - Dentist appointment\nGo for a 30min walk\nRead 20 pages\n```\n\n"
            "Tasks without a time will be added as all-day reminders 📅",
            parse_mode="Markdown",
        )
        app.bot_data["waiting_for_tasks"] = True
        logger.info("Morning prompt sent.")

    # ── Evening review + habit check-in (9:00 PM) ───────────────────────────────
    async def evening_review():
        from bot import send_evening_review, send_habit_checkin
        tz   = pytz.timezone(timezone)
        date = datetime.now(tz).strftime("%Y-%m-%d")
        await send_evening_review(app, chat_id)
        await send_habit_checkin(app, chat_id, date)
        logger.info("Evening review + habit check-in sent.")

    # ── Weekly habit summary (Sunday 8:00 PM) ────────────────────────────────
    async def weekly_summary():
        from bot import send_weekly_habit_summary
        await send_weekly_habit_summary(app, chat_id)
        logger.info("Weekly habit summary sent.")

    scheduler.add_job(
        morning_prompt,
        CronTrigger(hour=8, minute=30, timezone=tz),
        id="morning_prompt",
    )

    scheduler.add_job(
        evening_review,
        CronTrigger(hour=21, minute=0, timezone=tz),
        id="evening_review",
    )

    scheduler.add_job(
        weekly_summary,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=tz),
        id="weekly_summary",
    )

    scheduler.start()
    logger.info(f"Scheduler started — morning 8:00 AM, evening 9:00 PM ({timezone})")
