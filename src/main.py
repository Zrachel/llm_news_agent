"""LLM News Agent - Entry point."""

import asyncio
import signal
import sys

from src.agent import LLMNewsAgent
from src.utils import get_settings, setup_logging


def main() -> None:
    """Main entry point."""

    # Setup logging
    logger = setup_logging("INFO")

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        logger.error("Please check your .env file and config/settings.yaml")
        sys.exit(1)

    # Create agent
    agent = LLMNewsAgent(settings)

    # Handle graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown_handler(sig: signal.Signals) -> None:
        logger.info(f"Received signal {sig.name}, shutting down...")
        loop.create_task(agent.stop())

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler, sig)

    try:
        loop.run_until_complete(agent.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
