"""Tests for concurrent task limiting in cron daemon."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from adw.agent.models import Task, TaskStatus
from adw.triggers.cron import CronConfig, CronDaemon

# Use pytest-anyio for async tests
pytestmark = pytest.mark.anyio


class TestConcurrentLimiting:
    """Tests for concurrent task execution limits."""

    def test_config_default_max_concurrent(self) -> None:
        """Test that CronConfig has default max_concurrent value."""
        config = CronConfig()
        assert config.max_concurrent == 3

    def test_config_custom_max_concurrent(self) -> None:
        """Test setting custom max_concurrent value."""
        config = CronConfig(max_concurrent=5)
        assert config.max_concurrent == 5

    def test_daemon_respects_max_concurrent_on_init(self) -> None:
        """Test that daemon initializes with configured max_concurrent."""
        config = CronConfig(max_concurrent=10)
        daemon = CronDaemon(config=config)
        assert daemon.config.max_concurrent == 10

    @patch("adw.triggers.cron.get_eligible_tasks")
    def test_get_eligible_count_with_no_running_tasks(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test eligible count when no tasks are running."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n[] Task 3\n")

        # Mock 3 eligible tasks
        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.PENDING),
            Task(description="Task 3", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=2)
        daemon = CronDaemon(config=config)

        count = daemon._get_eligible_count()

        # Should return 2 (max_concurrent) even though 3 are eligible
        assert count == 2

    @patch("adw.triggers.cron.get_eligible_tasks")
    def test_get_eligible_count_with_running_tasks(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test eligible count when some tasks are already running."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n[] Task 3\n")

        # Mock 2 eligible tasks
        mock_get_eligible.return_value = [
            Task(description="Task 2", status=TaskStatus.PENDING),
            Task(description="Task 3", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=3)
        daemon = CronDaemon(config=config)

        # Simulate 1 running task by adding to internal dict
        with patch.object(type(daemon.manager), "count", new_callable=PropertyMock) as mock_count:
            mock_count.return_value = 1
            count = daemon._get_eligible_count()

        # Should return 2 (3 max - 1 running)
        assert count == 2

    @patch("adw.triggers.cron.get_eligible_tasks")
    def test_get_eligible_count_at_max_capacity(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test eligible count when at max concurrent capacity."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n")

        # Mock 2 eligible tasks
        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=3)
        daemon = CronDaemon(config=config)

        # Simulate 3 running tasks (at max)
        with patch.object(type(daemon.manager), "count", new_callable=PropertyMock) as mock_count:
            mock_count.return_value = 3
            count = daemon._get_eligible_count()

        # Should return 0 (no available slots)
        assert count == 0

    @patch("adw.triggers.cron.get_eligible_tasks")
    def test_get_eligible_count_over_capacity(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test eligible count when running tasks exceed max (edge case)."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n")

        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=2)
        daemon = CronDaemon(config=config)

        # Simulate more running tasks than max (shouldn't happen but test defensive code)
        with patch.object(type(daemon.manager), "count", new_callable=PropertyMock) as mock_count:
            mock_count.return_value = 5
            count = daemon._get_eligible_count()

        # Should return 0 (no available slots, using max(0, ...))
        assert count == 0

    @patch("adw.triggers.cron.get_eligible_tasks")
    def test_pick_next_task_respects_limit_implicitly(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that _pick_next_task filters already running tasks."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n")

        task1 = Task(description="Task 1", status=TaskStatus.PENDING)
        task2 = Task(description="Task 2", status=TaskStatus.PENDING)
        mock_get_eligible.return_value = [task1, task2]

        config = CronConfig(tasks_file=tasks_file)
        daemon = CronDaemon(config=config)

        # Mark task1 as running
        daemon._task_agents["Task 1"] = "adw_id_1"

        # Should pick task2 since task1 is already running
        next_task = daemon._pick_next_task()
        assert next_task is not None
        assert next_task.description == "Task 2"

    @patch("adw.triggers.cron.get_eligible_tasks")
    def test_pick_next_task_returns_none_when_all_running(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that _pick_next_task returns None when all eligible tasks are running."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n")

        task1 = Task(description="Task 1", status=TaskStatus.PENDING)
        task2 = Task(description="Task 2", status=TaskStatus.PENDING)
        mock_get_eligible.return_value = [task1, task2]

        config = CronConfig(tasks_file=tasks_file)
        daemon = CronDaemon(config=config)

        # Mark both as running
        daemon._task_agents["Task 1"] = "adw_id_1"
        daemon._task_agents["Task 2"] = "adw_id_2"

        # Should return None
        next_task = daemon._pick_next_task()
        assert next_task is None

    @patch("adw.triggers.cron.get_eligible_tasks")
    async def test_run_once_respects_max_concurrent(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that run_once respects max_concurrent limit."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n[] Task 3\n[] Task 4\n")

        # Mock 4 eligible tasks
        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.PENDING),
            Task(description="Task 3", status=TaskStatus.PENDING),
            Task(description="Task 4", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=2, auto_start=True)
        daemon = CronDaemon(config=config)

        # Mock spawn_workflow to track calls and add to manager._agents
        from adw.agent.manager import AgentProcess
        spawn_count = 0
        def mock_spawn(**kwargs):
            nonlocal spawn_count
            spawn_count += 1
            adw_id = f"adw{spawn_count}"
            # Simulate adding to manager's internal dict
            daemon.manager._agents[adw_id] = Mock(spec=AgentProcess, adw_id=adw_id)
            return adw_id

        with patch.object(daemon.manager, "spawn_workflow", side_effect=mock_spawn):
            with patch("adw.triggers.cron.mark_in_progress"):
                spawned = await daemon.run_once()

        # Should spawn exactly 2 tasks (max_concurrent limit)
        assert spawned == 2
        assert len(daemon._task_agents) == 2
        assert daemon.manager.count == 2

    @patch("adw.triggers.cron.get_eligible_tasks")
    async def test_run_once_spawns_partial_when_near_limit(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that run_once spawns only available slots when near limit."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n[] Task 2\n")

        # Mock 2 eligible tasks
        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=3, auto_start=True)
        daemon = CronDaemon(config=config)

        # Pre-populate with 2 running tasks in both daemon and manager
        from adw.agent.manager import AgentProcess
        daemon._task_agents["Existing Task 1"] = "existing_adw1"
        daemon._task_agents["Existing Task 2"] = "existing_adw2"
        daemon.manager._agents["existing_adw1"] = Mock(spec=AgentProcess, adw_id="existing_adw1")
        daemon.manager._agents["existing_adw2"] = Mock(spec=AgentProcess, adw_id="existing_adw2")

        spawn_count = 0
        def mock_spawn(**kwargs):
            nonlocal spawn_count
            spawn_count += 1
            adw_id = f"adw{spawn_count}"
            daemon.manager._agents[adw_id] = Mock(spec=AgentProcess, adw_id=adw_id)
            return adw_id

        with patch.object(daemon.manager, "spawn_workflow", side_effect=mock_spawn):
            with patch.object(daemon.manager, "poll", return_value=[]):  # No completions
                with patch("adw.triggers.cron.mark_in_progress"):
                    spawned = await daemon.run_once()

        # Should spawn only 1 task (3 max - 2 running = 1 slot)
        assert spawned == 1
        assert len(daemon._task_agents) == 3  # 2 existing + 1 new
        assert daemon.manager.count == 3

    @patch("adw.triggers.cron.get_eligible_tasks")
    async def test_run_once_spawns_nothing_at_max(
        self, mock_get_eligible: Mock, tmp_path: Path
    ) -> None:
        """Test that run_once spawns nothing when at max capacity."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n")

        mock_get_eligible.return_value = [
            Task(description="Task 1", status=TaskStatus.PENDING),
        ]

        config = CronConfig(tasks_file=tasks_file, max_concurrent=3, auto_start=True)
        daemon = CronDaemon(config=config)

        # Pre-populate with 3 running tasks (at max) in both daemon and manager
        from adw.agent.manager import AgentProcess
        daemon._task_agents["Task A"] = "adw_a"
        daemon._task_agents["Task B"] = "adw_b"
        daemon._task_agents["Task C"] = "adw_c"
        daemon.manager._agents["adw_a"] = Mock(spec=AgentProcess, adw_id="adw_a")
        daemon.manager._agents["adw_b"] = Mock(spec=AgentProcess, adw_id="adw_b")
        daemon.manager._agents["adw_c"] = Mock(spec=AgentProcess, adw_id="adw_c")

        with patch.object(daemon.manager, "poll", return_value=[]):  # No completions
            spawned = await daemon.run_once()

        # Should spawn 0 tasks
        assert spawned == 0
        assert len(daemon._task_agents) == 3  # No new tasks added
        assert daemon.manager.count == 3

    def test_check_completions_frees_up_slots(self, tmp_path: Path) -> None:
        """Test that completed tasks free up slots for new tasks."""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text("[] Task 1\n")

        config = CronConfig(tasks_file=tasks_file, max_concurrent=2)
        daemon = CronDaemon(config=config)

        # Add running tasks
        daemon._task_agents["Task 1"] = "adw1"
        daemon._task_agents["Task 2"] = "adw2"

        # Mock manager.poll to return completed tasks
        # poll() returns list of (adw_id, return_code, stderr)
        with patch.object(daemon.manager, "poll") as mock_poll:
            mock_poll.return_value = [("adw1", 0, "")]
            with patch("adw.triggers.cron.mark_done"):
                completed = daemon._check_completions()

        # Should have freed up one slot
        assert len(completed) == 1
        assert "Task 1" not in daemon._task_agents
        assert "Task 2" in daemon._task_agents


