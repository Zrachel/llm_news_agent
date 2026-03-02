"""LLM News Agent - Base notifier class."""

from abc import ABC, abstractmethod

from src.monitors.base import NewsItem


class BaseNotifier(ABC):
    """Base class for all notifiers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def send(self, item: NewsItem) -> bool:
        """Send a notification for a news item.

        Args:
            item: The news item to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def send_message(self, text: str) -> bool:
        """Send a plain text message.

        Args:
            text: The message text.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass
