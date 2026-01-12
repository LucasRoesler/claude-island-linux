"""Session state management."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


class SessionPhase(Enum):
    """Session execution phases."""

    IDLE = "idle"
    PROCESSING = "processing"
    RUNNING_TOOL = "running_tool"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Tool:
    """Tool execution information."""

    name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    parameters: Optional[dict[str, Any]] = None


@dataclass
class Session:
    """Session state."""

    session_id: str
    phase: SessionPhase
    active_tool: Optional[Tool] = None
    pending_approval: Optional[dict[str, Any]] = None
    tools: list[Tool] = field(default_factory=list)
    conversation: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class SessionStore:
    """Centralized session state management.

    All state mutations flow through process_event() for consistency.
    Observers are notified of state changes.
    """

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.observers: list[Callable[[Session], None]] = []
        self._pending_tool_cache: dict[str, Tool] = {}  # Correlate PreToolUse with PermissionRequest

    def process_event(self, event: dict[str, Any]) -> None:
        """Process hook event and update state."""
        event_type = event.get("type")
        session_id = event.get("session_id")

        if not session_id:
            logger.warning("Event missing session_id: %s", event_type)
            return

        # Ensure session exists
        if session_id not in self.sessions:
            self.sessions[session_id] = Session(
                session_id=session_id,
                phase=SessionPhase.IDLE,
            )
            logger.info("Created session: %s", session_id[:8])

        session = self.sessions[session_id]
        session.updated_at = datetime.now()

        # Process event type
        if event_type == "SessionStart":
            self._handle_session_start(session, event)
        elif event_type == "SessionEnd":
            self._handle_session_end(session, event)
        elif event_type == "UserPromptSubmit":
            self._handle_user_prompt(session, event)
        elif event_type == "PreToolUse":
            self._handle_pre_tool_use(session, event)
        elif event_type == "PostToolUse":
            self._handle_post_tool_use(session, event)
        elif event_type == "PermissionRequest":
            self._handle_permission_request(session, event)
        elif event_type == "Notification":
            self._handle_notification(session, event)
        elif event_type in ("Stop", "SubagentStop"):
            self._handle_stop(session, event)
        else:
            logger.debug("Unhandled event type: %s", event_type)

        # Notify observers
        self.notify_observers(session)

    def _handle_session_start(self, session: Session, event: dict[str, Any]) -> None:
        """Handle SessionStart event."""
        session.phase = SessionPhase.IDLE
        logger.info("Session started: %s", session.session_id[:8])

    def _handle_session_end(self, session: Session, event: dict[str, Any]) -> None:
        """Handle SessionEnd event."""
        session.phase = SessionPhase.COMPLETED
        logger.info("Session ended: %s", session.session_id[:8])

    def _handle_user_prompt(self, session: Session, event: dict[str, Any]) -> None:
        """Handle UserPromptSubmit event."""
        session.phase = SessionPhase.PROCESSING
        logger.debug("User prompt submitted: %s", session.session_id[:8])

    def _handle_pre_tool_use(self, session: Session, event: dict[str, Any]) -> None:
        """Handle PreToolUse event."""
        tool_name = event.get("tool_name", "Unknown")
        tool = Tool(
            name=tool_name,
            status="running",
            start_time=datetime.now(),
            parameters=event.get("parameters"),
        )

        session.active_tool = tool
        session.phase = SessionPhase.RUNNING_TOOL

        # Cache tool for correlation with PermissionRequest
        cache_key = f"{session.session_id}:{tool_name}"
        self._pending_tool_cache[cache_key] = tool

        logger.debug("Tool started: %s on %s", tool_name, session.session_id[:8])

    def _handle_post_tool_use(self, session: Session, event: dict[str, Any]) -> None:
        """Handle PostToolUse event."""
        tool_name = event.get("tool_name", "Unknown")

        if session.active_tool and session.active_tool.name == tool_name:
            session.active_tool.end_time = datetime.now()
            session.active_tool.status = "success"
            session.active_tool.result = event.get("result")
            session.tools.append(session.active_tool)
            session.active_tool = None

        session.phase = SessionPhase.IDLE

        # Clean up cache
        cache_key = f"{session.session_id}:{tool_name}"
        self._pending_tool_cache.pop(cache_key, None)

        logger.debug("Tool completed: %s on %s", tool_name, session.session_id[:8])

    def _handle_permission_request(self, session: Session, event: dict[str, Any]) -> None:
        """Handle PermissionRequest event."""
        tool_name = event.get("tool_name", "Unknown")
        session.pending_approval = {
            "tool_name": tool_name,
            "parameters": event.get("parameters", {}),
            "timestamp": datetime.now(),
        }
        session.phase = SessionPhase.WAITING_APPROVAL

        logger.info("Permission requested: %s on %s", tool_name, session.session_id[:8])

    def _handle_notification(self, session: Session, event: dict[str, Any]) -> None:
        """Handle Notification event."""
        logger.debug("Notification: %s", event.get("message", ""))

    def _handle_stop(self, session: Session, event: dict[str, Any]) -> None:
        """Handle Stop/SubagentStop event."""
        session.phase = SessionPhase.IDLE
        session.active_tool = None
        logger.debug("Session stopped: %s", session.session_id[:8])

    def add_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Add message to session conversation."""
        if session_id not in self.sessions:
            logger.warning("Cannot add message to unknown session: %s", session_id[:8])
            return

        session = self.sessions[session_id]
        session.conversation.append(message)
        session.updated_at = datetime.now()

        logger.debug(
            "Message added to %s: %s", session_id[:8], message.get("type", "unknown")
        )

        self.notify_observers(session)

    def clear_approval(self, session_id: str) -> None:
        """Clear pending approval after decision sent."""
        if session_id not in self.sessions:
            return

        session = self.sessions[session_id]
        session.pending_approval = None
        session.phase = SessionPhase.IDLE

        self.notify_observers(session)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    def get_all_sessions(self) -> list[Session]:
        """Get all sessions."""
        return list(self.sessions.values())

    def notify_observers(self, session: Session) -> None:
        """Notify all observers of session state change."""
        for observer in self.observers:
            try:
                observer(session)
            except Exception as e:
                logger.error("Observer error: %s", e)
