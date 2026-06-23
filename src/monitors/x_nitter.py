"""LLM News Agent - X.com monitor via Nitter RSS."""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any

import feedparser
import httpx

from src.monitors.base import BaseMonitor, NewsItem
from src.utils.logging import get_logger

logger = get_logger("monitors.x_nitter")


class XNitterMonitor(BaseMonitor):
    """Monitor for X.com (Twitter) via Nitter RSS feeds."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("X.com")
        config = config or {}

        self.instances = config.get(
            "instances",
            [
                "nitter.privacydev.net",
                "nitter.poast.org",
                "nitter.woodland.cafe",
                "nitter.1d4.us",
            ],
        )

        self.accounts = config.get(
            "accounts",
            [
                "OpenAI",
                "AnthropicAI",
                "GoogleDeepMind",
                "MetaAI",
                "_akhaliq",
            ],
        )

        self._working_instance: str | None = None
        self._instance_check_time: float = 0

    async def _get_working_instance(self) -> str | None:
        """Find a working Nitter instance."""

        # Cache instance for 10 minutes
        import time

        if (
            self._working_instance
            and time.time() - self._instance_check_time < 600
        ):
            return self._working_instance

        async with httpx.AsyncClient(timeout=10) as client:
            for instance in self.instances:
                try:
                    resp = await client.get(f"https://{instance}")
                    if resp.status_code == 200:
                        self._working_instance = instance
                        self._instance_check_time = time.time()
                        logger.info(f"Using Nitter instance: {instance}")
                        return instance
                except Exception as e:
                    logger.debug(f"Instance {instance} failed: {e}")
                    continue

        logger.warning("No working Nitter instance found")
        return None

    async def fetch_new_items(self) -> list[NewsItem]:
        """Fetch new tweets from monitored accounts."""

        instance = await self._get_working_instance()
        if not instance:
            logger.warning("X.com monitoring skipped - no working Nitter instance")
            return []

        new_items: list[NewsItem] = []
        loop = asyncio.get_event_loop()

        for account in self.accounts:
            try:
                rss_url = f"https://{instance}/{account}/rss"

                # Run feedparser in thread pool with timeout
                try:
                    feed = await asyncio.wait_for(
                        loop.run_in_executor(None, feedparser.parse, rss_url),
                        timeout=30  # 30 second timeout per account
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching @{account}")
                    continue

                for entry in feed.entries[:10]:
                    # Generate unique ID from link
                    tweet_id = hashlib.md5(entry.link.encode()).hexdigest()

                    if self.is_seen(tweet_id):
                        continue

                    self.mark_seen(tweet_id)

                    # Clean up text
                    raw_text = re.sub(r"<[^>]+>", "", entry.title)  # Remove HTML
                    clean_text = re.sub(r"http\S+", "", raw_text).strip()  # Remove URLs

                    # Parse published date
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except Exception:
                            pass

                    # Convert Nitter URL back to X.com
                    url = entry.link.replace(instance, "x.com")
                    if "nitter" in url:
                        url = re.sub(r"https?://[^/]+/", "https://x.com/", url)

                    item = NewsItem(
                        id=tweet_id,
                        title=clean_text[:200] if clean_text else raw_text[:200],
                        source="X.com",
                        url=url,
                        published=published,
                        text=raw_text,  # Keep full text with URLs
                        author=account,
                    )
                    new_items.append(item)

                # Rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Failed to fetch @{account}: {e}")
                continue

        logger.info(f"X.com: Found {len(new_items)} new tweets")
        return new_items
