# Claude Island Linux - Executive Summary

## What is Claude Island?

Claude Island is a macOS menu bar application that provides Dynamic Island-style notifications for Claude Code CLI sessions. It allows users to:

- Monitor multiple Claude Code sessions in real-time
- Approve/deny tool execution requests from a UI overlay
- View full conversation history with rich formatting
- Track session status and tool execution

## Linux Port Feasibility: ✅ Highly Feasible

The core architecture is platform-agnostic. Main differences are in UI framework and window management.

## Recommended Technology Stack

- **Language**: Python 3.11+
- **UI Framework**: GTK4 + libadwaita
- **Window Management**: gtk-layer-shell (Wayland/X11)
- **IPC**: Unix domain sockets
- **File Monitoring**: watchdog library (inotify)
- **Distribution**: Flatpak + PyPI

## Key Architecture Components (Reusable from macOS)

1. **Hook System** (Python) - Works cross-platform ✅
2. **Unix Socket Server** - Works cross-platform ✅
3. **State Management** - Logic is portable ✅
4. **JSONL Parser** - Works cross-platform ✅
5. **File Monitoring** - Needs Linux API (inotify) ⚠️
6. **UI Layer** - Needs complete rewrite (SwiftUI → GTK4) ⚠️

## Timeline Estimate

**8-10 weeks** for feature-complete v1.0 (1 full-time developer)

### Phase Breakdown:
- **Weeks 1-2**: Foundation (hook system, socket server)
- **Weeks 3-4**: Core logic (state management, file monitoring, parsing)
- **Weeks 5-7**: User interface (GTK4 UI components)
- **Weeks 8-9**: Integration and polish
- **Week 10**: Packaging and distribution

## Main Challenges & Solutions

### 1. No Physical Notch
**Solution**: Floating overlay window at top-center, or GNOME top bar extension

### 2. Wayland vs X11
**Solution**: gtk-layer-shell library handles both automatically

### 3. Markdown Rendering
**Solution**: Start with Pango markup, optionally add WebKitGTK for rich content

### 4. Click-Through Behavior
**Solution**: GTK input regions + layer-shell keyboard modes

### 5. Distribution
**Solution**: Primary: Flatpak, Secondary: PyPI package

## Project Structure

```
claude-island-linux/
├── claude_island/
│   ├── ui/                    # GTK4 UI components
│   ├── core/                  # Platform-agnostic logic
│   └── resources/             # Hook script, CSS, icons
├── data/                      # Desktop files
├── tests/                     # Unit/integration tests
└── pyproject.toml            # Package configuration
```

## Linux-Specific OS Features Required

1. **Wayland Layer-Shell Protocol**: Overlay windows above all content
2. **inotify API**: File system monitoring
3. **D-Bus**: Desktop notifications, optional IPC
4. **Procfs (/proc)**: TTY detection, process management
5. **libadwaita**: GNOME design patterns
6. **XDG Base Directory**: Standard config/cache locations

## What's Different from macOS Version?

| Aspect | macOS | Linux/GNOME |
|--------|-------|-------------|
| Language | Swift | Python |
| UI Framework | SwiftUI | GTK4 + libadwaita |
| Window System | AppKit (NSPanel) | gtk-layer-shell |
| File Monitoring | FSEvents | inotify (watchdog) |
| Markdown | swift-markdown | Pango/WebKitGTK |
| Updates | Sparkle | Flatpak/package manager |
| Design | Dynamic Island style | Floating overlay/top bar |

## What Stays the Same?

- Hook system architecture (Python script)
- Unix domain socket IPC
- JSONL conversation parsing logic
- Session state management concepts
- Event flow and processing
- Permission approval workflow
- tmux integration approach

## Development Recommendations

### Start Here:
1. Set up GTK4 development environment
2. Port hook script (minimal changes needed)
3. Implement socket server
4. Create proof-of-concept: basic window + socket communication

### Critical Path:
1. Hook system + socket server (enables testing with real Claude sessions)
2. State management (core business logic)
3. Basic UI (functional before polished)
4. Chat view + approval interface (core UX)
5. Polish + packaging

### Testing Strategy:
- Use `CLAUDE_ISLAND_TEST_MODE` environment variable
- Create mock session directories
- Test with real Claude Code CLI sessions
- Test on both Wayland and X11
- Test in different terminals (GNOME Terminal, tmux, Alacritty)

## Distribution Strategy

### Primary: Flatpak
- Self-contained, works across distributions
- Automatic updates via Flathub
- Sandboxed (with necessary permissions)

### Secondary: PyPI
- For power users and developers
- Requires system GTK4 libraries
- `pip install claude-island-linux`

### Optional: Native Packages
- Fedora: RPM via Copr
- Ubuntu: DEB via PPA
- Arch: AUR package

## Success Metrics for v1.0

- ✅ Automatic hook installation
- ✅ Real-time session detection
- ✅ Permission approval workflow
- ✅ Chat history viewing
- ✅ Multi-session support
- ✅ Wayland + X11 support
- ✅ GNOME design consistency
- ✅ Stable on Fedora + GNOME

## Future Enhancements (v2.0+)

- GNOME Shell extension for top bar integration
- KDE Plasma support
- Session export (markdown/JSON)
- Statistics dashboard
- Custom themes
- Command palette
- Notification rules
- Multi-account support

## Resources

- **Original repo**: https://github.com/farouqaldori/claude-island
- **GTK4 docs**: https://docs.gtk.org/gtk4/
- **gtk-layer-shell**: https://github.com/wmww/gtk-layer-shell
- **PyGObject docs**: https://pygobject.readthedocs.io/
- **Flatpak docs**: https://docs.flatpak.org/

## Conclusion

Building a Linux/GNOME version of Claude Island is **highly feasible** with the right technology stack. The core architecture translates well to Linux, and GTK4 provides excellent tools for creating the overlay UI. The recommended approach prioritizes:

1. **Native GNOME integration** (GTK4 + libadwaita)
2. **Rapid development** (Python over Rust for v1.0)
3. **Cross-distribution support** (Flatpak primary)
4. **Reusing proven architecture** (port macOS logic where possible)

The estimated 8-10 week timeline assumes a developer familiar with Python and GTK. The result will be a polished, GNOME-native companion app for Claude Code CLI that feels at home on Linux desktops.
