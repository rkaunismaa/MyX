# Twitter Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python system that scrapes Twitter accounts and search queries via Brave CDP, stores normalized data in MySQL, and runs on a configurable cron schedule with a Click CLI for on-demand control.

**Architecture:** Playwright connects to a running Brave instance via Chrome DevTools Protocol and intercepts Twitter's internal GraphQL API responses (`UserTweets`, `SearchTimeline`). A data pipeline normalises captured JSON payloads and writes to MySQL. A shared `runner.py` module drives the per-target scrape loop; `scheduler.py` calls it on a cron schedule via APScheduler; `cli.py` exposes it and target management commands.

**Tech Stack:** Python 3.11+, Playwright, APScheduler 3.x, Click, mysql-connector-python, PyYAML, loguru, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | `load_config()` — reads `config.yaml` |
| `db/schema.sql` | DDL for all five MySQL tables |
| `db/connection.py` | `get_connection(config)`, `get_enabled_targets(conn)` |
| `pipeline/parser.py` | `extract_tweets(payload, endpoint)`, `parse_tweet()`, `parse_user()` |
| `pipeline/writer.py` | `upsert_user()`, `insert_tweet()`, `link_tweet_target()`, `write_run_log()` |
| `scraper/engine.py` | `connect_to_brave(config)`, `scrape_target(page, target, on_payload, ...)` |
| `scraper/targets.py` | `get_target_url(target)` |
| `runner.py` | `run_targets(config, targets, conn)` — shared loop used by CLI and scheduler |
| `cli.py` | Click CLI: `run`, `target add/list/enable/disable`, `logs` |
| `scheduler.py` | APScheduler background process |
| `tests/conftest.py` | Pytest fixtures: test DB connection, table setup/teardown |
| `tests/test_parser.py` | Unit tests for `pipeline/parser.py` |
| `tests/test_writer.py` | Integration tests for `pipeline/writer.py` |
| `.gitignore` | Excludes `config.yaml`, `logs/`, `__pycache__/`, `.env` |
| `config.example.yaml` | Credential-free config template (committed to git) |
| `requirements.txt` | Pinned dependencies |
| `launch-brave.sh` | Shell script to start Brave with CDP enabled |
| `twitter-scraper.service` | systemd user service unit file |

---

## Task 1: Project Scaffold

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `config.example.yaml`
- Create: `config.yaml` (git-ignored)
- Create: `launch-brave.sh`

- [ ] **Step 1: Initialise git repository**

```bash
cd /home/rob/PythonEnvironments/Twitter
git init
```
Expected: `Initialized empty Git repository in /home/rob/PythonEnvironments/Twitter/.git/`

- [ ] **Step 2: Create virtual environment and activate it**

```bash
cd /home/rob/PythonEnvironments/Twitter
python3 -m venv .venv
source .venv/bin/activate
```

- [ ] **Step 3: Create `.gitignore`**

```
config.yaml
logs/
__pycache__/
*.pyc
.env
.venv/
*.egg-info/
dist/
```

- [ ] **Step 4: Create `requirements.txt`**

```
playwright==1.44.0
apscheduler==3.10.4
click==8.1.7
mysql-connector-python==8.4.0
pyyaml==6.0.1
loguru==0.7.2
pytest==8.2.0
pytest-asyncio==0.23.6
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```
Expected: packages install without errors; `playwright install` downloads Chromium.

- [ ] **Step 6: Create `config.example.yaml`**

```yaml
schedule:
  cron: "0 */6 * * *"   # every 6 hours

brave:
  debugging_port: 9222
  user_data_dir: /home/rob/.config/BraveSoftware/Brave-Browser

database:
  host: localhost
  port: 3306
  name: twitter_scraper
  user: YOUR_MYSQL_USER
  password: ""  # set your MySQL password here

scraper:
  max_scrolls: 20
  scroll_delay_seconds: 2
```

- [ ] **Step 7: Create `config.yaml`** (fill in your actual MySQL credentials)

