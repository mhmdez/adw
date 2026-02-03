"""Slack integration for ADW.

Enables ADW to receive commands from Slack slash commands and
send progress updates to channels/threads.

Configuration:
    Environment variables:
    - SLACK_BOT_TOKEN: Slack bot token (xoxb-...) (required)
    - SLACK_SIGNING_SECRET: Slack signing secret for request verification (required)
    - SLACK_CHANNEL_ID: Default channel for notifications (optional)

    Or via config file (~/.adw/config.toml):
    [slack]
    bot_token = "xoxb-..."
    signing_secret = "..."
    channel_id = "C01234567"

Features:
    - Slash commands: /adw create, /adw status, /adw approve
    - Thread-based progress updates
    - Button interactions for approve/reject workflows
    - Rate limiting for Slack API calls
"""

from __future__ import annotations

import hashlib
import hmac
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
SLACK_STATE_FILE = ADW_DIR / "slack_state.json"


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SlackConfig:
    """Configuration for Slack integration.

    Attributes:
        bot_token: Slack bot token (xoxb-...).
        signing_secret: Slack signing secret for request verification.
        channel_id: Default channel for notifications.
        notification_events: Events to notify on.
    """

    bot_token: str
    signing_secret: str
    channel_id: str | None = None
    notification_events: list[str] = field(default_factory=lambda: ["task_started", "task_completed", "task_failed"])

    @classmethod
    def from_env(cls) -> SlackConfig | None:
        """Create config from environment variables.

        Returns:
            SlackConfig or None if required vars not set.
        """
        bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
        signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")

        if not bot_token or not signing_secret:
            return None

        return cls(
            bot_token=bot_token,
            signing_secret=signing_secret,
            channel_id=os.environ.get("SLACK_CHANNEL_ID"),
        )

    @classmethod
    def from_config_file(cls, path: Path | None = None) -> SlackConfig | None:
        """Load config from TOML file.

        Args:
            path: Path to config file (default: ~/.adw/config.toml).

        Returns:
            SlackConfig or None if not configured.
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

        slack_config = config.get("slack", {})
        if not slack_config.get("bot_token") or not slack_config.get("signing_secret"):
            return None

        return cls(
            bot_token=slack_config["bot_token"],
            signing_secret=slack_config["signing_secret"],
            channel_id=slack_config.get("channel_id"),
            notification_events=slack_config.get(
                "notification_events",
                ["task_started", "task_completed", "task_failed"],
            ),
        )

    @classmethod
    def load(cls) -> SlackConfig | None:
        """Load config from environment or config file.

        Prefers environment variables over config file.

        Returns:
            SlackConfig or None if not configured.
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
            "channel_id": self.channel_id,
            "notification_events": self.notification_events,
        }


# =============================================================================
# Slack API Client
# =============================================================================


