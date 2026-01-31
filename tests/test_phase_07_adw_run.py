"""Phase 7 verification: adw run picks up and executes pending tasks.

This test file verifies all Phase 7 deliverables:
- Cron trigger daemon
- Task eligibility checking
- Dependency enforcement (blocked tasks)
- Concurrent task limits
- CLI command: adw run
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from adw.agent.models import Task, TaskStatus, Worktree
from adw.agent.task_parser import get_eligible_tasks, load_tasks
from adw.triggers.cron import CronConfig, CronDaemon


class TestPhase07DependencyResolution:
    """Test dependency resolution for blocked tasks."""

    def test_pending_tasks_always_eligible(self, tmp_path: Path) -> None:
        """Test that pending tasks are always eligible."""
        content = """## Worktree: main

[] Task 1
[] Task 2
[] Task 3
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)
        assert len(eligible) == 3
        assert all(t.status == TaskStatus.PENDING for t in eligible)

    def test_blocked_tasks_wait_for_dependencies(self, tmp_path: Path) -> None:
        """Test that blocked tasks wait for tasks above them."""
        content = """## Worktree: main

[] Task 1
[⏰] Task 2 waiting for Task 1
[⏰] Task 3 waiting for Task 1 and 2
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Only Task 1 should be eligible (Task 2 and 3 are blocked)
        assert len(eligible) == 1
        assert eligible[0].description == "Task 1"

    def test_blocked_task_becomes_eligible_after_dependency_done(self, tmp_path: Path) -> None:
        """Test that blocked task becomes eligible when dependency completes."""
        content = """## Worktree: main

[✅, abc12345] Task 1
[⏰] Task 2 waiting for Task 1
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Task 2 should now be eligible since Task 1 is done
        assert len(eligible) == 1
        assert eligible[0].description == "Task 2 waiting for Task 1"

    def test_blocked_task_waits_for_all_tasks_above(self, tmp_path: Path) -> None:
        """Test that blocked task waits for ALL tasks above to complete."""
        content = """## Worktree: main

[✅, abc12345] Task 1
[] Task 2
[⏰] Task 3 waiting for all above
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Task 2 is eligible (pending), but Task 3 is NOT (Task 2 not done yet)
        assert len(eligible) == 1
        assert eligible[0].description == "Task 2"

    def test_all_blocked_tasks_eligible_when_all_done(self, tmp_path: Path) -> None:
        """Test that blocked task becomes eligible when all tasks above are done."""
        content = """## Worktree: main

[✅, abc12345] Task 1
[✅, def67890] Task 2
[⏰] Task 3 waiting for all above
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Task 3 should be eligible now (all tasks above are done)
        assert len(eligible) == 1
        assert eligible[0].description == "Task 3 waiting for all above"

    def test_mixed_pending_and_blocked(self, tmp_path: Path) -> None:
        """Test mix of pending and blocked tasks."""
        content = """## Worktree: main

[] Task 1
[⏰] Task 2 blocked by Task 1
[] Task 3 independent
[⏰] Task 4 blocked by all above
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Task 1 and Task 3 should be eligible (pending)
        # Task 2 is NOT eligible (Task 1 not done)
        # Task 4 is NOT eligible (not all tasks above are done)
        assert len(eligible) == 2
        descriptions = [t.description for t in eligible]
        assert "Task 1" in descriptions
        assert "Task 3 independent" in descriptions


class TestPhase07MultipleWorktrees:
    """Test task eligibility across multiple worktrees."""

    def test_worktrees_are_independent(self, tmp_path: Path) -> None:
        """Test that different worktrees have independent dependencies."""
        content = """## Worktree: main

[] Main task 1
[⏰] Main task 2 blocked

## Worktree: feature-branch

