"""Entry point for Claude Island backend service."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import GLib

from .dbus_service import ClaudeIslandDBusService
from .file_monitor import FileMonitor
from .hook_installer import HookInstaller
from .socket_server import HookSocketServer
from .state_manager import SessionStore


def setup_logging() -> None:
    """Configure logging based on environment variable."""
    log_level = os.environ.get("CLAUDE_ISLAND_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Main entry point for backend service."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Claude Island Backend Service v%s", "0.1.0")

    # Install hooks on first run
    hook_installer = HookInstaller()
    if not hook_installer.is_installed():
        logger.info("Installing hook script...")
        try:
            hook_installer.install()
            logger.info("Hook script installed successfully")
        except Exception as e:
            logger.error("Failed to install hook script: %s", e)
            sys.exit(1)
    else:
        logger.info("Hook script already installed")

    # Create components
    session_store = SessionStore()
    socket_server = HookSocketServer(session_store)
    sessions_dir = Path.home() / ".claude" / "sessions"
    file_monitor = FileMonitor(sessions_dir, session_store)

    # Start socket server in asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_socket() -> None:
        await socket_server.start()

    loop.run_until_complete(start_socket())

    # Start file monitor
    file_monitor.start()

    # Create D-Bus service
    dbus_service = ClaudeIslandDBusService(session_store, socket_server)

    logger.info("Backend service started")
    logger.info("Unix socket: /tmp/claude-island.sock")
    logger.info("D-Bus service: com.claudeisland.Service")
    logger.info("Monitoring sessions in: %s", sessions_dir)

    # Set up signal handlers
    def signal_handler(sig: int, frame) -> None:
        logger.info("Received signal %s, shutting down...", sig)
        file_monitor.stop()
        socket_server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run GLib main loop
    try:
        main_loop = GLib.MainLoop()
        main_loop.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        file_monitor.stop()
        socket_server.stop()
        logger.info("Backend service stopped")


if __name__ == "__main__":
    main()
