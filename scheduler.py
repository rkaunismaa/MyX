"""APScheduler background process that runs scrape jobs on a configurable cron schedule.

Managed by systemd as a user service (twitter-scraper.service). Run directly with:
    python scheduler.py
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from config import load_config
from runner import run_all


def main():
    config = load_config()
    cron_expr = config["schedule"]["cron"]
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr!r}")

    minute, hour, day, month, day_of_week = parts

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_all,
        "cron",
        args=[config],
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        misfire_grace_time=3600,  # tolerate up to 1 hour lateness (e.g. after suspend/resume)
        coalesce=True,            # collapse multiple missed runs into one
        max_instances=1,          # prevent overlapping runs
    )

    logger.info(f"Scheduler started. Cron: {cron_expr}")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
