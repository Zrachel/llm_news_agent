"""LLM News Agent - Telegram notifier."""

import httpx

from src.monitors.base import NewsItem
from src.notifiers.base import BaseNotifier
from src.utils.logging import get_logger

logger = get_logger("notifiers.telegram")


class TelegramNotifier(BaseNotifier):
    """Send notifications via Telegram bot."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        parse_mode: str = "Markdown",
        disable_preview: bool = False,
    ):
        super().__init__("Telegram")
        self.token = token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.disable_preview = disable_preview
        self.api_base = f"https://api.telegram.org/bot{token}"

    def _format_message(self, item: NewsItem) -> str:
        """Format a news item as Telegram message."""

        importance = item.importance or "🔥"
        summary = item.summary or item.title

        # Escape Markdown special characters in summary
        summary_escaped = summary.replace("*", "\\*").replace("_", "\\_")

        lines = [
            f"{importance} *{summary_escaped}*",
            "",
            f"📍 来源: {item.source}",
        ]

        if item.author:
            lines.append(f"👤 作者: {item.author}")

        lines.append(f"🔗 {item.url}")

        return "\n".join(lines)

    async def send(self, item: NewsItem) -> bool:
        """Send a news item notification."""
        message = self._format_message(item)
        return await self.send_message(message)

    async def send_message(self, text: str) -> bool:
        """Send a plain text message."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": self.parse_mode,
                        "disable_web_page_preview": self.disable_preview,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        logger.debug(f"Telegram: Message sent successfully")
                        return True
                    else:
                        logger.warning(f"Telegram API error: {data.get('description')}")
                        return False
                else:
                    logger.warning(f"Telegram: HTTP {resp.status_code}")
                    return False

            except httpx.TimeoutException:
                logger.warning("Telegram: Request timeout")
                return False
            except Exception as e:
                logger.error(f"Telegram: Send failed - {e}")
                return False
