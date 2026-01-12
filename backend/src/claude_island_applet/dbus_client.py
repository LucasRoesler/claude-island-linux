"""D-Bus client for communicating with backend service."""

import logging
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import GLib, GObject, Gio

logger = logging.getLogger(__name__)


class DBusClient(GObject.GObject):
    """Client for Claude Island D-Bus service.

    Signals:
        session-state-changed(session_id: str, phase: str)
        permission-request(session_id: str, tool_name: str, params: dict)
        new-message(session_id: str, message: dict)
    """

    __gsignals__ = {
        "session-state-changed": (GObject.SIGNAL_RUN_FIRST, None, (str, str)),
        "permission-request": (GObject.SIGNAL_RUN_FIRST, None, (str, str, object)),
        "new-message": (GObject.SIGNAL_RUN_FIRST, None, (str, object)),
    }

    def __init__(self) -> None:
        super().__init__()

        try:
            # Create proxy
            self.proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "com.claudeisland.Service",
                "/com/claudeisland/Service",
                "com.claudeisland.Service",
                None,
            )

            # Connect to signals
            self.proxy.connect("g-signal", self._on_dbus_signal)

            logger.info("Connected to D-Bus service")
        except Exception as e:
            logger.error("Failed to connect to D-Bus service: %s", e)
            raise

    def _on_dbus_signal(
        self,
        proxy: Gio.DBusProxy,
        sender_name: str,
        signal_name: str,
        parameters: GLib.Variant,
    ) -> None:
        """Handle D-Bus signals from backend."""
        try:
            if signal_name == "SessionStateChanged":
                session_id, phase = parameters.unpack()
                self.emit("session-state-changed", session_id, phase)

            elif signal_name == "PermissionRequest":
                session_id, tool_name, params = parameters.unpack()
                # Convert variant dict to Python dict
                params_dict = {k: v for k, v in params.items()}
                self.emit("permission-request", session_id, tool_name, params_dict)

            elif signal_name == "NewMessage":
                session_id, message = parameters.unpack()
                message_dict = {k: v for k, v in message.items()}
                self.emit("new-message", session_id, message_dict)

            else:
                logger.debug("Unknown signal: %s", signal_name)

        except Exception as e:
            logger.error("Error handling signal %s: %s", signal_name, e)

    def get_sessions(self) -> list[dict[str, Any]]:
        """Get all active sessions."""
        try:
            result = self.proxy.call_sync(
                "GetSessions",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )

            sessions_variant = result.unpack()[0]
            sessions = []

            for session_variant in sessions_variant:
                session = {}
                for key, value in session_variant.items():
                    # Unpack variant values
                    if hasattr(value, "unpack"):
                        session[key] = value.unpack()
                    else:
                        session[key] = value
                sessions.append(session)

            return sessions

        except Exception as e:
            logger.error("Failed to get sessions: %s", e)
            raise

    def get_conversation(self, session_id: str) -> list[dict[str, Any]]:
        """Get conversation for a session."""
        try:
            result = self.proxy.call_sync(
                "GetConversation",
                GLib.Variant("(s)", (session_id,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )

            messages_variant = result.unpack()[0]
            messages = []

            for msg_variant in messages_variant:
                message = {}
                for key, value in msg_variant.items():
                    if hasattr(value, "unpack"):
                        message[key] = value.unpack()
                    else:
                        message[key] = value
                messages.append(message)

            return messages

        except Exception as e:
            logger.error("Failed to get conversation: %s", e)
            raise

    def send_approval_decision(self, session_id: str, decision: str) -> None:
        """Send approval decision to backend."""
        try:
            self.proxy.call_sync(
                "SendApprovalDecision",
                GLib.Variant("(ss)", (session_id, decision)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )

            logger.debug("Sent approval decision: %s for %s", decision, session_id[:8])

        except Exception as e:
            logger.error("Failed to send approval decision: %s", e)
            raise
