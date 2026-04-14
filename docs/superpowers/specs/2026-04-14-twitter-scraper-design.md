# Twitter Scraper — Design Spec

**Date:** 2026-04-14  
**Status:** Approved  

---

## Overview

A Python-based system that scrapes Twitter data from authenticated sessions using Brave browser, stores results in a local MySQL database, and runs on a configurable schedule with manual on-demand triggering via CLI. Project code and assets are version-controlled in a local git repository synced to GitHub.

**Scrape targets:**
- Specific accounts (by username)
- Search queries and hashtags

**Goals:**
- Personal archive (offline access to content)
- Analysis and research (trends, engagement metrics)

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Scheduler (APScheduler)                    │  ← runs jobs on cron + on-demand trigger
├─────────────────────────────────────────────┤
│  Scraper Engine (Playwright + Brave CDP)    │  ← connects to running Brave, intercepts XHR
├─────────────────────────────────────────────┤
│  Data Pipeline (parser + deduplicator)      │  ← normalizes Twitter JSON → DB schema
├─────────────────────────────────────────────┤
│  MySQL Database                             │  ← stores tweets, users, searches, run logs
└─────────────────────────────────────────────┘
```

Brave is launched once by the user with `--remote-debugging-port=9222`, pointing to the existing user profile so the Twitter session is already authenticated. Playwright connects to Brave via Chrome DevTools Protocol (CDP) and intercepts Twitter's internal GraphQL API responses to capture clean, structured JSON data without HTML parsing.

---

## Brave Setup

Launch Brave with:
```bash
brave-browser --remote-debugging-port=9222 --user-data-dir=/home/rob/.config/BraveSoftware/Brave-Browser
```

This reuses your existing Brave profile and authenticated Twitter session. A shell alias or launcher script will be provided.

---

## Database

MySQL runs as a system service with data files managed by the MySQL server (typically `/var/lib/mysql`). The project does not manage MySQL's data directory — it connects to a named database (`twitter_scraper`) on the local MySQL instance. The database name and connection credentials are defined in `config.yaml`.

To initialise the database, the `db/schema.sql` file is applied once:
```bash
mysql -u rob -p < db/schema.sql
```

---

## Database Schema (MySQL)

### `tweets`
| Column | Type | Notes |
|---|---|---|
| tweet_id | BIGINT PRIMARY KEY | |
| author_id | BIGINT FK → users | |
| full_text | TEXT | |
| lang | VARCHAR(10) | |
| created_at | DATETIME | |
| retweet_count | INT | |
| like_count | INT | |
| reply_count | INT | |
| quote_count | INT | |
| is_retweet | BOOLEAN | |
| is_quote | BOOLEAN | |
| raw_json | JSON | Original payload for reprocessing |
| scraped_at | DATETIME | |

### `users`
| Column | Type | Notes |
|---|---|---|
| user_id | BIGINT PRIMARY KEY | |
| username | VARCHAR(50) | |
| display_name | VARCHAR(100) | |
| followers_count | INT | |
| following_count | INT | |
| verified | BOOLEAN | |
| scraped_at | DATETIME | Updated on each scrape |

### `scrape_targets`
| Column | Type | Notes |
|---|---|---|
| target_id | INT PK AUTO_INCREMENT | |
| type | ENUM('account','search') | |
| value | VARCHAR(255) | e.g. "elonmusk" or "#python" |
| enabled | BOOLEAN | |
| created_at | DATETIME | |

### `tweet_targets`
| Column | Type | Notes |
|---|---|---|
| tweet_id | BIGINT FK → tweets | |
| target_id | INT FK → scrape_targets | |
| PRIMARY KEY | (tweet_id, target_id) | |

### `run_logs`
| Column | Type | Notes |
|---|---|---|
| run_id | INT PK AUTO_INCREMENT | |
| target_id | INT FK → scrape_targets | |
| started_at | DATETIME | |
| finished_at | DATETIME | |
| tweets_collected | INT | |
| status | ENUM('success','error') | |
| error_message | TEXT | NULL on success |

---

## Scraper Engine

**File:** `scraper/engine.py`, `scraper/targets.py`

Playwright connects to Brave at `http://localhost:9222` and attaches to the existing Twitter tab (or opens one). A response listener intercepts Twitter's internal GraphQL endpoints:

