# Claude Island for Linux - Implementation Summary

## Recommended Approach: Dual Frontend Architecture

After comprehensive research, the optimal approach is a **three-tier architecture**:

1. **Python Backend Service** (D-Bus provider, universal business logic)
2. **GNOME Shell Extension** (JavaScript/GJS, native GNOME integration)
3. **StatusNotifier Applet** (Python/GTK3, cross-desktop compatibility)

## Why This Approach?

### ✅ Advantages

**Native Integration**:
- GNOME users get deep desktop integration (top bar, overlays, native styling)
- Other desktop users get proper system tray integration

**Code Reuse**:
- Backend service is shared (80% of logic)
- Hook system works universally (port from macOS)
- JSONL parsing, state management, file monitoring all shared

**Desktop Coverage**:
- GNOME: Extension provides best experience
- KDE Plasma, XFCE, MATE, Cinnamon, LXQt: StatusNotifier applet
- All desktops: Same backend, same functionality

**Maintainability**:
- Single source of truth (backend service)
- Frontend is lightweight presentation layer
- Easy to add new frontends (e.g., Qt for KDE natives)

**Distribution**:
- Backend: PyPI package + systemd service
- GNOME Extension: extensions.gnome.org
- Applet: Native packages (RPM, DEB) + Flatpak
- Automatic desktop detection

### ❌ Rejected Alternatives

**Single GTK4 Application with Layer Shell**:
- ❌ Doesn't work on GNOME (Shell owns top bar)
- ❌ Less native feel than extension
- ❌ Wayland layer-shell not universally supported
- ❌ Would need X11 fallback anyway

**GNOME Extension Only**:
- ❌ Excludes 60%+ of Linux desktop users
- ❌ No support for KDE, XFCE, MATE, etc.

**Qt Application with QSystemTrayIcon**:
- ❌ Heavy Qt dependency for simple applet
- ❌ GNOME users need extension anyway
- ❌ Less native GTK integration on GNOME

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Desktop Environment                        │
│                                                               │
│  GNOME: Extension loads       Others: Applet starts          │
│  ┌────────────────────┐       ┌────────────────────┐         │
│  │ GNOME Shell Ext    │       │ StatusNotifier     │         │
│  │ (JavaScript/GJS)   │       │ (Python/GTK3)      │         │
│  │ - Top bar          │       │ - System tray      │         │
│  │ - Overlays         │       │ - GTK windows      │         │
│  └─────────┬──────────┘       └─────────┬──────────┘         │
│            │                            │                     │
│            └─────────D-Bus──────────────┘                     │
└──────────────────────┼───────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────────────┐
│              Backend Service (Python)                         │
│  - Unix socket server (Claude Code CLI hooks)                │
│  - D-Bus service provider (frontends)                        │
│  - State management (sessions, tools, messages)              │
│  - JSONL parsing (conversation files)                        │
│  - File monitoring (inotify)                                 │
│  - Permission approval workflow                              │
└──────────────────────▲───────────────────────────────────────┘
                       │ Unix Socket
┌──────────────────────┴───────────────────────────────────────┐
│              Hook System (Python)                             │
│  ~/.claude/hooks/claude-island-state.py                      │
│  - Captures Claude Code CLI events                           │
│  - Sends via Unix socket                                     │
└───────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Backend Service
- **Language**: Python 3.11+
- **IPC**: Unix domain sockets (hook communication)
- **D-Bus**: GLib/GDBus (frontend communication)
- **File Monitoring**: `watchdog` library (inotify wrapper)
- **Async**: `asyncio` + `gbulb` (GLib event loop)
- **State**: Actor-like pattern (single event processor)

### GNOME Shell Extension
- **Language**: JavaScript (ES6+) with GJS
- **UI**: St (Shell Toolkit) + Clutter
- **D-Bus**: Gio.DBusProxy
- **GNOME Version**: 45+ (ESModules)
- **Distribution**: extensions.gnome.org

### StatusNotifier Applet
- **Language**: Python 3.11+
- **UI**: GTK3 (for compatibility)
- **System Tray**: libayatana-appindicator3
- **Notifications**: libnotify (Notify)
- **D-Bus**: GLib/GDBus (same as backend)
- **Distribution**: RPM/DEB packages, Flatpak

---

## Key Implementation Details

### D-Bus Interface

