# Claude Island Backend Service

Backend service for Claude Island Linux. Provides session monitoring and state management for Claude Code CLI, exposing a D-Bus interface for frontend applications.

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
- PyGObject (GLib bindings)
- watchdog (file monitoring)
- psutil (process management)

## Installation

```bash
cd backend
pip install -e .
```

## Usage

### Start Service

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

### Testing D-Bus Interface

```bash
# List sessions
busctl --user call com.claudeisland.Service \
  /com/claudeisland/Service \
  com.claudeisland.Service \
  GetSessions

# Monitor signals
busctl --user monitor com.claudeisland.Service
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
backend/
├── claude_island_service/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── socket_server.py     # Unix socket server
│   ├── state_manager.py     # Session state management
│   ├── conversation_parser.py  # JSONL parsing
│   ├── file_monitor.py      # File watching
│   ├── dbus_service.py      # D-Bus interface
│   ├── hook_installer.py    # Hook installation
│   └── resources/
│       └── claude-island-state.py  # Hook script
├── tests/
│   ├── test_parser.py
│   ├── test_state.py
│   └── test_socket.py
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
pytest tests/
```

### Logging

Set log level via environment variable:

```bash
CLAUDE_ISLAND_LOG_LEVEL=DEBUG python -m claude_island_service
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
