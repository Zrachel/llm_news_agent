"""LLM News Agent - Xiaohongshu (Little Red Book) monitor."""

import asyncio
import json
import re
from datetime import datetime
from typing import Any

import httpx

from src.monitors.base import BaseMonitor, NewsItem
from src.utils.logging import get_logger

logger = get_logger("monitors.xiaohongshu")


class XiaohongshuMonitor(BaseMonitor):
    """Monitor for Xiaohongshu (Little Red Book) platform."""

    def __init__(self, cookie: str | None = None, config: dict[str, Any] | None = None):
        super().__init__("小红书")
        config = config or {}

        self.cookie = cookie
        self.enabled = config.get("enabled", False) and bool(cookie)

        self.keywords = config.get(
            "keywords",
            ["LLM", "大模型", "GPT", "Claude", "ChatGPT", "AI模型"],
        )

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/",
        }

        if cookie:
            self.headers["Cookie"] = cookie

    async def _search_notes(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search notes by keyword."""

        # Xiaohongshu web search API
        url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"

        params = {
            "keyword": keyword,
            "page": 1,
            "page_size": limit,
            "sort": "time_descending",
            "note_type": 0,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers)

                if resp.status_code == 403:
                    logger.warning("Xiaohongshu: Cookie expired or invalid")
                    return []

                if resp.status_code != 200:
                    logger.warning(f"Xiaohongshu: Request failed with {resp.status_code}")
                    return []

                data = resp.json()

                if not data.get("success"):
                    logger.warning(f"Xiaohongshu: API error - {data.get('msg', 'unknown')}")
                    return []

                notes = []
                for item in data.get("data", {}).get("items", []):
                    note_card = item.get("note_card", {})
                    notes.append({
                        "id": item.get("id"),
                        "title": note_card.get("display_title", ""),
                        "desc": note_card.get("desc", ""),
                        "user": note_card.get("user", {}).get("nickname", ""),
                        "likes": note_card.get("interact_info", {}).get("liked_count", 0),
                        "type": note_card.get("type", ""),
                    })

                return notes

            except httpx.TimeoutException:
                logger.warning("Xiaohongshu: Request timeout")
                return []
            except json.JSONDecodeError:
                logger.warning("Xiaohongshu: Invalid JSON response")
                return []
            except Exception as e:
                logger.warning(f"Xiaohongshu: Search failed - {e}")
                return []

    async def fetch_new_items(self) -> list[NewsItem]:
        """Fetch new notes from Xiaohongshu."""

        if not self.enabled:
            logger.debug("Xiaohongshu: Disabled or no cookie configured")
            return []

        new_items: list[NewsItem] = []

        for keyword in self.keywords:
            notes = await self._search_notes(keyword, limit=5)

            for note in notes:
                note_id = note.get("id")
                if not note_id or self.is_seen(note_id):
                    continue

                self.mark_seen(note_id)

                title = note.get("title", "").strip()
                desc = note.get("desc", "").strip()

                item = NewsItem(
                    id=note_id,
                    title=title or desc[:100],
                    source="小红书",
                    url=f"https://www.xiaohongshu.com/explore/{note_id}",
                    text=desc[:500],
                    author=note.get("user", ""),
                    extra={
                        "likes": note.get("likes", 0),
                        "type": note.get("type", ""),
                    },
                )
                new_items.append(item)

            # Rate limiting
            await asyncio.sleep(2)

        logger.info(f"小红书: Found {len(new_items)} new notes")
        return new_items