**Service Name**: `com.claudeisland.Service`
**Object Path**: `/com/claudeisland/Service`

**Methods**:
- `GetSessions() → a{sv}` - Returns all active sessions
- `GetConversation(session_id: s) → aa{sv}` - Returns messages for session
- `SendApprovalDecision(session_id: s, decision: s)` - Send approval response

**Signals**:
- `SessionStateChanged(session_id: s, phase: s)` - Session phase changed
- `PermissionRequest(session_id: s, tool_name: s, params: a{sv})` - Needs approval
- `NewMessage(session_id: s, message: a{sv})` - New conversation message

### Desktop Detection

Backend detects environment on startup:
```python
desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
```

Frontends auto-activate based on desktop:
- GNOME: Extension enabled (installed separately)
- Others: Applet starts (via autostart desktop file)

### Auto-Start Mechanisms

**Backend**:
- D-Bus activation (`.service` file) - starts on first D-Bus call
- Or systemd user service - starts on login

**GNOME Extension**:
- Managed by GNOME Shell (user enables once)

**StatusNotifier Applet**:
- XDG autostart desktop file
- `OnlyShowIn=KDE;XFCE;MATE;Cinnamon;LXQt;` (excludes GNOME)

---

## Implementation Timeline

### Phase 1: Backend Service (3 weeks)
- Week 1: Hook system + Unix socket server
- Week 2: State management + JSONL parsing + file monitoring
- Week 3: D-Bus service provider + testing

### Phase 2: GNOME Shell Extension (3 weeks)
- Week 4: Basic extension + top bar indicator + D-Bus connection
- Week 5: Chat view overlay + approval dialog + styling
- Week 6: Polish + testing + memory leak checks

### Phase 3: StatusNotifier Applet (3 weeks)
- Week 7: System tray indicator + menu + D-Bus connection
- Week 8: GTK chat window + approval dialog
- Week 9: Cross-desktop testing (KDE, XFCE, MATE, Cinnamon, LXQt)

### Phase 4: Integration & Distribution (2-3 weeks)
- Week 10: End-to-end testing + auto-start + configuration
- Week 11: Packaging (PyPI, extensions.gnome.org, RPM, Flatpak)
- Week 12: Documentation + release

**Total**: 10-12 weeks (single full-time developer)

---

## Distribution Strategy

### Backend Service

**PyPI**:
```bash
pip install claude-island-service
```

**Auto-Start via D-Bus Activation**:
```
~/.local/share/dbus-1/services/com.claudeisland.Service.service
```

**Or systemd User Service**:
```
~/.config/systemd/user/claude-island.service
systemctl --user enable --now claude-island
```

### GNOME Shell Extension

**Extensions.gnome.org**:
- Submit ZIP package for review
- Users install via Extensions app or website
- Automatic updates

**Manual**:
```bash
git clone URL ~/.local/share/gnome-shell/extensions/claude-island@namespace
gnome-extensions enable claude-island@namespace
```

### StatusNotifier Applet

**Fedora (Copr)**:
```bash
sudo dnf copr enable user/claude-island
sudo dnf install claude-island-applet
```

**Ubuntu/Debian (PPA)**:
```bash
sudo add-apt-repository ppa:user/claude-island
sudo apt install claude-island-applet
```

**Arch (AUR)**:
```bash
yay -S claude-island-applet
```

**Auto-Start**:
Desktop file installed to `/etc/xdg/autostart/` or `~/.config/autostart/`

### Unified Flatpak (Optional)

Single Flatpak bundle that:
- Includes backend service
- Includes StatusNotifier applet
- Detects desktop environment
- On GNOME: Prompts to install extension from extensions.gnome.org
- On others: Starts applet

```bash
flatpak install flathub com.claudeisland.App
```

---

## Testing Strategy

### Backend Testing
- Unit tests for state management
- Integration tests with mock hook events
- Test JSONL parsing with real conversation files
- Test file monitoring with rapid changes
- D-Bus interface testing

### GNOME Extension Testing
- Test on GNOME 45, 46, 47
- Enable/disable cycles (memory leak detection)
- Test with multiple concurrent sessions
- Test approval workflow
- Test on X11 and Wayland

### Applet Testing
- Test on KDE Plasma (X11 + Wayland)
- Test on XFCE (X11)
- Test on MATE (X11)
- Test on Cinnamon (X11)
- Test on LXQt (X11 + Wayland)
- Verify system tray icon rendering
- Test HiDPI displays

