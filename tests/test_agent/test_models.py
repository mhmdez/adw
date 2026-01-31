"""Unit tests for data models."""

import pytest
from adw.agent.models import (
    TaskStatus,
    RetryCode,
    AgentPromptRequest,
    AgentPromptResponse,
    Task,
    Worktree,
)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_all_statuses_defined(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.BLOCKED == "blocked"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.FAILED == "failed"


class TestRetryCode:
    """Test RetryCode enum."""

    def test_all_codes_defined(self):
        assert RetryCode.NONE == "none"
        assert RetryCode.CLAUDE_CODE_ERROR == "claude_code_error"
        assert RetryCode.TIMEOUT_ERROR == "timeout_error"
        assert RetryCode.EXECUTION_ERROR == "execution_error"
        assert RetryCode.RATE_LIMIT == "rate_limit"


class TestAgentPromptRequest:
    """Test AgentPromptRequest model."""

    def test_minimal_request(self):
        req = AgentPromptRequest(prompt="test prompt", adw_id="abc123de")
        assert req.prompt == "test prompt"
        assert req.adw_id == "abc123de"
        assert req.agent_name == "default"
        assert req.model == "sonnet"
        assert req.working_dir is None
        assert req.timeout == 300
        assert req.dangerously_skip_permissions is False

    def test_full_request(self):
        req = AgentPromptRequest(
            prompt="test prompt",
            adw_id="abc123de",
            agent_name="custom",
            model="opus",
            working_dir="/tmp/test",
            timeout=600,
            dangerously_skip_permissions=True,
        )
        assert req.prompt == "test prompt"
        assert req.adw_id == "abc123de"
        assert req.agent_name == "custom"
        assert req.model == "opus"
        assert req.working_dir == "/tmp/test"
        assert req.timeout == 600
        assert req.dangerously_skip_permissions is True

    def test_model_validation(self):
        # Valid models
        AgentPromptRequest(prompt="test", adw_id="abc", model="haiku")
        AgentPromptRequest(prompt="test", adw_id="abc", model="sonnet")
        AgentPromptRequest(prompt="test", adw_id="abc", model="opus")

        # Invalid model should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            AgentPromptRequest(prompt="test", adw_id="abc", model="invalid")


class TestAgentPromptResponse:
    """Test AgentPromptResponse model."""

    def test_success_response(self):
        resp = AgentPromptResponse(
            output="Success output",
            success=True,
            session_id="session123",
            duration_seconds=1.5,
        )
        assert resp.output == "Success output"
        assert resp.success is True
        assert resp.session_id == "session123"
        assert resp.retry_code == RetryCode.NONE
        assert resp.error_message is None
        assert resp.duration_seconds == 1.5

    def test_error_response(self):
        resp = AgentPromptResponse(
            output="",
            success=False,
            retry_code=RetryCode.TIMEOUT_ERROR,
            error_message="Request timed out",
            duration_seconds=300.0,
        )
        assert resp.output == ""
        assert resp.success is False
        assert resp.retry_code == RetryCode.TIMEOUT_ERROR
        assert resp.error_message == "Request timed out"
        assert resp.duration_seconds == 300.0


class TestTask:
    """Test Task model."""

    def test_minimal_task(self):
        task = Task(description="Test task")
        assert task.description == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.adw_id is None
        assert task.commit_hash is None
        assert task.error_message is None
        assert task.tags == []
        assert task.worktree_name is None
        assert task.line_number is None

    def test_full_task(self):
        task = Task(
            description="Test task",
            status=TaskStatus.IN_PROGRESS,
            adw_id="abc123de",
            commit_hash="abc123",
            error_message="Some error",
            tags=["opus", "urgent"],
            worktree_name="feature-x",
            line_number=42,
        )
        assert task.description == "Test task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.adw_id == "abc123de"
        assert task.commit_hash == "abc123"
        assert task.error_message == "Some error"
        assert task.tags == ["opus", "urgent"]
        assert task.worktree_name == "feature-x"
        assert task.line_number == 42

    def test_is_running_property(self):
        pending = Task(description="Test", status=TaskStatus.PENDING)
        running = Task(description="Test", status=TaskStatus.IN_PROGRESS)
        done = Task(description="Test", status=TaskStatus.DONE)

        assert pending.is_running is False
        assert running.is_running is True
        assert done.is_running is False

    def test_is_eligible_property(self):
        pending = Task(description="Test", status=TaskStatus.PENDING)
        blocked = Task(description="Test", status=TaskStatus.BLOCKED)
        running = Task(description="Test", status=TaskStatus.IN_PROGRESS)
        done = Task(description="Test", status=TaskStatus.DONE)
        failed = Task(description="Test", status=TaskStatus.FAILED)

        assert pending.is_eligible is True
        assert blocked.is_eligible is True
        assert running.is_eligible is False
        assert done.is_eligible is False
        assert failed.is_eligible is False

    def test_model_property_opus(self):
        task = Task(description="Test", tags=["opus", "other"])
        assert task.model == "opus"

    def test_model_property_haiku(self):
        task = Task(description="Test", tags=["haiku"])
        assert task.model == "haiku"

    def test_model_property_default(self):
        task = Task(description="Test")
        assert task.model == "sonnet"

    def test_model_property_priority(self):
        # Opus takes priority over haiku
        task = Task(description="Test", tags=["haiku", "opus"])
        assert task.model == "opus"


class TestWorktree:
    """Test Worktree model."""

    def test_minimal_worktree(self):
        wt = Worktree(name="main")
        assert wt.name == "main"
        assert wt.tasks == []

    def test_worktree_with_tasks(self):
        tasks = [
            Task(description="Task 1"),
            Task(description="Task 2"),
        ]
        wt = Worktree(name="feature-x", tasks=tasks)
        assert wt.name == "feature-x"
        assert len(wt.tasks) == 2
        assert wt.tasks[0].description == "Task 1"
        assert wt.tasks[1].description == "Task 2"

    def test_get_eligible_tasks_all_pending(self):
        """All pending tasks are eligible."""
        tasks = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.PENDING),
            Task(description="Task 3", status=TaskStatus.PENDING),
        ]
        wt = Worktree(name="main", tasks=tasks)
        eligible = wt.get_eligible_tasks()
        assert len(eligible) == 3

    def test_get_eligible_tasks_with_done(self):
        """Done tasks are not eligible."""
        tasks = [
            Task(description="Task 1", status=TaskStatus.DONE),
            Task(description="Task 2", status=TaskStatus.PENDING),
            Task(description="Task 3", status=TaskStatus.PENDING),
        ]
        wt = Worktree(name="main", tasks=tasks)
        eligible = wt.get_eligible_tasks()
        assert len(eligible) == 2
        assert eligible[0].description == "Task 2"
        assert eligible[1].description == "Task 3"

    def test_get_eligible_tasks_blocked_after_done(self):
        """Blocked task becomes eligible when all above are done."""
        tasks = [
            Task(description="Task 1", status=TaskStatus.DONE),
            Task(description="Task 2", status=TaskStatus.BLOCKED),
        ]
        wt = Worktree(name="main", tasks=tasks)
        eligible = wt.get_eligible_tasks()
        assert len(eligible) == 1
        assert eligible[0].description == "Task 2"

    def test_get_eligible_tasks_blocked_not_eligible(self):
        """Blocked task is not eligible when tasks above are not done."""
        tasks = [
            Task(description="Task 1", status=TaskStatus.PENDING),
            Task(description="Task 2", status=TaskStatus.BLOCKED),
        ]
        wt = Worktree(name="main", tasks=tasks)
        eligible = wt.get_eligible_tasks()
        assert len(eligible) == 1
        assert eligible[0].description == "Task 1"

    def test_get_eligible_tasks_complex_scenario(self):
        """Complex scenario with mixed statuses."""
        tasks = [
            Task(description="Task 1", status=TaskStatus.DONE),
            Task(description="Task 2", status=TaskStatus.DONE),
            Task(description="Task 3", status=TaskStatus.BLOCKED),  # Eligible: all above done
            Task(description="Task 4", status=TaskStatus.PENDING),
            Task(description="Task 5", status=TaskStatus.BLOCKED),  # Not eligible: Task 3,4 not done
            Task(description="Task 6", status=TaskStatus.IN_PROGRESS),
            Task(description="Task 7", status=TaskStatus.FAILED),
        ]
        wt = Worktree(name="main", tasks=tasks)
        eligible = wt.get_eligible_tasks()
        assert len(eligible) == 2
        assert eligible[0].description == "Task 3"
        assert eligible[1].description == "Task 4"

    def test_get_eligible_tasks_empty_worktree(self):
        """Empty worktree has no eligible tasks."""
        wt = Worktree(name="main", tasks=[])
        eligible = wt.get_eligible_tasks()
        assert len(eligible) == 0
