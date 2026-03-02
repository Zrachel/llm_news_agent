# LLM News Agent

## Project Overview

A real-time monitoring agent that tracks LLM (Large Language Model) research progress from multiple sources and pushes relevant updates via Telegram.

### Monitored Sources
- **arXiv**: Academic papers on cs.CL, cs.LG categories
- **X.com**: Via Nitter RSS feeds from key AI accounts
- **Xiaohongshu**: Chinese social platform (optional, requires cookie)

### Tech Stack
- Python 3.11+
- asyncio for concurrent monitoring
- httpx for HTTP requests
- feedparser for RSS parsing
- arxiv library for arXiv API
- OpenAI API (or compatible) for LLM filtering

## Project Structure

```
llm-news-agent/
├── CLAUDE.md           # This file - project context for Claude
├── README.md           # User documentation
├── pyproject.toml      # Project dependencies
├── config/
│   └── settings.yaml   # Configuration file
├── src/
│   ├── __init__.py
│   ├── main.py         # Entry point
│   ├── agent.py        # Main agent orchestrator
│   ├── monitors/       # Data source monitors
│   │   ├── __init__.py
│   │   ├── base.py     # Base monitor class
│   │   ├── arxiv.py    # arXiv monitor
│   │   ├── x_nitter.py # X.com via Nitter RSS
│   │   └── xiaohongshu.py  # Xiaohongshu monitor
│   ├── filters/        # Content filtering
│   │   ├── __init__.py
│   │   └── llm_filter.py   # LLM-based relevance filter
│   ├── notifiers/      # Notification channels
│   │   ├── __init__.py
│   │   ├── base.py     # Base notifier class
│   │   └── telegram.py # Telegram notifier
│   └── utils/
│       ├── __init__.py
│       ├── config.py   # Configuration loader
│       └── logging.py  # Logging setup
└── tests/
    ├── __init__.py
    ├── test_monitors.py
    └── test_filters.py
```

## Key Design Decisions

1. **Async-first**: All monitors run concurrently using asyncio
2. **Deduplication**: Each monitor maintains a seen_ids set to avoid duplicates
3. **Graceful degradation**: If one source fails, others continue working
4. **Rate limiting**: Built-in delays between requests to avoid blocking
5. **LLM filtering**: Uses GPT-4o-mini/GLM-4-flash to filter relevant content

## Configuration

Configuration is loaded from:
1. `config/settings.yaml` (default)
2. Environment variables (override)

Required environment variables:
- `OPENAI_API_KEY`: For LLM filtering
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_CHAT_ID`: Target chat ID

Optional:
- `OPENAI_BASE_URL`: Custom API endpoint
- `XIAOHONGSHU_COOKIE`: For Xiaohongshu monitoring

## Development Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the agent
python -m src.main

# Run tests
pytest tests/ -v

# Type checking
mypy src/

# Linting
ruff check src/
```

## Code Style Guidelines

- Use type hints for all function signatures
- Use dataclasses or Pydantic models for data structures
- Async functions should be prefixed with `async_` or be obviously async
- All monitors inherit from `BaseMonitor`
- All notifiers inherit from `BaseNotifier`
- Use logging instead of print statements

## Important Notes

### Nitter Instances
Nitter instances frequently go down. The code maintains a list of fallback instances.
If all fail, X.com monitoring will be skipped gracefully.

### Xiaohongshu
- Requires valid browser cookie
- Cookie expires periodically, needs manual refresh
- API endpoints may change, check if 403 errors occur

### Rate Limits
- arXiv: 1 request per 3 seconds recommended
- Nitter: 1 request per second per instance
- Xiaohongshu: 2 seconds between searches

## Testing

Run integration tests with real APIs:
```bash
pytest tests/ -v --integration
```

Mock tests (no API calls):
```bash
pytest tests/ -v
```