class SlackClient:
    """Simple Slack API client using urllib (no external dependencies).

    Uses the Slack Web API.
    """

    BASE_URL = "https://slack.com/api"

    def __init__(self, bot_token: str) -> None:
        """Initialize client with bot token.

        Args:
            bot_token: Slack bot token (xoxb-...).
        """
        self.bot_token = bot_token
        self._rate_limit_reset: float = 0

    def _request(
        self,
        method: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Make an API request.

        Args:
            method: Slack API method (e.g., "chat.postMessage").
            data: Request body data.

        Returns:
            Response JSON or None on error.
        """
        # Rate limit check
        if time.time() < self._rate_limit_reset:
            wait_time = self._rate_limit_reset - time.time()
            console.print(f"[yellow]Rate limited, waiting {wait_time:.1f}s...[/yellow]")
            time.sleep(wait_time)

        url = f"{self.BASE_URL}/{method}"

        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        body = json.dumps(data or {}).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                # Check for rate limit headers
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    self._rate_limit_reset = time.time() + float(retry_after)

                result: dict[str, Any] = json.loads(response.read().decode("utf-8"))

                if not result.get("ok"):
                    error = result.get("error", "unknown_error")
                    console.print(f"[red]Slack API error: {error}[/red]")
                    return None

                return result

        except urllib.error.HTTPError as e:
            # Handle rate limiting
            if e.code == 429:
                retry_after = e.headers.get("Retry-After", "60")
                self._rate_limit_reset = time.time() + float(retry_after)
                console.print(f"[yellow]Rate limited, retry after {retry_after}s[/yellow]")
            else:
                error_body = e.read().decode("utf-8") if e.fp else ""
                console.print(f"[red]Slack API error {e.code}: {error_body}[/red]")
            return None

        except urllib.error.URLError as e:
            console.print(f"[red]Slack connection error: {e.reason}[/red]")
            return None

        except Exception as e:
            console.print(f"[red]Slack request failed: {e}[/red]")
            return None

    # -------------------------------------------------------------------------
    # Chat Methods
    # -------------------------------------------------------------------------

    def post_message(
        self,
        channel: str,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Post a message to a channel.

        Args:
            channel: Channel ID or name.
            text: Plain text message (fallback for notifications).
            blocks: Block Kit blocks for rich formatting.
            thread_ts: Thread timestamp to reply in thread.
            attachments: Legacy attachments.

        Returns:
            Response containing ts (timestamp) for thread replies.
        """
        data: dict[str, Any] = {"channel": channel}

        if text:
            data["text"] = text
        if blocks:
            data["blocks"] = blocks
        if thread_ts:
            data["thread_ts"] = thread_ts
        if attachments:
            data["attachments"] = attachments

        return self._request("chat.postMessage", data)

    def update_message(
        self,
        channel: str,
        ts: str,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing message.

        Args:
            channel: Channel ID.
            ts: Timestamp of the message to update.
            text: New text.
            blocks: New blocks.
            attachments: New attachments.

        Returns:
            Updated message response.
        """
        data: dict[str, Any] = {"channel": channel, "ts": ts}

        if text:
            data["text"] = text
        if blocks:
            data["blocks"] = blocks
        if attachments:
            data["attachments"] = attachments

        return self._request("chat.update", data)

    def delete_message(
        self,
        channel: str,
        ts: str,
    ) -> dict[str, Any] | None:
        """Delete a message.

        Args:
            channel: Channel ID.
            ts: Timestamp of the message to delete.

        Returns:
            Response.
        """
        return self._request("chat.delete", {"channel": channel, "ts": ts})

    def add_reaction(
        self,
        channel: str,
        ts: str,
        name: str,
    ) -> dict[str, Any] | None:
        """Add a reaction to a message.

        Args:
            channel: Channel ID.
            ts: Message timestamp.
            name: Reaction emoji name (without colons).

        Returns:
            Response.
        """
        return self._request(
            "reactions.add",
            {"channel": channel, "timestamp": ts, "name": name},
        )

    # -------------------------------------------------------------------------
    # View Methods (for modals/dialogs)
    # -------------------------------------------------------------------------

    def open_modal(
        self,
        trigger_id: str,
        view: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Open a modal view.

        Args:
            trigger_id: Trigger ID from interaction payload.
            view: Modal view definition.

        Returns:
            Response with view ID.
        """
        return self._request("views.open", {"trigger_id": trigger_id, "view": view})

    def update_modal(
        self,
        view_id: str,
        view: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update an existing modal view.

        Args:
            view_id: View ID to update.
            view: New view definition.

        Returns:
            Response.
        """
        return self._request("views.update", {"view_id": view_id, "view": view})

    # -------------------------------------------------------------------------
    # Response Methods (for interactions)
    # -------------------------------------------------------------------------

    def respond_to_interaction(
        self,
        response_url: str,
        text: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        response_type: str = "ephemeral",
        replace_original: bool = False,
    ) -> bool:
        """Respond to a Slack interaction via response_url.

        Args:
            response_url: Response URL from interaction payload.
            text: Text message.
            blocks: Block Kit blocks.
            response_type: "ephemeral" (only user) or "in_channel".
            replace_original: Replace the original message.

        Returns:
            True if successful.
        """
        data: dict[str, Any] = {"response_type": response_type}

        if text:
            data["text"] = text
        if blocks:
            data["blocks"] = blocks
        if replace_original:
            data["replace_original"] = True

        body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            response_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                status_ok: bool = response.status == 200
                return status_ok
        except Exception as e:
            console.print(f"[red]Failed to respond to interaction: {e}[/red]")
            return False

    # -------------------------------------------------------------------------
    # User/Channel Info
    # -------------------------------------------------------------------------

    def get_user_info(self, user_id: str) -> dict[str, Any] | None:
        """Get user information.

        Args:
            user_id: Slack user ID.

        Returns:
            User info dict or None.
        """
        result = self._request("users.info", {"user": user_id})
        return result.get("user") if result else None

    def get_channel_info(self, channel_id: str) -> dict[str, Any] | None:
        """Get channel information.

        Args:
            channel_id: Slack channel ID.

        Returns:
            Channel info dict or None.
        """
        result = self._request("conversations.info", {"channel": channel_id})
        return result.get("channel") if result else None

    def auth_test(self) -> dict[str, Any] | None:
        """Test authentication and get bot info.

        Returns:
            Bot info including user_id, team_id, etc.
        """
        return self._request("auth.test")


# =============================================================================
# Request Verification
# =============================================================================


def verify_slack_request(
    signing_secret: str,
    timestamp: str,
    signature: str,
    body: bytes,
) -> bool:
    """Verify a Slack request signature.

    Args:
        signing_secret: Slack signing secret.
        timestamp: X-Slack-Request-Timestamp header.
        signature: X-Slack-Signature header.
        body: Raw request body.

    Returns:
        True if signature is valid.
    """
    # Check timestamp is within 5 minutes
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            return False
    except (ValueError, TypeError):
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(signature, expected)


# =============================================================================
# Message Formatting
# =============================================================================


def format_task_started_message(
    adw_id: str,
    description: str,
    workflow: str = "standard",
    user_id: str | None = None,
) -> dict[str, Any]:
    """Format a task started notification.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        workflow: Workflow type.
        user_id: Requesting user ID (for mention).

    Returns:
        Slack message payload with blocks.
    """
    mention = f"<@{user_id}> " if user_id else ""

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":rocket: *Task Started*\n\n{mention}{description[:200]}",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"ADW ID: `{adw_id}`"},
                {"type": "mrkdwn", "text": f"Workflow: `{workflow}`"},
                {
                    "type": "mrkdwn",
                    "text": f"Started: <!date^{int(time.time())}^{{time}}|{datetime.now().strftime('%H:%M')}>",
                },
            ],
        },
    ]

    return {
        "text": f"Task started: {description[:100]}",
        "blocks": blocks,
    }


def format_task_completed_message(
    adw_id: str,
    description: str,
    duration_seconds: int | None = None,
    pr_url: str | None = None,
) -> dict[str, Any]:
    """Format a task completed notification.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        duration_seconds: Time taken in seconds.
        pr_url: URL to created PR.

    Returns:
        Slack message payload with blocks.
    """
    duration_str = ""
    if duration_seconds:
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        duration_str = f" in {minutes}m {seconds}s"

    pr_link = f"\n\n:link: <{pr_url}|View Pull Request>" if pr_url else ""

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":white_check_mark: *Task Completed{duration_str}*\n\n{description[:200]}{pr_link}",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"ADW ID: `{adw_id}`"},
            ],
        },
    ]

    return {
        "text": f"Task completed: {description[:100]}",
        "blocks": blocks,
    }


def format_task_failed_message(
    adw_id: str,
    description: str,
    error: str | None = None,
) -> dict[str, Any]:
    """Format a task failed notification.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        error: Error message.

    Returns:
        Slack message payload with blocks.
    """
    error_block = ""
    if error:
        error_block = f"\n\n```{error[:500]}```"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":x: *Task Failed*\n\n{description[:200]}{error_block}",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"ADW ID: `{adw_id}`"},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Retry"},
                    "style": "primary",
                    "action_id": f"retry_task_{adw_id}",
                    "value": adw_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Logs"},
                    "action_id": f"view_logs_{adw_id}",
                    "value": adw_id,
                },
            ],
        },
    ]

    return {
        "text": f"Task failed: {description[:100]}",
        "blocks": blocks,
    }


def format_approval_request_message(
    adw_id: str,
    description: str,
    plan_summary: str | None = None,
) -> dict[str, Any]:
    """Format an approval request message with buttons.

    Args:
        adw_id: ADW task ID.
        description: Task description.
        plan_summary: Summary of the implementation plan.

    Returns:
        Slack message payload with approve/reject buttons.
    """
    plan_block = ""
    if plan_summary:
        plan_block = f"\n\n*Plan Summary:*\n```{plan_summary[:800]}```"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":hourglass: *Approval Required*\n\n{description[:300]}{plan_block}",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"ADW ID: `{adw_id}`"},
                {"type": "mrkdwn", "text": "Waiting for human approval..."},
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": f"approve_task_{adw_id}",
                    "value": adw_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": f"reject_task_{adw_id}",
                    "value": adw_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Details"},
                    "action_id": f"view_details_{adw_id}",
                    "value": adw_id,
                },
            ],
        },
    ]

    return {
        "text": f"Approval required for task: {description[:100]}",
        "blocks": blocks,
    }


def format_status_message(
    tasks: list[dict[str, Any]],
    queue_summary: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Format a status overview message.

    Args:
        tasks: List of recent tasks with status.
        queue_summary: Summary counts by status.

    Returns:
        Slack message payload.
    """
    if not tasks:
        return {
            "text": "No active tasks",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":clipboard: *ADW Status*\n\nNo active tasks.",
                    },
                },
            ],
        }

    # Build task list
    task_lines = []
    for task in tasks[:10]:  # Limit to 10
        status_emoji = {
            "pending": ":hourglass:",
            "in_progress": ":gear:",
            "completed": ":white_check_mark:",
            "failed": ":x:",
            "awaiting_review": ":eyes:",
        }.get(task.get("status", "pending"), ":grey_question:")

        task_lines.append(f"{status_emoji} `{task.get('adw_id', '?')[:8]}` {task.get('description', 'Unknown')[:50]}")

    tasks_text = "\n".join(task_lines)

    # Build summary if available
    summary_text = ""
    if queue_summary:
        parts = []
        for status, count in queue_summary.items():
            if count > 0:
                parts.append(f"{status}: {count}")
        if parts:
            summary_text = f"\n\n*Summary:* {', '.join(parts)}"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":clipboard: *ADW Status*{summary_text}\n\n{tasks_text}",
            },
        },
    ]

    return {
        "text": "ADW Status",
        "blocks": blocks,
    }