class TestConcurrentLimitingIntegration:
    """Integration tests for concurrent limiting with real scenarios."""

    async def test_concurrent_limit_real_scenario(self, tmp_path: Path) -> None:
        """Test realistic concurrent limiting scenario."""
        tasks_content = """## Worktree: test-phase

[] Build frontend
[] Build backend
[] Run tests
[] Deploy staging
"""
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(tasks_content)

        config = CronConfig(
            tasks_file=tasks_file, max_concurrent=2, poll_interval=0.1, auto_start=True
        )
        daemon = CronDaemon(config=config)

        # Mock spawn_workflow to track calls
        from adw.agent.manager import AgentProcess
        spawn_calls = []
        spawn_count = 0

        def mock_spawn(**kwargs):
            nonlocal spawn_count
            spawn_count += 1
            adw_id = f"adw{spawn_count}"
            spawn_calls.append(kwargs["task_description"])
            daemon.manager._agents[adw_id] = Mock(spec=AgentProcess, adw_id=adw_id)
            return adw_id

        with patch.object(daemon.manager, "spawn_workflow", side_effect=mock_spawn):
            with patch("adw.triggers.cron.mark_in_progress"):
                await daemon.run_once()

        # Should have spawned exactly 2 tasks (max_concurrent)
        assert len(spawn_calls) == 2
        assert len(daemon._task_agents) == 2
        assert daemon.manager.count == 2

    def test_concurrent_limit_prevents_overload(self, tmp_path: Path) -> None:
        """Test that concurrent limit prevents system overload."""
        # Create many pending tasks
        tasks_content = "\n".join([f"[] Task {i}" for i in range(100)])
        tasks_file = tmp_path / "tasks.md"
        tasks_file.write_text(tasks_content)

        config = CronConfig(tasks_file=tasks_file, max_concurrent=5)
        daemon = CronDaemon(config=config)

        # Even with 100 tasks, eligible count should respect limit
        with patch("adw.triggers.cron.get_eligible_tasks") as mock_eligible:
            mock_eligible.return_value = [
                Task(description=f"Task {i}", status=TaskStatus.PENDING)
                for i in range(100)
            ]
            with patch.object(type(daemon.manager), "count", new_callable=PropertyMock) as mock_count:
                mock_count.return_value = 0
                count = daemon._get_eligible_count()

        # Should never exceed max_concurrent
        assert count <= 5
        assert count == 5  # All slots available
