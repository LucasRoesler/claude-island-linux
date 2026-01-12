#!/usr/bin/env python3
"""Claude Island hook script for Claude Code CLI.

This script is installed to ~/.claude/hooks/ and captures session events,
sending them to the backend service via Unix socket.

Based on the hook system from Claude Island for macOS.
"""

import json
import os
import socket
import sys
from pathlib import Path


SOCKET_PATH = "/tmp/claude-island.sock"
TIMEOUT = 300  # 5 minutes for permission requests


def detect_tty():
    """Detect if running in a TTY terminal.

    Checks stdin and walks up process tree to find terminal/tmux.
    """
    import stat

    # Check if stdin is a TTY
    try:
        stdin_stat = os.fstat(0)
        if stat.S_ISCHR(stdin_stat.st_mode):
            return True
    except Exception:
        pass

    # Walk up process tree
    pid = os.getpid()
    ppid = os.getppid()

    while ppid > 1:
        try:
            # Read parent process command line
            cmdline_path = f"/proc/{ppid}/cmdline"
            if os.path.exists(cmdline_path):
                with open(cmdline_path, 'r') as f:
                    cmdline = f.read().replace('\x00', ' ')
                    # Check for known terminal emulators
                    if any(term in cmdline.lower() for term in
                           ['tmux', 'gnome-terminal', 'konsole', 'xterm',
                            'alacritty', 'kitty', 'terminator']):
                        return True

            # Get parent's parent
            stat_path = f"/proc/{ppid}/stat"
            if os.path.exists(stat_path):
                with open(stat_path, 'r') as f:
                    stats = f.read().split()
                    if len(stats) > 3:
                        ppid = int(stats[3])  # PPID is 4th field
                    else:
                        break
            else:
                break

        except (IOError, ValueError):
            break

    return False


def send_event(event):
    """Send event to backend service via Unix socket."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        sock.connect(SOCKET_PATH)

        # Send event as JSON
        data = json.dumps(event).encode('utf-8')
        sock.sendall(data)

        # Wait for response (for PermissionRequest events)
        if event.get("type") == "PermissionRequest":
            response_data = sock.recv(65536)
            if response_data:
                response = json.loads(response_data.decode('utf-8'))
                sock.close()
                return response

        sock.close()
        return None

    except socket.timeout:
        print("Error: Timeout waiting for approval decision", file=sys.stderr)
        return {"decision": "deny", "reason": "Timeout"}
    except FileNotFoundError:
        print(f"Error: Backend service not running (socket not found: {SOCKET_PATH})",
              file=sys.stderr)
        return {"decision": "deny", "reason": "Backend not running"}
    except Exception as e:
        print(f"Error communicating with backend: {e}", file=sys.stderr)
        return {"decision": "deny", "reason": str(e)}


def main():
    """Main hook entry point."""
    # Read event from stdin
    try:
        event_data = sys.stdin.read()
        event = json.loads(event_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON from Claude Code: {e}", file=sys.stderr)
        sys.exit(1)

    # Add TTY detection
    has_tty = detect_tty()
    event["has_tty"] = has_tty

    # Send to backend
    response = send_event(event)

    # For PermissionRequest, output decision
    if event.get("type") == "PermissionRequest":
        if response:
            # Claude Code CLI expects JSON response
            print(json.dumps(response))
        else:
            # Default to deny if no response
            print(json.dumps({"decision": "deny", "reason": "No response from backend"}))

    sys.exit(0)


if __name__ == "__main__":
    main()