- `SearchTimeline` — search/hashtag targets
- `UserTweets` — account targets
- `TweetDetail` — individual tweet threads

**Per-target flow:**
1. Navigate to target URL (`twitter.com/search?q=...` or `twitter.com/username`)
2. Intercept responses until scroll exhaustion or `max_scrolls` limit reached
3. Pass raw JSON payloads to the data pipeline
4. Write `run_log` entry (success or error)
5. Move to next target

**Pagination:** The scraper scrolls the page to trigger additional API calls, repeating until no new tweets are returned or the `max_scrolls` limit is hit.

**Error handling:** If a target run throws (rate limit, network error, unexpected response shape), the error is logged to `run_logs` and the local log file. The scraper stops that target and moves on to the next one. No automatic retry — manual restart required.

---

## Data Pipeline

**Files:** `pipeline/parser.py`, `pipeline/writer.py`

1. **Parse** — extract normalized fields from raw GraphQL JSON
2. **Deduplicate** — `INSERT IGNORE` on `tweet_id` prevents duplicates on re-scrape
3. **Upsert users** — update follower/following counts on each scrape
4. **Link targets** — insert into `tweet_targets` to record which target produced each tweet

The `raw_json` column on `tweets` preserves the original payload for future reprocessing (e.g. extracting media URLs, card data) without requiring a re-scrape.

---

## Scheduler & CLI

### Configuration (`config.yaml`)
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
  user: rob
  password: ""  # set your MySQL password here

scraper:
  max_scrolls: 20
  scroll_delay_seconds: 2
```

### Scheduler (`scheduler.py`)
APScheduler runs as a persistent background process. Reads enabled targets from `scrape_targets` and runs the scraper engine against each on the configured cron schedule.

Runs as a `systemd` user service for automatic startup:
```bash
systemctl --user start twitter-scraper
systemctl --user stop twitter-scraper
systemctl --user status twitter-scraper
```

### CLI (`cli.py`) — built with `click`
```bash
# Trigger a full scrape run immediately
python cli.py run

# Scrape a single specific target
python cli.py run --target 3

# Add a new scrape target
python cli.py target add --type account --value elonmusk
python cli.py target add --type search --value "#python"

# List all targets
python cli.py target list

# Enable/disable a target
python cli.py target enable 3
python cli.py target disable 3

# View recent run logs
python cli.py logs --last 10
```

---

## Project Structure

```
Twitter/
├── .gitignore               # excludes config.yaml, logs/, __pycache__, .env
├── config.yaml              # schedule, DB credentials, scraper settings (git-ignored)
├── config.example.yaml      # safe template committed to git (no credentials)
├── cli.py                   # click CLI entry point
├── scheduler.py             # APScheduler background process
├── scraper/
│   ├── engine.py            # Playwright CDP connection + scroll + interception
│   └── targets.py           # per-target navigation logic (account vs search)
├── pipeline/
│   ├── parser.py            # raw Twitter JSON → normalized dicts
│   └── writer.py            # MySQL writes, deduplication, upsert logic
├── db/
│   ├── schema.sql           # table definitions
│   └── connection.py        # MySQL connection pool
├── logs/                    # structured log files (git-ignored)
├── docs/
│   └── superpowers/specs/   # this design doc
└── requirements.txt
```

## Version Control

The project is a local git repository pushed to GitHub. The `.gitignore` excludes:
- `config.yaml` — contains database credentials
- `logs/` — runtime log files
- `__pycache__/`, `*.pyc` — Python bytecode
- `.env` — any future secrets file

A `config.example.yaml` with placeholder values is committed to git so the structure is documented without exposing credentials.

---

## Dependencies

| Package | Purpose |
|---|---|
| `playwright` | Browser automation via CDP |
| `apscheduler` | Cron-style scheduling |
| `click` | CLI interface |
| `mysql-connector-python` | MySQL database driver |
| `pyyaml` | Config file parsing |
| `loguru` | Structured logging |

---

## Out of Scope

- Twitter API (official) integration
- Scraping DMs or notifications
- Web UI / dashboard
- Alerting / notifications on scrape results
- Proxy support or anti-detection measures
