"""Tests for monitors."""

import pytest

from src.monitors import ArxivMonitor, NewsItem, XNitterMonitor


class TestNewsItem:
    """Tests for NewsItem dataclass."""

    def test_create_item(self) -> None:
        """Test creating a news item."""
        item = NewsItem(
            id="test-123",
            title="Test Paper",
            source="arXiv",
            url="https://arxiv.org/abs/1234.5678",
        )
        assert item.id == "test-123"
        assert item.title == "Test Paper"
        assert item.source == "arXiv"
        assert item.relevant is False
        assert item.importance == "🔥"

    def test_to_dict(self) -> None:
        """Test converting item to dict."""
        item = NewsItem(
            id="test-123",
            title="Test Paper",
            source="arXiv",
            url="https://arxiv.org/abs/1234.5678",
            author="John Doe",
        )
        d = item.to_dict()
        assert d["id"] == "test-123"
        assert d["author"] == "John Doe"
        assert d["published"] is None


class TestArxivMonitor:
    """Tests for ArxivMonitor."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        monitor = ArxivMonitor()
        assert monitor.name == "arXiv"
        assert monitor.max_results == 50
        assert "cs.CL" in monitor.categories

    def test_init_custom_config(self) -> None:
        """Test custom configuration."""
        config = {
            "max_results": 100,
            "categories": ["cs.AI"],
            "keywords": ["GPT"],
        }
        monitor = ArxivMonitor(config)
        assert monitor.max_results == 100
        assert monitor.categories == ["cs.AI"]
        assert monitor.keywords == ["GPT"]

    def test_build_query(self) -> None:
        """Test query building."""
        monitor = ArxivMonitor({
            "categories": ["cs.CL"],
            "keywords": ["LLM", "GPT"],
        })
        query = monitor._build_query()
        assert "cat:cs.CL" in query
        assert "LLM" in query
        assert "GPT" in query

    def test_seen_tracking(self) -> None:
        """Test seen ID tracking."""
        monitor = ArxivMonitor()
        assert not monitor.is_seen("test-id")
        monitor.mark_seen("test-id")
        assert monitor.is_seen("test-id")
        monitor.clear_seen()
        assert not monitor.is_seen("test-id")


class TestXNitterMonitor:
    """Tests for XNitterMonitor."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        monitor = XNitterMonitor()
        assert monitor.name == "X.com"
        assert len(monitor.instances) > 0
        assert len(monitor.accounts) > 0

    def test_init_custom_config(self) -> None:
        """Test custom configuration."""
        config = {
            "instances": ["nitter.example.com"],
            "accounts": ["TestAccount"],
        }
        monitor = XNitterMonitor(config)
        assert monitor.instances == ["nitter.example.com"]
        assert monitor.accounts == ["TestAccount"]


@pytest.mark.asyncio
async def test_arxiv_fetch_integration() -> None:
    """Integration test for arXiv fetching (requires network)."""
    monitor = ArxivMonitor({"max_results": 5})
    items = await monitor.fetch_new_items()

    # Should return some items (unless arXiv is down)
    # Note: This may fail if run repeatedly due to deduplication
    assert isinstance(items, list)

    if items:
        item = items[0]
        assert item.source == "arXiv"
        assert item.url.startswith("http")
        assert len(item.title) > 0
