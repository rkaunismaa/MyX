import pytest
from datetime import datetime
from pipeline.writer import (
    upsert_user, insert_tweet, link_tweet_target, write_run_log
)


def sample_user(user_id=1001):
    return {
        "user_id": user_id,
        "username": "testuser",
        "display_name": "Test User",
        "followers_count": 100,
        "following_count": 50,
        "verified": False,
    }


def sample_tweet(tweet_id=5001, author_id=1001):
    return {
        "tweet_id": tweet_id,
        "author_id": author_id,
        "full_text": "This is a test tweet",
        "lang": "en",
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
        "retweet_count": 2,
        "like_count": 10,
        "reply_count": 1,
        "quote_count": 0,
        "is_retweet": False,
        "is_quote": False,
        "raw_json": '{"test": true}',
    }


def sample_target(db_conn):
    cursor = db_conn.cursor()
    cursor.execute(
        "INSERT INTO scrape_targets (type, value, enabled, created_at) VALUES ('account', 'testuser', TRUE, NOW())"
    )
    db_conn.commit()
    target_id = cursor.lastrowid
    cursor.close()
    return target_id


def test_upsert_user_inserts_new_user(db_conn):
    upsert_user(db_conn, sample_user(user_id=1001))
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE user_id = 1001")
    row = cursor.fetchone()
    cursor.close()
    assert row is not None
    assert row["username"] == "testuser"
    assert row["followers_count"] == 100


def test_upsert_user_updates_existing_user(db_conn):
    upsert_user(db_conn, sample_user(user_id=1001))
    updated = sample_user(user_id=1001)
    updated["followers_count"] = 999
    upsert_user(db_conn, updated)
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT followers_count FROM users WHERE user_id = 1001")
    row = cursor.fetchone()
    cursor.close()
    assert row["followers_count"] == 999


def test_insert_tweet_inserts_new_tweet(db_conn):
    upsert_user(db_conn, sample_user(user_id=1001))
    insert_tweet(db_conn, sample_tweet(tweet_id=5001, author_id=1001))
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tweets WHERE tweet_id = 5001")
    row = cursor.fetchone()
    cursor.close()
    assert row is not None
    assert row["full_text"] == "This is a test tweet"
    assert row["like_count"] == 10


def test_insert_tweet_ignores_duplicate(db_conn):
    upsert_user(db_conn, sample_user(user_id=1001))
    insert_tweet(db_conn, sample_tweet(tweet_id=5001, author_id=1001))
    insert_tweet(db_conn, sample_tweet(tweet_id=5001, author_id=1001))  # duplicate
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tweets WHERE tweet_id = 5001")
    count = cursor.fetchone()[0]
    cursor.close()
    assert count == 1


def test_link_tweet_target(db_conn):
    upsert_user(db_conn, sample_user(user_id=1001))
    insert_tweet(db_conn, sample_tweet(tweet_id=5001, author_id=1001))
    target_id = sample_target(db_conn)
    link_tweet_target(db_conn, 5001, target_id)
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM tweet_targets WHERE tweet_id = 5001 AND target_id = %s",
        (target_id,),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    assert count == 1


def test_link_tweet_target_ignores_duplicate(db_conn):
    upsert_user(db_conn, sample_user(user_id=1001))
    insert_tweet(db_conn, sample_tweet(tweet_id=5001, author_id=1001))
    target_id = sample_target(db_conn)
    link_tweet_target(db_conn, 5001, target_id)
    link_tweet_target(db_conn, 5001, target_id)  # duplicate
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tweet_targets WHERE tweet_id = 5001")
    count = cursor.fetchone()[0]
    cursor.close()
    assert count == 1


def test_write_run_log_success(db_conn):
    target_id = sample_target(db_conn)
    started = datetime(2024, 1, 1, 10, 0, 0)
    finished = datetime(2024, 1, 1, 10, 1, 0)
    write_run_log(db_conn, target_id, started, finished, 42, "success")
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM run_logs WHERE target_id = %s", (target_id,))
    row = cursor.fetchone()
    cursor.close()
    assert row["status"] == "success"
    assert row["tweets_collected"] == 42
    assert row["error_message"] is None


def test_write_run_log_error(db_conn):
    target_id = sample_target(db_conn)
    started = datetime(2024, 1, 1, 10, 0, 0)
    finished = datetime(2024, 1, 1, 10, 0, 5)
    write_run_log(db_conn, target_id, started, finished, 0, "error", "Rate limit hit")
    cursor = db_conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM run_logs WHERE target_id = %s", (target_id,))
    row = cursor.fetchone()
    cursor.close()
    assert row["status"] == "error"
    assert row["error_message"] == "Rate limit hit"
