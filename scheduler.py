import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)


def setup_scheduler(app, chat_id: int, timezone: str = "Asia/Tokyo"):
    tz        = pytz.timezone(timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    async def morning_prompt():
        from bot import NAME
        await app.bot.send_message(
            chat_id,
            "Good morning, " + NAME + "! What do you want to achieve today?\n\n"
            "Send me your tasks, one per line.\n"
            "You can add a time and/or a date:\n\n"
            "9am - Team standup\n"
            "11:30am - Review proposal\n"
            "3pm tomorrow - Dentist\n"
            "Friday 2pm - Team dinner\n"
            "Go for a walk\n\n"
            "Tasks without a time are added as all-day events for today (or the date you mention).",
        )
        app.bot_data["waiting_for_tasks"] = True
        logger.info("Morning prompt sent.")

    async def evening_review():
        from bot import send_evening_review, send_habit_checkin
        tz_local = pytz.timezone(timezone)
        date     = datetime.now(tz_local).strftime("%Y-%m-%d")
        await send_evening_review(app, chat_id)
        await send_habit_checkin(app, chat_id, date)
        logger.info("Evening review + habit check-in sent.")

    async def weekly_summary():
        from bot import send_weekly_habit_summary
        await send_weekly_habit_summary(app, chat_id)
        logger.info("Weekly habit summary sent.")

    async def month_end_check():
        from bot import send_month_end_rewards
        await send_month_end_rewards(app, chat_id)
        logger.info("Month-end reward check sent.")

    scheduler.add_job(morning_prompt,  CronTrigger(hour=8,  minute=30, timezone=tz), id="morning")
    scheduler.add_job(evening_review,  CronTrigger(hour=21, minute=0,  timezone=tz), id="evening")
    scheduler.add_job(weekly_summary,  CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=tz), id="weekly")
    scheduler.add_job(month_end_check, CronTrigger(day=1, hour=9, minute=0, timezone=tz), id="month_end")

    scheduler.start()
    logger.info("Scheduler started (" + timezone + "): morning 8:30am, evening 9pm, weekly Sun 8pm")
