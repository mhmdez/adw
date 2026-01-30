"""Tests for task parsing."""

from pathlib import Path

import pytest

from adw.tasks import Task, TaskStatus, get_tasks_summary, load_tasks, parse_tasks


class TestParseTasks:
    """Tests for parse_tasks function."""

    def test_parse_simple_task(self) -> None:
        """Test parsing a simple task."""
        content = "- [ ] TASK-001: Implement feature X"
        tasks = parse_tasks(content)

        assert len(tasks) == 1
        assert tasks[0].id == "TASK-001"
        assert tasks[0].title == "Implement feature X"
        assert tasks[0].status == TaskStatus.PENDING

    def test_parse_done_task(self) -> None:
        """Test parsing a completed task."""
        content = "- [x] TASK-001: Implement feature X"
        tasks = parse_tasks(content)

        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.DONE

    def test_parse_blocked_task(self) -> None:
        """Test parsing a blocked task."""
        content = "- [-] TASK-001: Implement feature X"
        tasks = parse_tasks(content)

        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.BLOCKED

    def test_parse_explicit_status(self) -> None:
        """Test parsing task with explicit status."""
        content = "- [ ] TASK-001: Implement feature X (in_progress)"
        tasks = parse_tasks(content)

        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.IN_PROGRESS

    def test_parse_with_metadata(self) -> None:
        """Test parsing task with metadata."""
        content = """- [ ] TASK-001: Implement feature X
  - Status: in_progress
  - Spec: specs/feature-x.md
  - Assignee: claude"""
        tasks = parse_tasks(content)

        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.IN_PROGRESS
        assert tasks[0].spec == "specs/feature-x.md"
        assert tasks[0].assignee == "claude"

    def test_parse_with_subtasks(self) -> None:
        """Test parsing task with subtasks."""
        content = """- [ ] TASK-001: Implement feature X
  - [ ] Create database schema
  - [x] Write tests"""
        tasks = parse_tasks(content)

        assert len(tasks) == 1
        assert len(tasks[0].subtasks) == 2
        assert tasks[0].subtasks[0].status == TaskStatus.PENDING
        assert tasks[0].subtasks[1].status == TaskStatus.DONE

    def test_parse_multiple_tasks(self) -> None:
        """Test parsing multiple tasks."""
        content = """- [ ] TASK-001: First task
- [x] TASK-002: Second task
- [-] TASK-003: Third task"""
        tasks = parse_tasks(content)

        assert len(tasks) == 3
        assert tasks[0].id == "TASK-001"
        assert tasks[1].id == "TASK-002"
        assert tasks[2].id == "TASK-003"

    def test_parse_auto_generate_ids(self) -> None:
        """Test auto-generating task IDs."""
        content = """- [ ] First task without ID
- [ ] Second task without ID"""
        tasks = parse_tasks(content)

        assert len(tasks) == 2
        assert tasks[0].id == "TASK-001"
        assert tasks[1].id == "TASK-002"


class TestLoadTasks:
    """Tests for load_tasks function."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading tasks from file."""
        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("""# Tasks

- [ ] TASK-001: First task
- [x] TASK-002: Second task
""")

        tasks = load_tasks(tasks_md)
        assert len(tasks) == 2

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file."""
        tasks = load_tasks(tmp_path / "nonexistent.md")
        assert len(tasks) == 0


class TestGetTasksSummary:
    """Tests for get_tasks_summary function."""

    def test_summary(self) -> None:
        """Test task summary."""
        tasks = [
            Task("1", "Task 1", TaskStatus.PENDING),
            Task("2", "Task 2", TaskStatus.PENDING),
            Task("3", "Task 3", TaskStatus.IN_PROGRESS),
            Task("4", "Task 4", TaskStatus.DONE),
            Task("5", "Task 5", TaskStatus.DONE),
            Task("6", "Task 6", TaskStatus.DONE),
            Task("7", "Task 7", TaskStatus.BLOCKED),
        ]

        summary = get_tasks_summary(tasks)

        assert summary["total"] == 7
        assert summary["pending"] == 2
        assert summary["in_progress"] == 1
        assert summary["done"] == 3
        assert summary["blocked"] == 1
        assert summary["failed"] == 0


class TestTaskIsActionable:
    """Tests for Task.is_actionable property."""

    def test_pending_is_actionable(self) -> None:
        """Test that pending tasks are actionable."""
        task = Task("1", "Test", TaskStatus.PENDING)
        assert task.is_actionable is True

    def test_in_progress_is_actionable(self) -> None:
        """Test that in_progress tasks are actionable."""
        task = Task("1", "Test", TaskStatus.IN_PROGRESS)
        assert task.is_actionable is True

    def test_done_not_actionable(self) -> None:
        """Test that done tasks are not actionable."""
        task = Task("1", "Test", TaskStatus.DONE)
        assert task.is_actionable is False

    def test_blocked_not_actionable(self) -> None:
        """Test that blocked tasks are not actionable."""
        task = Task("1", "Test", TaskStatus.BLOCKED)
        assert task.is_actionable is False
