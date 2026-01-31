"""Cron daemon for autonomous task execution.

This module provides a daemon that continuously monitors tasks.md
for eligible tasks and spawns agents to execute them.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from ..agent.manager import AgentManager
from ..agent.models import TaskStatus
from ..agent.task_parser import get_eligible_tasks, load_tasks
from ..agent.task_updater import mark_in_progress, mark_done, mark_failed
from ..agent.utils import generate_adw_id


@dataclass
class CronConfig:
    """Configuration for the cron daemon."""

    tasks_file: Path = field(default_factory=lambda: Path("tasks.md"))
    poll_interval: float = 5.0  # seconds between task checks
    max_concurrent: int = 3  # max simultaneous agents
    default_workflow: str = "standard"
    default_model: str = "sonnet"
    auto_start: bool = True  # start tasks automatically


class CronDaemon:
    """Daemon for autonomous task execution.

    Monitors tasks.md for eligible tasks and spawns agents
    to execute them within configured concurrency limits.
    """

    def __init__(
        self,
        config: CronConfig | None = None,
        manager: AgentManager | None = None,
    ):
        self.config = config or CronConfig()
        self.manager = manager or AgentManager()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._callbacks: list[Callable] = []
        self._task_agents: dict[str, str] = {}  # task description -> adw_id

    def subscribe(self, callback: Callable) -> None:
        """Subscribe to daemon events."""
        self._callbacks.append(callback)

    def notify(self, event: str, **data) -> None:
        """Notify subscribers of daemon event."""
        for cb in self._callbacks:
            try:
                cb(event, data)
            except Exception:
                pass  # Don't let callback errors crash daemon

    @property
    def is_running(self) -> bool:
        """Check if daemon is running."""
        return self._running

    def _get_eligible_count(self) -> int:
        """Get count of eligible tasks respecting concurrency."""
        eligible = get_eligible_tasks(self.config.tasks_file)
        running = self.manager.count
        available_slots = max(0, self.config.max_concurrent - running)
        return min(len(eligible), available_slots)

    def _pick_next_task(self):
        """Pick next task to execute.

        Returns:
            Task object or None if no eligible tasks.
        """
        eligible = get_eligible_tasks(self.config.tasks_file)

        # Filter out already running tasks
        for task in eligible:
            if task.description not in self._task_agents:
                return task

        return None

    def _spawn_task(self, task) -> str | None:
        """Spawn an agent for a task.

        Returns:
            ADW ID of spawned agent or None on failure.
        """
        adw_id = task.adw_id or generate_adw_id()
        model = task.model  # Uses tags to determine model

        # Mark task as in progress
        mark_in_progress(self.config.tasks_file, task.description, adw_id)

        try:
            spawned_id = self.manager.spawn_workflow(
                task_description=task.description,
                worktree_name=task.worktree_name,
                workflow=self.config.default_workflow,
                model=model,
                adw_id=adw_id,
            )

            self._task_agents[task.description] = spawned_id
            self.notify(
                "task_started",
                adw_id=spawned_id,
                description=task.description,
                model=model,
            )

            return spawned_id

        except Exception as e:
            mark_failed(self.config.tasks_file, task.description, adw_id, str(e))
            self.notify("task_failed", adw_id=adw_id, error=str(e))
            return None

    def _check_completions(self) -> list[tuple[str, int]]:
        """Check for completed agents and update tasks.

        Returns:
            List of (adw_id, return_code) for completed agents.
        """
        completed = self.manager.poll()

        for adw_id, return_code in completed:
            # Find task by adw_id
            task_desc = None
            for desc, aid in list(self._task_agents.items()):
                if aid == adw_id:
                    task_desc = desc
                    del self._task_agents[desc]
                    break

            if task_desc:
                if return_code == 0:
                    mark_done(self.config.tasks_file, task_desc, adw_id)
                    self.notify(
                        "task_completed",
                        adw_id=adw_id,
                        description=task_desc,
                    )
                else:
                    mark_failed(
                        self.config.tasks_file,
                        task_desc,
                        adw_id,
                        f"Exit code {return_code}",
                    )
                    self.notify(
                        "task_failed",
                        adw_id=adw_id,
                        description=task_desc,
                        return_code=return_code,
                    )

        return completed

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                # Check for completed agents
                self._check_completions()

                # Spawn new tasks if slots available
                if self.config.auto_start:
                    while self.manager.count < self.config.max_concurrent:
                        task = self._pick_next_task()
                        if not task:
                            break
                        self._spawn_task(task)

                # Wait for next poll or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.config.poll_interval,
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue polling

            except Exception as e:
                self.notify("error", error=str(e))
                await asyncio.sleep(self.config.poll_interval)

    async def start(self) -> None:
        """Start the daemon."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()
        self.notify("started")

        await self._poll_loop()

        self.notify("stopped")

    def stop(self) -> None:
        """Signal daemon to stop."""
        self._running = False
        self._shutdown_event.set()

    async def run_once(self) -> int:
        """Run one polling cycle.

        Returns:
            Number of tasks spawned.
        """
        self._check_completions()

        spawned = 0
        while self.manager.count < self.config.max_concurrent:
            task = self._pick_next_task()
            if not task:
                break
            if self._spawn_task(task):
                spawned += 1

        return spawned


async def run_daemon(
    tasks_file: Path | None = None,
    poll_interval: float = 5.0,
    max_concurrent: int = 3,
) -> None:
    """Run the cron daemon.

    Args:
        tasks_file: Path to tasks.md
        poll_interval: Seconds between polls
        max_concurrent: Max simultaneous agents
    """
    config = CronConfig(
        tasks_file=tasks_file or Path("tasks.md"),
        poll_interval=poll_interval,
        max_concurrent=max_concurrent,
    )

    daemon = CronDaemon(config)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        daemon.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    print(f"[cron] Starting daemon (poll={poll_interval}s, max={max_concurrent})")
    print(f"[cron] Watching: {config.tasks_file}")

    await daemon.start()

    print("[cron] Daemon stopped")


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="ADW cron daemon")
    parser.add_argument(
        "--tasks-file",
        type=Path,
        default=Path("tasks.md"),
        help="Path to tasks.md",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between task checks",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Max simultaneous agents",
    )

    args = parser.parse_args()

    asyncio.run(
        run_daemon(
            tasks_file=args.tasks_file,
            poll_interval=args.poll_interval,
            max_concurrent=args.max_concurrent,
        )
    )


if __name__ == "__main__":
    main()
