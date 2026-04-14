import urllib.parse


def get_target_url(target: dict) -> str:
    if target["type"] == "account":
        username = target["value"].lstrip("@")
        return f"https://x.com/{username}"
    if target["type"] == "search":
        query = urllib.parse.quote(target["value"])
        return f"https://x.com/search?q={query}&src=typed_query&f=live"
    raise ValueError(f"Unknown target type: {target['type']}")
