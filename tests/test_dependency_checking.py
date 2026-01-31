"""Tests for dependency checking and blocked task eligibility."""

from pathlib import Path

import pytest

from adw.agent.models import Task, TaskStatus, Worktree
from adw.agent.task_parser import get_eligible_tasks, parse_tasks_md


class TestWorktreeEligibility:
    """Tests for Worktree.get_eligible_tasks method."""

    def test_pending_tasks_always_eligible(self) -> None:
        """Test that PENDING tasks are always eligible."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.PENDING),
                Task(description="Task 2", status=TaskStatus.PENDING),
                Task(description="Task 3", status=TaskStatus.DONE),
            ],
        )

        eligible = worktree.get_eligible_tasks()

        assert len(eligible) == 2
        assert eligible[0].description == "Task 1"
        assert eligible[1].description == "Task 2"

    def test_blocked_not_eligible_with_pending_above(self) -> None:
        """Test that BLOCKED tasks are not eligible if tasks above are not done."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.PENDING),
                Task(description="Task 2", status=TaskStatus.BLOCKED),
            ],
        )

        eligible = worktree.get_eligible_tasks()

        # Only the pending task should be eligible
        assert len(eligible) == 1
        assert eligible[0].description == "Task 1"

    def test_blocked_eligible_when_all_above_done(self) -> None:
        """Test that BLOCKED tasks become eligible when all tasks above are DONE."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.DONE),
                Task(description="Task 2", status=TaskStatus.DONE),
                Task(description="Task 3", status=TaskStatus.BLOCKED),
            ],
        )

        eligible = worktree.get_eligible_tasks()

        # The blocked task should now be eligible
        assert len(eligible) == 1
        assert eligible[0].description == "Task 3"

    def test_blocked_not_eligible_if_any_above_not_done(self) -> None:
        """Test that BLOCKED tasks are not eligible if any task above is not DONE."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.DONE),
                Task(description="Task 2", status=TaskStatus.IN_PROGRESS),
                Task(description="Task 3", status=TaskStatus.BLOCKED),
            ],
        )

        eligible = worktree.get_eligible_tasks()

        # The blocked task should not be eligible
        assert len(eligible) == 0

    def test_multiple_blocked_sequential_unlocking(self) -> None:
        """Test that blocked tasks unlock sequentially as dependencies complete."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.DONE),
                Task(description="Task 2", status=TaskStatus.BLOCKED),
                Task(description="Task 3", status=TaskStatus.BLOCKED),
            ],
        )

        # First blocked task should be eligible
        eligible = worktree.get_eligible_tasks()
        assert len(eligible) == 1
        assert eligible[0].description == "Task 2"

        # After task 2 completes, task 3 should become eligible
        worktree.tasks[1].status = TaskStatus.DONE
        eligible = worktree.get_eligible_tasks()
        assert len(eligible) == 1
        assert eligible[0].description == "Task 3"

    def test_in_progress_and_failed_not_returned(self) -> None:
        """Test that IN_PROGRESS and FAILED tasks are not eligible."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.IN_PROGRESS),
                Task(description="Task 2", status=TaskStatus.FAILED),
                Task(description="Task 3", status=TaskStatus.DONE),
            ],
        )

        eligible = worktree.get_eligible_tasks()

        assert len(eligible) == 0

    def test_empty_worktree(self) -> None:
        """Test that empty worktree returns no eligible tasks."""
        worktree = Worktree(name="test", tasks=[])

        eligible = worktree.get_eligible_tasks()

        assert len(eligible) == 0

    def test_mixed_pending_and_blocked(self) -> None:
        """Test worktree with mix of pending and blocked tasks."""
        worktree = Worktree(
            name="test",
            tasks=[
                Task(description="Task 1", status=TaskStatus.PENDING),
                Task(description="Task 2", status=TaskStatus.BLOCKED),
                Task(description="Task 3", status=TaskStatus.DONE),
                Task(description="Task 4", status=TaskStatus.PENDING),
                Task(description="Task 5", status=TaskStatus.BLOCKED),
            ],
        )

        eligible = worktree.get_eligible_tasks()

        # Pending tasks are always eligible, blocked task 2 is not (task 1 not done)
        assert len(eligible) == 2
        assert eligible[0].description == "Task 1"
        assert eligible[1].description == "Task 4"


