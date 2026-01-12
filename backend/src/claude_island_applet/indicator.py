"""System tray indicator for Claude Island."""

import logging
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")
from gi.repository import AppIndicator3, GLib, Gtk

from .dbus_client import DBusClient

logger = logging.getLogger(__name__)


class ClaudeIslandIndicator:
    """System tray indicator using AppIndicator3."""

    def __init__(self) -> None:
        self.dbus_client = DBusClient()

        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            "claude-island",
            "application-x-executable",  # Generic icon for now
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Claude Island")

        # Build menu
        self.menu = self.build_menu()
        self.indicator.set_menu(self.menu)

        # Track sessions
        self.sessions: dict[str, dict[str, Any]] = {}
        self.session_menu_items: dict[str, Gtk.MenuItem] = {}

        # Connect to D-Bus signals
        self.dbus_client.connect("session-state-changed", self.on_session_state_changed)
        self.dbus_client.connect("permission-request", self.on_permission_request)

        # Initial state fetch (delayed to allow main loop to start)
        GLib.timeout_add(500, self.refresh_sessions)

        logger.info("Applet initialized")

    def build_menu(self) -> Gtk.Menu:
        """Build the indicator menu."""
        menu = Gtk.Menu()

        # Header
        self.header_item = Gtk.MenuItem(label="Claude Island")
        self.header_item.set_sensitive(False)
        menu.append(self.header_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Sessions section (will be populated dynamically)
        self.sessions_separator = Gtk.SeparatorMenuItem()
        menu.append(self.sessions_separator)

        # Refresh
        refresh_item = Gtk.MenuItem(label="Refresh")
        refresh_item.connect("activate", lambda _: self.refresh_sessions())
        menu.append(refresh_item)

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def refresh_sessions(self) -> bool:
        """Fetch sessions from backend."""
        try:
            sessions = self.dbus_client.get_sessions()
            self.update_sessions_menu(sessions)
            logger.info("Refreshed: %d sessions", len(sessions))
        except Exception as e:
            logger.error("Failed to fetch sessions: %s", e)
            self.update_header("Error: Backend not running")

        return False  # Don't repeat timer

    def update_sessions_menu(self, sessions: list[dict[str, Any]]) -> None:
        """Update menu with current sessions."""
        # Remove old session items
        for item in list(self.session_menu_items.values()):
            self.menu.remove(item)
        self.session_menu_items.clear()

        # Update sessions dict
        self.sessions = {s["id"]: s for s in sessions}

        if not sessions:
            self.update_header("No active sessions")
            self.sessions_separator.hide()
            return

        self.update_header(f"{len(sessions)} session(s)")
        self.sessions_separator.show()

        # Add session items before the separator
        separator_pos = None
        for i, child in enumerate(self.menu.get_children()):
            if child == self.sessions_separator:
                separator_pos = i
                break

        for session in sessions:
            item = self.create_session_item(session)
            self.session_menu_items[session["id"]] = item
            self.menu.insert(item, separator_pos)
            separator_pos += 1

        self.menu.show_all()

    def create_session_item(self, session: dict[str, Any]) -> Gtk.MenuItem:
        """Create menu item for a session."""
        session_id = session["id"][:8]
        phase = session["phase"]
        tool = session.get("active_tool", "")

        if tool:
            label = f"[{session_id}] {phase} - {tool}"
        else:
            label = f"[{session_id}] {phase}"

        item = Gtk.MenuItem(label=label)
        item.connect("activate", lambda _: self.show_session_info(session))
        return item

    def show_session_info(self, session: dict[str, Any]) -> None:
        """Show dialog with session details."""
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=f"Session {session['id'][:8]}",
        )

        details = [
            f"Phase: {session['phase']}",
            f"Messages: {session.get('message_count', 0)}",
        ]

        if session.get("active_tool"):
            details.append(f"Active Tool: {session['active_tool']}")

        if session.get("has_pending_approval"):
            details.append("⚠️  Pending Approval")

        dialog.format_secondary_text("\n".join(details))
        dialog.run()
        dialog.destroy()

    def update_header(self, text: str) -> None:
        """Update header menu item text."""
        self.header_item.set_label(text)

    def on_session_state_changed(
        self, client: DBusClient, session_id: str, phase: str
    ) -> None:
        """Handle session state change signal."""
        logger.info("Session %s changed to %s", session_id[:8], phase)
        # Refresh to get latest state
        GLib.idle_add(self.refresh_sessions)

    def on_permission_request(
        self,
        client: DBusClient,
        session_id: str,
        tool_name: str,
        params: dict[str, Any],
    ) -> None:
        """Handle permission request signal."""
        logger.info("Permission requested: %s for session %s", tool_name, session_id[:8])

        # Show approval dialog
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Approve {tool_name}?",
        )

        dialog.format_secondary_text(
            f"Session {session_id[:8]} wants to execute {tool_name}\n\n"
            f"Parameters: {params}"
        )

        response = dialog.run()
        dialog.destroy()

        decision = "allow" if response == Gtk.ResponseType.YES else "deny"

        try:
            self.dbus_client.send_approval_decision(session_id, decision)
            logger.info("Sent decision: %s", decision)
        except Exception as e:
            logger.error("Failed to send decision: %s", e)
