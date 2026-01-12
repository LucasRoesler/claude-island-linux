"""Unix domain socket server for hook communication."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from .state_manager import SessionStore


logger = logging.getLogger(__name__)


class HookSocketServer:
    """Unix socket server for receiving hook events.

    Listens on /tmp/claude-island.sock for events from hook script.
    Sends approval responses back through the same connection.
    """

    def __init__(
        self,
        session_store: SessionStore,
        socket_path: str = "/tmp/claude-island.sock",
    ) -> None:
        self.session_store = session_store
        self.socket_path = socket_path
        self.server: Optional[asyncio.AbstractServer] = None
        self.pending_approvals: dict[str, asyncio.StreamWriter] = {}

    async def start(self) -> None:
        """Start the Unix socket server."""
        # Remove existing socket if present
        socket_file = Path(self.socket_path)
        if socket_file.exists():
            socket_file.unlink()
            logger.info("Removed existing socket file")

        # Create server
        self.server = await asyncio.start_unix_server(
            self.handle_client, path=self.socket_path
        )

        logger.info("Socket server listening on %s", self.socket_path)

    def stop(self) -> None:
        """Stop the socket server."""
        if self.server:
            self.server.close()
            logger.info("Socket server stopped")

        # Clean up socket file
        socket_file = Path(self.socket_path)
        if socket_file.exists():
            socket_file.unlink()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming client connection."""
        addr = writer.get_extra_info("peername")
        logger.debug("Client connected: %s", addr)

        try:
            # Read event data (up to 64KB)
            data = await reader.read(65536)
            if not data:
                logger.warning("Received empty data from client")
                return

            # Parse JSON event
            try:
                event = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON from client: %s", e)
                return

            logger.debug("Received event: %s", event.get("type"))

            # Process event
            response = await self.process_event(event, writer)

            # Send response if needed
            if response:
                writer.write(json.dumps(response).encode("utf-8"))
                await writer.drain()

        except Exception as e:
            logger.error("Error handling client: %s", e)
        finally:
            writer.close()
            await writer.wait_closed()

    async def process_event(
        self, event: dict[str, Any], writer: asyncio.StreamWriter
    ) -> Optional[dict[str, Any]]:
        """Process hook event and return response if needed."""
        event_type = event.get("type")
        session_id = event.get("session_id")

        # Update session state
        self.session_store.process_event(event)

        # Handle permission requests specially
        if event_type == "PermissionRequest":
            # Store writer for approval response
            if session_id:
                self.pending_approvals[session_id] = writer

            # Return "waiting" status immediately
            # Actual decision will be sent later via send_approval_response
            return {"status": "waiting_for_approval"}

        return None

    def send_approval_response(self, session_id: str, decision: str) -> None:
        """Send approval decision back to hook script.

        Called by D-Bus service when frontend sends decision.
        """
        writer = self.pending_approvals.get(session_id)
        if not writer:
            logger.warning("No pending approval for session: %s", session_id[:8])
            return

        response = {
            "decision": decision,  # "allow" or "deny"
            "reason": "User decision from frontend",
        }

        try:
            # Send response
            writer.write(json.dumps(response).encode("utf-8"))
            # Note: We can't await here since this is called from sync context
            # The drain will happen when the writer is closed
            logger.info("Sent approval decision for %s: %s", session_id[:8], decision)
        except Exception as e:
            logger.error("Failed to send approval response: %s", e)
        finally:
            # Clean up
            del self.pending_approvals[session_id]
            self.session_store.clear_approval(session_id)
