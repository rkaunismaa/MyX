import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger

from db.connection import get_connection, get_enabled_targets
from pipeline.parser import extract_tweets
from pipeline.writer import insert_tweet, link_tweet_target, upsert_user, write_run_log
from scraper.engine import connect_to_brave, scrape_target


async def run_targets(config: dict, targets: list[dict], conn) -> None:
    playwright, browser = await connect_to_brave(config)
    try:
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        for target in targets:
            started_at = datetime.now()
            tweets_collected = 0
            try:
                def on_payload(payload: dict, endpoint: str) -> list:
                    items = extract_tweets(payload, endpoint)
                    for item in items:
                        if item["user"]:
                            upsert_user(conn, item["user"])
                        insert_tweet(conn, item["tweet"])
                        link_tweet_target(conn, item["tweet"]["tweet_id"], target["target_id"])
                    return items

                tweets_collected = await scrape_target(
                    page,
                    target,
                    on_payload,
                    config["scraper"]["max_scrolls"],
                    config["scraper"]["scroll_delay_seconds"],
                )
                write_run_log(
                    conn, target["target_id"], started_at, datetime.now(),
                    tweets_collected, "success",
                )
                logger.info(f"Target '{target['value']}': {tweets_collected} tweets collected")
            except Exception as e:
                logger.error(f"Target '{target['value']}' failed: {e}")
                write_run_log(
                    conn, target["target_id"], started_at, datetime.now(),
                    tweets_collected, "error", str(e),
                )
    finally:
        await playwright.stop()


def run_all(config: dict, target_id: Optional[int] = None) -> None:
    conn = get_connection(config)
    try:
        if target_id is not None:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM scrape_targets WHERE target_id = %s AND enabled = TRUE",
                (target_id,),
            )
            targets = cursor.fetchall()
            cursor.close()
        else:
            targets = get_enabled_targets(conn)

        if not targets:
            logger.warning("No enabled targets found.")
            return

        asyncio.run(run_targets(config, targets, conn))
    finally:
        conn.close()
