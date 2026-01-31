"""Message models for ADW agent communication.

This module defines the message file protocol for bidirectional communication
with running agents via `agents/{adw_id}/adw_messages.jsonl`.
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterator, Literal
from pydantic import BaseModel, Field


class MessagePriority(str, Enum):
    """Priority levels for agent messages."""
    NORMAL = "normal"
    HIGH = "high"
    INTERRUPT = "interrupt"


class MessageType(str, Enum):
    """Type of agent message."""
    USER_MESSAGE = "user_message"     # Human → Agent
    AGENT_MESSAGE = "agent_message"   # Agent → Human (info)
    QUESTION = "question"             # Agent → Human (needs answer)
    ANSWER = "answer"                 # Human → Agent (response to question)
    ATTENTION = "attention"           # Agent needs user (no answer needed)
    STATUS = "status"                 # Phase/progress update


class AgentQuestion(BaseModel):
    """Question from agent needing user input."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    question: str                     # The question text
    context: str | None = None        # Additional context
    options: list[str] | None = None  # Multiple choice options (if any)
    default: str | None = None        # Default answer
    required: bool = True             # Can user skip?
    timeout_action: Literal["block", "skip", "default"] = "block"


class AgentMessage(BaseModel):
    """Message sent to a running agent.

    Messages are written to `agents/{adw_id}/adw_messages.jsonl` and picked up
    by the check_messages.py hook during agent execution.
    """
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    message: str
    priority: MessagePriority = MessagePriority.NORMAL
    message_type: MessageType = MessageType.USER_MESSAGE
    question: AgentQuestion | None = None  # For QUESTION type messages

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


def write_question(
    adw_id: str,
    question: str,
    context: str | None = None,
    options: list[str] | None = None,
    project_dir: Path | None = None,
) -> str:
    """Write a question to agent's message file. Returns question ID.

    Args:
        adw_id: Agent identifier
        question: The question text
        context: Additional context for the question
        options: Multiple choice options (if any)
        project_dir: Project directory (defaults to current directory)

    Returns:
        Question ID for tracking the answer
    """
    if project_dir is None:
        project_dir = Path.cwd()

    messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"
    messages_file.parent.mkdir(parents=True, exist_ok=True)

    agent_question = AgentQuestion(
        question=question,
        context=context,
        options=options,
    )

    msg = AgentMessage(
        message=question,
        message_type=MessageType.QUESTION,
        question=agent_question,
        priority=MessagePriority.HIGH,
    )

    with open(messages_file, "a") as f:
        f.write(msg.to_jsonl() + "\n")

    return agent_question.id


def write_answer(
    adw_id: str,
    question_id: str,
    answer: str,
    project_dir: Path | None = None,
) -> None:
    """Write an answer to a pending question.

    Args:
        adw_id: Agent identifier
        question_id: ID of the question being answered
        answer: The answer text
        project_dir: Project directory (defaults to current directory)
    """
    if project_dir is None:
        project_dir = Path.cwd()

    messages_file = project_dir / "agents" / adw_id / "adw_messages.jsonl"
    messages_file.parent.mkdir(parents=True, exist_ok=True)

    # Create answer message with question_id in context
    msg = AgentMessage(
        message=f"Answer to question {question_id}: {answer}",
        message_type=MessageType.ANSWER,
        priority=MessagePriority.HIGH,
    )

    with open(messages_file, "a") as f:
        f.write(msg.to_jsonl() + "\n")


def get_pending_questions(
    adw_id: str,
    project_dir: Path | None = None,
) -> list[AgentQuestion]:
    """Get all unanswered questions for an agent.

    This function reads the message file and returns questions that don't
    have corresponding answers yet.

    Args:
        adw_id: Agent identifier
        project_dir: Project directory (defaults to current directory)

    Returns:
        List of unanswered questions in chronological order
    """
    if project_dir is None:
        project_dir = Path.cwd()

    messages = read_messages(adw_id, project_dir)

    # Collect all questions and answered question IDs
    questions: dict[str, AgentQuestion] = {}
    answered_ids: set[str] = set()

    for msg in messages:
        if msg.message_type == MessageType.QUESTION and msg.question:
            questions[msg.question.id] = msg.question
        elif msg.message_type == MessageType.ANSWER:
            # Extract question ID from answer message
            # Format: "Answer to question {question_id}: {answer}"
            if msg.message.startswith("Answer to question "):
                try:
                    question_id = msg.message.split(":")[0].split()[-1]
                    answered_ids.add(question_id)
                except (IndexError, ValueError):
                    pass

    # Return questions that haven't been answered
    return [q for qid, q in questions.items() if qid not in answered_ids]
