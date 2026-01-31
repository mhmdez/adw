"""Desktop notifications for ADW.

Provides macOS native notifications via osascript.
Can be subscribed to daemon/manager events.
"""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class NotificationSound(str, Enum):
    """macOS notification sounds."""
    DEFAULT = "default"
    BASSO = "Basso"
    BLOW = "Blow"
    BOTTLE = "Bottle"
    FROG = "Frog"
    FUNK = "Funk"
    GLASS = "Glass"
    HERO = "Hero"
    MORSE = "Morse"
    PING = "Ping"
    POP = "Pop"
    PURR = "Purr"
    SOSUMI = "Sosumi"
    SUBMARINE = "Submarine"
    TINK = "Tink"
    NONE = ""


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = True
    sound_success: NotificationSound = NotificationSound.GLASS
    sound_failure: NotificationSound = NotificationSound.BASSO
    sound_started: NotificationSound = NotificationSound.NONE
    show_on_start: bool = False  # Usually too noisy


def is_macos() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def send_notification(
    title: str,
    message: str,
    sound: NotificationSound | str = NotificationSound.DEFAULT,
    subtitle: str = "",
) -> bool:
    """Send a macOS desktop notification.
    
    Args:
        title: Notification title
        message: Main message body
        sound: Sound to play (NotificationSound or string)
        subtitle: Optional subtitle
        
    Returns:
        True if notification was sent successfully
    """
    if not is_macos():
        return False
    
    # Build AppleScript
    sound_name = sound.value if isinstance(sound, NotificationSound) else sound
    
    script_parts = [
        f'display notification "{_escape(message)}"',
        f'with title "{_escape(title)}"',
    ]
    
    if subtitle:
        script_parts.append(f'subtitle "{_escape(subtitle)}"')
    
    if sound_name:
        script_parts.append(f'sound name "{sound_name}"')
    
    script = " ".join(script_parts)
    
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def _escape(text: str) -> str:
    """Escape special characters for AppleScript."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


class NotificationHandler:
    """Event handler for ADW notifications.
    
    Subscribe this to a CronDaemon or AgentManager to get
    desktop notifications on task completion/failure.
    
    Usage:
        daemon = CronDaemon(config)
        notifier = NotificationHandler()
        daemon.subscribe(notifier.on_event)
    """
    
    def __init__(self, config: NotificationConfig | None = None):
        self.config = config or NotificationConfig()
    
    def on_event(self, event: str, data: dict) -> None:
        """Handle daemon/manager events."""
        if not self.config.enabled or not is_macos():
            return
        
        if event == "task_started" and self.config.show_on_start:
            desc = data.get("description", "Task")[:50]
            adw_id = data.get("adw_id", "")[:8]
            send_notification(
                title="⏳ ADW Task Started",
                message=desc,
                subtitle=f"ID: {adw_id}",
                sound=self.config.sound_started,
            )
        
        elif event == "task_completed":
            desc = data.get("description", "Task")[:50]
            adw_id = data.get("adw_id", "")[:8]
            send_notification(
                title="✅ ADW Task Completed",
                message=desc,
                subtitle=f"ID: {adw_id}",
                sound=self.config.sound_success,
            )
        
        elif event == "task_failed":
            desc = data.get("description", "Task")[:50]
            adw_id = data.get("adw_id", "")[:8]
            error = data.get("error") or f"Exit {data.get('return_code', '?')}"
            send_notification(
                title="❌ ADW Task Failed",
                message=f"{desc}\n{error[:100]}",
                subtitle=f"ID: {adw_id}",
                sound=self.config.sound_failure,
            )
        
        elif event == "completed":
            # AgentManager event (direct agent completion)
            adw_id = data.get("adw_id", "")[:8] if isinstance(data, dict) else ""
            send_notification(
                title="✅ Agent Completed",
                message=f"Agent {adw_id} finished successfully",
                sound=self.config.sound_success,
            )
        
        elif event == "failed":
            # AgentManager event
            adw_id = data.get("adw_id", "")[:8] if isinstance(data, dict) else ""
            send_notification(
                title="❌ Agent Failed",
                message=f"Agent {adw_id} failed",
                sound=self.config.sound_failure,
            )


# Convenience function for quick notifications
def notify_complete(task: str, adw_id: str = "") -> None:
    """Send task completion notification."""
    send_notification(
        title="✅ ADW Task Completed",
        message=task[:50],
        subtitle=f"ID: {adw_id[:8]}" if adw_id else "",
        sound=NotificationSound.GLASS,
    )


def notify_failed(task: str, error: str = "", adw_id: str = "") -> None:
    """Send task failure notification."""
    msg = task[:50]
    if error:
        msg += f"\n{error[:100]}"
    send_notification(
        title="❌ ADW Task Failed",
        message=msg,
        subtitle=f"ID: {adw_id[:8]}" if adw_id else "",
        sound=NotificationSound.BASSO,
    )
