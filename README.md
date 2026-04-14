# MyX — X/Twitter Scraper

A local X (Twitter) scraper that uses Playwright + Brave CDP to collect tweets from specific accounts and search queries into a MySQL database. Runs on a configurable cron schedule and provides a CLI for manual control.

## How It Works

1. Brave Browser is launched with remote debugging enabled (`--remote-debugging-port=9222`).
2. The scraper connects to Brave via the Chrome DevTools Protocol (CDP) and intercepts X's internal GraphQL API responses as it navigates to each target.
3. Tweets are parsed and upserted into MySQL — users, tweets, and target associations are stored in normalized tables.
4. A background scheduler (APScheduler) fires the scrape on a cron schedule. A Click CLI lets you trigger runs and manage targets manually.

## Requirements

- Python 3.11+
- Brave Browser
- MySQL 8.x (running locally)
- A valid X (Twitter) session open in Brave

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Create the database

```bash
mysql -u root -p < db/schema.sql
```

This creates both `twitter_scraper` (production) and `twitter_scraper_test` (tests) databases.

### 3. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

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
  password: ""

scraper:
  max_scrolls: 20        # max scroll iterations per target
  scroll_delay_seconds: 2
```

> `config.yaml` is gitignored. Never commit it — it contains your database password.

### 4. Launch Brave with debugging enabled

```bash
./launch-brave.sh
```

Log into X (x.com) in the Brave window that opens. Keep it running while the scraper operates.

## CLI Usage

Activate the virtual environment first:

```bash
source .venv/bin/activate
```

### Trigger a scrape

```bash
# Run all enabled targets
python cli.py run

# Run a single target by ID
python cli.py run --target 3
```

### Manage targets

```bash
# Add a user account target
python cli.py target add --type account --value elonmusk

# Add a search query target
python cli.py target add --type search --value "python machine learning"

# List all targets
python cli.py target list

# Enable / disable a target
python cli.py target enable 2
python cli.py target disable 2
```

### View run logs

```bash
# Show last 10 runs (default)
python cli.py logs

# Show last 50 runs
python cli.py logs --last 50
```

## Scheduler

The scheduler runs as a systemd user service and fires scrape jobs on the cron schedule defined in `config.yaml`.

### Start / stop the service

```bash
# Enable and start (survives reboots)
systemctl --user enable --now twitter-scraper.service

# Check status and logs
systemctl --user status twitter-scraper.service
journalctl --user -u twitter-scraper.service -f

# Stop
systemctl --user stop twitter-scraper.service
```

### Run the scheduler manually (foreground)

```bash
python scheduler.py
```

## Project Structure

```
.
├── cli.py                   # Click CLI entry point
├── scheduler.py             # APScheduler background process
├── runner.py                # Shared scrape loop (CLI + scheduler)
├── config.py                # Config loader
├── config.yaml              # Local config (gitignored)
├── config.example.yaml      # Safe template to commit
├── launch-brave.sh          # Launch Brave with CDP debugging
├── twitter-scraper.service  # systemd user service unit
├── requirements.txt
├── db/
│   ├── schema.sql           # MySQL DDL (5 tables)
│   └── connection.py        # DB connection factory + target queries
├── pipeline/
│   ├── parser.py            # Parse X GraphQL JSON → normalized dicts
│   └── writer.py            # Upsert users/tweets/links, write run logs
├── scraper/
│   ├── engine.py            # Playwright CDP engine
│   └── targets.py           # Build x.com URLs from target type/value
└── tests/
    ├── conftest.py
    ├── test_connection.py
    ├── test_parser.py
    └── test_writer.py
```

## Database Schema

| Table | Purpose |
|---|---|
| `users` | X user profiles (upserted on each scrape) |
| `tweets` | Individual tweets (INSERT IGNORE — never overwritten) |
| `scrape_targets` | Accounts and search queries to scrape |
| `tweet_targets` | Many-to-many: which tweets came from which target |
| `run_logs` | Per-run history with tweet count and status |

## Running Tests

```bash
pytest
```

Tests run against the `twitter_scraper_test` database. All tables are truncated between tests.

## Notes

- The scraper intercepts X's internal GraphQL API responses — it does not use any official API.
- Brave must be running with `--remote-debugging-port=9222` and logged into x.com for scrapes to work.
- MySQL availability is not guaranteed at scheduler startup. If MySQL is unavailable, the job will fail and the service will restart after 30 seconds (`Restart=on-failure`).
- `raw_json` is stored on each tweet for reprocessing if the parser is updated.
