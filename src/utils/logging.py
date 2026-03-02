"""LLM News Agent - Logging utilities."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Set up application logging with file output."""

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Create log file with timestamp
    log_file = log_path / f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Create file handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("arxiv").setLevel(logging.WARNING)

    # Log startup info
    logger = logging.getLogger("llm-news-agent")
    logger.info(f"📝 Log file: {log_file.absolute()}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(f"llm-news-agent.{name}")
