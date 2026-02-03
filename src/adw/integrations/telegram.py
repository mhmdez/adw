"""Telegram Bot integration for ADW.

Enables ADW to receive commands from Telegram bot and
send progress updates to chats.

Configuration:
    Environment variables:
    - TELEGRAM_BOT_TOKEN: Telegram bot token from @BotFather (required)
    - TELEGRAM_CHAT_ID: Default chat ID for notifications (optional)

    Or via config file (~/.adw/config.toml):
    [telegram]
    bot_token = "123456789:ABC..."
    chat_id = "123456789"

Features:
    - Commands: /task, /status, /approve, /reject, /help
    - Progress updates in chat
    - Inline keyboard for approve/reject workflows
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# Storage paths
ADW_DIR = Path.home() / ".adw"
TELEGRAM_STATE_FILE = ADW_DIR / "telegram_state.json"


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class TelegramConfig:
    """Configuration for Telegram integration.

    Attributes:
        bot_token: Telegram bot token from @BotFather.
        chat_id: Default chat ID for notifications.
        notification_events: Events to notify on.
        poll_timeout: Long polling timeout in seconds.
    """

    bot_token: str
    chat_id: str | None = None
    notification_events: list[str] = field(
        default_factory=lambda: ["task_started", "task_completed", "task_failed"]
    )
    poll_timeout: int = 30

    @classmethod
    def from_env(cls) -> TelegramConfig | None:
        """Create config from environment variables.

        Returns:
            TelegramConfig or None if required vars not set.
        """
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

        if not bot_token:
            return None

        return cls(
            bot_token=bot_token,
            chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
            poll_timeout=int(os.environ.get("TELEGRAM_POLL_TIMEOUT", "30")),
        )

    @classmethod
    def from_config_file(cls, path: Path | None = None) -> TelegramConfig | None:
        """Load config from TOML file.

        Args:
            path: Path to config file (default: ~/.adw/config.toml).

        Returns:
            TelegramConfig or None if not configured.
        """
        if path is None:
            path = Path.home() / ".adw" / "config.toml"

        if not path.exists():
            return None

        try:
            import tomli

            with open(path, "rb") as f:
                config = tomli.load(f)
        except ImportError:
            # Fallback: simple TOML parsing
            config = _parse_simple_toml(path)

        telegram_config = config.get("telegram", {})
        if not telegram_config.get("bot_token"):
            return None

        return cls(
            bot_token=telegram_config["bot_token"],
            chat_id=telegram_config.get("chat_id"),
            notification_events=telegram_config.get(
                "notification_events",
                ["task_started", "task_completed", "task_failed"],
            ),
            poll_timeout=int(telegram_config.get("poll_timeout", 30)),
        )

    @classmethod
    def load(cls) -> TelegramConfig | None:
        """Load config from environment or config file.

        Prefers environment variables over config file.

        Returns:
            TelegramConfig or None if not configured.
        """
        # Try environment first
        config = cls.from_env()
        if config:
            return config

        # Fall back to config file
        return cls.from_config_file()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "chat_id": self.chat_id,
            "notification_events": self.notification_events,
            "poll_timeout": self.poll_timeout,
        }


# =============================================================================
# Telegram Bot API Client
# =============================================================================


class TelegramClient:
    """Simple Telegram Bot API client using urllib (no external dependencies).

    Uses the Telegram Bot API: https://core.telegram.org/bots/api
    """

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str) -> None:
        """Initialize client with bot token.

        Args:
            bot_token: Telegram bot token from @BotFather.
        """
        self.bot_token = bot_token
        self._rate_limit_reset: float = 0
        self._last_update_id: int = 0

    def _request(
        self,
        method: str,
        data: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any] | None:
        """Make an API request.

        Args:
            method: Telegram API method (e.g., "sendMessage").
            data: Request body data.
            timeout: Request timeout in seconds.

        Returns:
            Response JSON or None on error.
        """
        # Rate limit check
        if time.time() < self._rate_limit_reset:
            wait_time = self._rate_limit_reset - time.time()
            console.print(f"[yellow]Rate limited, waiting {wait_time:.1f}s...[/yellow]")
            time.sleep(wait_time)

        url = f"{self.BASE_URL}{self.bot_token}/{method}"

        headers = {
            "Content-Type": "application/json",
        }

        body = json.dumps(data).encode("utf-8") if data else None

        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

                if not result.get("ok"):
                    error_code = result.get("error_code", "unknown")
                    description = result.get("description", "Unknown error")
                    console.print(f"[red]Telegram API error {error_code}: {description}[/red]")
                    return None

                return result.get("result")

        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited
                retry_after = int(e.headers.get("Retry-After", 30))
                self._rate_limit_reset = time.time() + retry_after
                console.print(f"[yellow]Rate limited, retry after {retry_after}s[/yellow]")
            else:
                console.print(f"[red]HTTP error {e.code}: {e.reason}[/red]")
            return None
        except urllib.error.URLError as e:
            console.print(f"[red]URL error: {e.reason}[/red]")
            return None
        except json.JSONDecodeError as e:
            console.print(f"[red]JSON decode error: {e}[/red]")
            return None
        except TimeoutError:
            # Timeout is normal for long polling
            return None

    def get_me(self) -> dict[str, Any] | None:
        """Get bot information.

        Returns:
            Bot info dict or None on error.
        """
        return self._request("getMe")

    def get_updates(
        self,
        offset: int | None = None,
        limit: int = 100,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Get pending updates using long polling.

        Args:
            offset: Identifier of the first update to be returned.
            limit: Maximum number of updates to retrieve.
            timeout: Timeout in seconds for long polling.

        Returns:
            List of update objects.
        """
        data: dict[str, Any] = {
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }

        if offset is not None:
            data["offset"] = offset

        result = self._request("getUpdates", data, timeout=timeout + 5)
        return result if result else []

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "HTML",
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Send a text message.

        Args:
            chat_id: Target chat ID.
            text: Message text (supports HTML formatting).
            parse_mode: Parse mode (HTML, Markdown, MarkdownV2).
            reply_to_message_id: Message ID to reply to.
            reply_markup: Inline keyboard or reply markup.

        Returns:
            Sent message object or None on error.
        """
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        if reply_markup:
            data["reply_markup"] = reply_markup

        return self._request("sendMessage", data)

    def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Edit a message's text.

        Args:
            chat_id: Chat ID containing the message.
            message_id: Message ID to edit.
            text: New message text.
            parse_mode: Parse mode.
            reply_markup: New inline keyboard.

        Returns:
            Edited message object or None on error.
        """
        data: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        return self._request("editMessageText", data)

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> bool:
        """Answer a callback query (button press).

        Args:
            callback_query_id: ID of the callback query.
            text: Text to show to user.
            show_alert: Show as alert popup instead of toast.

        Returns:
            True on success.
        """
        data: dict[str, Any] = {
            "callback_query_id": callback_query_id,
        }

        if text:
            data["text"] = text
            data["show_alert"] = show_alert

        result = self._request("answerCallbackQuery", data)
        return result is not None

    def delete_message(
        self,
        chat_id: int | str,
        message_id: int,
    ) -> bool:
        """Delete a message.

        Args:
            chat_id: Chat ID containing the message.
            message_id: Message ID to delete.

        Returns:
            True on success.
        """
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        result = self._request("deleteMessage", data)
        return result is True


