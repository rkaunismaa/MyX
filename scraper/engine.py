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
