"""Tests for session state manager."""

import pytest

from claude_island_service.state_manager import Session, SessionPhase, SessionStore


def test_session_creation():
    """Test creating a new session."""
    session = Session(session_id="test-123", phase=SessionPhase.IDLE)
    assert session.session_id == "test-123"
    assert session.phase == SessionPhase.IDLE
    assert len(session.conversation) == 0


def test_session_store_process_event():
    """Test processing events through session store."""
    store = SessionStore()

    # Process SessionStart event
    event = {"type": "SessionStart", "session_id": "test-123"}
    store.process_event(event)

    assert "test-123" in store.sessions
    session = store.sessions["test-123"]
    assert session.phase == SessionPhase.IDLE


def test_session_store_pre_tool_use():
    """Test PreToolUse event handling."""
    store = SessionStore()

    event = {
        "type": "PreToolUse",
        "session_id": "test-123",
        "tool_name": "Read",
        "parameters": {"file_path": "/tmp/test.txt"},
    }
    store.process_event(event)

    session = store.sessions["test-123"]
    assert session.phase == SessionPhase.RUNNING_TOOL
    assert session.active_tool is not None
    assert session.active_tool.name == "Read"


def test_session_store_permission_request():
    """Test PermissionRequest event handling."""
    store = SessionStore()

    event = {
        "type": "PermissionRequest",
        "session_id": "test-123",
        "tool_name": "Bash",
        "parameters": {"command": "ls -la"},
    }
    store.process_event(event)

    session = store.sessions["test-123"]
    assert session.phase == SessionPhase.WAITING_APPROVAL
    assert session.pending_approval is not None
    assert session.pending_approval["tool_name"] == "Bash"


def test_session_store_add_message():
    """Test adding messages to session conversation."""
    store = SessionStore()

    # Create session
    store.process_event({"type": "SessionStart", "session_id": "test-123"})

    # Add message
    message = {"type": "user", "content": "Hello"}
    store.add_message("test-123", message)

    session = store.sessions["test-123"]
    assert len(session.conversation) == 1
    assert session.conversation[0]["content"] == "Hello"


def test_session_store_observers():
    """Test observer notifications."""
    store = SessionStore()
    notifications = []

    def observer(session):
        notifications.append(session.session_id)

    store.observers.append(observer)

    # Trigger event
    store.process_event({"type": "SessionStart", "session_id": "test-123"})

    assert len(notifications) == 1
    assert notifications[0] == "test-123"
