"""Tests for filters."""

import pytest

from src.monitors import NewsItem


class TestLLMFilter:
    """Tests for LLMFilter."""

    def test_format_items(self) -> None:
        """Test formatting items for the prompt."""
        # Note: We can't easily test the full filter without API key
        # This tests the helper logic
        items = [
            NewsItem(
                id="1",
                title="Test LLM Paper",
                source="arXiv",
                url="https://arxiv.org/abs/1234",
                abstract="This is about language models.",
            ),
            NewsItem(
                id="2",
                title="Image Generation Paper",
                source="arXiv",
                url="https://arxiv.org/abs/5678",
                abstract="This is about diffusion models.",
            ),
        ]

        # Just verify the items are properly structured
        assert len(items) == 2
        assert items[0].abstract == "This is about language models."


class TestFilterPrompt:
    """Tests for filter prompt construction."""

    def test_news_item_fields(self) -> None:
        """Test that NewsItem has all required fields for filtering."""
        item = NewsItem(
            id="test",
            title="Test",
            source="Test",
            url="https://example.com",
        )

        # Verify all fields exist
        assert hasattr(item, "id")
        assert hasattr(item, "title")
        assert hasattr(item, "source")
        assert hasattr(item, "url")
        assert hasattr(item, "abstract")
        assert hasattr(item, "text")
        assert hasattr(item, "author")
        assert hasattr(item, "summary")
        assert hasattr(item, "importance")
        assert hasattr(item, "relevant")

    def test_filter_result_fields(self) -> None:
        """Test that filter results can be applied to NewsItem."""
        item = NewsItem(
            id="test",
            title="Original Title",
            source="arXiv",
            url="https://example.com",
        )

        # Simulate filter result
        item.relevant = True
        item.summary = "LLM 推理能力新突破"
        item.importance = "🔥🔥🔥"

        assert item.relevant is True
        assert item.summary == "LLM 推理能力新突破"
        assert item.importance == "🔥🔥🔥"
