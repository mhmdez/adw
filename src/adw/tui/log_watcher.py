"""Watch agent output files and stream to TUI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Callable
from dataclasses import dataclass, field
from datetime import datetime

from watchfiles import awatch, Change

from ..protocol.messages import AgentQuestion


@dataclass
class LogEvent:
    """A single log event."""
    timestamp: datetime
    adw_id: str
    event_type: str
    message: str
    tool_name: str | None = None
    file_path: str | None = None
    phase: str | None = None


@dataclass
class QuestionEvent:
    """Event when agent asks a question."""
    adw_id: str
    question: AgentQuestion
    timestamp: datetime = field(default_factory=datetime.now)


class LogWatcher:
    """Watch agent output directories for log events."""

    def __init__(self, agents_dir: Path | None = None):
        self.agents_dir = agents_dir or Path("agents")
        self._subscribers: dict[str, list[Callable]] = {}  # adw_id -> callbacks
        self._question_callbacks: list[Callable[[QuestionEvent], None]] = []
        self._file_positions: dict[str, int] = {}  # file -> last read position
        self._running = False
        self._watched_agents: set[str] = set()

    def subscribe(self, adw_id: str, callback: Callable[[LogEvent], None]) -> None:
        """Subscribe to logs for an ADW ID."""
        if adw_id not in self._subscribers:
            self._subscribers[adw_id] = []
        self._subscribers[adw_id].append(callback)

    def subscribe_all(self, callback: Callable[[LogEvent], None]) -> None:
        """Subscribe to all logs."""
        self.subscribe("*", callback)

    def subscribe_questions(self, callback: Callable[[QuestionEvent], None]) -> None:
        """Subscribe to question events."""
        self._question_callbacks.append(callback)

    def _notify_question(self, event: QuestionEvent) -> None:
        """Notify question subscribers."""
        for cb in self._question_callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def watch_agent(self, adw_id: str) -> None:
        """Start watching a specific agent's logs.

        This creates the output directory and resets position tracking
        so we capture all new output.
        """
        agent_dir = self.agents_dir / adw_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        self._watched_agents.add(adw_id)

        # Reset position for this agent's files so we read from start
        for f in agent_dir.glob("**/*.jsonl"):
            self._file_positions[str(f)] = 0

    def unsubscribe(self, adw_id: str, callback: Callable) -> None:
        """Unsubscribe from logs."""
        if adw_id in self._subscribers:
            self._subscribers[adw_id] = [
                cb for cb in self._subscribers[adw_id] if cb != callback
            ]

    async def watch(self) -> None:
        """Main watch loop."""
        self._running = True

        if not self.agents_dir.exists():
            self.agents_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Start watcher
            watcher = awatch(self.agents_dir)
            
            while self._running:
                # Check for file changes with timeout to allow polling questions
                try:
                    async for changes in watcher:
                        if not self._running:
                            break

                        for change_type, path_str in changes:
                            path = Path(path_str)

                            # Only handle JSONL files
                            if not path.name.endswith(".jsonl"):
                                continue

                            # Extract ADW ID from path
                            try:
                                rel = path.relative_to(self.agents_dir)
                                adw_id = rel.parts[0]
                            except (ValueError, IndexError):
                                continue

                            # Read new content
                            if change_type in (Change.added, Change.modified):
                                await self._handle_file_change(adw_id, path)
                        
                        # Break inner loop to poll questions
                        break
                except Exception:
                    pass

                # Poll for questions
                for adw_id in list(self._watched_agents):
                    agent_dir = self.agents_dir / adw_id
                    if agent_dir.exists():
                        await self._process_message_file(adw_id, agent_dir / "adw_messages.jsonl")

                await asyncio.sleep(0.5)

        except Exception as e:
            # Log but don't crash
            pass

    def stop(self) -> None:
        """Stop watching."""
        self._running = False

    async def _process_message_file(self, adw_id: str, path: Path) -> None:
        """Process messages looking for questions."""
        if not path.exists():
            return

        # Use file positions to only read new lines
        path_key = str(path)
        last_pos = self._file_positions.get(path_key, 0)

        try:
            with open(path, "r") as f:
                f.seek(last_pos)
                new_content = f.read()
                self._file_positions[path_key] = f.tell()

            for line in new_content.strip().split("\n"):
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("message_type") == "question":
                        question = AgentQuestion.model_validate(msg.get("question", {}))
                        # Check if already answered
                        if not self._is_question_answered(adw_id, question.id):
                            event = QuestionEvent(adw_id=adw_id, question=question)
                            self._notify_question(event)
                except Exception:
                    continue
        except Exception:
            pass

    def _is_question_answered(self, adw_id: str, question_id: str) -> bool:
        """Check if a question has been answered."""
        # Look for ANSWER message with matching question_id
        # We need to read the whole file or cache answers
        # For simplicity/robustness, reading file is safer but less efficient
        # Optimized: check recent messages or cache in memory
        
        answers_file = self.agents_dir / adw_id / "adw_messages.jsonl"
        if not answers_file.exists():
            return False

        try:
            content = answers_file.read_text()
            for line in content.strip().split("\n"):
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if (msg.get("message_type") == "answer" and
                        f"question {question_id}" in msg.get("message", "")):
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    async def _handle_file_change(self, adw_id: str, path: Path) -> None:
        """Handle a file change."""
        if not path.exists():
            return

        # Get last position
        path_key = str(path)
        last_pos = self._file_positions.get(path_key, 0)

        try:
            with open(path, "r") as f:
                f.seek(last_pos)
                new_content = f.read()
                self._file_positions[path_key] = f.tell()

            # Parse new lines
            for line in new_content.strip().split("\n"):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = self._parse_event(adw_id, data)
                    if event:
                        self._notify(adw_id, event)
                except json.JSONDecodeError:
                    continue

        except Exception:
            pass

    def _parse_event(self, adw_id: str, data: dict) -> LogEvent | None:
        """Parse raw event data into LogEvent."""
        event_type = data.get("type", "unknown")

        # Map Claude Code message types
        if event_type == "assistant":
            content = data.get("message", {}).get("content", [])
            if content:
                text = ""
                if isinstance(content, list):
                    for c in content:
                        if c.get("type") == "text":
                            text = c.get("text", "")[:100]
                            break
                else:
                    text = str(content)[:100]

                return LogEvent(
                    timestamp=datetime.now(),
                    adw_id=adw_id,
                    event_type="assistant",
                    message=text,
                )

        elif event_type == "tool_use":
            tool = data.get("tool", {})
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="tool",
                message=f"Using {tool.get('name', 'unknown')}",
                tool_name=tool.get("name"),
            )

        elif event_type == "tool_result":
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="tool_result",
                message="Tool completed",
            )

        elif event_type == "result":
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="result",
                message="Agent completed",
            )

        elif event_type == "error":
            error = data.get("error", {})
            return LogEvent(
                timestamp=datetime.now(),
                adw_id=adw_id,
                event_type="error",
                message=error.get("message", "Unknown error"),
            )

        return None

    def _notify(self, adw_id: str, event: LogEvent) -> None:
        """Notify subscribers of event."""
        # Specific subscribers
        for cb in self._subscribers.get(adw_id, []):
            cb(event)

        # All subscribers
        for cb in self._subscribers.get("*", []):
            cb(event)
