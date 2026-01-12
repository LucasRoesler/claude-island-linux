"""D-Bus service for frontend communication."""

import logging
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

from .socket_server import HookSocketServer
from .state_manager import Session, SessionStore


logger = logging.getLogger(__name__)


DBUS_INTERFACE_XML = """
<node>
  <interface name="com.claudeisland.Service">
    <method name="GetSessions">
      <arg type="aa{sv}" direction="out" name="sessions"/>
    </method>
    <method name="GetConversation">
      <arg type="s" direction="in" name="session_id"/>
      <arg type="aa{sv}" direction="out" name="messages"/>
    </method>
    <method name="SendApprovalDecision">
      <arg type="s" direction="in" name="session_id"/>
      <arg type="s" direction="in" name="decision"/>
    </method>
    <signal name="SessionStateChanged">
      <arg type="s" name="session_id"/>
      <arg type="s" name="phase"/>
    </signal>
    <signal name="PermissionRequest">
      <arg type="s" name="session_id"/>
      <arg type="s" name="tool_name"/>
      <arg type="a{sv}" name="params"/>
    </signal>
    <signal name="NewMessage">
      <arg type="s" name="session_id"/>
      <arg type="a{sv}" name="message"/>
    </signal>
  </interface>
</node>
"""


class ClaudeIslandDBusService:
    """D-Bus service exposing backend state to frontends."""

    def __init__(self, session_store: SessionStore, socket_server: HookSocketServer) -> None:
        self.session_store = session_store
        self.socket_server = socket_server
        self.connection: Gio.DBusConnection | None = None
        self.registration_id: int | None = None

        # Parse interface
        self.node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_INTERFACE_XML)
        self.interface_info = self.node_info.interfaces[0]

        # Register service
        self.owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            "com.claudeisland.Service",
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            None,  # on_name_acquired
            None,  # on_name_lost
        )

        # Subscribe to session store events
        session_store.observers.append(self._on_session_changed)

        logger.info("D-Bus service registered: com.claudeisland.Service")

    def _on_bus_acquired(
        self, connection: Gio.DBusConnection, name: str
    ) -> None:
        """Callback when bus is acquired."""
        self.connection = connection
        self.registration_id = connection.register_object(
            "/com/claudeisland/Service",
            self.interface_info,
            self._handle_method_call,
            None,  # get_property
            None,  # set_property
        )
        logger.info("D-Bus object registered at /com/claudeisland/Service")

    def _handle_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Handle D-Bus method calls."""
        try:
            if method_name == "GetSessions":
                sessions = self._get_sessions()
                result = GLib.Variant("(aa{sv})", (sessions,))
                invocation.return_value(result)

            elif method_name == "GetConversation":
                session_id = parameters.unpack()[0]
                messages = self._get_conversation(session_id)
                result = GLib.Variant("(aa{sv})", (messages,))
                invocation.return_value(result)

            elif method_name == "SendApprovalDecision":
                session_id, decision = parameters.unpack()
                self._send_approval_decision(session_id, decision)
                invocation.return_value(None)

            else:
                invocation.return_error_literal(
                    Gio.dbus_error_quark(),
                    Gio.DBusError.UNKNOWN_METHOD,
                    f"Unknown method: {method_name}",
                )

        except Exception as e:
            logger.error("Error handling method call %s: %s", method_name, e)
            invocation.return_error_literal(
                Gio.dbus_error_quark(),
                Gio.DBusError.FAILED,
                str(e),
            )

    def _get_sessions(self) -> list[dict[str, GLib.Variant]]:
        """Get all sessions as D-Bus format."""
        sessions = []
        for session in self.session_store.get_all_sessions():
            sessions.append(
                {
                    "id": GLib.Variant("s", session.session_id),
                    "phase": GLib.Variant("s", session.phase.value),
                    "has_pending_approval": GLib.Variant(
                        "b", session.pending_approval is not None
                    ),
                    "active_tool": GLib.Variant(
                        "s", session.active_tool.name if session.active_tool else ""
                    ),
                    "message_count": GLib.Variant("i", len(session.conversation)),
                }
            )
        return sessions

    def _get_conversation(self, session_id: str) -> list[dict[str, GLib.Variant]]:
        """Get conversation messages for a session."""
        session = self.session_store.get_session(session_id)
        if not session:
            return []

        messages = []
        for msg in session.conversation:
            # Convert message to D-Bus format
            dbus_msg = {
                "type": GLib.Variant("s", msg.get("type", "unknown")),
                "content": GLib.Variant("s", str(msg.get("content", ""))),
            }

            # Add optional fields
            if "name" in msg:
                dbus_msg["name"] = GLib.Variant("s", msg["name"])
            if "status" in msg:
                dbus_msg["status"] = GLib.Variant("s", msg["status"])

            messages.append(dbus_msg)

        return messages

    def _send_approval_decision(self, session_id: str, decision: str) -> None:
        """Send approval decision to hook via socket server."""
        logger.info("Sending approval decision for %s: %s", session_id[:8], decision)
        self.socket_server.send_approval_response(session_id, decision)

    def _on_session_changed(self, session: Session) -> None:
        """Observer callback for session state changes."""
        if not self.connection:
            return

        # Emit SessionStateChanged signal
        self.connection.emit_signal(
            None,
            "/com/claudeisland/Service",
            "com.claudeisland.Service",
            "SessionStateChanged",
            GLib.Variant("(ss)", (session.session_id, session.phase.value)),
        )

        # Emit PermissionRequest if waiting for approval
        if session.pending_approval:
            params = self._convert_to_variant_dict(
                session.pending_approval.get("parameters", {})
            )
            self.connection.emit_signal(
                None,
                "/com/claudeisland/Service",
                "com.claudeisland.Service",
                "PermissionRequest",
                GLib.Variant(
                    "(ssa{sv})",
                    (
                        session.session_id,
                        session.pending_approval["tool_name"],
                        params,
                    ),
                ),
            )

    def _convert_to_variant_dict(self, data: dict[str, Any]) -> dict[str, GLib.Variant]:
        """Convert Python dict to D-Bus variant dict."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = GLib.Variant("s", value)
            elif isinstance(value, int):
                result[key] = GLib.Variant("i", value)
            elif isinstance(value, bool):
                result[key] = GLib.Variant("b", value)
            elif isinstance(value, (list, tuple)):
                result[key] = GLib.Variant("as", [str(v) for v in value])
            else:
                result[key] = GLib.Variant("s", str(value))
        return result
