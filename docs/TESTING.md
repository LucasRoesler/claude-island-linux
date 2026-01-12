# Testing Guide

Quick guide for testing the minimal functional implementation.

## Prerequisites

1. **Install system dependencies** (Fedora):
```bash
sudo dnf install python3-devel python3-gobject gtk3-devel libappindicator-gtk3-devel
```

2. **Install uv** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup

1. **Install the project**:
```bash
uv sync
```

## Testing the Backend Service

### Start the backend service

In terminal 1:
```bash
uv run claude-island-service
```

Expected output:
- "Installing hook script..." (first run only)
- "Socket server listening on /tmp/claude-island.sock"
- "D-Bus service registered: com.claudeisland.Service"
- "File monitor started..."

### Verify D-Bus registration

In terminal 2:
```bash
# List available D-Bus services (should see com.claudeisland.Service)
busctl --user list | grep claude

# Test GetSessions method (should return empty array initially)
busctl --user call com.claudeisland.Service \
  /com/claudeisland/Service \
  com.claudeisland.Service \
  GetSessions
```

### Test with Claude Code CLI

In terminal 3:
```bash
# Start a Claude Code session
claude

# In Claude session, trigger some tool usage
# The backend should log events as they come in
```

Watch terminal 1 for backend logs showing:
- Hook events being received
- Session state changes
- Tool executions

## Testing the Applet

### Start the applet

In terminal 4 (while backend is running):
```bash
uv run claude-island-applet
```

Expected output:
- "Applet initialized"
- "Connected to D-Bus service"
- System tray icon should appear

### Verify functionality

1. **Click the tray icon** - Menu should show:
   - "Claude Island"
   - List of active sessions (if any)
   - "Refresh"
   - "Quit"

2. **Start a Claude Code session** (terminal 3):
   - Applet should update to show the session
   - Session should show current phase (idle, processing, etc.)

3. **Trigger a permission request**:
   - In Claude session, try a command that needs approval
   - Applet should show approval dialog
   - Click Yes/No to send decision back

4. **Click on a session** in the menu:
   - Should show dialog with session details

## Manual D-Bus Testing

### Send test events

You can manually trigger backend events:

```bash
# Create test event
python3 << 'EOF'
import socket
import json

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/tmp/claude-island.sock')

event = {
    "type": "SessionStart",
    "session_id": "test-session-123"
}

sock.sendall(json.dumps(event).encode())
sock.close()
EOF
```

### Monitor D-Bus signals

In a separate terminal:
```bash
busctl --user monitor com.claudeisland.Service
```

This will show all signals emitted by the backend (SessionStateChanged, PermissionRequest, etc.)

## Troubleshooting

### Backend won't start

**Check socket exists**:
```bash
ls -la /tmp/claude-island.sock
```

If it exists with wrong permissions:
```bash
rm /tmp/claude-island.sock
```

**Check D-Bus service**:
```bash
busctl --user list | grep claude
```

### Applet won't start

**Check AppIndicator is available**:
```bash
python3 -c "import gi; gi.require_version('AppIndicator3', '0.1'); from gi.repository import AppIndicator3; print('OK')"
```

If error, install:
```bash
sudo dnf install libappindicator-gtk3
```

**Check D-Bus connection**:
```bash
# Should return method information
busctl --user introspect com.claudeisland.Service \
  /com/claudeisland/Service
```

### Hook not working

**Verify hook is installed**:
```bash
ls -la ~/.claude/hooks/claude-island-state.py
cat ~/.claude/settings.json | grep -A 2 claude-island
```

**Test hook script directly**:
```bash
echo '{"type":"SessionStart","session_id":"test"}' | \
  ~/.claude/hooks/claude-island-state.py
```

Should connect to socket and not error.

### No sessions showing

**Check Claude Code is using hooks**:
```bash
# In Claude session, check if hook events appear in backend logs
# Set debug logging:
CLAUDE_ISLAND_LOG_LEVEL=DEBUG uv run claude-island-service
```

**Check conversation files exist**:
```bash
ls -la ~/.claude/sessions/
```

## Expected Behavior

1. **Start backend** → Hook installed, socket created, D-Bus registered
2. **Start applet** → Connects to backend, shows tray icon
3. **Start Claude session** → Backend detects new session, applet updates menu
4. **Use Claude** → Backend tracks tool executions, state changes
5. **Permission request** → Applet shows approval dialog, sends decision back
6. **View session** → Click session in menu, see details

## Next Steps

After confirming basic functionality works:
1. Test conversation parsing (JSONL files)
2. Test file monitoring (make changes to conversation files)
3. Test multiple concurrent sessions
4. Test error handling (kill backend while applet running, etc.)
