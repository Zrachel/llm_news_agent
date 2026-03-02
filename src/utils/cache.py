"""LLM News Agent - Cache utilities for storing fetched items."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.monitors.base import NewsItem
from src.utils.logging import get_logger

logger = get_logger("utils.cache")


class ItemCache:
    """Cache for storing fetched news items."""

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        logger.info(f"📦 Cache directory: {self.cache_dir.absolute()}")

    def _item_to_dict(self, item: NewsItem) -> dict[str, Any]:
        """Convert NewsItem to serializable dict."""
        return {
            "id": item.id,
            "title": item.title,
            "source": item.source,
            "url": item.url,
            "published": item.published.isoformat() if item.published else None,
            "abstract": item.abstract,
            "text": item.text,
            "author": item.author,
            "extra": item.extra,
            "summary": item.summary,
            "importance": item.importance,
            "relevant": item.relevant,
        }

    def _dict_to_item(self, data: dict[str, Any]) -> NewsItem:
        """Convert dict back to NewsItem."""
        published = None
        if data.get("published"):
            try:
                published = datetime.fromisoformat(data["published"])
            except (ValueError, TypeError):
                pass

        return NewsItem(
            id=data["id"],
            title=data["title"],
            source=data["source"],
            url=data["url"],
            published=published,
            abstract=data.get("abstract", ""),
            text=data.get("text", ""),
            author=data.get("author", ""),
            extra=data.get("extra", {}),
            summary=data.get("summary", ""),
            importance=data.get("importance", "🔥"),
            relevant=data.get("relevant", False),
        )

    def save_fetched(self, items: list[NewsItem], source: str) -> None:
        """Save raw fetched items (before filtering)."""
        if not items:
            return

        today = datetime.now().strftime("%Y%m%d")
        fetched_file = self.cache_dir / f"fetched_{today}.json"

        # Load existing
        existing = []
        if fetched_file.exists():
            try:
                with open(fetched_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Add new items (avoid duplicates)
        existing_ids = {item.get("id") for item in existing}
        timestamp = datetime.now().isoformat()

        for item in items:
            if item.id in existing_ids:
                continue
            # For content, prefer abstract > text > title (for X.com, title IS the content)
            content = item.abstract or item.text or ""
            record = {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "author": item.author,
                "affiliations": item.extra.get("affiliations", []),
                "source": item.source,
                "abstract": content,
                "published": item.published.isoformat() if item.published else None,
                "_fetched_at": timestamp,
                "_source_name": source,
            }
            existing.append(record)

        with open(fetched_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 Saved {len(items)} fetched items to {fetched_file.name}")

    def save_filtered(self, items: list[NewsItem], source: str) -> None:
        """Save filtered relevant items (after LLM filtering)."""
        if not items:
            return

        today = datetime.now().strftime("%Y%m%d")
        filtered_file = self.cache_dir / f"filtered_{today}.json"

        # Load existing
        existing = []
        if filtered_file.exists():
            try:
                with open(filtered_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Add new items (avoid duplicates)
        existing_ids = {item.get("id") for item in existing}
        timestamp = datetime.now().isoformat()

        for item in items:
            if item.id in existing_ids:
                continue
            # For content, prefer abstract > text (for X.com, text contains the tweet)
            content = item.abstract or item.text or ""
            record = {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "author": item.author,
                "affiliations": item.extra.get("affiliations", []),
                "source": item.source,
                "summary": item.summary,
                "importance": item.importance,
                "abstract": content,
                "published": item.published.isoformat() if item.published else None,
                "_filtered_at": timestamp,
                "_source_name": source,
            }
            existing.append(record)

        with open(filtered_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.info(f"📚 Saved {len(items)} filtered items to {filtered_file.name}")

    def get_fetched_today(self, source: str | None = None) -> list[NewsItem]:
        """Get today's fetched items, optionally filtered by source."""
        today = datetime.now().strftime("%Y%m%d")
        fetched_file = self.cache_dir / f"fetched_{today}.json"

        if not fetched_file.exists():
            return []

        try:
            with open(fetched_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

        if source:
            items = [i for i in items if i.get("_source_name") == source]

        return [self._dict_to_item(i) for i in items]

    def get_filtered_today(self) -> list[dict[str, Any]]:
        """Get today's filtered items."""
        today = datetime.now().strftime("%Y%m%d")
        filtered_file = self.cache_dir / f"filtered_{today}.json"

        if not filtered_file.exists():
            return []

        try:
            with open(filtered_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_tsv(self, items: list[NewsItem], source: str) -> None:
        """Save filtered items to TSV file (affiliations, summary, url)."""
        if not items:
            return

        today = datetime.now().strftime("%Y%m%d")
        tsv_file = self.cache_dir / f"summary_{today}.tsv"

        # Load existing lines to avoid duplicates
        existing_urls = set()
        if tsv_file.exists():
            try:
                with open(tsv_file, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split("\t")
                        if len(parts) >= 3:
                            existing_urls.add(parts[2])
            except IOError:
                pass

        # Append new items
        with open(tsv_file, "a", encoding="utf-8") as f:
            for item in items:
                if item.url in existing_urls:
                    continue

                # Format affiliations as comma-separated string
                affiliations = item.extra.get("affiliations", [])
                aff_str = ", ".join(affiliations) if affiliations else ""

                # Clean summary (remove newlines/tabs)
                summary = item.summary.replace("\t", " ").replace("\n", " ").strip()

                # Write TSV line: affiliations \t summary \t url
                f.write(f"{aff_str}\t{summary}\t{item.url}\n")

        logger.info(f"📋 Saved {len(items)} items to {tsv_file.name}")
