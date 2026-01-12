"""File system monitoring for session directories."""

import logging
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .conversation_parser import ConversationParser, detect_clear_command
from .state_manager import SessionStore


logger = logging.getLogger(__name__)


class ConversationFileHandler(FileSystemEventHandler):
    """Handle file system events for conversation files."""

    def __init__(self, session_store: SessionStore) -> None:
        super().__init__()
        self.session_store = session_store
        self.parsers: dict[str, ConversationParser] = {}
        self.debounce_times: dict[str, float] = {}
        self.debounce_delay = 0.1  # 100ms debounce

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Only handle conversation.jsonl files
        if path.name != "conversation.jsonl":
            return

        # Debounce: ignore rapid successive changes
        now = time.time()
        last_time = self.debounce_times.get(event.src_path, 0)
        if now - last_time < self.debounce_delay:
            return

        self.debounce_times[event.src_path] = now

        # Extract session ID from path
        session_id = path.parent.name

        logger.debug("Conversation file modified: %s", session_id[:8])

        # Get or create parser
        if session_id not in self.parsers:
            self.parsers[session_id] = ConversationParser(path.parent)

        parser = self.parsers[session_id]

        # Parse new messages
        new_messages = parser.parse_incremental()

        # Check for /clear command
        if detect_clear_command(new_messages):
            logger.info("Clear command detected in %s", session_id[:8])
            # Reset parser to start from beginning
            parser.reset()
            # Clear conversation in session store
            session = self.session_store.get_session(session_id)
            if session:
                session.conversation.clear()

        # Add messages to session
        for message in new_messages:
            self.session_store.add_message(session_id, message)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        path = Path(event.src_path)

        if path.name == "conversation.jsonl":
            session_id = path.parent.name
            logger.info("New session detected: %s", session_id[:8])

            # Create parser
            parser = ConversationParser(path.parent)
            self.parsers[session_id] = parser

            # Parse initial content
            messages = parser.parse_full()
            for message in messages:
                self.session_store.add_message(session_id, message)


class FileMonitor:
    """Monitor session directory for conversation file changes.

    Uses watchdog library which wraps inotify on Linux.
    """

    def __init__(self, sessions_dir: Path, session_store: SessionStore) -> None:
        self.sessions_dir = sessions_dir
        self.session_store = session_store
        self.observer: Optional[Observer] = None
        self.handler = ConversationFileHandler(session_store)

    def start(self) -> None:
        """Start monitoring sessions directory."""
        if not self.sessions_dir.exists():
            logger.warning("Sessions directory does not exist: %s", self.sessions_dir)
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created sessions directory: %s", self.sessions_dir)

        self.observer = Observer()
        self.observer.schedule(
            self.handler,
            str(self.sessions_dir),
            recursive=True,
        )
        self.observer.start()

        logger.info("File monitor started for: %s", self.sessions_dir)

        # Parse existing sessions
        self._scan_existing_sessions()

    def stop(self) -> None:
        """Stop monitoring."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("File monitor stopped")

    def _scan_existing_sessions(self) -> None:
        """Scan for existing session directories on startup."""
        if not self.sessions_dir.exists():
            return

        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            conversation_file = session_dir / "conversation.jsonl"
            if not conversation_file.exists():
                continue

            session_id = session_dir.name
            logger.info("Found existing session: %s", session_id[:8])

            # Create parser and parse
            parser = ConversationParser(session_dir)
            self.handler.parsers[session_id] = parser

            messages = parser.parse_full()
            for message in messages:
                self.session_store.add_message(session_id, message)
