"""JSONL conversation file parser."""

import json
import logging
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


class ConversationParser:
    """Parse Claude Code CLI conversation JSONL files.

    Supports incremental parsing to only read new lines since last parse.
    """

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.conversation_file = session_dir / "conversation.jsonl"
        self.last_position = 0

    def parse_incremental(self) -> list[dict[str, Any]]:
        """Parse new messages since last parse."""
        if not self.conversation_file.exists():
            return []

        new_messages: list[dict[str, Any]] = []

        try:
            with open(self.conversation_file, "r") as f:
                # Seek to last position
                f.seek(self.last_position)

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        message = json.loads(line)
                        new_messages.append(message)
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON line in conversation: %s", e)

                # Update position
                self.last_position = f.tell()

        except Exception as e:
            logger.error("Error reading conversation file: %s", e)

        return new_messages

    def parse_full(self) -> list[dict[str, Any]]:
        """Parse entire conversation file from beginning."""
        self.last_position = 0
        return self.parse_incremental()

    def reset(self) -> None:
        """Reset parser to read from beginning next time."""
        self.last_position = 0

    @property
    def exists(self) -> bool:
        """Check if conversation file exists."""
        return self.conversation_file.exists()


class SubagentParser:
    """Parse subagent conversation files.

    Subagents create nested conversation files for task execution.
    """

    def __init__(self, session_dir: Path, task_id: str) -> None:
        self.session_dir = session_dir
        self.task_id = task_id
        self.subagent_file = session_dir / f"task-{task_id}.jsonl"

    def parse(self) -> list[dict[str, Any]]:
        """Parse subagent conversation file."""
        if not self.subagent_file.exists():
            return []

        messages: list[dict[str, Any]] = []

        try:
            with open(self.subagent_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        message = json.loads(line)
                        messages.append(message)
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON in subagent file: %s", e)

        except Exception as e:
            logger.error("Error reading subagent file: %s", e)

        return messages

    @property
    def exists(self) -> bool:
        """Check if subagent file exists."""
        return self.subagent_file.exists()


def detect_clear_command(messages: list[dict[str, Any]]) -> bool:
    """Detect if /clear command was used in conversation.

    When /clear is used, conversation history should be reset.
    """
    for message in messages:
        if message.get("type") == "user":
            content = message.get("content", "")
            if content.strip().startswith("/clear"):
                return True
    return False