# =============================================================================
# Message Formatting
# =============================================================================


def format_task_started_message(
    adw_id: str,
    description: str,
    workflow: str,
    model: str,
    user: str | None = None,
) -> str:
    """Format task started notification message.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        workflow: Workflow type.
        model: Model being used.
        user: User who created the task.

    Returns:
        Formatted HTML message.
    """
    lines = [
        "🚀 <b>Task Started</b>",
        "",
        f"<b>ID:</b> <code>{adw_id}</code>",
        f"<b>Description:</b> {_escape_html(description[:200])}",
        f"<b>Workflow:</b> {workflow}",
        f"<b>Model:</b> {model}",
    ]

    if user:
        lines.append(f"<b>Created by:</b> {_escape_html(user)}")

    lines.append(f"\n<i>Started at {datetime.now().strftime('%H:%M:%S')}</i>")

    return "\n".join(lines)


def format_task_completed_message(
    adw_id: str,
    description: str,
    duration: str | None = None,
    pr_url: str | None = None,
) -> str:
    """Format task completed notification message.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        duration: Task duration string.
        pr_url: Pull request URL if created.

    Returns:
        Formatted HTML message.
    """
    lines = [
        "✅ <b>Task Completed</b>",
        "",
        f"<b>ID:</b> <code>{adw_id}</code>",
        f"<b>Description:</b> {_escape_html(description[:200])}",
    ]

    if duration:
        lines.append(f"<b>Duration:</b> {duration}")

    if pr_url:
        lines.append(f"<b>PR:</b> <a href=\"{pr_url}\">{pr_url}</a>")

    lines.append(f"\n<i>Completed at {datetime.now().strftime('%H:%M:%S')}</i>")

    return "\n".join(lines)


