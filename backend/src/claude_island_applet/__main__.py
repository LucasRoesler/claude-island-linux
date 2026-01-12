"""Entry point for Claude Island applet."""

import logging
import os
import signal
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")
from gi.repository import Gtk

from .indicator import ClaudeIslandIndicator


def setup_logging() -> None:
    """Configure logging."""
    log_level = os.environ.get("CLAUDE_ISLAND_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Claude Island Applet v0.1.0")

    # Allow Ctrl+C to quit
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    try:
        indicator = ClaudeIslandIndicator()
        Gtk.main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
