"""LLM News Agent - Main agent orchestrator."""

import asyncio
from typing import Any

from src.filters import LLMFilter
from src.monitors import ArxivMonitor, NewsItem, XNitterMonitor, XiaohongshuMonitor
from src.notifiers import ConsoleNotifier
from src.utils import ItemCache, LLMProvider, Settings, get_logger

logger = get_logger("agent")


class LLMNewsAgent:
    """Main agent that orchestrates monitoring, filtering, and notification."""

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize cache
        self.cache = ItemCache()

        # Initialize monitors
        self.arxiv_monitor = ArxivMonitor(settings.get_arxiv_config())
        self.x_monitor = XNitterMonitor(settings.get_x_nitter_config())
        self.xhs_monitor = XiaohongshuMonitor(
            cookie=settings.xiaohongshu_cookie,
            config=settings.get_xiaohongshu_config(),
        )

        # Initialize filter with appropriate provider
        self.llm_filter = LLMFilter(
            provider=settings.llm_provider.value,
            anthropic_api_key=settings.anthropic_api_key,
            anthropic_base_url=settings.anthropic_base_url,
            openai_api_key=settings.openai_api_key,
            openai_base_url=settings.openai_base_url,
            config=settings.get_llm_filter_config(),
        )

        # Initialize notifier (console output)
        self.notifier = ConsoleNotifier()

        # Track running state
        self._running = False

    async def _process_items(self, items: list[NewsItem], source: str) -> None:
        """Process items through filter and send notifications."""
        if not items:
            return

        logger.info(f"{source}: Processing {len(items)} items...")

        # Save fetched items (before filtering)
        self.cache.save_fetched(items, source)

        # Filter items using LLM
        filtered = await self.llm_filter.filter_items(items)

        if not filtered:
            logger.info(f"{source}: No relevant items after filtering")
            return

        logger.info(f"{source}: {len(filtered)} relevant items to notify")

        # Save filtered results (after filtering)
        self.cache.save_filtered(filtered, source)
        self.cache.save_tsv(filtered, source)

        # Send notifications
        for item in filtered:
            success = await self.notifier.send(item)
            if success:
                logger.info(f"Notified: {item.summary[:50]}...")
            else:
                logger.warning(f"Failed to notify: {item.title[:50]}...")

            # Rate limit notifications
            await asyncio.sleep(1)

    async def _monitor_loop(
        self,
        name: str,
        fetch_func: Any,
        interval: int,
    ) -> None:
        """Generic monitoring loop."""
        while self._running:
            try:
                logger.info(f"🔍 Checking {name}...")
                items = await fetch_func()
                await self._process_items(items, name)

            except asyncio.CancelledError:
                logger.info(f"{name}: Monitor cancelled")
                break
            except Exception as e:
                logger.error(f"{name}: Monitor error - {e}")

            await asyncio.sleep(interval)

    async def monitor_arxiv(self) -> None:
        """arXiv monitoring loop."""
        await self._monitor_loop(
            "arXiv",
            self.arxiv_monitor.fetch_new_items,
            self.settings.get_interval("arxiv"),
        )

    async def monitor_x(self) -> None:
        """X.com monitoring loop."""
        await self._monitor_loop(
            "X.com",
            self.x_monitor.fetch_new_items,
            self.settings.get_interval("x_nitter"),
        )

    async def monitor_xiaohongshu(self) -> None:
        """Xiaohongshu monitoring loop."""
        if not self.settings.xiaohongshu_cookie:
            logger.info("小红书: Skipped (no cookie configured)")
            return

        await self._monitor_loop(
            "小红书",
            self.xhs_monitor.fetch_new_items,
            self.settings.get_interval("xiaohongshu"),
        )

    async def start(self) -> None:
        """Start the agent."""
        self._running = True

        provider_name = self.settings.llm_provider.value.upper()
        logger.info("🚀 LLM News Agent starting...")
        logger.info(f"🤖 LLM Provider: {provider_name}")
        logger.info(f"📊 Monitors: arXiv, X.com (Nitter), 小红书")
        logger.info(f"⏱️  Intervals: arXiv={self.settings.get_interval('arxiv')}s, "
                   f"X={self.settings.get_interval('x_nitter')}s, "
                   f"小红书={self.settings.get_interval('xiaohongshu')}s")

        # Send startup notification
        await self.notifier.send_message(
            f"✅ LLM News Agent 已启动\n\n"
            f"🤖 过滤模型: {provider_name}\n"
            f"📊 监控中..."
        )

        # Process any pending items from previous run
        await self._process_pending_cache()

        # Run all monitors concurrently
        await asyncio.gather(
            self.monitor_arxiv(),
            self.monitor_x(),
            self.monitor_xiaohongshu(),
            return_exceptions=True,
        )

    async def _process_pending_cache(self) -> None:
        """Process any items left in cache from previous run (not yet implemented for new cache)."""
        # New cache design saves fetched/filtered separately, no pending queue needed
        pass

    async def stop(self) -> None:
        """Stop the agent."""
        self._running = False
        logger.info("🛑 LLM News Agent stopping...")
        await self.notifier.send_message("🛑 LLM News Agent 已停止")