### Cross-Desktop Compatibility
- Verify D-Bus communication on all desktops
- Test permission approval on all desktops
- Test notifications on all desktops
- Verify auto-start mechanisms

---

## Known Limitations & Future Work

### Current Limitations

**GNOME**:
- Extension requires manual installation from extensions.gnome.org
- Extension needs update for each major GNOME version
- No API stability guarantees

**StatusNotifier**:
- Requires AppIndicator extension on GNOME (if used there)
- GTK3-based (not GTK4) for broader compatibility
- Less visually integrated than native desktop solutions

**General**:
- No macOS-style "notch" on Linux desktops
- Backend service uses polling for some file operations
- Python dependency (not a single binary)

### Future Enhancements

**Version 2.0+**:
- Qt6-based applet for native KDE Plasma integration
- XFCE panel plugin for deeper integration
- KDE Plasma plasmoid for system tray
- Electron/Tauri version for web tech enthusiasts
- Custom Wayland overlay compositor for "floating island" effect
- Session export (markdown, JSON)
- Statistics dashboard
- Command palette (keyboard shortcuts)
- Theming support

**Native Desktop Plugins**:
- XFCE Panel Plugin (C + GTK3)
- KDE Plasmoid (QML + JavaScript)
- MATE Panel Applet (C/Python + GTK3)
- Cinnamon Applet (JavaScript)

---

## Comparison with Original macOS Version

| Aspect | macOS (Original) | Linux (This Approach) |
|--------|------------------|----------------------|
| **Architecture** | Monolithic app | Three-tier (backend + 2 frontends) |
| **Language** | Swift | Python (backend) + JS/Python (frontends) |
| **UI Framework** | SwiftUI | St/Clutter (GNOME) + GTK3 (others) |
| **Window System** | AppKit (NSPanel) | GNOME Shell overlays + GTK windows |
| **IPC** | Unix socket only | Unix socket + D-Bus |
| **File Monitoring** | FSEvents | inotify (watchdog) |
| **Markdown** | swift-markdown | Pango markup / HTML |
| **Updates** | Sparkle | Flatpak / package manager |
| **Visual Style** | Dynamic Island | Top bar + overlays (GNOME) / Tray (others) |
| **Code Reuse** | N/A | ~80% (backend + hook) |
| **Desktop Coverage** | macOS only | GNOME + KDE + XFCE + MATE + Cinnamon + LXQt |

---

## Quick Start for Developers

### Setup Development Environment

```bash
# Install dependencies (Fedora)
sudo dnf install python3-devel python3-pip python3-gobject gtk3-devel \
                 libappindicator-gtk3-devel libnotify-devel

# Install Python packages
pip install watchdog psutil pygobject

# For GNOME extension development
sudo dnf install gnome-shell-extension-tool gjs
```

### Clone and Run

```bash
# Backend
cd claude-island-service
pip install -e .
python -m claude_island_service

# GNOME Extension (separate terminal)
cd claude-island-extension
cp -r . ~/.local/share/gnome-shell/extensions/claude-island@namespace
gnome-extensions enable claude-island@namespace
# Restart GNOME Shell: Alt+F2 → 'r' (X11) or logout/login (Wayland)

# StatusNotifier Applet (separate terminal, non-GNOME desktop)
cd claude-island-applet
pip install -e .
python -m claude_island_applet
```

### Test with Claude Code CLI

```bash
# Start a Claude Code session
claude

# Hook should be auto-installed on first run
# Check backend logs to see events flowing
```

---

## Conclusion

The dual-frontend architecture provides:

✅ **Best of Both Worlds**: Native GNOME integration + cross-desktop support
✅ **Efficient Development**: Shared backend (80% of code)
✅ **User Choice**: Desktop-appropriate experience for everyone
✅ **Easy Maintenance**: Single source of truth
✅ **Scalable**: Easy to add new frontends

This approach is **production-ready**, **maintainable**, and provides the best user experience across the diverse Linux desktop ecosystem.

**Next Steps**:
1. Review this document and GNOME_EXTENSION_APPROACH.md
2. Start with Phase 1 (backend service)
3. Create proof-of-concept with basic D-Bus communication
4. Iterate on frontends once backend is stable
