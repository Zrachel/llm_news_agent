"""LLM News Agent - Entry point."""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path


# Load environment variables from ~/.baidu-cc/user.json BEFORE importing anything
def load_baidu_cc_env() -> None:
    """Load environment variables from ~/.baidu-cc/user.json."""
    user_json_path = Path.home() / ".baidu-cc" / "user.json"
    if not user_json_path.exists():
        return

    try:
        with open(user_json_path) as f:
            data = json.load(f)
            env_vars = data.get("env", {})
            for key, value in env_vars.items():
                os.environ[key] = value
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to load ~/.baidu-cc/user.json: {e}", file=sys.stderr)


# Load env vars BEFORE any imports that use them
load_baidu_cc_env()

# Now import modules that depend on environment variables
from src.agent import LLMNewsAgent  # noqa: E402
from src.utils import get_settings, setup_logging  # noqa: E402


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