class TestTaskIsEligible:
    """Tests for Task.is_eligible property."""

    def test_pending_is_eligible(self) -> None:
        """Test that PENDING tasks report as eligible."""
        task = Task(description="Test", status=TaskStatus.PENDING)
        assert task.is_eligible is True

    def test_blocked_is_eligible(self) -> None:
        """Test that BLOCKED tasks report as eligible (dependency check separate)."""
        task = Task(description="Test", status=TaskStatus.BLOCKED)
        assert task.is_eligible is True

    def test_in_progress_not_eligible(self) -> None:
        """Test that IN_PROGRESS tasks are not eligible."""
        task = Task(description="Test", status=TaskStatus.IN_PROGRESS)
        assert task.is_eligible is False

    def test_done_not_eligible(self) -> None:
        """Test that DONE tasks are not eligible."""
        task = Task(description="Test", status=TaskStatus.DONE)
        assert task.is_eligible is False

    def test_failed_not_eligible(self) -> None:
        """Test that FAILED tasks are not eligible."""
        task = Task(description="Test", status=TaskStatus.FAILED)
        assert task.is_eligible is False


class TestGetEligibleTasksIntegration:
    """Integration tests for get_eligible_tasks with real tasks.md parsing."""

    def test_parse_and_get_eligible(self, tmp_path: Path) -> None:
        """Test parsing tasks.md and getting eligible tasks."""
        tasks_content = """# Tasks

## Worktree: phase-01

[] First task
[⏰] Second task (blocked)
[✅] Third task (done)
[] Fourth task

## Worktree: phase-02

[✅] Task A (done)
[✅] Task B (done)
[⏰] Task C (blocked, should be eligible)
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(tasks_content)

        eligible = get_eligible_tasks(tasks_file)

        # Should get: First task, Fourth task (pending from phase-01)
        # and Task C (blocked but all above are done from phase-02)
        assert len(eligible) == 3
        descriptions = [t.description for t in eligible]
        assert "First task" in descriptions
        assert "Fourth task" in descriptions
        assert "Task C (blocked, should be eligible)" in descriptions

    def test_real_world_scenario(self, tmp_path: Path) -> None:
        """Test real-world ADW build scenario."""
        tasks_content = """## Worktree: phase-03-task-system

[✅, 7dff1da0] Create src/adw/agent/task_parser.py to parse tasks.md
[✅, 0ad90e90] Create src/adw/agent/task_updater.py for atomic status updates
[✅, 7c99f459] Create src/adw/tui/state.py with reactive AppState
[⏰] Create src/adw/tui/widgets/task_list.py widget
[⏰] Create src/adw/tui/widgets/task_detail.py widget
[⏰] Update src/adw/tui/app.py to use real task widgets
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(tasks_content)

        eligible = get_eligible_tasks(tasks_file)

        # Only the first blocked task should be eligible (all above are done)
        assert len(eligible) == 1
        assert "task_list.py" in eligible[0].description

        # Simulate completing the first blocked task
        updated_content = tasks_content.replace(
            "[⏰] Create src/adw/tui/widgets/task_list.py widget",
            "[✅, abc12345] Create src/adw/tui/widgets/task_list.py widget",
        )
        tasks_file.write_text(updated_content)

        eligible = get_eligible_tasks(tasks_file)

        # Now the second blocked task should be eligible
        assert len(eligible) == 1
        assert "task_detail.py" in eligible[0].description

    def test_multiple_worktrees_independence(self, tmp_path: Path) -> None:
        """Test that worktrees are independent for dependency checking."""
        tasks_content = """## Worktree: worktree-1

[] Task A1
[⏰] Task A2

## Worktree: worktree-2

[⏰] Task B1
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(tasks_content)

        eligible = get_eligible_tasks(tasks_file)

        # Task A1 is pending (eligible)
        # Task A2 is blocked by A1 (not eligible)
        # Task B1 is blocked but no tasks above it, so eligible
        assert len(eligible) == 2
        descriptions = [t.description for t in eligible]
        assert "Task A1" in descriptions
        assert "Task B1" in descriptions
