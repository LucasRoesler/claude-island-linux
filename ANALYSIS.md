# Claude Island for Linux - Technical Analysis and Implementation Plan

## Executive Summary

Claude Island is a macOS menu bar application that provides Dynamic Island-style notifications for Claude Code CLI sessions. This document analyzes the original implementation and provides a comprehensive plan for creating a similar application for Linux, specifically targeting Fedora and GNOME desktop environment.

## Table of Contents

1. [Original Application Analysis](#original-application-analysis)
2. [Core Functionality](#core-functionality)
3. [Technical Architecture](#technical-architecture)
4. [macOS-Specific Features](#macos-specific-features)
5. [Linux/GNOME OS Features Required](#linuxgnome-os-features-required)
6. [Technology Stack for Linux](#technology-stack-for-linux)
7. [Implementation Plan](#implementation-plan)
8. [Challenges and Solutions](#challenges-and-solutions)

---

## Original Application Analysis

### What Claude Island Does

Claude Island is a companion application for Claude Code CLI that provides:

- **Real-time Session Monitoring**: Tracks multiple concurrent Claude Code sessions with visual status indicators
- **Permission Management**: Approve/deny tool execution requests directly from a notch-style overlay without switching to terminal
- **Chat History Viewing**: Full conversation history with markdown rendering for each Claude session
- **Automatic Hook Installation**: Installs Claude Code hooks to capture session events on first launch
- **Session State Tracking**: Monitors processing, tool execution, approval waiting, and completion states
- **Multi-screen Support**: Can display on different screens in multi-monitor setups

---

## Core Functionality

### 1. Hook System

**Python Hook Script** (`claude-island-state.py`):
- Installed to `~/.claude/hooks/`
- Captures session events from Claude Code CLI
- Sends events via Unix domain socket to `/tmp/claude-island.sock`
- Waits for user decisions on permission requests (300-second timeout)
- Detects TTY using parent process inspection or stdin/stdout fallback

**Registered Events**:
- `UserPromptSubmit`: When user submits a prompt
- `PreToolUse`: Before a tool is executed
- `PostToolUse`: After a tool completes
- `PermissionRequest`: When approval is needed
- `Notification`: General notifications
- `Stop`, `SubagentStop`: Session termination
- `SessionStart`, `SessionEnd`: Session lifecycle
- `PreCompact`: Before conversation compaction

### 2. Inter-Process Communication

**Unix Domain Socket Server**:
- Listens on `/tmp/claude-island.sock`
- Non-blocking I/O using GCD's DispatchSource (macOS)
- Maintains correlation between PreToolUse and PermissionRequest events
- Bidirectional communication: receives events, sends user decisions

**Event Flow**:
```
Claude Code CLI → Hook Script (Python) → Unix Socket → Server → State Manager → UI Updates
```

### 3. Session Monitoring

**Conversation File Parsing**:
- Monitors JSONL files in `~/.claude/sessions/{session_id}/conversation.jsonl`
- Incremental parsing for efficiency (only reads new lines)
- Parses conversation metadata, messages, tool uses, and results
- Supports subagent files for nested tool invocations
- Handles `/clear` command detection for history reset

**State Management**:
- Actor-based state store (Swift concurrency model)
- Single `process()` method for all state mutations
- Publishes state changes via reactive framework
- Tracks sessions, tools, subagents, and conversation history

### 4. User Interface

**Dynamic Island-Style Notch**:
- Transparent overlay window positioned over MacBook Pro notch
- Three states: closed (compact), opened (expanded), popping (notification)
- Hover expansion: 1-second hover triggers automatic expansion
- Click-through behavior when closed (ignores mouse events)

**Chat Interface**:
- Inverted scrolling with latest messages at bottom
- Autoscroll system with pause when user scrolls up
- Markdown rendering for rich text formatting
- Structured display for different tool types
- Collapsible thinking blocks
- Status badges for tool execution states

---

## Technical Architecture

### Components

1. **Hook System** (Python)
   - Event capture from Claude Code CLI
   - Unix socket client
   - TTY detection and tmux integration

2. **Socket Server** (Swift on macOS)
   - Unix domain socket server
   - Non-blocking I/O
   - Event routing and response handling

3. **State Management** (Swift)
   - Central state store with actor model
   - Reactive state publishing (Combine framework)
   - Session and conversation tracking

4. **File Synchronization**
   - JSONL file monitoring (FSEvents on macOS)
   - Incremental parsing
   - Debounced updates (100ms intervals)

5. **UI Layer** (SwiftUI)
   - Custom transparent window overlay
   - Dynamic click-through behavior
   - Event reposting using CGEvent
   - Reactive state binding

### Data Flow

```
┌─────────────────┐
│  Claude Code    │
│      CLI        │
└────────┬────────┘
         │ Hook Events
         ▼
┌─────────────────┐
│  Python Hook    │
│     Script      │
└────────┬────────┘
         │ Unix Socket
         ▼
┌─────────────────┐
│  Socket Server  │
└────────┬────────┘
         │ Events
         ▼
┌─────────────────┐       ┌─────────────────┐
│  State Manager  │◄─────►│  File Monitor   │
└────────┬────────┘       └─────────────────┘
         │ State Changes        │ JSONL Files
         ▼                      │
┌─────────────────┐             │
│   UI Layer      │             │
│  (SwiftUI)      │◄────────────┘
└─────────────────┘
```

---

## macOS-Specific Features

### Window Management

**APIs Used**:
- `NSPanel` with custom configuration (borderless, non-activating, transparent)
- `NSWindow.Level.mainMenu + 3` to position above menu bar
- `NSWindow.CollectionBehavior.canJoinAllSpaces` for all workspaces
- `NSWindow.CollectionBehavior.stationary` to prevent movement

**Notch Detection**:
- `NSScreen.auxiliaryTopLeftArea` and `NSScreen.auxiliaryTopRightArea`
- Calculates notch rectangle from auxiliary areas

### Event Handling

**Mouse Event Management**:
- `NSEvent.addGlobalMonitorForEvents` for outside-app events
- `NSEvent.addLocalMonitorForEvents` for inside-app events
- `CGEvent` for event reposting with coordinate conversion
- Mouse event throttling (50ms intervals)

**Click-Through Behavior**:
- Dynamic `ignoreMouseEvents` based on panel state
- Event coordinate testing to determine if click is inside content
- Event reposting to allow clicks to pass through to underlying windows

### Display Management

**Multi-Screen Support**:
- `NSScreen` API for screen enumeration and geometry
- Screen change notifications for repositioning
- Coordinate system conversion (AppKit Y-up vs CoreGraphics Y-down)

### File System

**File Monitoring**:
- `DispatchSource.makeFileSystemObjectSource` for file changes
- Monitors JSONL files for new content
- Debounced updates to prevent excessive reads

**Hook Installation**:
- `FileManager` for file operations
- Modifies `~/.claude/settings.json` (JSON parsing/writing)
- Sets POSIX permissions (0o755 for executable scripts)

### Process Management

**Terminal Integration**:
- `Process` API for executing shell commands
- Finding Python interpreter in PATH
- Executing tmux commands (list sessions, send keys, switch focus)
- TTY detection via parent process inspection

### Dependencies

**Swift Package Manager**:
1. **swift-markdown** (v0.5.0+): Markdown parsing and rendering
2. **Sparkle** (v2.0.0+): Automatic application updates
3. **Mixpanel-swift**: Anonymous analytics tracking

**System Frameworks**:
- AppKit/NSKit: Window management
- CoreGraphics: Low-level graphics and events
- Foundation: File system and JSON
- IOKit: Hardware UUID detection

### Security Model

**Entitlements**:
- Sandbox: **DISABLED** (needs filesystem access, socket creation, process execution)
- User-selected files: Read-only access enabled

**Requirements**:
- Access to `~/.claude/` directory
- Create Unix socket at `/tmp/claude-island.sock`
- Execute shell commands (Python, tmux)
- Monitor arbitrary session files

---

## Linux/GNOME OS Features Required

### 1. Window Management

#### Wayland (Primary Target)

**Layer Shell Protocol**:
- `zwlr_layer_shell_v1` for overlay windows
- Layer specification: overlay, top, bottom, background
- Anchor edges and set exclusive zones
- Keyboard interactivity control

**Implementation Library**:
- GTK4 with `gtk-layer-shell` library
- Provides GTK integration with layer-shell protocol
- Handles Wayland-specific window positioning

**Features Needed**:
- Create overlay window above all other windows
- Position window at top-center of screen
- Transparent window with custom shape
- Click-through behavior when closed
- Capture mouse events when opened

#### X11 (Fallback Support)

**Window Types and Hints**:
- `_NET_WM_WINDOW_TYPE_DOCK` for panel-like behavior
- `_NET_WM_STATE_ABOVE` to stay above other windows
- Override-redirect windows for positioning control

**Features Needed**:
- Manual window positioning at top of screen
- Input shape extension for click-through
- Composite extension for transparency

### 2. Desktop Integration

#### GNOME Shell

**Extension System** (Optional):
- JavaScript-based extensions for GNOME Shell
- Top bar integration via PanelMenu
- System status area indicators
- Quick settings integration

**D-Bus Integration**:
- `org.gnome.Shell` interface for shell interaction
- Notification daemon interface
- Session manager integration

**GSettings/DConf**:
- Application settings storage
- GNOME-standard configuration system

#### Desktop Notifications

**libnotify/D-Bus**:
- `org.freedesktop.Notifications` interface
- Notification with actions (approve/deny buttons)
- Urgency levels and categories
- Notification persistence

### 3. File System Monitoring

#### inotify API

**Linux Kernel Feature**:
- File and directory monitoring
- Events: `IN_MODIFY`, `IN_CREATE`, `IN_CLOSE_WRITE`
- Watch descriptors for monitored paths

**Implementation Options**:
- **Python**: `watchdog` library (cross-platform abstraction)
- **Rust**: `notify` crate (cross-platform)
- **C/C++**: Direct inotify API usage
- **GLib**: `GFileMonitor` (platform-agnostic)

**Features Needed**:
- Monitor `~/.claude/sessions/*/conversation.jsonl`
- Detect file modifications in real-time
- Debounced updates (avoid excessive reads)

### 4. Inter-Process Communication

#### Unix Domain Sockets

**Same as macOS**:
- Create socket at `/tmp/claude-island.sock`
- Non-blocking I/O using poll/epoll
- Bidirectional communication

**Implementation Options**:
- Python: `socket` module (standard library)
- Rust: `tokio` async runtime + Unix socket support
- C/C++: POSIX socket API
- GLib: `GSocketService` and `GSocketConnection`

#### D-Bus (Alternative/Additional)

**Session Bus**:
- Well-known bus name: `com.claudeisland.App`
- Object path: `/com/claudeisland/App`
- Interface for method calls and signals

**Advantages**:
- Standard Linux IPC mechanism
- Desktop integration benefits
- Service activation (auto-start on method call)
- Introspection and debugging tools

### 5. Process Management

#### Procfs (/proc)

**TTY Detection**:
- Read `/proc/<pid>/fd/0` symlink (stdin)
- Check if points to `/dev/pts/*` or `/dev/tty*`
- Read `/proc/<pid>/stat` for controlling terminal

**Parent Process Inspection**:
- Read `/proc/<pid>/stat` for parent PID (PPID)
- Walk up process tree to find tmux/terminal
- Read `/proc/<pid>/cmdline` for process name

#### Process Execution

**Subprocess Management**:
- Python: `subprocess` module
- Rust: `std::process::Command`
- C/C++: `fork()`/`exec()` family
- GLib: `GSubprocess`

**Features Needed**:
- Execute Python hook script
- Run tmux commands for session management
- Find Python interpreter in PATH

### 6. Graphics and Rendering

#### GTK4 + libadwaita

**Modern GNOME Toolkit**:
- Hardware-accelerated rendering
- CSS-based styling
- Adaptive design patterns
- Built-in animations

**Transparency and Compositing**:
- `gtk_widget_set_opacity()`
- CSS `opacity` and `background` properties
- Custom drawing with Cairo

**Markdown Rendering**:
- No built-in markdown widget in GTK
- Options:
  - WebKitGTK for HTML rendering (convert markdown to HTML)
  - Custom text view with Pango markup
  - Third-party libraries (gtksourceview with markdown highlighting)

#### Qt6 (Alternative)

**Cross-Desktop Toolkit**:
- Qt Quick for declarative UI (similar to SwiftUI)
- QML for UI description
- Built-in markdown support in `QTextDocument`

**Transparency**:
- `Qt::WindowTransparentForInput` flag
- `setWindowFlags()` for frameless window
- Compositor support required

### 7. System Integration

#### XDG Base Directory Specification

**Configuration Storage**:
- `$XDG_CONFIG_HOME/claude-island/` or `~/.config/claude-island/`
- Settings, preferences, state files

**Cache Storage**:
- `$XDG_CACHE_HOME/claude-island/` or `~/.cache/claude-island/`
- Temporary data, logs

#### Systemd User Services (Optional)

**Auto-Start**:
- systemd user service unit
- Socket activation for on-demand start
- Dependency management

**Desktop Entry**:
- `~/.local/share/applications/claude-island.desktop`
- GNOME auto-start via `~/.config/autostart/`

### 8. Security Considerations

#### AppArmor/SELinux

**Fedora Security**:
- SELinux enabled by default
- May need policy adjustments for socket creation
- File access permissions for `~/.claude/`

#### Flatpak (If Distributed via Flathub)

**Permissions Required**:
- `--filesystem=home` (access to `~/.claude/`)
- `--socket=wayland` and `--socket=fallback-x11`
- `--socket=session-bus` (D-Bus access)
- `--talk-name=org.freedesktop.Notifications`
- `--share=network` (for updates, if using Sparkle equivalent)

**Portal Access**:
- File chooser portal (if needed)
- Notification portal

---

## Technology Stack for Linux

### Recommended: GTK4 + Python

**Rationale**:
- Native GNOME integration with libadwaita
- Python for rapid development (matches hook script language)
- Excellent GTK bindings via PyGObject (GObject Introspection)
- Cross-platform potential (GTK works on all major platforms)

**Stack**:
- **Language**: Python 3.11+
- **UI Framework**: GTK4 (via PyGObject)
- **Design**: libadwaita for GNOME design patterns
- **IPC**: Unix sockets (standard library) + D-Bus (dasbus/pydbus)
- **File Monitoring**: `watchdog` library
- **Async**: `asyncio` + `gbulb` (GLib event loop integration)
- **Markdown**: `markdown` + WebKitGTK or custom Pango rendering
- **Process Management**: `subprocess` + `psutil`

### Alternative: Rust + GTK4

**Rationale**:
- Performance and memory safety
- Growing Rust/GTK ecosystem (gtk-rs)
- Modern language with excellent tooling

**Stack**:
- **Language**: Rust 1.70+
- **UI Framework**: gtk4-rs + libadwaita-rs
- **IPC**: tokio + tokio-uds for Unix sockets
- **File Monitoring**: `notify` crate
- **Async**: tokio runtime
- **Markdown**: pulldown-cmark + custom rendering
- **Process Management**: `std::process::Command`

### Alternative: Electron/Tauri

**Rationale**:
- Web technologies (HTML/CSS/JavaScript/TypeScript)
- Cross-platform by design
- Rich UI possibilities

**Stack**:
- **Framework**: Tauri (Rust backend, web frontend)
- **Frontend**: React/Vue/Svelte + TypeScript
- **Styling**: Tailwind CSS or custom CSS
- **Markdown**: react-markdown or marked.js
- **IPC**: Tauri commands or Node.js (Electron)

**Drawbacks**:
- Larger application size
- Less native GNOME integration
- Wayland layer-shell support requires custom implementation

### Decision Matrix

| Criteria | GTK4 + Python | Rust + GTK4 | Electron/Tauri |
|----------|---------------|-------------|----------------|
| Native GNOME Integration | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Development Speed | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Performance | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Memory Usage | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| UI Flexibility | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Packaging/Distribution | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Cross-Platform | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Learning Curve | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**Recommendation**: Start with **GTK4 + Python** for rapid prototyping and native GNOME integration. Consider Rust port later for performance if needed.

---

## Implementation Plan

### Phase 1: Foundation (Week 1-2)

#### 1.1 Project Setup

**Tasks**:
- Initialize Git repository
- Set up Python project structure with proper packaging
- Configure development environment (virtual environment, dependencies)
- Create basic GTK4 application skeleton
- Set up logging and error handling

**Deliverables**:
- Project repository with README
- `pyproject.toml` or `setup.py` with dependencies
- Basic GTK4 window that launches

**Dependencies**:
```
PyGObject >= 3.42
pygobject-stubs
libadwaita >= 1.2
watchdog >= 3.0
psutil >= 5.9
```

#### 1.2 Hook System (Python Script)

**Tasks**:
- Port `claude-island-state.py` to Linux
- Implement TTY detection using `/proc` filesystem
- Test with Claude Code CLI
- Add error handling and logging
- Implement socket communication

**TTY Detection Logic**:
```python
def detect_tty():
    pid = os.getpid()
    ppid = os.getppid()

    # Check stdin
    stdin_stat = os.fstat(0)
    if stat.S_ISCHR(stdin_stat.st_mode):
        return True

    # Walk up process tree
    while ppid > 1:
        cmdline_path = f"/proc/{ppid}/cmdline"
        if os.path.exists(cmdline_path):
            with open(cmdline_path, 'r') as f:
                cmdline = f.read().replace('\x00', ' ')
                if 'tmux' in cmdline or 'gnome-terminal' in cmdline:
                    return True

        # Get parent's parent
        stat_path = f"/proc/{ppid}/stat"
        with open(stat_path, 'r') as f:
            stats = f.read().split()
            ppid = int(stats[3])  # PPID is 4th field

    return False
```

**Deliverables**:
- Working hook script that sends events via Unix socket
- TTY detection working in various terminal environments
- Integration with Claude Code CLI hooks

#### 1.3 Unix Socket Server

**Tasks**:
- Implement Unix domain socket server
- Create event parsing and routing
- Handle bidirectional communication (receive events, send responses)
- Implement non-blocking I/O with asyncio
- Add connection management (multiple concurrent clients)

**Socket Server Structure**:
```python
import asyncio
import socket
import json
from pathlib import Path

class HookSocketServer:
    def __init__(self, socket_path="/tmp/claude-island.sock"):
        self.socket_path = socket_path
        self.server = None
        self.event_handlers = []

    async def start(self):
        # Remove existing socket
        Path(self.socket_path).unlink(missing_ok=True)

        # Create server
        self.server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )

    async def handle_client(self, reader, writer):
        # Read event data
        data = await reader.read(65536)
        event = json.loads(data.decode())

        # Route event to handlers
        response = await self.process_event(event)

        # Send response if needed
        if response:
            writer.write(json.dumps(response).encode())
            await writer.drain()

        writer.close()
```

**Deliverables**:
- Working Unix socket server
- Event routing system
- Integration tests with hook script

### Phase 2: Core Logic (Week 3-4)

#### 2.1 State Management

**Tasks**:
- Design state model (sessions, tools, messages)
- Implement session store with proper synchronization
- Create event processing pipeline
- Add state change notifications
- Implement session lifecycle tracking

**State Model**:
```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class SessionPhase(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    RUNNING_TOOL = "running_tool"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class Tool:
    name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[dict] = None

@dataclass
class Session:
    session_id: str
    phase: SessionPhase
    active_tool: Optional[Tool] = None
    pending_approval: Optional[dict] = None
    tools: List[Tool] = field(default_factory=list)
    conversation: List[dict] = field(default_factory=list)

class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.observers = []

    def process_event(self, event: dict):
        session_id = event.get('session_id')
        event_type = event.get('type')

        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id, SessionPhase.IDLE)

        session = self.sessions[session_id]

        # Update state based on event
        if event_type == 'PreToolUse':
            session.phase = SessionPhase.RUNNING_TOOL
            session.active_tool = Tool(event['tool_name'], 'running', datetime.now())
        elif event_type == 'PermissionRequest':
            session.phase = SessionPhase.WAITING_APPROVAL
            session.pending_approval = event
        # ... handle other event types

        self.notify_observers(session)

    def notify_observers(self, session: Session):
        for observer in self.observers:
            observer(session)
```

**Deliverables**:
- Complete state model
- Event processing logic
- Observer pattern for UI updates

#### 2.2 JSONL File Parsing

**Tasks**:
- Implement conversation file parser
- Support incremental parsing (only read new lines)
- Parse different message types (user, assistant, tool, thinking)
- Handle subagent files
- Detect `/clear` commands
- Add file position tracking for efficient re-reading

**Parser Implementation**:
```python
import json
from pathlib import Path

class ConversationParser:
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.conversation_file = session_dir / "conversation.jsonl"
        self.last_position = 0

    def parse_incremental(self) -> List[dict]:
        if not self.conversation_file.exists():
            return []

        new_messages = []
        with open(self.conversation_file, 'r') as f:
            # Seek to last position
            f.seek(self.last_position)

            for line in f:
                if line.strip():
                    message = json.loads(line)
                    new_messages.append(message)

            # Update position
            self.last_position = f.tell()

        return new_messages

    def parse_full(self) -> List[dict]:
        self.last_position = 0
        return self.parse_incremental()
```

**Deliverables**:
- JSONL parser with incremental reading
- Message type classification
- Integration with state management

#### 2.3 File Monitoring

**Tasks**:
- Implement file watcher for `~/.claude/sessions/`
- Detect new session directories
- Monitor conversation.jsonl modifications
- Implement debouncing (avoid excessive updates)
- Handle file deletion/recreation

**File Monitor Implementation**:
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
from pathlib import Path

class ConversationFileHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self.debounce_tasks = {}

    def on_modified(self, event):
        if event.src_path.endswith('conversation.jsonl'):
            # Debounce: wait 100ms before processing
            path = event.src_path
            if path in self.debounce_tasks:
                self.debounce_tasks[path].cancel()

            async def debounced_callback():
                await asyncio.sleep(0.1)
                await self.callback(path)

            task = asyncio.create_task(debounced_callback())
            self.debounce_tasks[path] = task

class FileMonitor:
    def __init__(self, sessions_dir: Path, callback):
        self.sessions_dir = sessions_dir
        self.callback = callback
        self.observer = Observer()

    def start(self):
        handler = ConversationFileHandler(self.callback)
        self.observer.schedule(handler, str(self.sessions_dir), recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
```

**Deliverables**:
- Working file monitoring system
- Debounced updates
- Integration with parser and state management

### Phase 3: User Interface (Week 5-7)

#### 3.1 Basic Window Setup

**Tasks**:
- Create GTK4 application with libadwaita
- Implement transparent window
- Position window at top-center of screen
- Handle Wayland (layer-shell) and X11 (override-redirect)
- Implement click-through behavior

**GTK4 Window Setup**:
```python
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Adw, GtkLayerShell, Gdk

class ClaudeIslandWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)

        # Set up layer shell (Wayland)
        if GtkLayerShell.is_supported():
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, False)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, False)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        # Transparent window
        self.set_decorated(False)

        # CSS for transparency
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        window {
            background-color: transparent;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def set_click_through(self, enabled: bool):
        region = cairo.Region() if enabled else None
        self.set_input_region(region)
```

**Deliverables**:
- Transparent overlay window
- Proper positioning on Wayland and X11
- Click-through functionality

#### 3.2 Notch-Style UI Component

**Tasks**:
- Design compact "closed" state UI
- Design expanded "opened" state UI
- Implement smooth animations between states
- Add hover detection with timer
- Create status indicators (processing spinner, checkmark, etc.)

**UI State Machine**:
```python
from enum import Enum

class NotchState(Enum):
    CLOSED = "closed"
    OPENED = "opened"
    POPPING = "popping"

class NotchView(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.state = NotchState.CLOSED

        # Closed view (compact)
        self.closed_view = self.create_closed_view()

        # Opened view (expanded)
        self.opened_view = self.create_opened_view()

        # Initially show closed view
        self.append(self.closed_view)

        # Hover detection
        self.hover_controller = Gtk.EventControllerMotion()
        self.hover_controller.connect('enter', self.on_hover_enter)
        self.hover_controller.connect('leave', self.on_hover_leave)
        self.add_controller(self.hover_controller)

        self.hover_timer = None

    def create_closed_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_size_request(200, 40)
        box.add_css_class('notch-closed')

        # Status indicator
        spinner = Gtk.Spinner()
        box.append(spinner)

        # Session count
        label = Gtk.Label(label="2 sessions")
        box.append(label)

        return box

    def create_opened_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_size_request(600, 580)
        box.add_css_class('notch-opened')

        # Session list
        sessions_list = self.create_sessions_list()
        box.append(sessions_list)

        return box

    def on_hover_enter(self, controller, x, y):
        # Start 1-second timer
        self.hover_timer = GLib.timeout_add(1000, self.expand)

    def on_hover_leave(self, controller):
        # Cancel timer if exists
        if self.hover_timer:
            GLib.source_remove(self.hover_timer)
            self.hover_timer = None

    def expand(self):
        if self.state == NotchState.CLOSED:
            self.transition_to_opened()
        return False  # Don't repeat timer

    def transition_to_opened(self):
        self.state = NotchState.OPENED
        self.remove(self.closed_view)
        self.append(self.opened_view)
        # TODO: Add animation
```

**CSS Styling**:
```css
.notch-closed {
    background-color: rgba(30, 30, 30, 0.9);
    border-radius: 24px;
    padding: 8px 16px;
}

.notch-opened {
    background-color: rgba(30, 30, 30, 0.95);
    border-radius: 30px;
    padding: 16px;
}

.notch-closed, .notch-opened {
    transition: all 500ms cubic-bezier(0.5, 0.85, 0.5, 1);
}
```

**Deliverables**:
- Notch-style UI component with states
- Smooth animations
- Hover expansion behavior

#### 3.3 Session List View

**Tasks**:
- Display list of active sessions
- Show session status (idle, processing, waiting approval, etc.)
- Implement session selection
- Add status indicators per session
- Handle empty state (no sessions)

**Session List Implementation**:
```python
class SessionListView(Gtk.ScrolledWindow):
    def __init__(self, session_store):
        super().__init__()
        self.session_store = session_store

        # List box for sessions
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect('row-activated', self.on_session_selected)
        self.set_child(self.list_box)

        # Observe session store
        session_store.observers.append(self.update_sessions)

    def update_sessions(self, session):
        # Clear list
        while (child := self.list_box.get_first_child()):
            self.list_box.remove(child)

        # Add session rows
        for session_id, session in self.session_store.sessions.items():
            row = self.create_session_row(session)
            self.list_box.append(row)

    def create_session_row(self, session):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Status indicator
        status_icon = self.get_status_icon(session.phase)
        box.append(status_icon)

        # Session info
        label = Gtk.Label(label=f"Session {session.session_id[:8]}")
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        box.append(label)

        # Current tool
        if session.active_tool:
            tool_label = Gtk.Label(label=session.active_tool.name)
            tool_label.add_css_class('dim-label')
            box.append(tool_label)

        row.set_child(box)
        return row

    def get_status_icon(self, phase):
        if phase == SessionPhase.PROCESSING:
            spinner = Gtk.Spinner()
            spinner.start()
            return spinner
        elif phase == SessionPhase.COMPLETED:
            icon = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            return icon
        elif phase == SessionPhase.WAITING_APPROVAL:
            icon = Gtk.Image.new_from_icon_name('dialog-question-symbolic')
            return icon
        else:
            return Gtk.Box()  # Empty placeholder
```

**Deliverables**:
- Session list with status indicators
- Session selection handling
- Dynamic updates from state store

#### 3.4 Chat View

**Tasks**:
- Implement scrolling message list
- Render different message types (user, assistant, tool, thinking)
- Add markdown rendering for assistant messages
- Implement autoscroll with pause detection
- Add "new messages" badge when scrolled up
- Create collapsible thinking blocks
- Style tool result displays

**Chat View Structure**:
```python
class ChatView(Gtk.Box):
    def __init__(self, session):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.session = session

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.append(scrolled)

        # Message list
        self.message_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.message_list.set_margin_start(12)
        self.message_list.set_margin_end(12)
        self.message_list.set_margin_top(12)
        self.message_list.set_margin_bottom(12)
        scrolled.set_child(self.message_list)

        # Scroll controller
        self.vadjustment = scrolled.get_vadjustment()
        self.vadjustment.connect('changed', self.on_scroll_changed)
        self.vadjustment.connect('value-changed', self.on_scroll_value_changed)

        self.autoscroll = True
        self.new_message_count = 0

        # New message badge
        self.badge = Gtk.Button(label="↓ New messages")
        self.badge.add_css_class('suggested-action')
        self.badge.connect('clicked', self.scroll_to_bottom)
        self.badge.set_visible(False)
        self.append(self.badge)

        # Input area
        input_box = self.create_input_area()
        self.append(input_box)

    def add_message(self, message):
        widget = self.create_message_widget(message)
        self.message_list.append(widget)

        if self.autoscroll:
            self.scroll_to_bottom()
        else:
            self.new_message_count += 1
            self.badge.set_label(f"↓ {self.new_message_count} new messages")
            self.badge.set_visible(True)

    def create_message_widget(self, message):
        msg_type = message.get('type')

        if msg_type == 'user':
            return self.create_user_message(message)
        elif msg_type == 'assistant':
            return self.create_assistant_message(message)
        elif msg_type == 'tool_use':
            return self.create_tool_message(message)
        elif msg_type == 'thinking':
            return self.create_thinking_message(message)

    def create_assistant_message(self, message):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_halign(Gtk.Align.START)

        # Indicator dot
        indicator = Gtk.DrawingArea()
        indicator.set_size_request(8, 8)
        indicator.set_draw_func(self.draw_indicator)
        box.append(indicator)

        # Message content with markdown
        content = message.get('content', '')
        text_view = self.render_markdown(content)
        box.append(text_view)

        return box

    def render_markdown(self, markdown_text):
        # Option 1: Use WebKitGTK
        from gi.repository import WebKit
        webview = WebKit.WebView()

        # Convert markdown to HTML
        import markdown
        html = markdown.markdown(markdown_text)
        webview.load_html(f"<html><body>{html}</body></html>", None)

        return webview

        # Option 2: Use Pango markup (limited markdown support)
        # label = Gtk.Label()
        # pango_markup = self.markdown_to_pango(markdown_text)
        # label.set_markup(pango_markup)
        # return label

    def create_tool_message(self, message):
        tool_name = message.get('name', 'Unknown')
        status = message.get('status', 'running')

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class('tool-message')

        # Tool header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        icon = self.get_tool_icon(status)
        header.append(icon)

        label = Gtk.Label(label=tool_name)
        label.add_css_class('tool-name')
        header.append(label)

        box.append(header)

        # Tool result (if available)
        if 'result' in message:
            result_widget = self.create_tool_result(tool_name, message['result'])
            box.append(result_widget)

        return box
```

**Deliverables**:
- Complete chat view with message types
- Markdown rendering
- Autoscroll system with badge
- Tool result displays

#### 3.5 Approval Interface

**Tasks**:
- Create permission request UI
- Add approve/deny buttons
- Show tool details and parameters
- Implement approval decision sending
- Add timeout indicator

**Approval Bar Implementation**:
```python
class ApprovalBar(Gtk.Box):
    def __init__(self, approval_request, on_decision):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class('approval-bar')
        self.approval_request = approval_request
        self.on_decision = on_decision

        # Tool info
        tool_name = approval_request.get('tool_name', 'Unknown')
        label = Gtk.Label(label=f"Approve {tool_name}?")
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.START)
        self.append(label)

        # Tool parameters (collapsible)
        expander = Gtk.Expander(label="Details")
        params_text = json.dumps(approval_request.get('parameters', {}), indent=2)
        params_label = Gtk.Label(label=params_text)
        params_label.set_selectable(True)
        expander.set_child(params_label)
        self.append(expander)

        # Buttons
        deny_button = Gtk.Button(label="Deny")
        deny_button.add_css_class('destructive-action')
        deny_button.connect('clicked', lambda _: self.send_decision('deny'))
        self.append(deny_button)

        approve_button = Gtk.Button(label="Approve")
        approve_button.add_css_class('suggested-action')
        approve_button.connect('clicked', lambda _: self.send_decision('allow'))
        self.append(approve_button)

    def send_decision(self, decision):
        self.on_decision(decision)
        self.set_visible(False)
```

**Deliverables**:
- Approval interface with buttons
- Tool parameter display
- Decision handling

### Phase 4: Integration and Polish (Week 8-9)

#### 4.1 Application Integration

**Tasks**:
- Connect all components (socket server, state management, file monitor, UI)
- Implement application lifecycle (startup, shutdown)
- Add logging throughout application
- Create configuration system
- Handle edge cases and errors

**Main Application**:
```python
class ClaudeIslandApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.claudeisland.App')

        # Core components
        self.session_store = SessionStore()
        self.socket_server = HookSocketServer()
        self.file_monitor = FileMonitor(
            Path.home() / '.claude' / 'sessions',
            self.on_file_changed
        )

        # UI
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = ClaudeIslandWindow(self)
            self.window.present()

        # Start services
        asyncio.create_task(self.socket_server.start())
        self.file_monitor.start()

        # Connect socket server to state store
        self.socket_server.event_handlers.append(
            self.session_store.process_event
        )

    def do_shutdown(self):
        # Clean up
        self.file_monitor.stop()
        # TODO: Stop socket server

        Adw.Application.do_shutdown(self)

    async def on_file_changed(self, file_path):
        # Parse conversation file
        session_id = Path(file_path).parent.name
        parser = ConversationParser(Path(file_path).parent)
        new_messages = parser.parse_incremental()

        # Update state
        for message in new_messages:
            self.session_store.add_message(session_id, message)
```

**Deliverables**:
- Fully integrated application
- Proper startup/shutdown
- Configuration system

#### 4.2 Hook Installation

**Tasks**:
- Implement automatic hook installation on first run
- Modify `~/.claude/settings.json` safely (preserve existing hooks)
- Add hook uninstallation option
- Verify Claude Code CLI is installed
- Handle permission errors

**Hook Installer**:
```python
import json
import shutil
from pathlib import Path

class HookInstaller:
    def __init__(self):
        self.claude_dir = Path.home() / '.claude'
        self.hooks_dir = self.claude_dir / 'hooks'
        self.settings_file = self.claude_dir / 'settings.json'

    def is_installed(self) -> bool:
        hook_script = self.hooks_dir / 'claude-island-state.py'
        return hook_script.exists()

    def install(self):
        # Create hooks directory
        self.hooks_dir.mkdir(parents=True, exist_ok=True)

        # Copy hook script
        source_script = Path(__file__).parent / 'resources' / 'claude-island-state.py'
        dest_script = self.hooks_dir / 'claude-island-state.py'
        shutil.copy(source_script, dest_script)
        dest_script.chmod(0o755)

        # Update settings.json
        self.update_settings()

    def update_settings(self):
        # Read existing settings
        if self.settings_file.exists():
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}

        # Add hooks
        if 'hooks' not in settings:
            settings['hooks'] = {}

        hook_path = str(self.hooks_dir / 'claude-island-state.py')

        hooks_to_register = [
            'UserPromptSubmit',
            'PreToolUse',
            'PostToolUse',
            'PermissionRequest',
            'Notification',
            'Stop',
            'SubagentStop',
            'SessionStart',
            'SessionEnd',
            'PreCompact'
        ]

        for hook_type in hooks_to_register:
            if hook_type not in settings['hooks']:
                settings['hooks'][hook_type] = []

            # Add if not already present
            hook_config = {
                'command': hook_path,
                'timeout': 300000 if hook_type == 'PermissionRequest' else 10000
            }

            if hook_config not in settings['hooks'][hook_type]:
                settings['hooks'][hook_type].append(hook_config)

        # Write settings
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
```

**Deliverables**:
- Automatic hook installation
- Safe settings.json modification
- Installation verification

#### 4.3 Testing and Bug Fixes

**Tasks**:
- Test with multiple concurrent Claude sessions
- Test permission approval workflow
- Test file monitoring with rapid changes
- Test on different terminal emulators (GNOME Terminal, tmux, Alacritty, etc.)
- Test Wayland and X11 compatibility
- Fix discovered bugs
- Add error handling for edge cases

**Test Scenarios**:
1. Start application, verify hook installation
2. Start Claude Code session, verify detection
3. Submit prompt, verify UI updates
4. Trigger tool execution, verify tool display
5. Approve/deny permission request, verify response
6. View conversation history
7. Start multiple sessions, verify session list
8. Close sessions, verify cleanup
9. Test hover expansion
10. Test click-through when closed
11. Test autoscroll and new message badge
12. Test markdown rendering in messages

**Deliverables**:
- Comprehensive test coverage
- Bug fixes
- Stable application

#### 4.4 UI Polish

**Tasks**:
- Refine animations and transitions
- Improve CSS styling for GNOME consistency
- Add icons and visual indicators
- Optimize performance (minimize redraws)
- Add accessibility features (keyboard navigation, screen reader support)
- Implement dark/light theme support

**CSS Refinement**:
```css
/* Notch styling */
.notch-closed {
    background: linear-gradient(135deg, rgba(40, 40, 40, 0.95), rgba(30, 30, 30, 0.95));
    border-radius: 24px;
    padding: 8px 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.notch-opened {
    background: linear-gradient(135deg, rgba(40, 40, 40, 0.98), rgba(30, 30, 30, 0.98));
    border-radius: 30px;
    padding: 16px;
    box-shadow: 0 16px 64px rgba(0, 0, 0, 0.5);
}

/* Message styling */
.user-message {
    background-color: alpha(@accent_bg_color, 0.2);
    border-radius: 12px;
    padding: 8px 12px;
    margin-left: auto;
    max-width: 80%;
}

.assistant-message {
    padding: 8px;
    max-width: 90%;
}

/* Tool styling */
.tool-message {
    background-color: alpha(@window_bg_color, 0.5);
    border-radius: 8px;
    padding: 8px;
    border-left: 3px solid @accent_color;
}

.tool-name {
    font-weight: bold;
    font-family: monospace;
}

/* Approval bar */
.approval-bar {
    background-color: alpha(@warning_color, 0.2);
    border-radius: 12px;
    padding: 12px;
    margin: 8px 0;
}

/* Animations */
@keyframes expand {
    from {
        transform: scale(0.95);
        opacity: 0.8;
    }
    to {
        transform: scale(1);
        opacity: 1;
    }
}

.notch-opened {
    animation: expand 300ms cubic-bezier(0.5, 0.85, 0.5, 1);
}
```

**Deliverables**:
- Polished, GNOME-consistent UI
- Smooth animations
- Accessibility features

### Phase 5: Distribution (Week 10)

#### 5.1 Packaging

**Tasks**:
- Create Python package with proper structure
- Write setup.py/pyproject.toml
- Include resources (hook script, icons, etc.)
- Add desktop entry file
- Create installation script

**Project Structure**:
```
claude-island-linux/
├── pyproject.toml
├── setup.py
├── README.md
├── LICENSE
├── claude_island/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── ui/
│   │   ├── window.py
│   │   ├── notch_view.py
│   │   ├── session_list.py
│   │   ├── chat_view.py
│   │   └── approval_bar.py
│   ├── core/
│   │   ├── socket_server.py
│   │   ├── state_management.py
│   │   ├── conversation_parser.py
│   │   ├── file_monitor.py
│   │   └── hook_installer.py
│   └── resources/
│       ├── claude-island-state.py
│       ├── style.css
│       └── icons/
├── data/
│   └── com.claudeisland.App.desktop
└── tests/
    ├── test_parser.py
    ├── test_state.py
    └── test_socket.py
```

**pyproject.toml**:
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "claude-island-linux"
version = "0.1.0"
description = "GNOME overlay for Claude Code CLI sessions"
authors = [{name = "Your Name", email = "your.email@example.com"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "PyGObject>=3.42",
    "watchdog>=3.0",
    "psutil>=5.9",
    "markdown>=3.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "black>=23.0",
    "mypy>=1.0",
]

[project.scripts]
claude-island = "claude_island.__main__:main"

[project.urls]
Homepage = "https://github.com/yourusername/claude-island-linux"
```

**Desktop Entry** (`com.claudeisland.App.desktop`):
```desktop
[Desktop Entry]
Type=Application
Name=Claude Island
Comment=GNOME overlay for Claude Code CLI sessions
Exec=claude-island
Icon=com.claudeisland.App
Terminal=false
Categories=Development;Utility;
StartupNotify=true
X-GNOME-Autostart-enabled=true
```

**Deliverables**:
- Installable Python package
- Desktop entry file
- Installation instructions

#### 5.2 Flatpak

**Tasks**:
- Create Flatpak manifest
- Define required permissions
- Test Flatpak build
- Submit to Flathub (optional)

**Flatpak Manifest** (`com.claudeisland.App.yml`):
```yaml
app-id: com.claudeisland.App
runtime: org.gnome.Platform
runtime-version: '46'
sdk: org.gnome.Sdk
command: claude-island

finish-args:
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --socket=session-bus
  - --filesystem=home
  - --talk-name=org.freedesktop.Notifications

modules:
  - name: python-dependencies
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app PyGObject watchdog psutil markdown

  - name: gtk-layer-shell
    buildsystem: meson
    config-opts:
      - -Dintrospection=true
    sources:
      - type: git
        url: https://github.com/wmww/gtk-layer-shell.git
        tag: v0.8.2

  - name: claude-island
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app .
      - install -Dm644 data/com.claudeisland.App.desktop /app/share/applications/com.claudeisland.App.desktop
    sources:
      - type: dir
        path: .
```

**Deliverables**:
- Working Flatpak package
- Flathub submission (optional)

#### 5.3 Documentation

**Tasks**:
- Write comprehensive README
- Create user guide
- Document API/architecture for contributors
- Add screenshots/GIFs
- Write troubleshooting guide

**README.md Structure**:
```markdown
# Claude Island for Linux

GNOME overlay for Claude Code CLI sessions with Dynamic Island-style notifications.

## Features

- Real-time session monitoring
- Permission approval interface
- Chat history viewing
- Multi-session support
- GNOME-native design

## Installation

### From PyPI
```bash
pip install claude-island-linux
```

### From Flatpak
```bash
flatpak install flathub com.claudeisland.App
```

### From Source
```bash
git clone https://github.com/yourusername/claude-island-linux
cd claude-island-linux
pip install -e .
```

## Usage

1. Start Claude Island: `claude-island`
2. Start a Claude Code CLI session
3. The overlay will appear at the top of your screen
4. Hover over the overlay to expand and view sessions

## Requirements

- Python 3.11+
- GTK4
- libadwaita
- Claude Code CLI

## Configuration

Settings are stored in `~/.config/claude-island/config.json`.

## Troubleshooting

### Hooks not installing
- Ensure `~/.claude/` directory exists
- Check permissions on `~/.claude/settings.json`

### Window not appearing
- Verify GTK4 and libadwaita are installed
- Check if running Wayland or X11
- Try restarting GNOME Shell (Alt+F2, `r`)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License - see [LICENSE](LICENSE).
```

**Deliverables**:
- Complete documentation
- User guide
- Contributor guide

---

## Challenges and Solutions

### Challenge 1: No Physical Notch on Linux Desktops

**Problem**: Unlike MacBook Pros with notches, standard Linux desktops don't have a notch area.

**Solutions**:
1. **GNOME Top Bar Integration**: Create a GNOME Shell extension that adds an indicator to the top bar
2. **Floating Overlay**: Position overlay window just below the top bar (similar to notifications)
3. **Alternative Design**: Use a different visual metaphor (e.g., slide-in panel from top)

**Recommended**: Start with floating overlay, consider GNOME Shell extension as optional enhancement.

### Challenge 2: Wayland vs X11 Window Management

**Problem**: Different windowing systems require different approaches for overlay windows.

**Solutions**:
1. **Use gtk-layer-shell**: Provides unified API for Wayland layer-shell and X11 fallback
2. **Detect Session Type**: Check `$XDG_SESSION_TYPE` and use appropriate method
3. **Graceful Degradation**: Fall back to X11 methods if Wayland support unavailable

**Implementation**: gtk-layer-shell handles most of the complexity automatically.

### Challenge 3: Markdown Rendering in GTK

**Problem**: GTK doesn't have built-in markdown support like macOS's swift-markdown.

**Solutions**:
1. **WebKitGTK**: Render markdown as HTML in embedded WebKit view
   - Pros: Full HTML/CSS support, rich rendering
   - Cons: Heavy dependency, resource intensive
2. **Pango Markup**: Convert subset of markdown to Pango markup
   - Pros: Lightweight, native GTK
   - Cons: Limited markdown features
3. **gtksourceview**: Use sourceview with markdown syntax highlighting
   - Pros: Good for code blocks
   - Cons: Not true rendering, just highlighting

**Recommended**: Start with Pango markup for basic formatting, optionally add WebKitGTK for rich messages.

### Challenge 4: Click-Through Behavior on Wayland

**Problem**: Wayland's security model makes click-through windows more complex than X11.

**Solutions**:
1. **Input Regions**: Use `gtk_widget_input_shape_combine_region()` to define clickable area
2. **Layer-Shell Keyboard Mode**: Set `GtkLayerShell.KeyboardMode.ON_DEMAND` to only capture input when expanded
3. **Event Handling**: Manually handle events and forward to underlying windows when appropriate

**Implementation**: gtk-layer-shell provides keyboard mode that mostly handles this.

### Challenge 5: Permission Request Timeout

**Problem**: Hook script waits 300 seconds for approval, needs responsive UI feedback.

**Solutions**:
1. **Timeout Indicator**: Show countdown timer in UI
2. **Notification Fallback**: Send desktop notification if window not visible
3. **Sound Alert**: Optional sound when approval needed (configurable)

**Implementation**: Combine UI timeout display with optional notification for background sessions.

### Challenge 6: tmux Integration

**Problem**: Detecting if Claude Code is running in tmux and sending responses to correct pane.

**Solutions**:
1. **Environment Variables**: tmux sets `$TMUX` variable, hook script can detect this
2. **Process Tree Walking**: Walk `/proc/<pid>/` tree to find tmux parent
3. **TTY Matching**: Match TTY from hook script to tmux pane TTY

**Implementation**: Hook script already handles this (cross-platform), reuse macOS approach.

### Challenge 7: Multi-Distribution Support

**Problem**: Different Linux distributions have different package managers and library versions.

**Solutions**:
1. **Flatpak**: Self-contained bundle works across distributions
2. **PyPI Package**: Works anywhere with Python and system GTK libraries
3. **Distribution Packages**: Create native packages for popular distros (Fedora, Ubuntu, Arch)

**Recommended**: Focus on Flatpak for primary distribution, PyPI for power users.

### Challenge 8: Auto-Start on Login

**Problem**: Application should start automatically when user logs in.

**Solutions**:
1. **Desktop Autostart**: Place desktop entry in `~/.config/autostart/`
2. **systemd User Service**: Create systemd user unit with socket activation
3. **GNOME Startup Applications**: Add to GNOME's startup application preferences

**Implementation**: Provide desktop entry for autostart directory, optionally create systemd service.

### Challenge 9: Performance with Many Sessions

**Problem**: Monitoring many concurrent sessions could impact performance.

**Solutions**:
1. **Efficient File Watching**: Use inotify for file changes instead of polling
2. **Incremental Parsing**: Only parse new lines in JSONL files
3. **Debouncing**: Delay updates by 100ms to batch rapid changes
4. **Lazy Loading**: Only load full conversation when chat view opened

**Implementation**: Follow macOS implementation's efficient patterns.

### Challenge 10: Testing Without Breaking Production Sessions

**Problem**: Testing could interfere with real Claude Code sessions.

**Solutions**:
1. **Test Mode**: Environment variable to use different socket path and settings
2. **Mock Sessions**: Create fake session directories with sample JSONL files
3. **Unit Tests**: Test components in isolation
4. **Integration Tests**: Use separate Claude Code profile for testing

**Implementation**: Add `CLAUDE_ISLAND_TEST_MODE` environment variable.

---

## Next Steps

### Immediate Actions

1. **Set up development environment**:
   - Install GTK4, libadwaita, gtk-layer-shell
   - Create Python virtual environment
   - Install dependencies

2. **Start with Phase 1**: Implement hook system and socket server (most critical, reuses macOS logic)

3. **Create proof-of-concept**: Basic GTK window + socket communication + hook integration

4. **Iterate**: Build UI components incrementally, test frequently

### Long-Term Enhancements

1. **GNOME Shell Extension**: Deeper integration with GNOME desktop
2. **KDE Plasma Support**: Adapt for KDE desktop environment
3. **Command Palette**: Quick actions via keyboard shortcuts
4. **Session Export**: Export conversations to markdown/JSON
5. **Statistics Dashboard**: Usage metrics, token counts, tool frequency
6. **Custom Themes**: User-configurable color schemes
7. **Notification Rules**: Configurable alerts for different event types
8. **Multi-Account Support**: Handle multiple Claude accounts

---

## Conclusion

Creating a Linux/GNOME version of Claude Island is entirely feasible. The core logic (hook system, state management, conversation parsing) is platform-agnostic. The main challenges are in UI framework (GTK4 vs SwiftUI) and window management (Wayland/X11 vs macOS AppKit).

The recommended approach is to use **GTK4 + Python** for rapid development and native GNOME integration, with **Flatpak** for distribution. The implementation can largely follow the macOS architecture, with adaptations for Linux-specific APIs.

Development time estimate: **8-10 weeks** for a feature-complete v1.0, assuming one developer working full-time.