def format_task_failed_message(
    adw_id: str,
    description: str,
    error: str | None = None,
) -> str:
    """Format task failed notification message.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        error: Error message.

    Returns:
        Formatted HTML message.
    """
    lines = [
        "❌ <b>Task Failed</b>",
        "",
        f"<b>ID:</b> <code>{adw_id}</code>",
        f"<b>Description:</b> {_escape_html(description[:200])}",
    ]

    if error:
        # Truncate and escape error
        error_text = error[:500] if len(error) > 500 else error
        lines.append(f"\n<b>Error:</b>\n<pre>{_escape_html(error_text)}</pre>")

    lines.append(f"\n<i>Failed at {datetime.now().strftime('%H:%M:%S')}</i>")

    return "\n".join(lines)


def format_approval_request_message(
    adw_id: str,
    description: str,
    plan_summary: str | None = None,
) -> str:
    """Format approval request message.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        plan_summary: Summary of the plan awaiting approval.

    Returns:
        Formatted HTML message.
    """
    lines = [
        "⏳ <b>Approval Required</b>",
        "",
        f"<b>ID:</b> <code>{adw_id}</code>",
        f"<b>Description:</b> {_escape_html(description[:200])}",
    ]

    if plan_summary:
        summary_text = plan_summary[:1000] if len(plan_summary) > 1000 else plan_summary
        lines.append(f"\n<b>Plan:</b>\n<pre>{_escape_html(summary_text)}</pre>")

    lines.append("\n<i>Use the buttons below to approve or reject.</i>")

    return "\n".join(lines)


def format_status_message(tasks: list[dict[str, Any]]) -> str:
    """Format status overview message.

    Args:
        tasks: List of task info dicts.

    Returns:
        Formatted HTML message.
    """
    if not tasks:
        return "📋 <b>No active tasks</b>\n\nUse /task to create a new task."

    lines = ["📋 <b>Active Tasks</b>", ""]

    status_emoji = {
        "pending": "⏳",
        "in_progress": "🟡",
        "completed": "✅",
        "failed": "❌",
        "awaiting_review": "👀",
    }

    for task in tasks[:10]:  # Limit to 10 tasks
        emoji = status_emoji.get(task.get("status", "pending"), "❓")
        adw_id = task.get("adw_id", "unknown")
        desc = task.get("description", "No description")[:50]
        lines.append(f"{emoji} <code>{adw_id}</code> - {_escape_html(desc)}")

    if len(tasks) > 10:
        lines.append(f"\n<i>...and {len(tasks) - 10} more tasks</i>")

    return "\n".join(lines)


def format_help_message() -> str:
    """Format help message with available commands.

    Returns:
        Formatted HTML message.
    """
    return """🤖 <b>ADW Bot Commands</b>

<b>Task Management</b>
/task &lt;description&gt; - Create a new task
/status - Show all active tasks
/status &lt;task_id&gt; - Show specific task status

<b>Approval Workflow</b>
/approve &lt;task_id&gt; - Approve a pending task
/reject &lt;task_id&gt; [reason] - Reject a pending task

<b>Options</b>
Add tags to customize workflow:
• <code>{opus}</code> - Use Claude Opus model
• <code>{haiku}</code> - Use Claude Haiku model
• <code>{sdlc}</code> - Use full SDLC workflow
• <code>{simple}</code> - Use simple workflow

<b>Example</b>
<code>/task Add user authentication {opus}</code>

<b>Info</b>
/help - Show this help message"""


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: Text to escape.

    Returns:
        HTML-escaped text.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# =============================================================================
# Inline Keyboards
# =============================================================================


def make_approve_reject_keyboard(adw_id: str) -> dict[str, Any]:
    """Create inline keyboard with approve/reject buttons.

    Args:
        adw_id: ADW task ID for callback data.

    Returns:
        Inline keyboard markup.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve_{adw_id}"},
                {"text": "❌ Reject", "callback_data": f"reject_{adw_id}"},
            ],
            [
                {"text": "📋 View Details", "callback_data": f"details_{adw_id}"},
            ],
        ]
    }


def make_retry_keyboard(adw_id: str) -> dict[str, Any]:
    """Create inline keyboard with retry button.

    Args:
        adw_id: ADW task ID for callback data.

    Returns:
        Inline keyboard markup.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 Retry", "callback_data": f"retry_{adw_id}"},
                {"text": "📋 View Logs", "callback_data": f"logs_{adw_id}"},
            ],
        ]
    }