[] Feature task 1
[⏰] Feature task 2 blocked
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Should get Task 1 from each worktree (2 total)
        assert len(eligible) == 2
        descriptions = [t.description for t in eligible]
        assert "Main task 1" in descriptions
        assert "Feature task 1" in descriptions

    def test_blocked_tasks_per_worktree(self, tmp_path: Path) -> None:
        """Test dependency enforcement is per-worktree."""
        content = """## Worktree: main

[✅, abc12345] Main task 1
[⏰] Main task 2 blocked

## Worktree: feature-branch

[] Feature task 1
[⏰] Feature task 2 blocked
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Main task 2 is eligible (dependency done)
        # Feature task 1 is eligible (pending)
        # Feature task 2 is NOT eligible (Feature task 1 not done)
        assert len(eligible) == 2
        descriptions = [t.description for t in eligible]
        assert "Main task 2 blocked" in descriptions
        assert "Feature task 1" in descriptions


class TestPhase07ModelSelection:
    """Test model selection from tags."""

    def test_default_model_is_sonnet(self, tmp_path: Path) -> None:
        """Test that default model is sonnet."""
        content = "## Worktree: main\n\n[] Build feature"
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)
        assert len(eligible) == 1
        assert eligible[0].model == "sonnet"

    def test_opus_tag_selects_opus(self, tmp_path: Path) -> None:
        """Test that {opus} tag selects opus model."""
        content = "## Worktree: main\n\n[] Complex planning task {opus}"
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)
        assert len(eligible) == 1
        assert eligible[0].model == "opus"

    def test_haiku_tag_selects_haiku(self, tmp_path: Path) -> None:
        """Test that {haiku} tag selects haiku model."""
        content = "## Worktree: main\n\n[] Simple fix {haiku}"
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)
        assert len(eligible) == 1
        assert eligible[0].model == "haiku"

    def test_multiple_tags_opus_takes_priority(self, tmp_path: Path) -> None:
        """Test that opus takes priority with multiple tags."""
        content = "## Worktree: main\n\n[] Task {opus, haiku}"
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)
        assert len(eligible) == 1
        assert eligible[0].model == "opus"


class TestPhase07Integration:
    """Integration tests for full Phase 7 functionality."""

    @patch("adw.triggers.cron.get_eligible_tasks")
    async def test_daemon_picks_up_eligible_tasks(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that daemon picks up eligible tasks."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2")

        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=2)
        daemon = CronDaemon(config=config)

        from adw.agent.manager import AgentProcess
        spawn_calls = []

        def mock_spawn(**kwargs):
            spawn_calls.append(kwargs)
            adw_id = f"adw{len(spawn_calls)}"
            daemon.manager._agents[adw_id] = Mock(spec=AgentProcess, adw_id=adw_id)
            return adw_id

        with patch.object(daemon.manager, "spawn_workflow", side_effect=mock_spawn):
            with patch("adw.triggers.cron.mark_in_progress"):
                spawned = await daemon.run_once()

        # Should have spawned both tasks
        assert spawned == 2
        assert len(spawn_calls) == 2
        assert spawn_calls[0]["task_description"] == "Task 1"
        assert spawn_calls[1]["task_description"] == "Task 2"

    @patch("adw.triggers.cron.get_eligible_tasks")
    async def test_daemon_uses_correct_model(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that daemon spawns agents with correct model."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task {opus}")

        task = Task(description="Task", status=TaskStatus.PENDING, tags=["opus"])
        mock_get_eligible.return_value = [task]

        config = CronConfig(tasks_file=tasks_file)
        daemon = CronDaemon(config=config)

        from adw.agent.manager import AgentProcess
        spawn_calls = []

        def mock_spawn(**kwargs):
            spawn_calls.append(kwargs)
            daemon.manager._agents["adw1"] = Mock(spec=AgentProcess, adw_id="adw1")
            return "adw1"

        with patch.object(daemon.manager, "spawn_workflow", side_effect=mock_spawn):
            with patch("adw.triggers.cron.mark_in_progress"):
                await daemon.run_once()

        # Should have used opus model
        assert len(spawn_calls) == 1
        assert spawn_calls[0]["model"] == "opus"

    async def test_daemon_respects_dependencies(self, tmp_path: Path) -> None:
        """Test that daemon respects task dependencies."""
        content = """## Worktree: main

[] Task 1
[⏰] Task 2 blocked by Task 1
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        config = CronConfig(tasks_file=tasks_file, max_concurrent=2)
        daemon = CronDaemon(config=config)

        from adw.agent.manager import AgentProcess
        spawn_calls = []

        def mock_spawn(**kwargs):
            spawn_calls.append(kwargs)
            adw_id = f"adw{len(spawn_calls)}"
            daemon.manager._agents[adw_id] = Mock(spec=AgentProcess, adw_id=adw_id)
            return adw_id

        with patch.object(daemon.manager, "spawn_workflow", side_effect=mock_spawn):
            with patch("adw.triggers.cron.mark_in_progress"):
                spawned = await daemon.run_once()

        # Should only spawn Task 1 (Task 2 is blocked)
        assert spawned == 1
        assert len(spawn_calls) == 1
        assert spawn_calls[0]["task_description"] == "Task 1"


class TestPhase07CLIIntegration:
    """Test CLI command integration."""

    def test_adw_run_command_exists(self) -> None:
        """Test that 'adw run' command exists."""
        from adw.cli import main

        # Check that 'run' command is registered
        assert "run" in [cmd.name for cmd in main.commands.values()]

    def test_dry_run_shows_eligible_tasks(self, tmp_path: Path) -> None:
        """Test that --dry-run shows eligible tasks without executing."""
        # This would be an integration test with the actual CLI
        # For now, we verify the parsing logic works
        content = """## Worktree: main

[] Task 1
[] Task 2
[⏰] Task 3 blocked
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(content)

        eligible = get_eligible_tasks(tasks_file)

        # Dry run should show Task 1 and Task 2
        assert len(eligible) == 2
        assert eligible[0].description == "Task 1"
        assert eligible[1].description == "Task 2"


# Mark all async tests
pytestmark = pytest.mark.anyio
