from datetime import datetime
from typing import Literal, Optional


def upsert_user(conn, user: dict) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users
                (user_id, username, display_name, followers_count, following_count, verified, scraped_at)
            VALUES
                (%(user_id)s, %(username)s, %(display_name)s, %(followers_count)s,
                 %(following_count)s, %(verified)s, NOW())
            ON DUPLICATE KEY UPDATE
                username        = VALUES(username),
                display_name    = VALUES(display_name),
                followers_count = VALUES(followers_count),
                following_count = VALUES(following_count),
                verified        = VALUES(verified),
                scraped_at      = NOW()
            """,
            user,
        )
        conn.commit()
    finally:
        cursor.close()


def insert_tweet(conn, tweet: dict) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT IGNORE INTO tweets
                (tweet_id, author_id, full_text, lang, created_at, retweet_count, like_count,
                 reply_count, quote_count, is_retweet, is_quote, raw_json, scraped_at)
            VALUES
                (%(tweet_id)s, %(author_id)s, %(full_text)s, %(lang)s, %(created_at)s,
                 %(retweet_count)s, %(like_count)s, %(reply_count)s, %(quote_count)s,
                 %(is_retweet)s, %(is_quote)s, %(raw_json)s, NOW())
            """,
            tweet,
        )
        conn.commit()
    finally:
        cursor.close()


def link_tweet_target(conn, tweet_id: int, target_id: int) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT IGNORE INTO tweet_targets (tweet_id, target_id) VALUES (%s, %s)",
            (tweet_id, target_id),
        )
        conn.commit()
    finally:
        cursor.close()


def write_run_log(
    conn,
    target_id: int,
    started_at: datetime,
    finished_at: Optional[datetime],
    tweets_collected: int,
    status: Literal["success", "error"],
    error_message: Optional[str] = None,
) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO run_logs
                (target_id, started_at, finished_at, tweets_collected, status, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (target_id, started_at, finished_at, tweets_collected, status, error_message),
        )
        conn.commit()
    finally:
        cursor.close()