# =============================================================================
# Slash Command Handling
# =============================================================================


@dataclass
class SlashCommandRequest:
    """Parsed Slack slash command request.

    Attributes:
        command: The command (e.g., "/adw").
        text: Text after the command.
        user_id: Requesting user ID.
        user_name: Requesting user name.
        channel_id: Channel where command was invoked.
        channel_name: Channel name.
        team_id: Workspace team ID.
        response_url: URL to respond to.
        trigger_id: Trigger ID for opening modals.
    """

    command: str
    text: str
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str
    team_id: str
    response_url: str
    trigger_id: str

    @classmethod
    def from_form_data(cls, data: dict[str, str]) -> SlashCommandRequest:
        """Parse from form-encoded slash command data.

        Args:
            data: Form data from Slack.

        Returns:
            Parsed SlashCommandRequest.
        """
        return cls(
            command=data.get("command", ""),
            text=data.get("text", ""),
            user_id=data.get("user_id", ""),
            user_name=data.get("user_name", ""),
            channel_id=data.get("channel_id", ""),
            channel_name=data.get("channel_name", ""),
            team_id=data.get("team_id", ""),
            response_url=data.get("response_url", ""),
            trigger_id=data.get("trigger_id", ""),
        )

    def get_subcommand(self) -> tuple[str, str]:
        """Parse subcommand and arguments from text.

        Returns:
            Tuple of (subcommand, remaining_text).
        """
        parts = self.text.strip().split(maxsplit=1)
        if not parts:
            return ("help", "")
        subcommand = parts[0].lower()
        remaining = parts[1] if len(parts) > 1 else ""
        return (subcommand, remaining)