```yaml
schedule:
  cron: "0 */6 * * *"

brave:
  debugging_port: 9222
  user_data_dir: /home/rob/.config/BraveSoftware/Brave-Browser

database:
  host: localhost
  port: 3306
  name: twitter_scraper
  user: rob
  password: ""

scraper:
  max_scrolls: 20
  scroll_delay_seconds: 2
```

- [ ] **Step 8: Create `launch-brave.sh`**

```bash
#!/usr/bin/env bash
# Launch Brave with remote debugging enabled, reusing your existing profile.
brave-browser \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/rob/.config/BraveSoftware/Brave-Browser \
  "$@"
```

```bash
chmod +x launch-brave.sh
```

- [ ] **Step 9: Create empty package `__init__.py` files**

```bash
mkdir -p scraper pipeline db tests logs
touch scraper/__init__.py pipeline/__init__.py db/__init__.py tests/__init__.py
```

- [ ] **Step 10: Initial commit**

```bash
git add .gitignore requirements.txt config.example.yaml launch-brave.sh \
        scraper/__init__.py pipeline/__init__.py db/__init__.py tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Database Schema

**Files:**
- Create: `db/schema.sql`

- [ ] **Step 1: Create `db/schema.sql`**

```sql
CREATE DATABASE IF NOT EXISTS twitter_scraper
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE twitter_scraper;

CREATE TABLE IF NOT EXISTS users (
  user_id         BIGINT PRIMARY KEY,
  username        VARCHAR(50)  NOT NULL,
  display_name    VARCHAR(100) NOT NULL,
  followers_count INT          NOT NULL DEFAULT 0,
  following_count INT          NOT NULL DEFAULT 0,
  verified        BOOLEAN      NOT NULL DEFAULT FALSE,
  scraped_at      DATETIME     NOT NULL
);

