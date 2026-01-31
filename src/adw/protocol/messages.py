"""Message models for ADW agent communication.

This module defines the message file protocol for bidirectional communication
with running agents via `agents/{adw_id}/adw_messages.jsonl`.
"""

from __future__ import annotations
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterator
from pydantic import BaseModel, Field


class MessagePriority(str, Enum):
    """Priority levels for agent messages."""
    NORMAL = "normal"
    HIGH = "high"
    INTERRUPT = "interrupt"


class AgentMessage(BaseModel):
    """Message sent to a running agent.

    Messages are written to `agents/{adw_id}/adw_messages.jsonl` and picked up
    by the check_messages.py hook during agent execution.
    """
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    message: str
    priority: MessagePriority = MessagePriority.NORMAL

    def to_jsonl(self) -> str:
        """Convert message to JSONL format."""
        return json.dumps(self.model_dump(), sort_keys=True)

    @classmethod
    def from_jsonl(cls, line: str) -> AgentMessage:
        """Parse message from JSONL line."""
        return cls.model_validate(json.loads(line))


def write_message(
    adw_id: str,
    message: str,
    priority: MessagePriority = MessagePriority.NORMAL,
    project_dir: Path | None = None,
) -> None:
    """Write a message to an agent's message file.

    Args:
        adw_id: Agent identifier
        message: Message content
        priority: Message priority level
        project_dir: Project directory (defaults to current directory)
    """
    if project_dir is None:
        project_dir = Path.cwd()

    messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"
    messages_file.parent.mkdir(parents=True, exist_ok=True)

    # Auto-detect STOP commands as interrupt priority
    if priority == MessagePriority.NORMAL and message.upper().startswith("STOP"):
        priority = MessagePriority.INTERRUPT

    msg = AgentMessage(message=message, priority=priority)

    with open(messages_file, "a") as f:
        f.write(msg.to_jsonl() + "\n")


def read_messages(
    adw_id: str,
    project_dir: Path | None = None,
) -> list[AgentMessage]:
    """Read all messages for an agent.

    Args:
        adw_id: Agent identifier
        project_dir: Project directory (defaults to current directory)

    Returns:
        List of all messages in chronological order
    """
    if project_dir is None:
        project_dir = Path.cwd()

    messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"

    if not messages_file.exists():
        return []

    messages = []
    for line in messages_file.read_text().strip().split("\n"):
        if line:
            messages.append(AgentMessage.from_jsonl(line))

    return messages


def read_unprocessed_messages(
    adw_id: str,
    project_dir: Path | None = None,
) -> Iterator[AgentMessage]:
    """Read and mark unprocessed messages for an agent.

    This function reads messages from the message file, compares them against
    the processed messages file, and yields only new messages. Each yielded
    message is immediately marked as processed.

    Args:
        adw_id: Agent identifier
        project_dir: Project directory (defaults to current directory)

    Yields:
        Unprocessed messages in chronological order
    """
    if project_dir is None:
        project_dir = Path.cwd()

    messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"
    processed_file = project_dir / "agents" / adw_id / "adw_messages_processed.jsonl"

    if not messages_file.exists():
        return

    # Read all messages
    messages = []
    for line in messages_file.read_text().strip().split("\n"):
        if line:
            messages.append(json.loads(line))

    # Read processed message keys
    processed = set()
    if processed_file.exists():
        for line in processed_file.read_text().strip().split("\n"):
            if line:
                processed.add(line)

    # Yield new messages and mark as processed
    for msg_dict in messages:
        msg_key = json.dumps(msg_dict, sort_keys=True)
        if msg_key not in processed:
            # Mark as processed immediately
            with open(processed_file, "a") as f:
                f.write(msg_key + "\n")

            # Yield the message
            yield AgentMessage.model_validate(msg_dict)
