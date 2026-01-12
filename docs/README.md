# Documentation

## Getting Started

- **[../README.md](../README.md)** - Main project README with installation and usage instructions
- **[TESTING.md](TESTING.md)** - Testing guide for the minimal implementation

## Planning & Research

- **[SUMMARY.md](SUMMARY.md)** - Executive summary of the project
- **[ANALYSIS.md](ANALYSIS.md)** - Comprehensive analysis of the original macOS Claude Island
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Quick reference for the Linux implementation
- **[GNOME_EXTENSION_APPROACH.md](GNOME_EXTENSION_APPROACH.md)** - Detailed GNOME Shell extension and multi-desktop approach

## Architecture

The project consists of:

1. **Backend Service** - Python daemon that monitors Claude Code CLI via hooks and D-Bus
2. **StatusNotifier Applet** - System tray indicator for KDE/XFCE/MATE/etc
3. **GNOME Extension** (future) - Native GNOME Shell integration

See the main README for current implementation status.
