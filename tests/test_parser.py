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
