"""LLM News Agent - Console notifier."""

from src.monitors.base import NewsItem
from src.notifiers.base import BaseNotifier
from src.utils.logging import get_logger

logger = get_logger("notifiers.console")


class ConsoleNotifier(BaseNotifier):
    """Output notifications to console/terminal."""

    def __init__(self):
        super().__init__("Console")

    def _format_message(self, item: NewsItem) -> str:
        """Format a news item for console output."""
        importance = item.importance or "🔥"
        summary = item.summary or item.title

        lines = [
            "=" * 60,
            f"{importance} {summary}",
            f"📍 来源: {item.source}",
        ]

        if item.author:
            lines.append(f"👤 作者: {item.author}")

        lines.append(f"🔗 {item.url}")
        lines.append("=" * 60)

        return "\n".join(lines)

    async def send(self, item: NewsItem) -> bool:
        """Print a news item to console."""
        message = self._format_message(item)
        print(message)
        return True

    async def send_message(self, text: str) -> bool:
        """Print a plain text message to console."""
        print(text)
        return True
