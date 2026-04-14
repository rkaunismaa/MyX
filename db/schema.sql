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
  scraped_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tweets (
  tweet_id        BIGINT PRIMARY KEY,
  author_id       BIGINT       NOT NULL,
  full_text       TEXT         CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  lang            VARCHAR(20)  NOT NULL DEFAULT '',
  created_at      DATETIME     NOT NULL,
  retweet_count   BIGINT       NOT NULL DEFAULT 0,
  like_count      BIGINT       NOT NULL DEFAULT 0,
  reply_count     BIGINT       NOT NULL DEFAULT 0,
  quote_count     BIGINT       NOT NULL DEFAULT 0,
  is_retweet      BOOLEAN      NOT NULL DEFAULT FALSE,
  is_quote        BOOLEAN      NOT NULL DEFAULT FALSE,
  raw_json        JSON,
  scraped_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (author_id) REFERENCES users(user_id),
  INDEX idx_tweets_author_id (author_id)
);

CREATE TABLE IF NOT EXISTS scrape_targets (
  target_id   INT AUTO_INCREMENT PRIMARY KEY,
  type        ENUM('account', 'search') NOT NULL,
  value       VARCHAR(255) NOT NULL,
  enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_scrape_targets_type_value (type, value)
);

CREATE TABLE IF NOT EXISTS tweet_targets (
  tweet_id  BIGINT NOT NULL,
  target_id INT    NOT NULL,
  PRIMARY KEY (tweet_id, target_id),
  FOREIGN KEY (tweet_id)  REFERENCES tweets(tweet_id),
  FOREIGN KEY (target_id) REFERENCES scrape_targets(target_id),
  INDEX idx_tweet_targets_target_id (target_id)
);

CREATE TABLE IF NOT EXISTS run_logs (
  run_id           INT AUTO_INCREMENT PRIMARY KEY,
  target_id        INT          NOT NULL,
  started_at       DATETIME     NOT NULL,
  finished_at      DATETIME     NULL,
  tweets_collected INT          NOT NULL DEFAULT 0,
  status           ENUM('success', 'error') NOT NULL,
  error_message    TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  FOREIGN KEY (target_id) REFERENCES scrape_targets(target_id),
  INDEX idx_run_logs_target_id (target_id)
);
