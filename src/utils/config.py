"""LLM News Agent - Configuration utilities."""

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Application settings loaded from environment and config file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Provider selection
    llm_provider: LLMProvider = Field(
        default=LLMProvider.ANTHROPIC,
        description="LLM provider to use (openai or anthropic)",
    )

    # Anthropic API (recommended)
    anthropic_api_key: str | None = Field(None, description="Anthropic API key")
    anthropic_base_url: str | None = Field(None, description="Custom Anthropic API base URL")

    # OpenAI API (alternative)
    openai_api_key: str | None = Field(None, description="OpenAI API key")
    openai_base_url: str | None = Field(None, description="Custom OpenAI API base URL")

    # Telegram settings (optional - for Telegram notifier)
    telegram_bot_token: str | None = Field(None, description="Telegram bot token")
    telegram_chat_id: str | None = Field(None, description="Telegram chat ID to send messages")

    # Optional: Xiaohongshu
    xiaohongshu_cookie: str | None = Field(None, description="Xiaohongshu browser cookie")

    # Config file path
    config_path: Path = Field(
        default=Path("config/settings.yaml"),
        description="Path to YAML config file",
    )

    _yaml_config: dict[str, Any] | None = None

    def model_post_init(self, __context: Any) -> None:
        """Validate that at least one LLM API key is provided."""
        if self.llm_provider == LLMProvider.ANTHROPIC and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")

    @property
    def yaml_config(self) -> dict[str, Any]:
        """Load and cache YAML configuration."""
        if self._yaml_config is None:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    self._yaml_config = yaml.safe_load(f) or {}
            else:
                self._yaml_config = {}
        return self._yaml_config

    def get_interval(self, source: str) -> int:
        """Get monitoring interval for a source."""
        defaults = {"arxiv": 3600, "x_nitter": 600, "xiaohongshu": 1800}
        intervals = self.yaml_config.get("intervals", {})
        return intervals.get(source, defaults.get(source, 3600))

    def get_arxiv_config(self) -> dict[str, Any]:
        """Get arXiv configuration."""
        return self.yaml_config.get("arxiv", {})

    def get_x_nitter_config(self) -> dict[str, Any]:
        """Get X.com Nitter configuration."""
        return self.yaml_config.get("x_nitter", {})

    def get_xiaohongshu_config(self) -> dict[str, Any]:
        """Get Xiaohongshu configuration."""
        return self.yaml_config.get("xiaohongshu", {})

    def get_llm_filter_config(self) -> dict[str, Any]:
        """Get LLM filter configuration."""
        return self.yaml_config.get("llm_filter", {})


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
