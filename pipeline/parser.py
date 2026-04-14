import json
from datetime import datetime

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


def parse_tweet(tweet_result: dict) -> dict | None:
    legacy = tweet_result.get("legacy", {})
    full_text = legacy.get("full_text", "")
    if not legacy or not full_text:
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
        if tweet_id == 0 or author_id == 0:
            return None
        created_at = datetime.strptime(legacy["created_at"], TWITTER_DATE_FORMAT)
    except (ValueError, KeyError):
        return None

    user = parse_user(user_legacy) if user_legacy else None

    return {
        "tweet": {
            "tweet_id": tweet_id,
            "author_id": author_id,
            "full_text": full_text,
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
        # NOTE: TimelinePinEntry is a real Twitter instruction type with a different shape
        # (single 'entry' key, not 'entries'). It is not handled here — pinned tweets
        # will not be collected.
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