CREATE TABLE IF NOT EXISTS tweets (
  tweet_id        BIGINT PRIMARY KEY,
  author_id       BIGINT       NOT NULL,
  full_text       TEXT         NOT NULL,
  lang            VARCHAR(10)  NOT NULL DEFAULT '',
  created_at      DATETIME     NOT NULL,
  retweet_count   INT          NOT NULL DEFAULT 0,
  like_count      INT          NOT NULL DEFAULT 0,
  reply_count     INT          NOT NULL DEFAULT 0,
  quote_count     INT          NOT NULL DEFAULT 0,
  is_retweet      BOOLEAN      NOT NULL DEFAULT FALSE,
  is_quote        BOOLEAN      NOT NULL DEFAULT FALSE,
  raw_json        JSON,
  scraped_at      DATETIME     NOT NULL,
  FOREIGN KEY (author_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS scrape_targets (
  target_id   INT AUTO_INCREMENT PRIMARY KEY,
  type        ENUM('account', 'search') NOT NULL,
  value       VARCHAR(255) NOT NULL,
  enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at  DATETIME     NOT NULL
);

CREATE TABLE IF NOT EXISTS tweet_targets (
  tweet_id  BIGINT NOT NULL,
  target_id INT    NOT NULL,
  PRIMARY KEY (tweet_id, target_id),
  FOREIGN KEY (tweet_id)  REFERENCES tweets(tweet_id),
  FOREIGN KEY (target_id) REFERENCES scrape_targets(target_id)
);

CREATE TABLE IF NOT EXISTS run_logs (
  run_id           INT AUTO_INCREMENT PRIMARY KEY,
  target_id        INT          NOT NULL,
  started_at       DATETIME     NOT NULL,
  finished_at      DATETIME     NOT NULL,
  tweets_collected INT          NOT NULL DEFAULT 0,
  status           ENUM('success', 'error') NOT NULL,
  error_message    TEXT,
  FOREIGN KEY (target_id) REFERENCES scrape_targets(target_id)
);
```

- [ ] **Step 2: Apply schema to MySQL**

```bash
mysql -u rob -p < db/schema.sql
```
Expected: no errors. Verify with:
```bash
mysql -u rob -p -e "USE twitter_scraper; SHOW TABLES;"
```
Expected output:
```
+---------------------------+
| Tables_in_twitter_scraper |
+---------------------------+
| run_logs                  |
| scrape_targets            |
| tweet_targets             |
| tweets                    |
| users                     |
+---------------------------+
```

- [ ] **Step 3: Create test database for use in later tasks**

```bash
mysql -u rob -p -e "
  CREATE DATABASE IF NOT EXISTS twitter_scraper_test
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"
```

Apply schema to test database too:
```bash
sed 's/twitter_scraper;/twitter_scraper_test;/' db/schema.sql | \
  sed 's/twitter_scraper$/twitter_scraper_test/' | \
  mysql -u rob -p
```

- [ ] **Step 4: Commit**

```bash
git add db/schema.sql
git commit -m "feat: add database schema"
```

---

## Task 3: Config Loader and DB Connection

**Files:**
- Create: `config.py`
- Create: `db/connection.py`
- Create: `tests/conftest.py`
- Create: `tests/test_connection.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_connection.py`:
```python
import pytest
from db.connection import get_connection, get_enabled_targets


def test_get_connection_returns_open_connection(test_config):
    conn = get_connection(test_config)
    assert conn.is_connected()
    conn.close()


def test_get_enabled_targets_returns_list(test_config):
    conn = get_connection(test_config)
    targets = get_enabled_targets(conn)
    assert isinstance(targets, list)
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_connection.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` — `config.py` and `db/connection.py` don't exist yet.

- [ ] **Step 3: Create `config.py`**

```python
import yaml
from pathlib import Path


def load_config(path: str = "config.yaml") -> dict:
    with open(Path(path)) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Create `db/connection.py`**

```python
import mysql.connector


def get_connection(config: dict):
    db = config["database"]
    return mysql.connector.connect(
        host=db["host"],
        port=db["port"],
        database=db["name"],
        user=db["user"],
        password=db["password"],
    )


def get_enabled_targets(conn) -> list[dict]:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM scrape_targets WHERE enabled = TRUE ORDER BY target_id")
    targets = cursor.fetchall()
    cursor.close()
    return targets
```

- [ ] **Step 5: Create `tests/conftest.py`**

```python
import copy
import pytest
from config import load_config
from db.connection import get_connection


@pytest.fixture(scope="session")
def test_config():
    cfg = load_config()
    cfg = copy.deepcopy(cfg)
    cfg["database"]["name"] = "twitter_scraper_test"
    return cfg


@pytest.fixture
def db_conn(test_config):
    conn = get_connection(test_config)
    yield conn
    # Truncate all tables after each test for isolation
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in ["run_logs", "tweet_targets", "tweets", "users", "scrape_targets"]:
        cursor.execute(f"TRUNCATE TABLE {table}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_connection.py -v
```
Expected:
```
tests/test_connection.py::test_get_connection_returns_open_connection PASSED
tests/test_connection.py::test_get_enabled_targets_returns_list PASSED
```

- [ ] **Step 7: Commit**

```bash
git add config.py db/connection.py tests/conftest.py tests/test_connection.py
git commit -m "feat: add config loader and db connection"
```

---

## Task 4: Pipeline Parser

**Files:**
- Create: `pipeline/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_parser.py`:
```python
import json
import pytest
from datetime import datetime
from pipeline.parser import extract_tweets, parse_tweet, parse_user


# --- Fixtures ---

def make_tweet_result(tweet_id="111", user_id="999", text="Hello world",
                      lang="en", created_at="Mon Jan 01 12:00:00 +0000 2024",
                      retweets=2, likes=5, replies=1, quotes=0,
                      is_retweet=False, is_quote=False):
    return {
        "__typename": "Tweet",
        "rest_id": tweet_id,
        "core": {
            "user_results": {
                "result": {
                    "__typename": "User",
                    "rest_id": user_id,
                    "legacy": {
                        "id_str": user_id,
                        "screen_name": "testuser",
                        "name": "Test User",
                        "followers_count": 1000,
                        "friends_count": 500,
                        "verified": False,
                    },
                }
            }
        },
        "legacy": {
            "full_text": text,
            "lang": lang,
            "created_at": created_at,
            "retweet_count": retweets,
            "favorite_count": likes,
            "reply_count": replies,
            "quote_count": quotes,
            "retweeted": is_retweet,
            "is_quote_status": is_quote,
            "user_id_str": user_id,
        },
    }


def make_user_tweets_payload(tweet_results: list) -> dict:
    entries = [
        {
            "entryId": f"tweet-{tr['rest_id']}",
            "content": {
                "itemContent": {
                    "itemType": "TimelineTweet",
                    "tweet_results": {"result": tr},
                }
            },
        }
        for tr in tweet_results
    ]
    return {
        "data": {
            "user": {
                "result": {
                    "timeline_v2": {
                        "timeline": {
                            "instructions": [
                                {"type": "TimelineAddEntries", "entries": entries}
                            ]
                        }
                    }
                }
            }
        }
    }


def make_search_timeline_payload(tweet_results: list) -> dict:
    entries = [
        {
            "entryId": f"tweet-{tr['rest_id']}",
            "content": {
                "itemContent": {
                    "itemType": "TimelineTweet",
                    "tweet_results": {"result": tr},
                }
            },
        }
        for tr in tweet_results
    ]
    return {
        "data": {
            "search_by_raw_query": {
                "search_timeline": {
                    "timeline": {
                        "instructions": [
                            {"type": "TimelineAddEntries", "entries": entries}
                        ]
                    }
                }
            }
        }
    }


# --- Tests ---

def test_parse_user_extracts_fields():
    user_legacy = {
        "id_str": "999",
        "screen_name": "testuser",
        "name": "Test User",
        "followers_count": 1000,
        "friends_count": 500,
        "verified": True,
    }
    result = parse_user(user_legacy)
    assert result["user_id"] == 999
    assert result["username"] == "testuser"
    assert result["display_name"] == "Test User"
    assert result["followers_count"] == 1000
    assert result["following_count"] == 500
    assert result["verified"] is True


def test_parse_tweet_extracts_fields():
    tweet_result = make_tweet_result(tweet_id="123", user_id="456", text="Test tweet")
    parsed = parse_tweet(tweet_result)
    assert parsed is not None
    assert parsed["tweet"]["tweet_id"] == 123
    assert parsed["tweet"]["author_id"] == 456
    assert parsed["tweet"]["full_text"] == "Test tweet"
    assert parsed["tweet"]["lang"] == "en"
    assert isinstance(parsed["tweet"]["created_at"], datetime)
    assert parsed["tweet"]["like_count"] == 5
    assert parsed["tweet"]["retweet_count"] == 2
    assert parsed["tweet"]["is_retweet"] is False
    assert parsed["user"] is not None
    assert parsed["user"]["username"] == "testuser"


def test_parse_tweet_raw_json_is_string():
    tweet_result = make_tweet_result()
    parsed = parse_tweet(tweet_result)
    assert isinstance(parsed["tweet"]["raw_json"], str)
    assert json.loads(parsed["tweet"]["raw_json"])  # valid JSON


def test_parse_tweet_returns_none_for_missing_legacy():
    result = parse_tweet({"__typename": "Tweet", "rest_id": "1", "core": {}, "legacy": {}})
    assert result is None


def test_extract_tweets_from_user_tweets_payload():
    tweet_results = [make_tweet_result(tweet_id="1"), make_tweet_result(tweet_id="2")]
    payload = make_user_tweets_payload(tweet_results)
    items = extract_tweets(payload, "UserTweets")
    assert len(items) == 2
    ids = {item["tweet"]["tweet_id"] for item in items}
    assert ids == {1, 2}


def test_extract_tweets_from_search_timeline_payload():
    tweet_results = [make_tweet_result(tweet_id="10"), make_tweet_result(tweet_id="20")]
    payload = make_search_timeline_payload(tweet_results)
    items = extract_tweets(payload, "SearchTimeline")
    assert len(items) == 2
    ids = {item["tweet"]["tweet_id"] for item in items}
    assert ids == {10, 20}


def test_extract_tweets_unknown_endpoint_returns_empty():
    payload = make_user_tweets_payload([make_tweet_result()])
    items = extract_tweets(payload, "UnknownEndpoint")
    assert items == []


def test_extract_tweets_skips_non_add_entries_instructions():
    payload = make_user_tweets_payload([])
    payload["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"] = [
        {"type": "TimelinePinEntry"},
        {"type": "TimelineClearCache"},
    ]
    items = extract_tweets(payload, "UserTweets")
    assert items == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py -v
```
Expected: `ImportError` — `pipeline/parser.py` does not exist yet.

- [ ] **Step 3: Create `pipeline/parser.py`**

```python
import json
from datetime import datetime
from typing import Optional

TWITTER_DATE_FORMAT = "%a %b %d %H:%M:%S +0000 %Y"


def parse_user(user_legacy: dict) -> dict:
    return {
        "user_id": int(user_legacy.get("id_str", "0") or "0"),
        "username": user_legacy.get("screen_name", ""),
        "display_name": user_legacy.get("name", ""),
        "followers_count": user_legacy.get("followers_count", 0),
        "following_count": user_legacy.get("friends_count", 0),
        "verified": bool(user_legacy.get("verified", False)),
    }


def parse_tweet(tweet_result: dict) -> Optional[dict]:
    legacy = tweet_result.get("legacy", {})
    if not legacy or not legacy.get("full_text"):
        return None

    user_result = (
        tweet_result.get("core", {})
        .get("user_results", {})
        .get("result", {})
    )
    user_legacy = user_result.get("legacy", {})
    user_id_str = user_result.get("rest_id", "0") or "0"

    try:
        tweet_id = int(tweet_result.get("rest_id", "0"))
        author_id = int(user_id_str)
        created_at = datetime.strptime(legacy["created_at"], TWITTER_DATE_FORMAT)
    except (ValueError, KeyError):
        return None

    user = parse_user(user_legacy) if user_legacy else None

    return {
        "tweet": {
            "tweet_id": tweet_id,
            "author_id": author_id,
            "full_text": legacy.get("full_text", ""),
            "lang": legacy.get("lang", ""),
            "created_at": created_at,
            "retweet_count": legacy.get("retweet_count", 0),
            "like_count": legacy.get("favorite_count", 0),
            "reply_count": legacy.get("reply_count", 0),
            "quote_count": legacy.get("quote_count", 0),
            "is_retweet": bool(legacy.get("retweeted", False)),
            "is_quote": bool(legacy.get("is_quote_status", False)),
            "raw_json": json.dumps(tweet_result),
        },
        "user": user,
    }


def _get_instructions(payload: dict, endpoint: str) -> list:
    if endpoint == "UserTweets":
        return (
            payload.get("data", {})
            .get("user", {})
            .get("result", {})
            .get("timeline_v2", {})
            .get("timeline", {})
            .get("instructions", [])
        )
    if endpoint == "SearchTimeline":
        return (
            payload.get("data", {})
            .get("search_by_raw_query", {})
            .get("search_timeline", {})
            .get("timeline", {})
            .get("instructions", [])
        )
    return []


def extract_tweets(payload: dict, endpoint: str) -> list[dict]:
    results = []
    for instruction in _get_instructions(payload, endpoint):
        if instruction.get("type") != "TimelineAddEntries":
            continue
        for entry in instruction.get("entries", []):
            item_content = entry.get("content", {}).get("itemContent", {})
            tweet_result = item_content.get("tweet_results", {}).get("result", {})
            if tweet_result.get("__typename") == "Tweet":
                parsed = parse_tweet(tweet_result)
                if parsed:
                    results.append(parsed)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/parser.py tests/test_parser.py
git commit -m "feat: add pipeline parser with tests"
```

---

## Task 5: Pipeline Writer

**Files:**
- Create: `pipeline/writer.py`
- Create: `tests/test_writer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_writer.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_writer.py -v
```
Expected: `ImportError` — `pipeline/writer.py` does not exist yet.

- [ ] **Step 3: Create `pipeline/writer.py`**

```python
from datetime import datetime
from typing import Optional


def upsert_user(conn, user: dict) -> None:
    cursor = conn.cursor()
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
    cursor.close()


def insert_tweet(conn, tweet: dict) -> None:
    cursor = conn.cursor()
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
    cursor.close()


def link_tweet_target(conn, tweet_id: int, target_id: int) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT IGNORE INTO tweet_targets (tweet_id, target_id) VALUES (%s, %s)",
        (tweet_id, target_id),
    )
    conn.commit()
    cursor.close()


def write_run_log(
    conn,
    target_id: int,
    started_at: datetime,
    finished_at: datetime,
    tweets_collected: int,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO run_logs
            (target_id, started_at, finished_at, tweets_collected, status, error_message)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (target_id, started_at, finished_at, tweets_collected, status, error_message),
    )
    conn.commit()
    cursor.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_writer.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
pytest -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/writer.py tests/test_writer.py
git commit -m "feat: add pipeline writer with integration tests"
```

---

## Task 6: Scraper Engine and Targets

**Files:**
- Create: `scraper/engine.py`
- Create: `scraper/targets.py`

> Note: These modules require a live Brave instance and Twitter session. Tests are manual smoke tests.

- [ ] **Step 1: Create `scraper/targets.py`**

```python
import urllib.parse


def get_target_url(target: dict) -> str:
    if target["type"] == "account":
        username = target["value"].lstrip("@")
        return f"https://twitter.com/{username}"
    if target["type"] == "search":
        query = urllib.parse.quote(target["value"])
        return f"https://twitter.com/search?q={query}&src=typed_query&f=live"
    raise ValueError(f"Unknown target type: {target['type']}")
```

- [ ] **Step 2: Create `scraper/engine.py`**

```python
import asyncio
from typing import Callable

from loguru import logger
from playwright.async_api import async_playwright, Page, Response

from scraper.targets import get_target_url

INTERCEPTED_ENDPOINTS = {"UserTweets", "SearchTimeline"}


async def connect_to_brave(config: dict):
    port = config["brave"]["debugging_port"]
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{port}")
    logger.info(f"Connected to Brave on port {port}")
    return playwright, browser


async def scrape_target(
    page: Page,
    target: dict,
    on_payload: Callable,
    max_scrolls: int,
    scroll_delay: float,
) -> int:
    collected: list = []

    async def handle_response(response: Response) -> None:
        for endpoint in INTERCEPTED_ENDPOINTS:
            if endpoint in response.url:
                try:
                    payload = await response.json()
                    items = on_payload(payload, endpoint)
                    collected.extend(items)
                except Exception as e:
                    logger.warning(f"Failed to parse {endpoint} response: {e}")

    page.on("response", handle_response)

    url = get_target_url(target)
    logger.info(f"Navigating to {url}")
    await page.goto(url, wait_until="domcontentloaded")

    prev_count = 0
    for scroll_num in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(scroll_delay)
        if len(collected) == prev_count:
            logger.info(f"No new tweets after scroll {scroll_num + 1}, stopping.")
            break
        prev_count = len(collected)

    page.remove_listener("response", handle_response)
    return len(collected)
```

- [ ] **Step 3: Verify `get_target_url` behaves correctly (quick inline check)**

```bash
python -c "
from scraper.targets import get_target_url
print(get_target_url({'type': 'account', 'value': 'elonmusk'}))
print(get_target_url({'type': 'search', 'value': '#python'}))
"
```
Expected:
```
https://twitter.com/elonmusk
https://twitter.com/search?q=%23python&src=typed_query&f=live
```

- [ ] **Step 4: Commit**

```bash
git add scraper/engine.py scraper/targets.py
git commit -m "feat: add scraper engine and target URL builder"
```

---

## Task 7: Runner (Shared Scrape Loop)

**Files:**
- Create: `runner.py`

- [ ] **Step 1: Create `runner.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add runner.py
git commit -m "feat: add shared runner module"
```

---

## Task 8: CLI

**Files:**
- Create: `cli.py`

- [ ] **Step 1: Create `cli.py`**

```python
import click
from loguru import logger

from config import load_config
from db.connection import get_connection
from runner import run_all


@click.group()
def cli():
    pass


@cli.command()
@click.option("--target", "target_id", type=int, default=None,
              help="Scrape a single target by ID. Omit to run all enabled targets.")
def run(target_id):
    """Trigger a scrape run immediately."""
    config = load_config()
    run_all(config, target_id=target_id)


@cli.group()
def target():
    """Manage scrape targets."""
    pass


@target.command("add")
@click.option("--type", "target_type", required=True,
              type=click.Choice(["account", "search"]), help="Target type")
@click.option("--value", required=True, help="Username (no @) or search query")
def target_add(target_type, value):
    """Add a new scrape target."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scrape_targets (type, value, enabled, created_at) VALUES (%s, %s, TRUE, NOW())",
        (target_type, value),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    click.echo(f"Added target #{new_id}: [{target_type}] {value}")


@target.command("list")
def target_list():
    """List all scrape targets."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM scrape_targets ORDER BY target_id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    if not rows:
        click.echo("No targets configured.")
        return
    for row in rows:
        status = "enabled" if row["enabled"] else "disabled"
        click.echo(f"#{row['target_id']} [{row['type']}] {row['value']} ({status})")


@target.command("enable")
@click.argument("target_id", type=int)
def target_enable(target_id):
    """Enable a scrape target by ID."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()
    cursor.execute("UPDATE scrape_targets SET enabled = TRUE WHERE target_id = %s", (target_id,))
    conn.commit()
    cursor.close()
    conn.close()
    click.echo(f"Target #{target_id} enabled.")


@target.command("disable")
@click.argument("target_id", type=int)
def target_disable(target_id):
    """Disable a scrape target by ID."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()
    cursor.execute("UPDATE scrape_targets SET enabled = FALSE WHERE target_id = %s", (target_id,))
    conn.commit()
    cursor.close()
    conn.close()
    click.echo(f"Target #{target_id} disabled.")


@cli.command()
@click.option("--last", default=10, show_default=True, help="Number of recent runs to display")
def logs(last):
    """View recent scrape run logs."""
    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT r.run_id, r.started_at, r.tweets_collected, r.status, r.error_message,
               t.type, t.value
        FROM run_logs r
        JOIN scrape_targets t ON r.target_id = t.target_id
        ORDER BY r.run_id DESC
        LIMIT %s
        """,
        (last,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    if not rows:
        click.echo("No run logs found.")
        return
    for row in rows:
        icon = "✓" if row["status"] == "success" else "✗"
        click.echo(
            f"{icon} #{row['run_id']} [{row['type']}] {row['value']}"
            f" — {row['tweets_collected']} tweets — {row['started_at']}"
        )
        if row["error_message"]:
            click.echo(f"  Error: {row['error_message']}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Smoke-test CLI help output**

```bash
python cli.py --help
```
Expected:
```
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  logs    View recent scrape run logs.
  run     Trigger a scrape run immediately.
  target  Manage scrape targets.
```

```bash
python cli.py target --help
```
Expected:
```
Usage: cli.py target [OPTIONS] COMMAND [ARGS]...

  Manage scrape targets.

Commands:
  add      Add a new scrape target.
  disable  Disable a scrape target by ID.
  enable   Enable a scrape target by ID.
  list     List all scrape targets.
```

- [ ] **Step 3: Smoke-test target add and list**

```bash
python cli.py target add --type account --value elonmusk
python cli.py target add --type search --value "#python"
python cli.py target list
```
Expected:
```
Added target #1: [account] elonmusk
Added target #2: [search] #python
#1 [account] elonmusk (enabled)
#2 [search] #python (enabled)
```

- [ ] **Step 4: Commit**

```bash
git add cli.py
git commit -m "feat: add CLI with run, target, and logs commands"
```

---

## Task 9: Scheduler

**Files:**
- Create: `scheduler.py`

- [ ] **Step 1: Create `scheduler.py`**

```python
from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from config import load_config
from db.connection import get_connection
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
    )

    logger.info(f"Scheduler started. Cron: {cron_expr}")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify scheduler starts without error**

```bash
python scheduler.py &
sleep 3
kill %1
```
Expected: log line `Scheduler started. Cron: 0 */6 * * *` then graceful stop.

- [ ] **Step 3: Commit**

```bash
git add scheduler.py
git commit -m "feat: add APScheduler background process"
```

---

## Task 10: systemd Service

**Files:**
- Create: `twitter-scraper.service`

- [ ] **Step 1: Create `twitter-scraper.service`**

```ini
[Unit]
Description=Twitter Scraper Scheduler
After=network.target mysql.service

[Service]
Type=simple
WorkingDirectory=/home/rob/PythonEnvironments/Twitter
ExecStart=/home/rob/PythonEnvironments/Twitter/.venv/bin/python scheduler.py
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Install and enable the service**

```bash
mkdir -p ~/.config/systemd/user
cp twitter-scraper.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable twitter-scraper
```
Expected: `Created symlink ...`

- [ ] **Step 3: Verify service status**

```bash
systemctl --user status twitter-scraper
```
Expected: `Loaded: loaded (...); Enabled: enabled`

- [ ] **Step 4: Commit**

```bash
git add twitter-scraper.service
git commit -m "feat: add systemd user service for scheduler"
```

---

## Task 11: GitHub Remote

- [ ] **Step 1: Create a new GitHub repository**

Go to https://github.com/new and create a repository named `twitter-scraper` (private recommended). Do not initialise with README or .gitignore — the repo should be empty.

- [ ] **Step 2: Add remote and push**

```bash
cd /home/rob/PythonEnvironments/Twitter
git remote add origin git@github.com:YOUR_GITHUB_USERNAME/twitter-scraper.git
git push -u origin main
```
Expected: all commits pushed; no `config.yaml` or `logs/` in remote.

- [ ] **Step 3: Verify `.gitignore` is working**

```bash
git status
```
Expected: `nothing to commit, working tree clean` (config.yaml should not appear as untracked).

---

## Task 12: End-to-End Smoke Test

> Requires Brave to be running with `--remote-debugging-port=9222` and logged into Twitter.

- [ ] **Step 1: Launch Brave with CDP**

```bash
./launch-brave.sh
```
Navigate to https://twitter.com in Brave and confirm you are logged in.

- [ ] **Step 2: Run a single-target scrape via CLI**

```bash
python cli.py target add --type account --value elonmusk
python cli.py run --target 1
```
Expected: output like:
```
Target 'elonmusk': 40 tweets collected
```

- [ ] **Step 3: Verify data in MySQL**

```bash
mysql -u rob -p twitter_scraper -e "SELECT COUNT(*) FROM tweets; SELECT COUNT(*) FROM users;"
```
Expected: non-zero counts.

- [ ] **Step 4: View run log**

```bash
python cli.py logs --last 5
```
Expected: one entry with `✓`, tweet count, and timestamp.

- [ ] **Step 5: Run all tests one final time**

```bash
pytest -v
```
Expected: all tests PASS.