def handle_slash_command(
    request: SlashCommandRequest,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle an /adw slash command.

    Args:
        request: Parsed slash command request.
        config: Slack configuration.

    Returns:
        Response payload (blocks and text).
    """
    subcommand, args = request.get_subcommand()

    if subcommand == "create":
        return _handle_create_command(args, request, config)
    elif subcommand == "status":
        return _handle_status_command(args, request, config)
    elif subcommand == "approve":
        return _handle_approve_command(args, request, config)
    elif subcommand == "reject":
        return _handle_reject_command(args, request, config)
    elif subcommand == "help":
        return _handle_help_command()
    else:
        return {
            "response_type": "ephemeral",
            "text": f"Unknown command: `{subcommand}`. Use `/adw help` for available commands.",
        }


def _handle_create_command(
    args: str,
    request: SlashCommandRequest,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle /adw create <task description>.

    Args:
        args: Task description.
        request: Original slash command request.
        config: Slack configuration.

    Returns:
        Response payload.
    """
    if not args.strip():
        return {
            "response_type": "ephemeral",
            "text": "Please provide a task description: `/adw create <description>`",
        }

    from ..agent.utils import generate_adw_id
    from ..triggers.webhook import _trigger_workflow_async

    adw_id = generate_adw_id()
    description = args.strip()

    # Determine workflow from tags in description
    workflow = "standard"
    model = "sonnet"

    if "{opus}" in description.lower():
        model = "opus"
        description = description.replace("{opus}", "").strip()
    elif "{haiku}" in description.lower():
        model = "haiku"
        description = description.replace("{haiku}", "").strip()

    if "{sdlc}" in description.lower():
        workflow = "sdlc"
        description = description.replace("{sdlc}", "").strip()
    elif "{simple}" in description.lower():
        workflow = "simple"
        description = description.replace("{simple}", "").strip()

    # Save thread state for updates
    _save_slack_task_state(
        adw_id=adw_id,
        channel_id=request.channel_id,
        user_id=request.user_id,
        description=description,
    )

    # Trigger workflow
    _trigger_workflow_async(
        task=description,
        body=f"Created via Slack by <@{request.user_id}> in #{request.channel_name}",
        adw_id=adw_id,
        workflow=workflow,
        model=model,
        worktree_name=f"slack-{adw_id}",
    )

    # Send immediate response
    client = SlackClient(config.bot_token)
    message = format_task_started_message(
        adw_id=adw_id,
        description=description,
        workflow=workflow,
        user_id=request.user_id,
    )

    # Post to channel (visible to all)
    result = client.post_message(
        channel=request.channel_id,
        **message,
    )

    # Save thread timestamp for updates
    if result and result.get("ts"):
        _update_slack_task_state(adw_id, thread_ts=result["ts"])

    return {
        "response_type": "in_channel",
        "text": f"Task `{adw_id}` created and processing started.",
    }


def _handle_status_command(
    args: str,
    request: SlashCommandRequest,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle /adw status [task_id].

    Args:
        args: Optional task ID.
        request: Original slash command request.
        config: Slack configuration.

    Returns:
        Response payload.
    """
    from ..agent.state import ADWState

    if args.strip():
        # Status of specific task
        adw_id = args.strip()[:8]

        try:
            state = ADWState.load(adw_id)
            if state is None:
                return {
                    "response_type": "ephemeral",
                    "text": f"Task `{adw_id}` not found.",
                }

            # Derive status from phase
            status = "in_progress"
            if state.current_phase == "complete":
                status = "completed"
            elif state.current_phase == "failed":
                status = "failed"
            elif state.current_phase == "init":
                status = "pending"

            status_emoji = {
                "pending": ":hourglass:",
                "in_progress": ":gear:",
                "completed": ":white_check_mark:",
                "failed": ":x:",
            }.get(status, ":grey_question:")

            phases_text = ", ".join(state.phases_completed) if state.phases_completed else "None"

            return {
                "response_type": "ephemeral",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{status_emoji} *Task {adw_id}*\n\n"
                            f"*Status:* {status}\n"
                            f"*Phase:* {state.current_phase}\n"
                            f"*Completed:* {phases_text}",
                        },
                    },
                ],
            }

        except FileNotFoundError:
            return {
                "response_type": "ephemeral",
                "text": f"Task `{adw_id}` not found.",
            }
    else:
        # General status
        tasks = _get_recent_tasks(limit=10)
        message = format_status_message(tasks)
        message["response_type"] = "ephemeral"
        return message


def _handle_approve_command(
    args: str,
    request: SlashCommandRequest,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle /adw approve <task_id>.

    Args:
        args: Task ID to approve.
        request: Original slash command request.
        config: Slack configuration.

    Returns:
        Response payload.
    """
    if not args.strip():
        return {
            "response_type": "ephemeral",
            "text": "Please provide a task ID: `/adw approve <task_id>`",
        }

    adw_id = args.strip()[:8]

    from ..github.approval_gate import approve_task

    success = approve_task(adw_id)

    if success:
        # Update thread message if we have one
        state = _load_slack_task_state(adw_id)
        if state and state.get("thread_ts"):
            client = SlackClient(config.bot_token)
            client.post_message(
                channel=state["channel_id"],
                text=f":white_check_mark: Task approved by <@{request.user_id}>",
                thread_ts=state["thread_ts"],
            )

        return {
            "response_type": "in_channel",
            "text": f":white_check_mark: Task `{adw_id}` approved by <@{request.user_id}>",
        }
    else:
        return {
            "response_type": "ephemeral",
            "text": f"Failed to approve task `{adw_id}`. It may not exist or may not be awaiting approval.",
        }


def _handle_reject_command(
    args: str,
    request: SlashCommandRequest,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle /adw reject <task_id> [reason].

    Args:
        args: Task ID and optional reason.
        request: Original slash command request.
        config: Slack configuration.

    Returns:
        Response payload.
    """
    parts = args.strip().split(maxsplit=1)
    if not parts:
        return {
            "response_type": "ephemeral",
            "text": "Please provide a task ID: `/adw reject <task_id> [reason]`",
        }

    adw_id = parts[0][:8]
    reason = parts[1] if len(parts) > 1 else "Rejected via Slack"

    from ..github.approval_gate import reject_task

    success = reject_task(adw_id, reason)

    if success:
        # Update thread message if we have one
        state = _load_slack_task_state(adw_id)
        if state and state.get("thread_ts"):
            client = SlackClient(config.bot_token)
            client.post_message(
                channel=state["channel_id"],
                text=f":x: Task rejected by <@{request.user_id}>: {reason}",
                thread_ts=state["thread_ts"],
            )

        return {
            "response_type": "in_channel",
            "text": f":x: Task `{adw_id}` rejected by <@{request.user_id}>",
        }
    else:
        return {
            "response_type": "ephemeral",
            "text": f"Failed to reject task `{adw_id}`. It may not exist or may not be awaiting approval.",
        }


def _handle_help_command() -> dict[str, Any]:
    """Handle /adw help.

    Returns:
        Help response payload.
    """
    return {
        "response_type": "ephemeral",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ADW Slack Commands*\n\n"
                    "`/adw create <description>` - Create a new task\n"
                    "`/adw status [task_id]` - Show status\n"
                    "`/adw approve <task_id>` - Approve a pending task\n"
                    "`/adw reject <task_id> [reason]` - Reject a task\n"
                    "`/adw help` - Show this help\n\n"
                    "*Tags for create:*\n"
                    "`{opus}` - Use Opus model\n"
                    "`{haiku}` - Use Haiku model\n"
                    "`{sdlc}` - Use full SDLC workflow\n"
                    "`{simple}` - Use simple workflow",
                },
            },
        ],
    }


# =============================================================================
# Button Interaction Handling
# =============================================================================


@dataclass
class InteractionPayload:
    """Parsed Slack interaction payload.

    Attributes:
        type: Interaction type (block_actions, view_submission, etc.).
        user_id: User who triggered the interaction.
        user_name: User name.
        channel_id: Channel ID (if applicable).
        action_id: Action ID from the button/select.
        action_value: Value associated with the action.
        trigger_id: Trigger ID for opening modals.
        response_url: URL to respond.
        message_ts: Original message timestamp.
    """

    type: str
    user_id: str
    user_name: str
    channel_id: str | None
    action_id: str
    action_value: str
    trigger_id: str
    response_url: str
    message_ts: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InteractionPayload:
        """Parse from interaction payload.

        Args:
            data: Interaction payload from Slack.

        Returns:
            Parsed InteractionPayload.
        """
        user = data.get("user", {})
        channel = data.get("channel", {})
        actions = data.get("actions", [{}])
        message = data.get("message", {})

        action = actions[0] if actions else {}

        return cls(
            type=data.get("type", ""),
            user_id=user.get("id", ""),
            user_name=user.get("name", ""),
            channel_id=channel.get("id"),
            action_id=action.get("action_id", ""),
            action_value=action.get("value", ""),
            trigger_id=data.get("trigger_id", ""),
            response_url=data.get("response_url", ""),
            message_ts=message.get("ts"),
        )


def handle_interaction(
    payload: InteractionPayload,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle a Slack block interaction.

    Args:
        payload: Parsed interaction payload.
        config: Slack configuration.

    Returns:
        Response payload.
    """
    action_id = payload.action_id

    # Parse action type and task ID from action_id
    # Format: action_type_<adw_id>
    if action_id.startswith("approve_task_"):
        adw_id = action_id.replace("approve_task_", "")
        return _handle_approve_interaction(adw_id, payload, config)

    elif action_id.startswith("reject_task_"):
        adw_id = action_id.replace("reject_task_", "")
        return _handle_reject_interaction(adw_id, payload, config)

    elif action_id.startswith("retry_task_"):
        adw_id = action_id.replace("retry_task_", "")
        return _handle_retry_interaction(adw_id, payload, config)

    elif action_id.startswith("view_logs_"):
        adw_id = action_id.replace("view_logs_", "")
        return _handle_view_logs_interaction(adw_id, payload, config)

    elif action_id.startswith("view_details_"):
        adw_id = action_id.replace("view_details_", "")
        return _handle_view_details_interaction(adw_id, payload, config)

    return {"text": "Unknown action"}


def _handle_approve_interaction(
    adw_id: str,
    payload: InteractionPayload,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle approve button click."""
    from ..github.approval_gate import approve_task

    success = approve_task(adw_id)

    client = SlackClient(config.bot_token)

    if success:
        # Update the original message
        if payload.response_url:
            client.respond_to_interaction(
                response_url=payload.response_url,
                text=f":white_check_mark: Approved by <@{payload.user_id}>",
                response_type="in_channel",
                replace_original=True,
            )

        return {"text": "Task approved"}
    else:
        return {"text": "Failed to approve task"}


def _handle_reject_interaction(
    adw_id: str,
    payload: InteractionPayload,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle reject button click."""
    # Open a modal to get rejection reason
    client = SlackClient(config.bot_token)

    modal = {
        "type": "modal",
        "callback_id": f"reject_modal_{adw_id}",
        "title": {"type": "plain_text", "text": "Reject Task"},
        "submit": {"type": "plain_text", "text": "Reject"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reason_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reason_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Enter rejection reason..."},
                },
                "label": {"type": "plain_text", "text": "Reason"},
            },
        ],
        "private_metadata": json.dumps({"adw_id": adw_id, "response_url": payload.response_url}),
    }

    client.open_modal(trigger_id=payload.trigger_id, view=modal)

    return {"text": "Opening rejection dialog..."}


def _handle_retry_interaction(
    adw_id: str,
    payload: InteractionPayload,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle retry button click."""
    from ..recovery.checkpoints import get_last_successful_checkpoint

    checkpoint = get_last_successful_checkpoint(adw_id)

    if not checkpoint:
        return {"text": "No checkpoint available for retry"}

    # Get task info from state snapshot or Slack state
    task_state = _load_slack_task_state(adw_id)
    task_description = (
        checkpoint.state_snapshot.get("task_description")
        or (task_state.get("description") if task_state else None)
        or "Retry task"
    )
    workflow = checkpoint.state_snapshot.get("workflow", "standard")

    # Resume from checkpoint
    from ..triggers.webhook import _trigger_workflow_async

    _trigger_workflow_async(
        task=task_description,
        body="",
        adw_id=adw_id,
        workflow=workflow,
        model="sonnet",
        worktree_name=f"retry-{adw_id}",
    )

    client = SlackClient(config.bot_token)
    if payload.response_url:
        client.respond_to_interaction(
            response_url=payload.response_url,
            text=f":arrows_counterclockwise: Retrying task `{adw_id}`...",
            response_type="in_channel",
        )

    return {"text": "Retry started"}


def _handle_view_logs_interaction(
    adw_id: str,
    payload: InteractionPayload,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle view logs button click."""
    from pathlib import Path

    log_path = Path(f"agents/{adw_id}/agent.log")

    if not log_path.exists():
        return {"text": f"No logs found for task `{adw_id}`"}

    # Read last 20 lines of log
    try:
        with open(log_path) as f:
            lines = f.readlines()[-20:]

        log_text = "".join(lines)[:2000]  # Limit size

        client = SlackClient(config.bot_token)

        # Post as ephemeral (only visible to user)
        if payload.response_url:
            client.respond_to_interaction(
                response_url=payload.response_url,
                text=f"*Logs for `{adw_id}`*\n```{log_text}```",
                response_type="ephemeral",
            )

        return {"text": "Logs displayed"}

    except Exception as e:
        return {"text": f"Failed to read logs: {e}"}


def _handle_view_details_interaction(
    adw_id: str,
    payload: InteractionPayload,
    config: SlackConfig,
) -> dict[str, Any]:
    """Handle view details button click."""
    from ..agent.state import ADWState

    try:
        state = ADWState.load(adw_id)
        if state is None:
            return {"text": f"Task `{adw_id}` not found"}

        details = f"""*Task Details: `{adw_id}`*

*Phase:* {state.current_phase}
*Completed Phases:* {", ".join(state.phases_completed) if state.phases_completed else "None"}
*Created:* {state.created_at}
*Updated:* {state.updated_at}
"""

        if state.errors:
            details += f"\n*Errors:*\n```{state.errors[-1][:500]}```"

        client = SlackClient(config.bot_token)

        if payload.response_url:
            client.respond_to_interaction(
                response_url=payload.response_url,
                text=details,
                response_type="ephemeral",
            )

        return {"text": "Details displayed"}

    except FileNotFoundError:
        return {"text": f"Task `{adw_id}` not found"}


# =============================================================================
# State Management
# =============================================================================


def _ensure_adw_dir() -> None:
    """Ensure ~/.adw directory exists."""
    ADW_DIR.mkdir(parents=True, exist_ok=True)


def _load_slack_state() -> dict[str, Any]:
    """Load Slack state from storage."""
    if not SLACK_STATE_FILE.exists():
        return {"tasks": {}}

    try:
        with open(SLACK_STATE_FILE) as f:
            data: dict[str, Any] = json.load(f)
            return data
    except json.JSONDecodeError:
        return {"tasks": {}}


def _save_slack_state(state: dict[str, Any]) -> None:
    """Save Slack state to storage."""
    _ensure_adw_dir()
    with open(SLACK_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _save_slack_task_state(
    adw_id: str,
    channel_id: str,
    user_id: str,
    description: str,
    thread_ts: str | None = None,
) -> None:
    """Save state for a Slack-created task.

    Args:
        adw_id: ADW task ID.
        channel_id: Channel where task was created.
        user_id: User who created the task.
        description: Task description.
        thread_ts: Thread timestamp for updates.
    """
    state = _load_slack_state()
    state["tasks"][adw_id] = {
        "channel_id": channel_id,
        "user_id": user_id,
        "description": description,
        "thread_ts": thread_ts,
        "created_at": datetime.now().isoformat(),
    }
    _save_slack_state(state)


def _update_slack_task_state(adw_id: str, **updates: Any) -> None:
    """Update state for a Slack-created task.

    Args:
        adw_id: ADW task ID.
        **updates: Fields to update.
    """
    state = _load_slack_state()
    if adw_id in state["tasks"]:
        state["tasks"][adw_id].update(updates)
        _save_slack_state(state)


def _load_slack_task_state(adw_id: str) -> dict[str, Any] | None:
    """Load state for a Slack-created task.

    Args:
        adw_id: ADW task ID.

    Returns:
        Task state dict or None if not found.
    """
    state = _load_slack_state()
    task_state: dict[str, Any] | None = state["tasks"].get(adw_id)
    return task_state


def _get_recent_tasks(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent tasks from state.

    Args:
        limit: Maximum number of tasks to return.

    Returns:
        List of task dicts with status info.
    """
    from ..agent.state import ADWState

    state = _load_slack_state()
    tasks = []

    for adw_id, task_data in list(state["tasks"].items())[-limit:]:
        try:
            adw_state = ADWState.load(adw_id)
            status = "in_progress"
            if adw_state:
                if adw_state.current_phase == "complete":
                    status = "completed"
                elif adw_state.current_phase == "failed":
                    status = "failed"
                elif adw_state.current_phase == "init":
                    status = "pending"

            tasks.append(
                {
                    "adw_id": adw_id,
                    "description": task_data.get("description", "Unknown"),
                    "status": status,
                    "created_at": task_data.get("created_at"),
                }
            )
        except Exception:
            tasks.append(
                {
                    "adw_id": adw_id,
                    "description": task_data.get("description", "Unknown"),
                    "status": "unknown",
                    "created_at": task_data.get("created_at"),
                }
            )

    return list(reversed(tasks))


# =============================================================================
# Thread Update Functions
# =============================================================================


def send_thread_update(
    config: SlackConfig,
    adw_id: str,
    message: str,
    emoji: str = "gear",
) -> bool:
    """Send an update to the task's Slack thread.

    Args:
        config: Slack configuration.
        adw_id: ADW task ID.
        message: Update message.
        emoji: Emoji to prefix message with.

    Returns:
        True if sent successfully.
    """
    task_state = _load_slack_task_state(adw_id)
    if not task_state or not task_state.get("thread_ts"):
        return False

    client = SlackClient(config.bot_token)
    result = client.post_message(
        channel=task_state["channel_id"],
        text=f":{emoji}: {message}",
        thread_ts=task_state["thread_ts"],
    )

    return result is not None


def notify_task_completed(
    config: SlackConfig,
    adw_id: str,
    duration_seconds: int | None = None,
    pr_url: str | None = None,
) -> bool:
    """Notify Slack that a task completed.

    Args:
        config: Slack configuration.
        adw_id: ADW task ID.
        duration_seconds: Time taken.
        pr_url: URL to created PR.

    Returns:
        True if notification sent.
    """
    task_state = _load_slack_task_state(adw_id)
    if not task_state:
        return False

    client = SlackClient(config.bot_token)
    message = format_task_completed_message(
        adw_id=adw_id,
        description=task_state.get("description", "Task"),
        duration_seconds=duration_seconds,
        pr_url=pr_url,
    )

    if task_state.get("thread_ts"):
        # Reply in thread
        result = client.post_message(
            channel=task_state["channel_id"],
            thread_ts=task_state["thread_ts"],
            **message,
        )
    else:
        # Post to channel
        result = client.post_message(
            channel=task_state["channel_id"],
            **message,
        )

    return result is not None


def notify_task_failed(
    config: SlackConfig,
    adw_id: str,
    error: str | None = None,
) -> bool:
    """Notify Slack that a task failed.

    Args:
        config: Slack configuration.
        adw_id: ADW task ID.
        error: Error message.

    Returns:
        True if notification sent.
    """
    task_state = _load_slack_task_state(adw_id)
    if not task_state:
        return False

    client = SlackClient(config.bot_token)
    message = format_task_failed_message(
        adw_id=adw_id,
        description=task_state.get("description", "Task"),
        error=error,
    )

    if task_state.get("thread_ts"):
        # Reply in thread
        result = client.post_message(
            channel=task_state["channel_id"],
            thread_ts=task_state["thread_ts"],
            **message,
        )
    else:
        # Post to channel
        result = client.post_message(
            channel=task_state["channel_id"],
            **message,
        )

    return result is not None


def request_approval(
    config: SlackConfig,
    adw_id: str,
    plan_summary: str | None = None,
) -> bool:
    """Request approval via Slack.

    Args:
        config: Slack configuration.
        adw_id: ADW task ID.
        plan_summary: Summary of the plan to approve.

    Returns:
        True if request sent.
    """
    task_state = _load_slack_task_state(adw_id)
    if not task_state:
        return False

    client = SlackClient(config.bot_token)
    message = format_approval_request_message(
        adw_id=adw_id,
        description=task_state.get("description", "Task"),
        plan_summary=plan_summary,
    )

    if task_state.get("thread_ts"):
        # Reply in thread
        result = client.post_message(
            channel=task_state["channel_id"],
            thread_ts=task_state["thread_ts"],
            **message,
        )
    else:
        # Post to channel
        result = client.post_message(
            channel=task_state["channel_id"],
            **message,
        )

    return result is not None


# =============================================================================
# FastAPI Application for Slack Events
# =============================================================================


def create_slack_app(config: SlackConfig) -> Any:
    """Create FastAPI app for Slack webhook handling.

    Args:
        config: Slack configuration.

    Returns:
        FastAPI application.
    """
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(
        title="ADW Slack Handler",
        description="Slack integration for ADW",
        version="1.0.0",
    )

    @app.post("/slack/commands")  # type: ignore[untyped-decorator]
    async def handle_command(request: Request) -> JSONResponse:
        """Handle Slack slash commands."""
        # Verify request signature
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        body = await request.body()

        if not verify_slack_request(config.signing_secret, timestamp, signature, body):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse form data
        form_data = urllib.parse.parse_qs(body.decode("utf-8"))
        data = {k: v[0] if v else "" for k, v in form_data.items()}

        # Handle command
        cmd_request = SlashCommandRequest.from_form_data(data)
        response = handle_slash_command(cmd_request, config)

        return JSONResponse(content=response)

    @app.post("/slack/interactions")  # type: ignore[untyped-decorator]
    async def handle_interaction_endpoint(request: Request) -> JSONResponse:
        """Handle Slack interactive components."""
        # Verify request signature
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        body = await request.body()

        if not verify_slack_request(config.signing_secret, timestamp, signature, body):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse payload
        form_data = urllib.parse.parse_qs(body.decode("utf-8"))
        payload_str = form_data.get("payload", [""])[0]

        if not payload_str:
            raise HTTPException(status_code=400, detail="No payload")

        payload_data = json.loads(payload_str)

        # Handle view submission for reject modal
        if payload_data.get("type") == "view_submission":
            return await _handle_view_submission(payload_data, config)

        # Handle block actions
        payload = InteractionPayload.from_dict(payload_data)
        response = handle_interaction(payload, config)

        return JSONResponse(content=response)

    async def _handle_view_submission(payload_data: dict[str, Any], config: SlackConfig) -> JSONResponse:
        """Handle modal view submission."""
        callback_id = payload_data.get("view", {}).get("callback_id", "")

        if callback_id.startswith("reject_modal_"):
            adw_id = callback_id.replace("reject_modal_", "")

            # Get reason from input
            values = payload_data.get("view", {}).get("state", {}).get("values", {})
            reason = values.get("reason_block", {}).get("reason_input", {}).get("value", "No reason provided")

            # Get metadata
            metadata = json.loads(payload_data.get("view", {}).get("private_metadata", "{}"))
            response_url = metadata.get("response_url")

            # Reject the task
            from ..github.approval_gate import reject_task

            reject_task(adw_id, reason)

            # Update the original message
            if response_url:
                client = SlackClient(config.bot_token)
                user_id = payload_data.get("user", {}).get("id", "")
                client.respond_to_interaction(
                    response_url=response_url,
                    text=f":x: Rejected by <@{user_id}>: {reason}",
                    response_type="in_channel",
                    replace_original=True,
                )

            return JSONResponse(content={})

        return JSONResponse(content={})

    @app.post("/slack/events")  # type: ignore[untyped-decorator]
    async def handle_events(request: Request) -> JSONResponse:
        """Handle Slack Events API.

        Required for URL verification challenge.
        """
        body = await request.body()
        data = json.loads(body)

        # Handle URL verification challenge
        if data.get("type") == "url_verification":
            return JSONResponse(content={"challenge": data.get("challenge")})

        # Verify request signature for other events
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not verify_slack_request(config.signing_secret, timestamp, signature, body):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # For now, just acknowledge events
        return JSONResponse(content={"ok": True})

    @app.get("/health")  # type: ignore[untyped-decorator]
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }

    return app


def start_slack_server(
    config: SlackConfig,
    host: str = "0.0.0.0",
    port: int = 3000,
    reload: bool = False,
) -> None:
    """Start the Slack webhook server.

    Args:
        config: Slack configuration.
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload for development.
    """
    import uvicorn

    # Store config in environment for factory function
    os.environ["_ADW_SLACK_BOT_TOKEN"] = config.bot_token
    os.environ["_ADW_SLACK_SIGNING_SECRET"] = config.signing_secret
    if config.channel_id:
        os.environ["_ADW_SLACK_CHANNEL_ID"] = config.channel_id

    uvicorn.run(
        "adw.integrations.slack:_create_app_factory",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def _create_app_factory() -> Any:
    """Factory function for uvicorn.

    Returns:
        FastAPI app.
    """
    config = SlackConfig(
        bot_token=os.environ.get("_ADW_SLACK_BOT_TOKEN", ""),
        signing_secret=os.environ.get("_ADW_SLACK_SIGNING_SECRET", ""),
        channel_id=os.environ.get("_ADW_SLACK_CHANNEL_ID"),
    )
    return create_slack_app(config)


# =============================================================================
# Connection Test
# =============================================================================


def test_slack_connection(config: SlackConfig) -> bool:
    """Test connection to Slack API.

    Args:
        config: Slack configuration.

    Returns:
        True if connection successful.
    """
    client = SlackClient(config.bot_token)
    result = client.auth_test()

    if result:
        console.print("[green]✓ Connected to Slack[/green]")
        console.print(f"[dim]Bot: {result.get('user', 'unknown')}[/dim]")
        console.print(f"[dim]Team: {result.get('team', 'unknown')}[/dim]")
        return True

    return False


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_simple_toml(path: Path) -> dict[str, Any]:
    """Simple TOML parser for basic key-value sections.

    Args:
        path: Path to TOML file.

    Returns:
        Parsed config dictionary.
    """
    config: dict[str, Any] = {}
    current_section: str | None = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Section header
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                config[current_section] = {}
                continue

            # Key-value pair
            if "=" in line and current_section:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")

                # Try to parse as number
                try:
                    value = int(value)  # type: ignore
                except ValueError:
                    pass

                config[current_section][key] = value

    return config
