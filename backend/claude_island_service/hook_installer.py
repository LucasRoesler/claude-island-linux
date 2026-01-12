"""Hook script installation and configuration."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class HookInstaller:
    """Install and configure Claude Code CLI hooks."""

    def __init__(self) -> None:
        self.claude_dir = Path.home() / ".claude"
        self.hooks_dir = self.claude_dir / "hooks"
        self.settings_file = self.claude_dir / "settings.json"
        self.hook_script_name = "claude-island-state.py"

    def is_installed(self) -> bool:
        """Check if hook script is installed."""
        hook_script = self.hooks_dir / self.hook_script_name
        return hook_script.exists()

    def install(self) -> None:
        """Install hook script and update settings."""
        # Create hooks directory
        self.hooks_dir.mkdir(parents=True, exist_ok=True)

        # Copy hook script from resources
        source_script = Path(__file__).parent / "resources" / self.hook_script_name
        dest_script = self.hooks_dir / self.hook_script_name

        if not source_script.exists():
            raise FileNotFoundError(f"Hook script not found: {source_script}")

        shutil.copy(source_script, dest_script)
        dest_script.chmod(0o755)

        logger.info("Copied hook script to: %s", dest_script)

        # Update settings.json
        self._update_settings()

        logger.info("Hook installation complete")

    def _update_settings(self) -> None:
        """Update Claude settings.json to register hooks."""
        # Read existing settings
        if self.settings_file.exists():
            with open(self.settings_file, "r") as f:
                settings = json.load(f)
        else:
            settings = {}

        # Ensure hooks section exists
        if "hooks" not in settings:
            settings["hooks"] = {}

        hook_path = str(self.hooks_dir / self.hook_script_name)

        # Define hooks to register
        hooks_to_register = {
            "UserPromptSubmit": {"timeout": 10000},
            "PreToolUse": {"timeout": 10000},
            "PostToolUse": {"timeout": 10000},
            "PermissionRequest": {"timeout": 300000},  # 5 minutes
            "Notification": {"timeout": 10000},
            "Stop": {"timeout": 10000},
            "SubagentStop": {"timeout": 10000},
            "SessionStart": {"timeout": 10000},
            "SessionEnd": {"timeout": 10000},
            "PreCompact": {"timeout": 10000},
        }

        # Add hooks if not present
        for hook_type, config in hooks_to_register.items():
            if hook_type not in settings["hooks"]:
                settings["hooks"][hook_type] = []

            # Check if our hook is already registered
            hook_config = {
                "type": "command",
                "command": hook_path,
                "timeout": config["timeout"],
            }

            # Add if not already present
            if not self._hook_exists(settings["hooks"][hook_type], hook_path):
                settings["hooks"][hook_type].append(
                    {"matcher": ".*", "hooks": [hook_config]}
                )
                logger.info("Registered hook: %s", hook_type)

        # Write settings
        with open(self.settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info("Updated settings.json")

    def _hook_exists(self, hook_list: list[dict[str, Any]], hook_path: str) -> bool:
        """Check if hook with given path already exists."""
        for entry in hook_list:
            hooks = entry.get("hooks", [])
            for hook in hooks:
                if hook.get("command") == hook_path:
                    return True
        return False

    def uninstall(self) -> None:
        """Remove hook script and clean up settings."""
        dest_script = self.hooks_dir / self.hook_script_name

        if dest_script.exists():
            dest_script.unlink()
            logger.info("Removed hook script")

        # TODO: Clean up settings.json (remove hook entries)
        logger.info("Hook uninstalled (settings.json not cleaned)")
