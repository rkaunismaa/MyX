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
