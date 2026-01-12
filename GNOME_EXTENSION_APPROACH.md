# Claude Island for Linux - GNOME Shell Extension + Multi-Desktop Applet Approach

## Executive Summary

This document outlines a dual-approach architecture for bringing Claude Island functionality to Linux:

1. **GNOME Shell Extension**: Deep integration for GNOME users with top bar indicator and custom overlays
2. **StatusNotifier Applet**: Cross-desktop fallback using system tray for KDE, XFCE, MATE, Cinnamon, etc.

Both approaches share the same backend (hook system, socket server, state management) but provide desktop-appropriate UI.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [GNOME Shell Extension Implementation](#gnome-shell-extension-implementation)
3. [StatusNotifier Applet Implementation](#statusnotifier-applet-implementation)
4. [Shared Backend](#shared-backend)
5. [Implementation Plan](#implementation-plan)
6. [Distribution Strategy](#distribution-strategy)

---

## Architecture Overview

### Three-Tier Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend Layer                         │
│  ┌──────────────────────────┐  ┌────────────────────────┐   │
│  │  GNOME Shell Extension   │  │  StatusNotifier Applet │   │
│  │  (JavaScript/GJS)        │  │  (Python/GTK3)         │   │
│  │  - Top bar indicator     │  │  - System tray icon    │   │
│  │  - Custom overlays       │  │  - Popup menus         │   │
│  │  - Native GNOME UI       │  │  - Modal dialogs       │   │
│  └──────────┬───────────────┘  └────────────┬───────────┘   │
│             │                                │               │
└─────────────┼────────────────────────────────┼───────────────┘
              │         D-Bus Communication    │
              │                                │
┌─────────────┴────────────────────────────────┴───────────────┐
│                      Backend Service                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Claude Island Service (Python)                      │    │
│  │  - Unix socket server                                │    │
│  │  - State management                                  │    │
│  │  - JSONL parsing                                     │    │
│  │  - File monitoring                                   │    │
│  │  - D-Bus service provider                            │    │
│  └──────────────────────────────────────────────────────┘    │
│                            ▲                                  │
└────────────────────────────┼──────────────────────────────────┘
                             │ Unix Socket
┌────────────────────────────┴──────────────────────────────────┐
│                    Hook System (Python)                       │
│  - Installed to ~/.claude/hooks/                             │
│  - Captures Claude Code CLI events                           │
│  - Sends events via Unix socket                              │
└───────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Backend Service** (Python daemon):
- Listens on Unix socket for hook events
- Manages session state (sessions, tools, messages)
- Monitors JSONL conversation files
- Exposes D-Bus interface for frontends
- Handles permission approval workflow
- NO direct UI rendering

**GNOME Shell Extension** (JavaScript/GJS):
- Connects to backend via D-Bus
- Renders top bar indicator
- Creates custom overlay popups
- Handles user interactions
- GNOME-only, deep integration

**StatusNotifier Applet** (Python/GTK3):
- Connects to backend via D-Bus
- Creates system tray icon
- Shows GTK popup windows/dialogs
- Works on KDE, XFCE, MATE, Cinnamon, LXQt
- Fallback for non-GNOME desktops

### Desktop Detection

The backend service detects the desktop environment and can be queried:

```python
import os

def get_desktop_environment():
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', 'unknown').lower()
    return desktop

# Examples: 'gnome', 'kde', 'xfce', 'mate', 'cinnamon', 'lxqt'
```

Frontend applications check desktop type and activate appropriate UI:
- On GNOME: Extension loads
- On others: StatusNotifier applet starts

---

## GNOME Shell Extension Implementation

### Technology Stack

- **Language**: JavaScript (ES6+) with GJS
- **UI Toolkit**: St (Shell Toolkit) + Clutter
- **Communication**: D-Bus via Gio.DBusProxy
- **State**: Reactive updates from D-Bus signals
- **GNOME Version**: 45+ (ESModules)

### Extension Structure

```
claude-island@namespace/
├── extension.js          # Main extension code
├── metadata.json         # Extension metadata
├── indicator.js          # Top bar indicator widget
├── sessionPopup.js       # Session list popup
├── chatView.js           # Chat conversation view
├── approvalDialog.js     # Permission approval dialog
├── stylesheet.css        # Custom styling
├── schemas/
│   └── org.gnome.shell.extensions.claude-island.gschema.xml
└── icons/
    └── claude-icon.svg
```

### Top Bar Indicator

**indicator.js**:
```javascript
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import GObject from 'gi://GObject';

const ClaudeIslandIndicator = GObject.registerClass(
class ClaudeIslandIndicator extends PanelMenu.Button {
    _init(dbusProxy) {
        super._init(0.0, 'Claude Island', false);

        this._proxy = dbusProxy;
        this._sessions = new Map();

        // Create icon
        this._icon = new St.Icon({
            icon_name: 'claude-icon-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(this._icon);

        // Create session count label
        this._label = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this.add_child(this._label);

        // Build menu
        this._buildMenu();

        // Watch D-Bus signals
        this._connectSignals();

        // Initial state fetch
        this._refreshState();
    }

    _buildMenu() {
        // Sessions section
        this._sessionsSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._sessionsSection);

        // Separator
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Settings item
        const settingsItem = new PopupMenu.PopupMenuItem('Settings');
        settingsItem.connect('activate', () => {
            this.emit('show-settings');
        });
        this.menu.addMenuItem(settingsItem);
    }

    _connectSignals() {
        // Session state changed
        this._proxy.connectSignal('SessionStateChanged',
            (proxy, sender, [sessionId, phase]) => {
                this._updateSession(sessionId, phase);
            }
        );

        // Permission request
        this._proxy.connectSignal('PermissionRequest',
            (proxy, sender, [sessionId, toolName, params]) => {
                this._showApprovalDialog(sessionId, toolName, params);
            }
        );

        // New message
        this._proxy.connectSignal('NewMessage',
            (proxy, sender, [sessionId, message]) => {
                this._handleNewMessage(sessionId, message);
            }
        );
    }

    async _refreshState() {
        try {
            const sessions = await this._proxy.GetSessionsAsync();
            this._updateSessionList(sessions);
        } catch (e) {
            console.error('Failed to fetch sessions:', e);
        }
    }

    _updateSession(sessionId, phase) {
        // Update icon based on phase
        if (phase === 'waiting_approval') {
            this._icon.icon_name = 'claude-icon-alert-symbolic';
        } else if (phase === 'processing') {
            this._icon.icon_name = 'claude-icon-active-symbolic';
        } else {
            this._icon.icon_name = 'claude-icon-symbolic';
        }

        // Update session count
        this._label.text = this._sessions.size > 0 ?
            String(this._sessions.size) : '';
    }

    _updateSessionList(sessions) {
        // Clear existing items
        this._sessionsSection.removeAll();
        this._sessions.clear();

        // Add session items
        sessions.forEach(session => {
            this._sessions.set(session.id, session);

            const item = new PopupMenu.PopupMenuItem(
                `Session ${session.id.substring(0, 8)}`
            );

            // Add status indicator
            const statusIcon = new St.Icon({
                icon_name: this._getStatusIcon(session.phase),
                icon_size: 16,
            });
            item.insert_child_at_index(statusIcon, 0);

            // Click to show chat
            item.connect('activate', () => {
                this._showChatView(session.id);
            });

            this._sessionsSection.addMenuItem(item);
        });

        // Update count
        this._updateSession(null, null);
    }

    _getStatusIcon(phase) {
        switch (phase) {
            case 'processing':
                return 'emblem-synchronizing-symbolic';
            case 'running_tool':
                return 'system-run-symbolic';
            case 'waiting_approval':
                return 'dialog-question-symbolic';
            case 'completed':
                return 'emblem-ok-symbolic';
            case 'error':
                return 'dialog-error-symbolic';
            default:
                return 'emblem-default-symbolic';
        }
    }

    _showChatView(sessionId) {
        // Import and show chat view overlay
        import('./chatView.js').then(module => {
            const chatView = new module.ChatView(this._proxy, sessionId);
            chatView.open();
        });
    }

    _showApprovalDialog(sessionId, toolName, params) {
        import('./approvalDialog.js').then(module => {
            const dialog = new module.ApprovalDialog(
                this._proxy,
                sessionId,
                toolName,
                params
            );
            dialog.open();
        });
    }

    destroy() {
        // Cleanup
        super.destroy();
    }
});

export { ClaudeIslandIndicator };
```

### Chat View Overlay

**chatView.js**:
```javascript
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import GObject from 'gi://GObject';

const ChatView = GObject.registerClass(
class ChatView extends ModalDialog.ModalDialog {
    _init(dbusProxy, sessionId) {
        super._init({
            styleClass: 'claude-chat-dialog',
            destroyOnClose: true,
        });

        this._proxy = dbusProxy;
        this._sessionId = sessionId;

        // Create content
        this._buildContent();

        // Load messages
        this._loadMessages();
    }

    _buildContent() {
        // Scrollable container
        const scrollView = new St.ScrollView({
            style_class: 'claude-chat-scroll',
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
        });

        // Message list
        this._messageBox = new St.BoxLayout({
            vertical: true,
            style_class: 'claude-chat-messages',
        });
        scrollView.add_actor(this._messageBox);

        this.contentLayout.add_child(scrollView);

        // Close button
        this.addButton({
            label: 'Close',
            action: () => this.close(),
            key: Clutter.KEY_Escape,
        });
    }

    async _loadMessages() {
        try {
            const messages = await this._proxy.GetConversationAsync(
                this._sessionId
            );
            this._renderMessages(messages);
        } catch (e) {
            console.error('Failed to load messages:', e);
        }
    }

    _renderMessages(messages) {
        messages.forEach(msg => {
            const widget = this._createMessageWidget(msg);
            this._messageBox.add_child(widget);
        });
    }

    _createMessageWidget(message) {
        const box = new St.BoxLayout({
            vertical: false,
            style_class: `claude-message claude-message-${message.type}`,
        });

        if (message.type === 'user') {
            // User message (right-aligned)
            const label = new St.Label({
                text: message.content,
                style_class: 'claude-message-user-text',
            });
            box.add_child(label);
        } else if (message.type === 'assistant') {
            // Assistant message (left-aligned)
            const indicator = new St.Icon({
                icon_name: 'user-available-symbolic',
                icon_size: 16,
                style_class: 'claude-message-indicator',
            });
            box.add_child(indicator);

            // TODO: Render markdown
            const label = new St.Label({
                text: message.content,
                style_class: 'claude-message-assistant-text',
            });
            box.add_child(label);
        } else if (message.type === 'tool_use') {
            // Tool execution
            const toolBox = this._createToolWidget(message);
            return toolBox;
        }

        return box;
    }

    _createToolWidget(message) {
        const box = new St.BoxLayout({
            vertical: true,
            style_class: 'claude-tool-message',
        });

        // Tool header
        const header = new St.BoxLayout({
            vertical: false,
        });

        const icon = new St.Icon({
            icon_name: this._getToolStatusIcon(message.status),
            icon_size: 16,
        });
        header.add_child(icon);

        const nameLabel = new St.Label({
            text: message.name,
            style_class: 'claude-tool-name',
        });
        header.add_child(nameLabel);

        box.add_child(header);

        // Tool result (if available)
        if (message.result) {
            const resultLabel = new St.Label({
                text: JSON.stringify(message.result, null, 2),
                style_class: 'claude-tool-result',
            });
            box.add_child(resultLabel);
        }

        return box;
    }

    _getToolStatusIcon(status) {
        switch (status) {
            case 'running':
                return 'emblem-synchronizing-symbolic';
            case 'success':
                return 'emblem-ok-symbolic';
            case 'error':
                return 'dialog-error-symbolic';
            default:
                return 'system-run-symbolic';
        }
    }
});

export { ChatView };
```

### Approval Dialog

**approvalDialog.js**:
```javascript
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';
import * as Dialog from 'resource:///org/gnome/shell/ui/dialog.js';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';

const ApprovalDialog = GObject.registerClass(
class ApprovalDialog extends ModalDialog.ModalDialog {
    _init(dbusProxy, sessionId, toolName, params) {
        super._init({
            styleClass: 'claude-approval-dialog',
            destroyOnClose: true,
        });

        this._proxy = dbusProxy;
        this._sessionId = sessionId;
        this._toolName = toolName;
        this._params = params;

        // Build UI
        const content = new Dialog.MessageDialogContent({
            title: `Approve ${toolName}?`,
            description: `Session ${sessionId.substring(0, 8)} wants to execute:`,
        });

        // Add parameters display
        const paramsBox = new St.BoxLayout({
            vertical: true,
            style_class: 'claude-approval-params',
        });

        const paramsLabel = new St.Label({
            text: JSON.stringify(params, null, 2),
            style_class: 'claude-approval-params-text',
        });
        paramsBox.add_child(paramsLabel);

        content.add_child(paramsBox);

        this.contentLayout.add_child(content);

        // Buttons
        this.addButton({
            label: 'Deny',
            action: () => this._sendDecision('deny'),
            key: Clutter.KEY_Escape,
        });

        this.addButton({
            label: 'Approve',
            action: () => this._sendDecision('allow'),
            default: true,
        });
    }

    async _sendDecision(decision) {
        try {
            await this._proxy.SendApprovalDecisionAsync(
                this._sessionId,
                decision
            );
            this.close();
        } catch (e) {
            console.error('Failed to send decision:', e);
        }
    }
});

export { ApprovalDialog };
```

### Main Extension Entry Point

**extension.js**:
```javascript
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import Gio from 'gi://Gio';
import {ClaudeIslandIndicator} from './indicator.js';

const DBUS_INTERFACE = `
<node>
  <interface name="com.claudeisland.Service">
    <method name="GetSessions">
      <arg type="a{sv}" direction="out" name="sessions"/>
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
</node>`;

export default class ClaudeIslandExtension extends Extension {
    enable() {
        // Create D-Bus proxy
        const ProxyClass = Gio.DBusProxy.makeProxyWrapper(DBUS_INTERFACE);
        this._proxy = new ProxyClass(
            Gio.DBus.session,
            'com.claudeisland.Service',
            '/com/claudeisland/Service'
        );

        // Create indicator
        this._indicator = new ClaudeIslandIndicator(this._proxy);

        // Add to panel
        Main.panel.addToStatusArea(
            this.uuid,
            this._indicator,
            0,
            'right'
        );
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
        this._proxy = null;
    }
}
```

### Styling

**stylesheet.css**:
```css
.claude-chat-dialog {
    min-width: 600px;
    min-height: 580px;
    background-color: rgba(30, 30, 30, 0.95);
    border-radius: 16px;
}

.claude-chat-scroll {
    max-height: 500px;
}

.claude-chat-messages {
    spacing: 12px;
    padding: 16px;
}

.claude-message-user {
    background-color: alpha(@theme_selected_bg_color, 0.2);
    border-radius: 12px;
    padding: 8px 12px;
}

.claude-message-user-text {
    color: @theme_fg_color;
}

.claude-message-assistant {
    padding: 8px;
}

.claude-message-indicator {
    margin-right: 8px;
    color: @theme_selected_bg_color;
}

.claude-message-assistant-text {
    color: @theme_fg_color;
}

.claude-tool-message {
    background-color: alpha(@theme_bg_color, 0.5);
    border-radius: 8px;
    padding: 8px;
    border-left: 3px solid @theme_selected_bg_color;
    spacing: 4px;
}

.claude-tool-name {
    font-weight: bold;
    font-family: monospace;
}

.claude-tool-result {
    font-family: monospace;
    font-size: 0.9em;
    color: alpha(@theme_fg_color, 0.8);
}

.claude-approval-dialog {
    min-width: 400px;
}

.claude-approval-params {
    background-color: alpha(@theme_bg_color, 0.3);
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}

.claude-approval-params-text {
    font-family: monospace;
    font-size: 0.9em;
}
```

### Extension Metadata

**metadata.json**:
```json
{
    "uuid": "claude-island@namespace.com",
    "name": "Claude Island",
    "description": "Monitor and control Claude Code CLI sessions from GNOME Shell",
    "version": 1,
    "version-name": "1.0.0",
    "shell-version": ["45", "46", "47"],
    "url": "https://github.com/yourusername/claude-island-linux",
    "settings-schema": "org.gnome.shell.extensions.claude-island",
    "session-modes": ["user"]
}
```

---

## StatusNotifier Applet Implementation

### Technology Stack

- **Language**: Python 3.11+
- **UI Toolkit**: GTK3 (for compatibility)
- **System Tray**: libayatana-appindicator3
- **Communication**: D-Bus via GLib (GDBus)
- **Desktop Support**: KDE, XFCE, MATE, Cinnamon, LXQt

### Applet Structure

```
claude-island-applet/
├── claude_island_applet/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── indicator.py         # System tray indicator
│   ├── chat_window.py       # Chat window (GTK)
│   ├── approval_dialog.py   # Approval dialog (GTK)
│   ├── dbus_client.py       # D-Bus communication
│   └── ui/
│       └── chat.glade       # GTK UI definition
└── setup.py
```

### System Tray Indicator

**indicator.py**:
```python
#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, AppIndicator3, Notify, GLib
import signal

class ClaudeIslandIndicator:
    def __init__(self, dbus_client):
        self.dbus_client = dbus_client

        # Initialize notifications
        Notify.init("Claude Island")

        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            "claude-island",
            "claude-icon",  # Icon name
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Build menu
        self.menu = self.build_menu()
        self.indicator.set_menu(self.menu)

        # Session tracking
        self.sessions = {}

        # Connect to D-Bus signals
        self.dbus_client.connect('session-state-changed',
                                 self.on_session_state_changed)
        self.dbus_client.connect('permission-request',
                                 self.on_permission_request)
        self.dbus_client.connect('new-message',
                                 self.on_new_message)

        # Initial state fetch
        GLib.idle_add(self.refresh_sessions)

    def build_menu(self):
        menu = Gtk.Menu()

        # Sessions section (dynamically updated)
        self.sessions_section = Gtk.MenuItem(label="No active sessions")
        self.sessions_section.set_sensitive(False)
        menu.append(self.sessions_section)

        menu.append(Gtk.SeparatorMenuItem())

        # Settings
        settings_item = Gtk.MenuItem(label="Settings")
        settings_item.connect('activate', self.show_settings)
        menu.append(settings_item)

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect('activate', self.quit)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def refresh_sessions(self):
        sessions = self.dbus_client.get_sessions()
        self.update_sessions_menu(sessions)
        return False  # Don't repeat idle callback

    def update_sessions_menu(self, sessions):
        # Clear existing items
        for child in self.menu.get_children():
            if isinstance(child, Gtk.MenuItem) and \
               child != self.sessions_section:
                # Keep non-session items
                pass

        # Remove old sessions section
        self.menu.remove(self.sessions_section)

        if not sessions:
            self.sessions_section = Gtk.MenuItem(label="No active sessions")
            self.sessions_section.set_sensitive(False)
            self.menu.prepend(self.sessions_section)
        else:
            # Add session items
            for session in sessions:
                item = Gtk.MenuItem(
                    label=f"Session {session['id'][:8]} - {session['phase']}"
                )
                item.connect('activate', self.show_chat, session['id'])
                self.menu.prepend(item)

        self.menu.show_all()
        self.sessions = {s['id']: s for s in sessions}

        # Update indicator icon
        self.update_indicator_icon(sessions)

    def update_indicator_icon(self, sessions):
        # Change icon based on session states
        has_waiting = any(s['phase'] == 'waiting_approval' for s in sessions)
        has_processing = any(s['phase'] == 'processing' for s in sessions)

        if has_waiting:
            self.indicator.set_icon("claude-icon-alert")
        elif has_processing:
            self.indicator.set_icon("claude-icon-active")
        else:
            self.indicator.set_icon("claude-icon")

    def on_session_state_changed(self, client, session_id, phase):
        # Update menu
        self.refresh_sessions()

        # Show notification for important states
        if phase == 'waiting_approval':
            notification = Notify.Notification.new(
                "Claude Island",
                f"Session {session_id[:8]} requires approval",
                "dialog-question"
            )
            notification.show()

    def on_permission_request(self, client, session_id, tool_name, params):
        # Show approval dialog
        from .approval_dialog import ApprovalDialog
        dialog = ApprovalDialog(self.dbus_client, session_id,
                               tool_name, params)
        dialog.run()

    def on_new_message(self, client, session_id, message):
        # Could show notification for new messages
        pass

    def show_chat(self, widget, session_id):
        from .chat_window import ChatWindow
        window = ChatWindow(self.dbus_client, session_id)
        window.show_all()

    def show_settings(self, widget):
        # TODO: Implement settings window
        pass

    def quit(self, widget):
        Notify.uninit()
        Gtk.main_quit()

    def run(self):
        # Allow Ctrl+C to quit
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        Gtk.main()
```

### Chat Window

**chat_window.py**:
```python
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango

class ChatWindow(Gtk.Window):
    def __init__(self, dbus_client, session_id):
        super().__init__(title=f"Claude Island - Session {session_id[:8]}")
        self.dbus_client = dbus_client
        self.session_id = session_id

        self.set_default_size(600, 580)
        self.set_border_width(10)

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        # Scrolled window for messages
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        vbox.pack_start(scrolled, True, True, 0)

        # Message list
        self.message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   spacing=12)
        self.message_box.set_margin_start(12)
        self.message_box.set_margin_end(12)
        self.message_box.set_margin_top(12)
        self.message_box.set_margin_bottom(12)
        scrolled.add(self.message_box)

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda w: self.destroy())
        vbox.pack_start(close_button, False, False, 0)

        # Load messages
        self.load_messages()

    def load_messages(self):
        messages = self.dbus_client.get_conversation(self.session_id)
        for msg in messages:
            widget = self.create_message_widget(msg)
            self.message_box.pack_start(widget, False, False, 0)

    def create_message_widget(self, message):
        msg_type = message.get('type')

        if msg_type == 'user':
            return self.create_user_message(message)
        elif msg_type == 'assistant':
            return self.create_assistant_message(message)
        elif msg_type == 'tool_use':
            return self.create_tool_message(message)
        else:
            return Gtk.Label(label=f"Unknown message type: {msg_type}")

    def create_user_message(self, message):
        frame = Gtk.Frame()
        frame.set_halign(Gtk.Align.END)
        frame.set_margin_start(100)

        label = Gtk.Label(label=message['content'])
        label.set_line_wrap(True)
        label.set_max_width_chars(50)
        label.set_margin_start(12)
        label.set_margin_end(12)
        label.set_margin_top(8)
        label.set_margin_bottom(8)

        frame.add(label)
        return frame

    def create_assistant_message(self, message):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox.set_halign(Gtk.Align.START)

        # Indicator
        indicator = Gtk.Image.new_from_icon_name(
            "user-available-symbolic",
            Gtk.IconSize.SMALL_TOOLBAR
        )
        hbox.pack_start(indicator, False, False, 0)

        # Message text
        label = Gtk.Label(label=message['content'])
        label.set_line_wrap(True)
        label.set_max_width_chars(60)
        label.set_halign(Gtk.Align.START)
        label.set_xalign(0)
        hbox.pack_start(label, True, True, 0)

        return hbox

    def create_tool_message(self, message):
        frame = Gtk.Frame()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_start(8)
        vbox.set_margin_end(8)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)

        # Header
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        icon = Gtk.Image.new_from_icon_name(
            self.get_tool_status_icon(message.get('status', 'running')),
            Gtk.IconSize.SMALL_TOOLBAR
        )
        hbox.pack_start(icon, False, False, 0)

        name_label = Gtk.Label(label=message['name'])
        name_label.set_markup(f"<b>{message['name']}</b>")
        hbox.pack_start(name_label, False, False, 0)

        vbox.pack_start(hbox, False, False, 0)

        # Result (if available)
        if 'result' in message:
            result_text = str(message['result'])
            result_label = Gtk.Label(label=result_text)
            result_label.set_line_wrap(True)
            result_label.set_selectable(True)
            result_label.set_max_width_chars(70)
            result_label.override_font(
                Pango.FontDescription.from_string("monospace 9")
            )
            vbox.pack_start(result_label, False, False, 0)

        frame.add(vbox)
        return frame

    def get_tool_status_icon(self, status):
        icons = {
            'running': 'emblem-synchronizing-symbolic',
            'success': 'emblem-ok-symbolic',
            'error': 'dialog-error-symbolic',
        }
        return icons.get(status, 'system-run-symbolic')
```

### Approval Dialog

**approval_dialog.py**:
```python
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import json

class ApprovalDialog(Gtk.Dialog):
    def __init__(self, dbus_client, session_id, tool_name, params):
        super().__init__(
            title=f"Approve {tool_name}?",
            flags=Gtk.DialogFlags.MODAL
        )

        self.dbus_client = dbus_client
        self.session_id = session_id

        self.set_default_size(400, 300)

        # Content area
        content = self.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        # Description
        label = Gtk.Label(
            label=f"Session {session_id[:8]} wants to execute:"
        )
        content.pack_start(label, False, False, 0)

        # Parameters
        frame = Gtk.Frame(label="Parameters")
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(150)

        params_text = json.dumps(params, indent=2)
        text_view = Gtk.TextView()
        text_view.get_buffer().set_text(params_text)
        text_view.set_editable(False)
        text_view.set_monospace(True)

        scrolled.add(text_view)
        frame.add(scrolled)
        content.pack_start(frame, True, True, 0)

        # Buttons
        self.add_button("Deny", Gtk.ResponseType.REJECT)
        self.add_button("Approve", Gtk.ResponseType.ACCEPT)

        self.show_all()

    def run(self):
        response = super().run()

        if response == Gtk.ResponseType.ACCEPT:
            decision = 'allow'
        else:
            decision = 'deny'

        self.dbus_client.send_approval_decision(self.session_id, decision)
        self.destroy()
```

### D-Bus Client

**dbus_client.py**:
```python
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib, GObject

class DBusClient(GObject.GObject):
    __gsignals__ = {
        'session-state-changed': (GObject.SIGNAL_RUN_FIRST, None,
                                 (str, str)),
        'permission-request': (GObject.SIGNAL_RUN_FIRST, None,
                              (str, str, object)),
        'new-message': (GObject.SIGNAL_RUN_FIRST, None,
                       (str, object)),
    }

    def __init__(self):
        super().__init__()

        # Create proxy
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            'com.claudeisland.Service',
            '/com/claudeisland/Service',
            'com.claudeisland.Service',
            None
        )

        # Connect to signals
        self.proxy.connect('g-signal', self.on_dbus_signal)

    def on_dbus_signal(self, proxy, sender_name, signal_name, parameters):
        if signal_name == 'SessionStateChanged':
            session_id, phase = parameters.unpack()
            self.emit('session-state-changed', session_id, phase)
        elif signal_name == 'PermissionRequest':
            session_id, tool_name, params = parameters.unpack()
            self.emit('permission-request', session_id, tool_name, params)
        elif signal_name == 'NewMessage':
            session_id, message = parameters.unpack()
            self.emit('new-message', session_id, message)

    def get_sessions(self):
        result = self.proxy.call_sync(
            'GetSessions',
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None
        )
        return result.unpack()[0]

    def get_conversation(self, session_id):
        result = self.proxy.call_sync(
            'GetConversation',
            GLib.Variant('(s)', (session_id,)),
            Gio.DBusCallFlags.NONE,
            -1,
            None
        )
        return result.unpack()[0]

    def send_approval_decision(self, session_id, decision):
        self.proxy.call_sync(
            'SendApprovalDecision',
            GLib.Variant('(ss)', (session_id, decision)),
            Gio.DBusCallFlags.NONE,
            -1,
            None
        )
```

### Main Entry Point

**main.py**:
```python
#!/usr/bin/env python3
import sys
import os
from .dbus_client import DBusClient
from .indicator import ClaudeIslandIndicator

def main():
    # Check desktop environment
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()

    if 'gnome' in desktop:
        print("GNOME detected. Please use the GNOME Shell extension instead.")
        print("This applet is for other desktop environments.")
        sys.exit(1)

    # Create D-Bus client
    dbus_client = DBusClient()

    # Create indicator
    indicator = ClaudeIslandIndicator(dbus_client)

    # Run
    indicator.run()

if __name__ == '__main__':
    main()
```

---

## Shared Backend

### Backend Service Architecture

The backend service is a Python daemon that:
- Runs independently of any UI
- Provides D-Bus interface for frontends
- Handles all business logic
- Works with both GNOME extension and StatusNotifier applet

### D-Bus Service Implementation

**service/dbus_server.py**:
```python
#!/usr/bin/env python3
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
import json

DBUS_INTERFACE_XML = '''
<node>
  <interface name="com.claudeisland.Service">
    <method name="GetSessions">
      <arg type="a{sv}" direction="out" name="sessions"/>
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
'''

class ClaudeIslandDBusService:
    def __init__(self, session_store, socket_server):
        self.session_store = session_store
        self.socket_server = socket_server

        # Parse interface
        self.node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_INTERFACE_XML)
        self.interface_info = self.node_info.interfaces[0]

        # Register service
        self.owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            'com.claudeisland.Service',
            Gio.BusNameOwnerFlags.NONE,
            self.on_bus_acquired,
            None,
            None
        )

        # Subscribe to session store events
        session_store.observers.append(self.on_session_changed)

    def on_bus_acquired(self, connection, name):
        self.connection = connection
        self.registration_id = connection.register_object(
            '/com/claudeisland/Service',
            self.interface_info,
            self.handle_method_call,
            None,  # get_property
            None   # set_property
        )

    def handle_method_call(self, connection, sender, object_path,
                          interface_name, method_name, parameters,
                          invocation):
        if method_name == 'GetSessions':
            sessions = self.get_sessions()
            result = GLib.Variant('(a{sv})', (sessions,))
            invocation.return_value(result)

        elif method_name == 'GetConversation':
            session_id = parameters.unpack()[0]
            messages = self.get_conversation(session_id)
            result = GLib.Variant('(aa{sv})', (messages,))
            invocation.return_value(result)

        elif method_name == 'SendApprovalDecision':
            session_id, decision = parameters.unpack()
            self.send_approval_decision(session_id, decision)
            invocation.return_value(None)

    def get_sessions(self):
        # Convert session store to D-Bus format
        sessions = []
        for session_id, session in self.session_store.sessions.items():
            sessions.append({
                'id': GLib.Variant('s', session_id),
                'phase': GLib.Variant('s', session.phase.value),
            })
        return sessions

    def get_conversation(self, session_id):
        session = self.session_store.sessions.get(session_id)
        if not session:
            return []

        messages = []
        for msg in session.conversation:
            messages.append({
                'type': GLib.Variant('s', msg['type']),
                'content': GLib.Variant('s', msg.get('content', '')),
            })
        return messages

    def send_approval_decision(self, session_id, decision):
        # Forward to socket server
        self.socket_server.send_approval_response(session_id, decision)

    def on_session_changed(self, session):
        # Emit SessionStateChanged signal
        self.connection.emit_signal(
            None,
            '/com/claudeisland/Service',
            'com.claudeisland.Service',
            'SessionStateChanged',
            GLib.Variant('(ss)', (session.session_id, session.phase.value))
        )

        # Emit PermissionRequest if waiting for approval
        if session.pending_approval:
            params = session.pending_approval.get('parameters', {})
            self.connection.emit_signal(
                None,
                '/com/claudeisland/Service',
                'com.claudeisland.Service',
                'PermissionRequest',
                GLib.Variant('(ssa{sv})', (
                    session.session_id,
                    session.pending_approval['tool_name'],
                    params
                ))
            )

    def emit_new_message(self, session_id, message):
        self.connection.emit_signal(
            None,
            '/com/claudeisland/Service',
            'com.claudeisland.Service',
            'NewMessage',
            GLib.Variant('(sa{sv})', (session_id, message))
        )
```

### Backend Service Main

**service/main.py**:
```python
#!/usr/bin/env python3
import asyncio
from pathlib import Path
from .socket_server import HookSocketServer
from .state_management import SessionStore
from .file_monitor import FileMonitor
from .dbus_server import ClaudeIslandDBusService
from gi.repository import GLib

async def main():
    # Create components
    session_store = SessionStore()
    socket_server = HookSocketServer(session_store)
    file_monitor = FileMonitor(
        Path.home() / '.claude' / 'sessions',
        session_store
    )
    dbus_service = ClaudeIslandDBusService(session_store, socket_server)

    # Start services
    await socket_server.start()
    file_monitor.start()

    # Run GLib main loop
    loop = GLib.MainLoop()
    loop.run()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Implementation Plan

### Phase 1: Backend Service (Weeks 1-3)

**Week 1: Foundation**
- Set up project structure
- Implement hook system (port from macOS)
- Create Unix socket server
- Test hook integration with Claude Code CLI

**Week 2: Core Logic**
- Implement session state management
- Create JSONL conversation parser
- Add file monitoring with inotify
- Test state updates with real sessions

**Week 3: D-Bus Service**
- Define D-Bus interface
- Implement D-Bus service provider
- Add signal emission for state changes
- Test D-Bus communication

### Phase 2: GNOME Shell Extension (Weeks 4-6)

**Week 4: Basic Extension**
- Set up extension structure
- Create top bar indicator
- Connect to D-Bus service
- Display session list in menu

**Week 5: UI Components**
- Build chat view overlay
- Create approval dialog
- Add animations and styling
- Test on GNOME 45/46/47

**Week 6: Polish and Testing**
- Refine UI/UX
- Add error handling
- Test enable/disable cycles
- Memory leak testing

### Phase 3: StatusNotifier Applet (Weeks 7-9)

**Week 7: Basic Applet**
- Create system tray indicator
- Connect to D-Bus service
- Build menu with sessions
- Test on KDE Plasma

**Week 8: GTK Windows**
- Create chat window
- Build approval dialog
- Add desktop notifications
- Test on XFCE, MATE

**Week 9: Cross-Desktop Testing**
- Test on Cinnamon, LXQt
- Fix desktop-specific issues
- Add fallback mechanisms
- Polish UI consistency

### Phase 4: Integration and Distribution (Weeks 10-12)

**Week 10: Integration**
- Test both frontends with backend
- Add auto-start mechanisms
- Create configuration system
- Write comprehensive logs

**Week 11: Packaging**
- Package backend as Python wheel
- Package extension for extensions.gnome.org
- Create RPM for Fedora
- Set up Flatpak manifest

**Week 12: Documentation and Release**
- Write user documentation
- Create developer guide
- Record demo videos
- Release v1.0

---

## Distribution Strategy

### Backend Service

**PyPI Package**:
```bash
pip install claude-island-service
```

**Systemd User Service** (`~/.config/systemd/user/claude-island.service`):
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

**D-Bus Service Activation** (`~/.local/share/dbus-1/services/com.claudeisland.Service.service`):
```ini
[D-BUS Service]
Name=com.claudeisland.Service
Exec=/usr/bin/python3 -m claude_island_service
```

### GNOME Shell Extension

**extensions.gnome.org**:
- Submit as ZIP package
- Users install via Extensions app or website
- Auto-updates via extensions platform

**Manual Installation**:
```bash
cd ~/.local/share/gnome-shell/extensions/
git clone https://github.com/user/claude-island-extension.git claude-island@namespace.com
gnome-extensions enable claude-island@namespace.com
```

### StatusNotifier Applet

**Fedora RPM** (via Copr):
```bash
sudo dnf copr enable username/claude-island
sudo dnf install claude-island-applet
```

**Desktop Auto-Start** (`~/.config/autostart/claude-island-applet.desktop`):
```desktop
[Desktop Entry]
Type=Application
Name=Claude Island Applet
Exec=claude-island-applet
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
OnlyShowIn=KDE;XFCE;MATE;Cinnamon;LXQt;
```

### Unified Flatpak

**Flatpak Bundle** (includes backend + appropriate frontend):
```bash
flatpak install flathub com.claudeisland.App
```

Flatpak detects desktop and launches:
- GNOME: Backend service (extension installed separately)
- Others: Backend service + StatusNotifier applet

---

## Summary

This dual-approach architecture provides:

✅ **Native GNOME Integration**: Extension feels like part of the desktop
✅ **Cross-Desktop Support**: StatusNotifier works everywhere else
✅ **Shared Logic**: Backend handles all complexity
✅ **Clean Separation**: UI and business logic decoupled
✅ **Easy Maintenance**: One backend, two lightweight frontends
✅ **User Choice**: GNOME users get best experience, others get full functionality

**Total Development Time**: 10-12 weeks (single developer, full-time)

**Technologies**:
- Backend: Python 3.11+ (asyncio, D-Bus, inotify)
- GNOME Extension: JavaScript/GJS (St, Clutter, Gio)
- StatusNotifier: Python/GTK3 (AppIndicator3, Notify)

**Distribution**:
- Backend: PyPI + systemd + D-Bus activation
- Extension: extensions.gnome.org
- Applet: RPM (Copr) + desktop auto-start
- Unified: Flatpak bundle
