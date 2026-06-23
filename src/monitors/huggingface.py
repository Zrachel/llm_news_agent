"""LLM News Agent - HuggingFace Datasets monitor."""

import asyncio
from datetime import datetime
from typing import Any

import httpx

from src.monitors.base import BaseMonitor, NewsItem
from src.utils.logging import get_logger

logger = get_logger("monitors.huggingface")


class HuggingFaceMonitor(BaseMonitor):
    """Monitor for new HuggingFace datasets."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("HuggingFace")
        config = config or {}

        self.max_results = config.get("max_results", 50)
        # Keywords to filter LLM-related datasets
        self.keywords = config.get(
            "keywords",
            [
                "llm", "language model", "instruction", "chat", "sft",
                "rlhf", "dpo", "preference", "reasoning", "cot",
                "code", "math", "benchmark", "evaluation", "finetune",
                "pretrain", "alignment", "gpt", "llama", "qwen",
                "mistral", "gemma", "phi", "deepseek",
            ],
        )

    async def fetch_new_items(self) -> list[NewsItem]:
        """Fetch new datasets from HuggingFace."""
        new_items: list[NewsItem] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch recently updated datasets
                resp = await client.get(
                    "https://huggingface.co/api/datasets",
                    params={
                        "sort": "lastModified",
                        "direction": "-1",
                        "limit": self.max_results,
                    },
                )

                if resp.status_code != 200:
                    logger.warning(f"HuggingFace API returned {resp.status_code}")
                    return []

                datasets = resp.json()

                for ds in datasets:
                    dataset_id = ds.get("id", "")

                    if self.is_seen(dataset_id):
                        continue

                    # Check if dataset is LLM-related
                    if not self._is_relevant(ds):
                        self.mark_seen(dataset_id)
                        continue

                    self.mark_seen(dataset_id)

                    # Parse last modified date
                    published = None
                    last_modified = ds.get("lastModified")
                    if last_modified:
                        try:
                            published = datetime.fromisoformat(
                                last_modified.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    # Get dataset info
                    author = ds.get("author", "")
                    downloads = ds.get("downloads", 0)
                    likes = ds.get("likes", 0)
                    tags = ds.get("tags", [])

                    # Format description
                    description = f"Downloads: {downloads:,} | Likes: {likes}"
                    if tags:
                        description += f" | Tags: {', '.join(tags[:5])}"

                    item = NewsItem(
                        id=dataset_id,
                        title=dataset_id,
                        source="HuggingFace",
                        url=f"https://huggingface.co/datasets/{dataset_id}",
                        published=published,
                        abstract=description,
                        author=author,
                        extra={
                            "downloads": downloads,
                            "likes": likes,
                            "tags": tags,
                        },
                    )
                    new_items.append(item)

                logger.info(f"HuggingFace: Found {len(new_items)} new datasets")

        except asyncio.TimeoutError:
            logger.warning("HuggingFace API request timed out")
        except Exception as e:
            logger.error(f"HuggingFace monitor error: {e}")

        return new_items

    def _is_relevant(self, dataset: dict) -> bool:
        """Check if dataset is relevant to LLM research."""
        dataset_id = dataset.get("id", "").lower()
        tags = [t.lower() for t in dataset.get("tags", [])]

        # Check dataset ID and tags for keywords
        text_to_check = dataset_id + " " + " ".join(tags)

        return any(kw in text_to_check for kw in self.keywords)
