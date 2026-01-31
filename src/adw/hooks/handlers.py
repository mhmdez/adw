"""Hook handlers for ADW observability.

This module provides Python handlers for Claude Code hooks that can be
called from the hook scripts in .claude/hooks/.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class HookType(str, Enum):
    """Types of Claude Code hooks."""
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    NOTIFICATION = "Notification"


@dataclass
class HookEvent:
    """Represents an incoming hook event."""
    hook_type: HookType
    session_id: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_result: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_stdin(cls, hook_type: HookType) -> "HookEvent":
        """Create HookEvent from stdin JSON input.

        Args:
            hook_type: The type of hook being processed.

        Returns:
            HookEvent instance.
        """
        import sys

        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError:
            data = {}

        return cls(
            hook_type=hook_type,
            session_id=os.environ.get("CLAUDE_SESSION_ID"),
            tool_name=data.get("tool_name"),
            tool_input=data.get("tool_input", {}),
            tool_result=data.get("tool_result", {}),
        )


@dataclass
class HookResult:
    """Result from processing a hook."""
    success: bool = True
    message: str | None = None
    block: bool = False  # If True, blocks the tool execution
    modified_input: dict[str, Any] | None = None

    def to_json(self) -> str:
        """Convert to JSON for hook response."""
        result = {"success": self.success}
        if self.message:
            result["message"] = self.message
        if self.block:
            result["block"] = True
        if self.modified_input:
            result["modified_input"] = self.modified_input
        return json.dumps(result)


def get_log_dir() -> Path:
    """Get directory for hook logs."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    log_dir = Path(project_dir) / ".claude" / "agents" / "hook_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_bundle_dir() -> Path:
    """Get directory for context bundles."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    bundle_dir = Path(project_dir) / ".claude" / "agents" / "context_bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    return bundle_dir


def log_event(event: HookEvent) -> None:
    """Log a hook event to the hook log file.

    Args:
        event: The hook event to log.
    """
    log_dir = get_log_dir()
    date_str = datetime.now().strftime("%Y%m%d")
    session_id = event.session_id or "unknown"

    log_file = log_dir / f"{date_str}_{session_id[:8]}.jsonl"

    entry = {
        "timestamp": event.timestamp,
        "hook": event.hook_type.value,
        "session_id": event.session_id,
        "tool_name": event.tool_name,
        "tool_input_keys": list(event.tool_input.keys()) if event.tool_input else [],
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def track_file_operation(event: HookEvent) -> None:
    """Track file operations for context bundles.

    Args:
        event: The hook event containing file operation.
    """
    if event.tool_name not in ("Read", "Write", "Edit"):
        return

    bundle_dir = get_bundle_dir()
    date_str = datetime.now().strftime("%Y%m%d_%H")
    session_id = event.session_id or "unknown"

    bundle_file = bundle_dir / f"{date_str}_{session_id[:8]}.jsonl"

    entry = {
        "timestamp": event.timestamp,
        "session_id": event.session_id,
        "tool": event.tool_name,
    }

    if event.tool_name == "Read":
        entry["file_path"] = event.tool_input.get("file_path")
        entry["offset"] = event.tool_input.get("offset")
        entry["limit"] = event.tool_input.get("limit")
    elif event.tool_name == "Write":
        entry["file_path"] = event.tool_input.get("file_path")
        entry["content_length"] = len(event.tool_input.get("content", ""))
    elif event.tool_name == "Edit":
        entry["file_path"] = event.tool_input.get("file_path")
        entry["old_string_length"] = len(event.tool_input.get("old_string", ""))
        entry["new_string_length"] = len(event.tool_input.get("new_string", ""))

    with open(bundle_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def handle_pre_tool_use(event: HookEvent) -> HookResult:
    """Handle PreToolUse hook.

    Called before a tool is executed. Can block or modify the tool call.

    Args:
        event: The hook event.

    Returns:
        HookResult indicating whether to proceed.
    """
    # Log the event
    log_event(event)

    # Check for potentially dangerous operations
    if event.tool_name == "Bash":
        command = event.tool_input.get("command", "")

        # Block dangerous commands (can be customized)
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf ~",
            ":(){:|:&};:",  # Fork bomb
        ]

        for pattern in dangerous_patterns:
            if pattern in command:
                return HookResult(
                    success=False,
                    message=f"Blocked potentially dangerous command",
                    block=True,
                )

    return HookResult(success=True)


def handle_post_tool_use(event: HookEvent) -> HookResult:
    """Handle PostToolUse hook.

    Called after a tool is executed. Used for logging and context tracking.

    Args:
        event: The hook event.

    Returns:
        HookResult.
    """
    # Log the event
    log_event(event)

    # Track file operations for context bundles
    track_file_operation(event)

    return HookResult(success=True)


def handle_user_prompt_submit(event: HookEvent) -> HookResult:
    """Handle UserPromptSubmit hook.

    Called when user submits a prompt. Used for logging.

    Args:
        event: The hook event.

    Returns:
        HookResult.
    """
    log_event(event)
    return HookResult(success=True)


def handle_stop(event: HookEvent) -> HookResult:
    """Handle Stop hook.

    Called when a session ends. Used for cleanup and final logging.

    Args:
        event: The hook event.

    Returns:
        HookResult.
    """
    log_event(event)

    # Could trigger session summary generation here

    return HookResult(success=True)


def handle_notification(event: HookEvent) -> HookResult:
    """Handle Notification hook.

    Called for various notifications. Used for alerting.

    Args:
        event: The hook event.

    Returns:
        HookResult.
    """
    log_event(event)
    return HookResult(success=True)


def dispatch_hook(hook_type: str) -> HookResult:
    """Dispatch a hook to the appropriate handler.

    This is the main entry point for hook scripts.

    Args:
        hook_type: The hook type string from CLAUDE_HOOK_NAME.

    Returns:
        HookResult from the handler.
    """
    try:
        hook_enum = HookType(hook_type)
    except ValueError:
        return HookResult(success=True)  # Unknown hook, pass through

    event = HookEvent.from_stdin(hook_enum)

    handlers = {
        HookType.PRE_TOOL_USE: handle_pre_tool_use,
        HookType.POST_TOOL_USE: handle_post_tool_use,
        HookType.USER_PROMPT_SUBMIT: handle_user_prompt_submit,
        HookType.STOP: handle_stop,
        HookType.NOTIFICATION: handle_notification,
    }

    handler = handlers.get(hook_enum)
    if handler:
        return handler(event)

    return HookResult(success=True)
