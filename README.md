# Claude Island for Linux

Backend service and StatusNotifier applet for monitoring Claude Code CLI sessions. Provides session monitoring, state management, and D-Bus interface for frontend applications.

## Architecture

The backend acts as a bridge between Claude Code CLI and frontend UIs:

```
Claude Code CLI → Hook Script → Unix Socket → Backend Service → D-Bus → Frontends
```

### Components

- **Unix Socket Server**: Receives events from Claude Code CLI hooks
- **Session State Manager**: Tracks active sessions, tools, and conversation state
- **JSONL Parser**: Reads and parses conversation files incrementally
- **File Monitor**: Watches session directories for changes (inotify)
- **D-Bus Service**: Exposes state and methods to frontend applications

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- PyGObject (GLib bindings)
- watchdog (file monitoring)
- psutil (process management)

## Installation

### Using uv (recommended)

```bash
uv sync
```

### Using pip

```bash
pip install -e .
```

## Usage

### Start Backend Service

With uv:
```bash
uv run claude-island-service
```

With pip:
```bash
python -m claude_island_service
```

The service will:
1. Create Unix socket at `/tmp/claude-island.sock`
2. Register D-Bus service at `com.claudeisland.Service`
3. Monitor `~/.claude/sessions/` for conversation files
4. Install hook script to `~/.claude/hooks/` on first run

### D-Bus Interface

**Service Name**: `com.claudeisland.Service`
**Object Path**: `/com/claudeisland/Service`

#### Methods

- `GetSessions() → a{sv}` - Returns all active sessions
- `GetConversation(session_id: s) → aa{sv}` - Returns messages for a session
- `SendApprovalDecision(session_id: s, decision: s)` - Send approval response

#### Signals

- `SessionStateChanged(session_id: s, phase: s)` - Session phase changed
- `PermissionRequest(session_id: s, tool_name: s, params: a{sv})` - Needs approval
- `NewMessage(session_id: s, message: a{sv})` - New conversation message

### Start StatusNotifier Applet

With uv:
```bash
uv run claude-island-applet
```

With pip:
```bash
python -m claude_island_applet
```

The applet will:
1. Connect to backend via D-Bus
2. Show system tray icon
3. Display menu with active sessions
4. Show approval dialogs for permission requests

### Testing

See [docs/TESTING.md](docs/TESTING.md) for detailed testing instructions.

Quick test:
```bash
# Terminal 1: Start backend
uv run claude-island-service

# Terminal 2: Start applet
uv run claude-island-applet

# Terminal 3: Start Claude Code
claude
```

## Hook System

The service installs a Python hook script to `~/.claude/hooks/claude-island-state.py`. This script:

- Captures Claude Code CLI events
- Sends events via Unix socket
- Waits for approval decisions on permission requests
- Detects TTY for proper terminal integration

### Supported Events

- `SessionStart` / `SessionEnd`
- `UserPromptSubmit`
- `PreToolUse` / `PostToolUse`
- `PermissionRequest`
- `Notification`
- `Stop` / `SubagentStop`
- `PreCompact`

## Development

### Project Structure

```
claude-island-linux/
├── src/
│   ├── claude_island_service/    # Backend service
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── socket_server.py
│   │   ├── state_manager.py
│   │   ├── conversation_parser.py
│   │   ├── file_monitor.py
│   │   ├── dbus_service.py
│   │   ├── hook_installer.py
│   │   └── resources/
│   │       └── claude-island-state.py
│   └── claude_island_applet/     # StatusNotifier applet
│       ├── __init__.py
│       ├── __main__.py
│       ├── indicator.py
│       └── dbus_client.py
├── tests/
│   └── test_state_manager.py
├── docs/
│   ├── TESTING.md
│   ├── ANALYSIS.md
│   ├── GNOME_EXTENSION_APPROACH.md
│   └── IMPLEMENTATION_SUMMARY.md
├── pyproject.toml
├── uv.lock
└── README.md
```

### Running Tests

With uv:
```bash
uv run pytest
```

With pip:
```bash
pytest tests/
```

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

### Logging

Set log level via environment variable:

```bash
CLAUDE_ISLAND_LOG_LEVEL=DEBUG uv run claude-island-service
```

## Auto-Start

### D-Bus Activation

Create `~/.local/share/dbus-1/services/com.claudeisland.Service.service`:

```ini
[D-BUS Service]
Name=com.claudeisland.Service
Exec=/usr/bin/python3 -m claude_island_service
```

The service will start automatically when a frontend connects.

### systemd User Service

Create `~/.config/systemd/user/claude-island.service`:

```ini
[Unit]
Description=Claude Island Backend Service
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m claude_island_service
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user enable --now claude-island.service
```

## Troubleshooting

### Hook Not Installing

Check that `~/.claude/` directory exists and is writable. The service needs to modify `~/.claude/settings.json`.

### Socket Permission Denied

Check permissions on `/tmp/claude-island.sock`. Remove the socket file if it exists with wrong permissions:

```bash
rm /tmp/claude-island.sock
```

### No Sessions Detected

Verify Claude Code CLI is running and hook script is installed:

```bash
cat ~/.claude/settings.json | grep claude-island
```

Start a Claude Code session and check backend logs.

## Credits

Based on [Claude Island](https://github.com/farouqaldori/claude-island) by Farouq Aldori. This is a Linux port adapting the hook system and state management approach for cross-platform desktop environments.

## License

TBD