# =============================================================================
# State Management
# =============================================================================


@dataclass
class TelegramTaskState:
    """State for a task tracked via Telegram.

    Attributes:
        adw_id: ADW task ID.
        chat_id: Telegram chat ID.
        message_id: Message ID for status updates.
        user_id: Telegram user ID who created the task.
        username: Telegram username.
        description: Task description.
        workflow: Workflow type used.
        model: Model used.
        status: Current task status.
        created_at: Creation timestamp.
    """

    adw_id: str
    chat_id: int
    message_id: int | None = None
    user_id: int | None = None
    username: str | None = None
    description: str = ""
    workflow: str = "standard"
    model: str = "sonnet"
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "adw_id": self.adw_id,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "username": self.username,
            "description": self.description,
            "workflow": self.workflow,
            "model": self.model,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelegramTaskState:
        """Create from dictionary."""
        return cls(
            adw_id=data["adw_id"],
            chat_id=data["chat_id"],
            message_id=data.get("message_id"),
            user_id=data.get("user_id"),
            username=data.get("username"),
            description=data.get("description", ""),
            workflow=data.get("workflow", "standard"),
            model=data.get("model", "sonnet"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


def load_telegram_state() -> dict[str, TelegramTaskState]:
    """Load Telegram state from file.

    Returns:
        Dict mapping adw_id to TelegramTaskState.
    """
    if not TELEGRAM_STATE_FILE.exists():
        return {}

    try:
        with open(TELEGRAM_STATE_FILE) as f:
            data = json.load(f)
        return {
            adw_id: TelegramTaskState.from_dict(task_data)
            for adw_id, task_data in data.get("tasks", {}).items()
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def save_telegram_state(tasks: dict[str, TelegramTaskState]) -> None:
    """Save Telegram state to file.

    Args:
        tasks: Dict mapping adw_id to TelegramTaskState.
    """
    ADW_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "tasks": {adw_id: task.to_dict() for adw_id, task in tasks.items()},
        "updated_at": datetime.now().isoformat(),
    }

    with open(TELEGRAM_STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_task_state(adw_id: str) -> TelegramTaskState | None:
    """Get state for a specific task.

    Args:
        adw_id: ADW task ID.

    Returns:
        TelegramTaskState or None if not found.
    """
    tasks = load_telegram_state()
    return tasks.get(adw_id)


def update_task_state(
    adw_id: str,
    status: str | None = None,
    message_id: int | None = None,
) -> TelegramTaskState | None:
    """Update task state.

    Args:
        adw_id: ADW task ID.
        status: New status.
        message_id: New message ID.

    Returns:
        Updated TelegramTaskState or None if not found.
    """
    tasks = load_telegram_state()
    task = tasks.get(adw_id)

    if not task:
        return None

    if status:
        task.status = status
    if message_id:
        task.message_id = message_id

    save_telegram_state(tasks)
    return task


# =============================================================================
# Command Handlers
# =============================================================================


def handle_task_command(
    client: TelegramClient,
    chat_id: int,
    user_id: int,
    username: str | None,
    args: str,
) -> None:
    """Handle /task command to create a new task.

    Args:
        client: Telegram client.
        chat_id: Chat ID.
        user_id: User ID.
        username: Username.
        args: Command arguments (task description).
    """
    if not args.strip():
        client.send_message(
            chat_id,
            "❌ Please provide a task description.\n\nUsage: /task <description>",
        )
        return

    from ..agent.utils import generate_adw_id
    from ..triggers.webhook import _trigger_workflow_async

    adw_id = generate_adw_id()
    description = args.strip()

    # Parse model tags
    workflow = "standard"
    model = "sonnet"

    if "{opus}" in description.lower():
        model = "opus"
        description = description.replace("{opus}", "").replace("{Opus}", "").strip()
    elif "{haiku}" in description.lower():
        model = "haiku"
        description = description.replace("{haiku}", "").replace("{Haiku}", "").strip()

    # Parse workflow tags
    if "{sdlc}" in description.lower():
        workflow = "sdlc"
        description = description.replace("{sdlc}", "").replace("{SDLC}", "").strip()
    elif "{simple}" in description.lower():
        workflow = "simple"
        description = description.replace("{simple}", "").replace("{Simple}", "").strip()

    # Save task state
    tasks = load_telegram_state()
    task_state = TelegramTaskState(
        adw_id=adw_id,
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        description=description,
        workflow=workflow,
        model=model,
        status="in_progress",
    )
    tasks[adw_id] = task_state
    save_telegram_state(tasks)

    # Trigger workflow
    _trigger_workflow_async(
        task=description,
        body=f"Created via Telegram by @{username or user_id}",
        adw_id=adw_id,
        workflow=workflow,
        model=model,
        worktree_name=f"telegram-{adw_id}",
    )

    # Send confirmation message
    message = format_task_started_message(
        adw_id=adw_id,
        description=description,
        workflow=workflow,
        model=model,
        user=username or str(user_id),
    )

    result = client.send_message(chat_id, message)

    # Update state with message ID
    if result:
        update_task_state(adw_id, message_id=result.get("message_id"))


def handle_status_command(
    client: TelegramClient,
    chat_id: int,
    args: str,
) -> None:
    """Handle /status command to check task status.

    Args:
        client: Telegram client.
        chat_id: Chat ID.
        args: Command arguments (optional task ID).
    """
    task_id = args.strip() if args else None

    if task_id:
        # Show specific task status
        task = get_task_state(task_id)
        if not task:
            # Try to find by partial ID
            tasks = load_telegram_state()
            for adw_id, t in tasks.items():
                if adw_id.startswith(task_id):
                    task = t
                    break

        if not task:
            client.send_message(chat_id, f"❌ Task not found: <code>{task_id}</code>")
            return

        status_emoji = {
            "pending": "⏳",
            "in_progress": "🟡",
            "completed": "✅",
            "failed": "❌",
            "awaiting_review": "👀",
        }

        emoji = status_emoji.get(task.status, "❓")
        message = f"""📋 <b>Task Details</b>

<b>ID:</b> <code>{task.adw_id}</code>
<b>Status:</b> {emoji} {task.status}
<b>Description:</b> {_escape_html(task.description[:200])}
<b>Workflow:</b> {task.workflow}
<b>Model:</b> {task.model}
<b>Created:</b> {task.created_at}"""

        client.send_message(chat_id, message)
    else:
        # Show all tasks
        tasks = load_telegram_state()
        task_list = [
            {
                "adw_id": t.adw_id,
                "status": t.status,
                "description": t.description,
            }
            for t in tasks.values()
        ]

        # Sort by creation time (most recent first)
        task_list.sort(key=lambda t: t.get("adw_id", ""), reverse=True)

        message = format_status_message(task_list)
        client.send_message(chat_id, message)


def handle_approve_command(
    client: TelegramClient,
    chat_id: int,
    args: str,
) -> None:
    """Handle /approve command to approve a pending task.

    Args:
        client: Telegram client.
        chat_id: Chat ID.
        args: Command arguments (task ID).
    """
    if not args.strip():
        client.send_message(
            chat_id,
            "❌ Please provide a task ID.\n\nUsage: /approve <task_id>",
        )
        return

    task_id = args.strip().split()[0]
    task = get_task_state(task_id)

    if not task:
        # Try partial match
        tasks = load_telegram_state()
        for adw_id, t in tasks.items():
            if adw_id.startswith(task_id):
                task = t
                task_id = adw_id
                break

    if not task:
        client.send_message(chat_id, f"❌ Task not found: <code>{task_id}</code>")
        return

    # Approve the task
    from ..github.approval_gate import approve_task

    try:
        approve_task(task_id)
        update_task_state(task_id, status="in_progress")
        client.send_message(
            chat_id,
            f"✅ Task <code>{task_id}</code> approved!\n\nWorkflow will continue.",
        )
    except Exception as e:
        client.send_message(
            chat_id,
            f"❌ Failed to approve task: {_escape_html(str(e))}",
        )


def handle_reject_command(
    client: TelegramClient,
    chat_id: int,
    args: str,
) -> None:
    """Handle /reject command to reject a pending task.

    Args:
        client: Telegram client.
        chat_id: Chat ID.
        args: Command arguments (task ID and optional reason).
    """
    if not args.strip():
        client.send_message(
            chat_id,
            "❌ Please provide a task ID.\n\nUsage: /reject <task_id> [reason]",
        )
        return

    parts = args.strip().split(maxsplit=1)
    task_id = parts[0]
    reason = parts[1] if len(parts) > 1 else "Rejected via Telegram"

    task = get_task_state(task_id)

    if not task:
        # Try partial match
        tasks = load_telegram_state()
        for adw_id, t in tasks.items():
            if adw_id.startswith(task_id):
                task = t
                task_id = adw_id
                break

    if not task:
        client.send_message(chat_id, f"❌ Task not found: <code>{task_id}</code>")
        return

    # Reject the task
    from ..github.approval_gate import reject_task

    try:
        reject_task(task_id, reason)
        update_task_state(task_id, status="failed")
        client.send_message(
            chat_id,
            f"❌ Task <code>{task_id}</code> rejected.\n\n<b>Reason:</b> {_escape_html(reason)}",
        )
    except Exception as e:
        client.send_message(
            chat_id,
            f"❌ Failed to reject task: {_escape_html(str(e))}",
        )


def handle_help_command(client: TelegramClient, chat_id: int) -> None:
    """Handle /help command to show available commands.

    Args:
        client: Telegram client.
        chat_id: Chat ID.
    """
    client.send_message(chat_id, format_help_message())


# =============================================================================
# Callback Query Handlers
# =============================================================================


def handle_callback_query(
    client: TelegramClient,
    callback_query: dict[str, Any],
) -> None:
    """Handle callback query from inline keyboard button press.

    Args:
        client: Telegram client.
        callback_query: Callback query object from update.
    """
    query_id = callback_query.get("id", "")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if not data or not chat_id:
        client.answer_callback_query(query_id, "Invalid callback data")
        return

    # Parse callback data: action_taskid
    if "_" not in data:
        client.answer_callback_query(query_id, "Invalid callback format")
        return

    action, task_id = data.split("_", 1)

    if action == "approve":
        _handle_approve_callback(client, query_id, chat_id, task_id)
    elif action == "reject":
        _handle_reject_callback(client, query_id, chat_id, task_id)
    elif action == "details":
        _handle_details_callback(client, query_id, chat_id, task_id)
    elif action == "retry":
        _handle_retry_callback(client, query_id, chat_id, task_id)
    elif action == "logs":
        _handle_logs_callback(client, query_id, chat_id, task_id)
    else:
        client.answer_callback_query(query_id, f"Unknown action: {action}")


def _handle_approve_callback(
    client: TelegramClient,
    query_id: str,
    chat_id: int,
    task_id: str,
) -> None:
    """Handle approve button callback."""
    from ..github.approval_gate import approve_task

    try:
        approve_task(task_id)
        update_task_state(task_id, status="in_progress")
        client.answer_callback_query(query_id, "Task approved!")
        client.send_message(
            chat_id,
            f"✅ Task <code>{task_id}</code> approved! Workflow continuing...",
        )
    except Exception as e:
        client.answer_callback_query(query_id, f"Error: {str(e)[:100]}", show_alert=True)


def _handle_reject_callback(
    client: TelegramClient,
    query_id: str,
    chat_id: int,
    task_id: str,
) -> None:
    """Handle reject button callback."""
    from ..github.approval_gate import reject_task

    try:
        reject_task(task_id, "Rejected via Telegram button")
        update_task_state(task_id, status="failed")
        client.answer_callback_query(query_id, "Task rejected!")
        client.send_message(
            chat_id,
            f"❌ Task <code>{task_id}</code> rejected.",
        )
    except Exception as e:
        client.answer_callback_query(query_id, f"Error: {str(e)[:100]}", show_alert=True)


def _handle_details_callback(
    client: TelegramClient,
    query_id: str,
    chat_id: int,
    task_id: str,
) -> None:
    """Handle details button callback."""
    task = get_task_state(task_id)

    if not task:
        client.answer_callback_query(query_id, "Task not found", show_alert=True)
        return

    client.answer_callback_query(query_id)
    handle_status_command(client, chat_id, task_id)


def _handle_retry_callback(
    client: TelegramClient,
    query_id: str,
    chat_id: int,
    task_id: str,
) -> None:
    """Handle retry button callback."""
    task = get_task_state(task_id)

    if not task:
        client.answer_callback_query(query_id, "Task not found", show_alert=True)
        return

    from ..triggers.webhook import _trigger_workflow_async

    _trigger_workflow_async(
        task=task.description,
        body="Retried via Telegram",
        adw_id=task_id,
        workflow=task.workflow,
        model=task.model,
        worktree_name=f"retry-{task_id}",
    )

    update_task_state(task_id, status="in_progress")
    client.answer_callback_query(query_id, "Task retry started!")
    client.send_message(
        chat_id,
        f"🔄 Retrying task <code>{task_id}</code>...",
    )


def _handle_logs_callback(
    client: TelegramClient,
    query_id: str,
    chat_id: int,
    task_id: str,
) -> None:
    """Handle view logs button callback."""
    from pathlib import Path

    log_path = Path("agents") / task_id / "agent.log"

    if not log_path.exists():
        client.answer_callback_query(query_id, "No logs found", show_alert=True)
        return

    client.answer_callback_query(query_id)

    try:
        # Read last 20 lines of log
        with open(log_path) as f:
            lines = f.readlines()[-20:]

        log_text = "".join(lines)
        if len(log_text) > 3000:
            log_text = log_text[-3000:]

        message = f"📋 <b>Logs for {task_id}</b>\n\n<pre>{_escape_html(log_text)}</pre>"
        client.send_message(chat_id, message)
    except Exception as e:
        client.send_message(chat_id, f"❌ Error reading logs: {_escape_html(str(e))}")


# =============================================================================
# Update Processing
# =============================================================================


def process_update(client: TelegramClient, update: dict[str, Any]) -> None:
    """Process a single update from Telegram.

    Args:
        client: Telegram client.
        update: Update object from getUpdates.
    """
    # Handle callback queries (button presses)
    if "callback_query" in update:
        handle_callback_query(client, update["callback_query"])
        return

    # Handle messages
    message = update.get("message")
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    username = message.get("from", {}).get("username")
    text = message.get("text", "")

    if not chat_id or not text:
        return

    # Parse command
    if not text.startswith("/"):
        return

    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Remove bot username if present (e.g., /task@adw_bot)
    if "@" in command:
        command = command.split("@")[0]

    # Route to handler
    if command == "/task":
        handle_task_command(client, chat_id, user_id, username, args)
    elif command == "/status":
        handle_status_command(client, chat_id, args)
    elif command == "/approve":
        handle_approve_command(client, chat_id, args)
    elif command == "/reject":
        handle_reject_command(client, chat_id, args)
    elif command in ("/help", "/start"):
        handle_help_command(client, chat_id)


# =============================================================================
# Notification Functions
# =============================================================================


def notify_task_started(
    adw_id: str,
    description: str,
    workflow: str = "standard",
    model: str = "sonnet",
) -> bool:
    """Send task started notification to configured chat.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        workflow: Workflow type.
        model: Model being used.

    Returns:
        True if notification sent successfully.
    """
    config = TelegramConfig.load()
    if not config or not config.chat_id:
        return False

    if "task_started" not in config.notification_events:
        return False

    client = TelegramClient(config.bot_token)
    message = format_task_started_message(adw_id, description, workflow, model)
    result = client.send_message(config.chat_id, message)
    return result is not None


def notify_task_completed(
    adw_id: str,
    description: str = "",
    duration: str | None = None,
    pr_url: str | None = None,
) -> bool:
    """Send task completed notification.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        duration: Task duration.
        pr_url: Pull request URL.

    Returns:
        True if notification sent successfully.
    """
    config = TelegramConfig.load()
    if not config or not config.chat_id:
        return False

    if "task_completed" not in config.notification_events:
        return False

    # Get description from state if not provided
    if not description:
        task = get_task_state(adw_id)
        if task:
            description = task.description

    client = TelegramClient(config.bot_token)
    message = format_task_completed_message(adw_id, description, duration, pr_url)
    result = client.send_message(config.chat_id, message)

    # Update state
    update_task_state(adw_id, status="completed")

    return result is not None


def notify_task_failed(
    adw_id: str,
    description: str = "",
    error: str | None = None,
) -> bool:
    """Send task failed notification.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        error: Error message.

    Returns:
        True if notification sent successfully.
    """
    config = TelegramConfig.load()
    if not config or not config.chat_id:
        return False

    if "task_failed" not in config.notification_events:
        return False

    # Get description from state if not provided
    if not description:
        task = get_task_state(adw_id)
        if task:
            description = task.description

    client = TelegramClient(config.bot_token)
    message = format_task_failed_message(adw_id, description, error)
    keyboard = make_retry_keyboard(adw_id)
    result = client.send_message(config.chat_id, message, reply_markup=keyboard)

    # Update state
    update_task_state(adw_id, status="failed")

    return result is not None


def request_approval(
    adw_id: str,
    description: str = "",
    plan_summary: str | None = None,
) -> bool:
    """Send approval request notification.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        plan_summary: Summary of the plan.

    Returns:
        True if notification sent successfully.
    """
    config = TelegramConfig.load()
    if not config or not config.chat_id:
        return False

    # Get description from state if not provided
    if not description:
        task = get_task_state(adw_id)
        if task:
            description = task.description

    client = TelegramClient(config.bot_token)
    message = format_approval_request_message(adw_id, description, plan_summary)
    keyboard = make_approve_reject_keyboard(adw_id)
    result = client.send_message(config.chat_id, message, reply_markup=keyboard)

    # Update state
    update_task_state(adw_id, status="awaiting_review")

    return result is not None


# =============================================================================
# Bot Runner
# =============================================================================


def run_telegram_bot(config: TelegramConfig | None = None) -> None:
    """Run the Telegram bot with long polling.

    Args:
        config: Telegram configuration. If None, loads from environment/config.
    """
    if config is None:
        config = TelegramConfig.load()

    if not config:
        console.print("[red]Telegram not configured. Set TELEGRAM_BOT_TOKEN.[/red]")
        return

    client = TelegramClient(config.bot_token)

    # Verify bot token
    me = client.get_me()
    if not me:
        console.print("[red]Failed to connect to Telegram. Check bot token.[/red]")
        return

    bot_name = me.get("username", "Unknown")
    console.print(f"[green]Connected as @{bot_name}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    # Long polling loop
    offset = None
    while True:
        try:
            updates = client.get_updates(
                offset=offset,
                timeout=config.poll_timeout,
            )

            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1

                try:
                    process_update(client, update)
                except Exception as e:
                    console.print(f"[red]Error processing update: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping bot...[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Polling error: {e}[/red]")
            time.sleep(5)


def test_telegram_connection() -> bool:
    """Test Telegram connection and display bot info.

    Returns:
        True if connection successful.
    """
    config = TelegramConfig.load()

    if not config:
        console.print("[red]Telegram not configured.[/red]")
        console.print("\nSet environment variables:")
        console.print("  TELEGRAM_BOT_TOKEN=your_bot_token")
        console.print("  TELEGRAM_CHAT_ID=your_chat_id (optional)")
        console.print("\nOr add to ~/.adw/config.toml:")
        console.print("  [telegram]")
        console.print('  bot_token = "123456789:ABC..."')
        console.print('  chat_id = "123456789"')
        return False

    client = TelegramClient(config.bot_token)
    me = client.get_me()

    if not me:
        console.print("[red]Failed to connect to Telegram.[/red]")
        return False

    console.print("[green]Telegram connection successful![/green]")
    console.print(f"  Bot: @{me.get('username', 'Unknown')}")
    console.print(f"  Name: {me.get('first_name', 'Unknown')}")
    console.print(f"  ID: {me.get('id', 'Unknown')}")

    if config.chat_id:
        console.print(f"  Default chat: {config.chat_id}")

    return True


def send_test_message(message: str = "Hello from ADW!") -> bool:
    """Send a test message to configured chat.

    Args:
        message: Message to send.

    Returns:
        True if message sent successfully.
    """
    config = TelegramConfig.load()

    if not config:
        console.print("[red]Telegram not configured.[/red]")
        return False

    if not config.chat_id:
        console.print("[red]No chat_id configured for notifications.[/red]")
        return False

    client = TelegramClient(config.bot_token)
    result = client.send_message(config.chat_id, message)

    if result:
        console.print("[green]Message sent successfully![/green]")
        return True
    else:
        console.print("[red]Failed to send message.[/red]")
        return False


# =============================================================================
# TOML Fallback Parser
# =============================================================================


def _parse_simple_toml(path: Path) -> dict[str, Any]:
    """Simple TOML parser for basic key-value sections.

    Args:
        path: Path to TOML file.

    Returns:
        Parsed config dict.
    """
    config: dict[str, Any] = {}
    current_section: dict[str, Any] | None = None

    with open(path) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Section header
            if line.startswith("[") and line.endswith("]"):
                section_name = line[1:-1].strip()
                config[section_name] = {}
                current_section = config[section_name]
                continue

            # Key-value pair
            if "=" in line and current_section is not None:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                # Parse as int if numeric
                elif value.isdigit():
                    value = int(value)  # type: ignore[assignment]
                # Parse as bool
                elif value.lower() in ("true", "false"):
                    value = value.lower() == "true"  # type: ignore[assignment]

                current_section[key] = value

    return config
