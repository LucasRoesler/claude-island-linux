# Claude Island for Linux

A Linux port of [Claude Island](https://github.com/farouqaldori/claude-island) - bringing Dynamic Island-style notifications and controls for Claude Code CLI to Linux desktops.

## Overview

This project aims to bring the Claude Island experience to Linux users across all major desktop environments:

- **GNOME**: Native Shell extension with top bar integration
- **KDE/XFCE/MATE/Cinnamon/LXQt**: StatusNotifier system tray applet

## Architecture

Three-tier design for maximum compatibility:

```
┌─────────────────────────────────────────────────────────┐
│           Frontend Layer (Desktop-Specific)             │
│  ┌────────────────┐         ┌──────────────────┐       │
│  │ GNOME Shell    │         │ StatusNotifier   │       │
│  │ Extension (JS) │         │ Applet (Python)  │       │
│  └────────┬───────┘         └────────┬─────────┘       │
└───────────┼──────────────────────────┼─────────────────┘
            │        D-Bus              │
┌───────────┴──────────────────────────┴─────────────────┐
│               Backend Service (Python)                  │
│  - Unix socket server (hook events)                    │
│  - D-Bus service (frontend communication)              │
│  - State management                                    │
│  - JSONL parsing                                       │
└─────────────────────────────────────────────────────────┘
```

## Features

- Real-time Claude Code CLI session monitoring
- Permission approval interface
- Chat history viewing with markdown support
- Multi-session support
- Desktop-appropriate UI for each environment

## Technology Stack

- **Backend**: Python 3.11+, asyncio, D-Bus, inotify
- **GNOME Extension**: JavaScript/GJS, St/Clutter
- **Applet**: Python/GTK3, AppIndicator3, libnotify

## Documentation

- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**: Quick overview and timeline
- **[GNOME_EXTENSION_APPROACH.md](GNOME_EXTENSION_APPROACH.md)**: Detailed implementation guide with code examples
- **[ANALYSIS.md](ANALYSIS.md)**: Comprehensive analysis of original macOS app
- **[SUMMARY.md](SUMMARY.md)**: Executive summary

## Development Status

🚧 **Planning Phase** - Currently in research and planning. Implementation has not started yet.

## Target Platforms

- Fedora (primary target)
- GNOME 45+
- KDE Plasma 5.27+
- XFCE 4.18+
- MATE 1.26+
- Cinnamon 5.8+
- LXQt 1.3+

## Estimated Timeline

**10-12 weeks** for v1.0 (single full-time developer):
- Weeks 1-3: Backend service
- Weeks 4-6: GNOME Shell extension
- Weeks 7-9: StatusNotifier applet
- Weeks 10-12: Integration, packaging, documentation

## License

To be determined

## Credits

Original Claude Island by [Farouq Aldori](https://github.com/farouqaldori/claude-island)

## Contributing

This project is in early planning stages. Contributions welcome once implementation begins.
