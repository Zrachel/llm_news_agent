"""LLM News Agent - LLM-based content filter with multi-provider support."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import anthropic
from openai import OpenAI

from src.monitors.base import NewsItem
from src.utils.logging import get_logger

logger = get_logger("filters.llm")

FILTER_PROMPT = """你是一个 LLM 技术研究追踪助手。请分析以下信息：

## 任务
1. 只保留与「纯文本 LLM 技术研究」直接相关的内容
2. 为相关内容生成一句话中文摘要（30字以内）
3. 评估重要程度

## 保留的内容（纯技术向）：
- 新模型发布（GPT、Claude、Gemini、Llama、GLM、DeepSeek、Qwen 等）的技术细节
- 预训练/后训练/Mid-training 技术
- RLHF、DPO 等对齐技术
- 推理能力提升（reasoning、chain-of-thought、test-time compute）
- 架构创新（attention、MoE、长上下文、稀疏注意力、KV cache）
- Agent 框架、Tool Use、代码生成的技术实现
- Scaling Law、训练效率、推理优化
- 数据工程、tokenization
- 开源模型、benchmark、评测

## 必须排除的内容：
- 多模态、视觉、语音、图像生成、视频、具身智能、机器人
- 公司政策、合作协议、安全政策声明（如 RSP、负责任扩展政策）
- 人事变动、招聘、离职、跳槽八卦
- 融资、估值、商业合作新闻
- 生物、医疗、化学、物理等非 LLM 核心的应用场景
- 法律、监管、政府政策
- 产品发布但无技术细节的营销内容

## 待分析内容：
{content}

## 输出格式（JSON 数组）：
[
  {{
    "index": 0,
    "relevant": true,
    "importance": "🔥🔥🔥",
    "summary": "一句话中文摘要"
  }}
]

重要程度说明：
- 🔥🔥🔥 = 重大技术突破/新模型发布
- 🔥🔥 = 值得关注的技术研究
- 🔥 = 一般性技术更新

只输出 JSON 数组，不要其他内容。"""


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Send prompt and get completion."""
        pass


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "auto",
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ):
        if base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, prompt: str) -> str:
        """Send prompt and get completion."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from response
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""


class OpenAIClient(BaseLLMClient):
    """OpenAI client."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(self, prompt: str) -> str:
        """Send prompt and get completion."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""


class LLMFilter:
    """Filter and summarize news items using LLM."""

    def __init__(
        self,
        provider: str = "anthropic",
        anthropic_api_key: str | None = None,
        anthropic_base_url: str | None = None,
        openai_api_key: str | None = None,
        openai_base_url: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        config = config or {}

        # Get model settings from config
        temperature = config.get("temperature", 0.2)
        max_tokens = config.get("max_tokens", 4096)  # Increased for large responses

        if provider == "anthropic":
            if not anthropic_api_key:
                raise ValueError("anthropic_api_key is required for Anthropic provider")

            # Default to auto, can be overridden in config
            model = config.get("anthropic_model", "auto")

            self.client: BaseLLMClient = AnthropicClient(
                api_key=anthropic_api_key,
                base_url=anthropic_base_url,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info(f"Using Anthropic provider with model: {model}")

        elif provider == "openai":
            if not openai_api_key:
                raise ValueError("openai_api_key is required for OpenAI provider")

            model = config.get("model") or config.get("openai_model", "gpt-4o-mini")

            self.client = OpenAIClient(
                api_key=openai_api_key,
                base_url=openai_base_url,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info(f"Using OpenAI provider with model: {model}")

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _format_items(self, items: list[NewsItem]) -> str:
        """Format items for the prompt."""
        lines = []
        for i, item in enumerate(items):
            line = f"[{i}] [{item.source}] {item.title}"
            if item.author:
                line += f" (@{item.author})"
            lines.append(line)

            # Add abstract/text if available
            content = item.abstract or item.text
            if content:
                lines.append(f"    内容: {content[:400]}")

            lines.append(f"    链接: {item.url}")
            lines.append("")

        return "\n".join(lines)

    async def filter_items(self, items: list[NewsItem]) -> list[NewsItem]:
        """Filter and summarize items using LLM.

        Args:
            items: List of news items to filter.

        Returns:
            List of relevant items with summary and importance filled.
        """
        if not items:
            return []

        # Process in batches to avoid LLM output truncation
        BATCH_SIZE = 40
        all_filtered: list[NewsItem] = []

        for batch_start in range(0, len(items), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(items))
            batch_items = items[batch_start:batch_end]

            logger.debug(f"Processing batch {batch_start}-{batch_end} of {len(items)} items")

            batch_filtered = await self._filter_batch(batch_items, batch_start)
            all_filtered.extend(batch_filtered)

        logger.info(f"LLM Filter: {len(all_filtered)}/{len(items)} items relevant")
        return all_filtered

    async def _filter_batch(self, items: list[NewsItem], index_offset: int = 0) -> list[NewsItem]:
        """Filter a single batch of items.

        Args:
            items: Batch of news items to filter.
            index_offset: Offset to add to indices for logging purposes.

        Returns:
            List of relevant items from this batch.
        """
        if not items:
            return []

        content = self._format_items(items)
        prompt = FILTER_PROMPT.format(content=content)

        try:
            result_text = self.client.complete(prompt)

            # Debug: log raw response
            logger.debug(f"LLM raw response length: {len(result_text)} chars")

            # Remove markdown code block wrappers if present
            result_text = result_text.strip()
            if "```" in result_text:
                # Remove ```json ... ``` or ``` ... ``` blocks
                result_text = re.sub(r"^```(?:json)?\s*", "", result_text).strip()
                result_text = re.sub(r"\s*```$", "", result_text).strip()

            # Try to parse the JSON directly first
            try:
                results = json.loads(result_text)
            except json.JSONDecodeError as e1:
                logger.debug(f"Direct JSON parse failed: {e1}")

                # Try to extract JSON array from response (may be truncated)
                # First try complete array
                json_match = re.search(r"\[[\s\S]*\]", result_text)
                if json_match:
                    try:
                        results = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        json_match = None

                if not json_match:
                    # JSON might be truncated (no closing ]), try to fix it
                    if result_text.startswith("["):
                        # Find last complete object (ends with })
                        last_brace = result_text.rfind("}")
                        if last_brace > 0:
                            fixed_json = result_text[:last_brace + 1] + "\n]"
                            try:
                                results = json.loads(fixed_json)
                                logger.info(f"Parsed truncated JSON with {len(results)} items")
                            except json.JSONDecodeError as e2:
                                logger.warning(f"Failed to parse truncated JSON: {e2}. First 300 chars: {result_text[:300]}...")
                                return []
                        else:
                            logger.warning(f"Cannot fix truncated JSON. First 300 chars: {result_text[:300]}...")
                            return []
                    else:
                        logger.warning(f"LLM response is not a JSON array. First 300 chars: {result_text[:300]}...")
                        return []

            # Merge results back to items
            filtered: list[NewsItem] = []
            for r in results:
                if not r.get("relevant", False):
                    continue

                idx = r.get("index", -1)
                if idx < 0 or idx >= len(items):
                    continue

                item = items[idx]
                item.relevant = True
                item.summary = r.get("summary", item.title)
                item.importance = r.get("importance", "🔥")
                filtered.append(item)

            return filtered

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []
        except Exception as e:
            logger.error(f"LLM filter error: {e}")
            return []
