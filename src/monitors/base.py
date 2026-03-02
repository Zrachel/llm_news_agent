"""LLM News Agent - Base monitor class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NewsItem:
    """Represents a single news item from any source."""

    id: str
    title: str
    source: str
    url: str
    published: datetime | None = None
    abstract: str = ""
    text: str = ""
    author: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    # Filled by LLM filter
    summary: str = ""
    importance: str = "🔥"
    relevant: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published": self.published.isoformat() if self.published else None,
            "abstract": self.abstract,
            "text": self.text,
            "author": self.author,
            "summary": self.summary,
            "importance": self.importance,
            "relevant": self.relevant,
        }


class BaseMonitor(ABC):
    """Base class for all monitors."""

    def __init__(self, name: str):
        self.name = name
        self.seen_ids: set[str] = set()

    @abstractmethod
    async def fetch_new_items(self) -> list[NewsItem]:
        """Fetch new items from the source.

        Returns:
            List of new items not seen before.
        """
        pass

    def mark_seen(self, item_id: str) -> None:
        """Mark an item as seen."""
        self.seen_ids.add(item_id)

    def is_seen(self, item_id: str) -> bool:
        """Check if an item has been seen."""
        return item_id in self.seen_ids

    def clear_seen(self) -> None:
        """Clear all seen items (use with caution)."""
        self.seen_ids.clear()
