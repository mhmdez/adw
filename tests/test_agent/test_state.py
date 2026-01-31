"""Unit tests for state management."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from adw.agent.state import ADWState


class TestADWState:
    """Test ADWState model."""

    def test_minimal_state(self):
        """Test state with minimal required fields."""
        state = ADWState(adw_id="test1234")
        assert state.adw_id == "test1234"
        assert state.task_description == ""
        assert state.task_id is None
        assert state.task_tags == []
        assert state.workflow_type == "standard"
        assert state.current_phase == "init"
        assert state.phases_completed == []
        assert state.worktree_name is None
        assert state.worktree_path is None
        assert state.branch_name is None
        assert state.commit_hash is None
        assert state.plan_file is None
        assert state.errors == []

    def test_full_state(self):
        """Test state with all fields populated."""
        state = ADWState(
            adw_id="test1234",
            task_description="Test task",
            task_id="task123",
            task_tags=["opus", "urgent"],
            workflow_type="full",
            current_phase="implement",
            phases_completed=["plan"],
            worktree_name="feature-x",
            worktree_path="/tmp/feature-x",
            branch_name="feature-x",
            commit_hash="abc123",
            plan_file="plan.md",
            errors=[{"phase": "plan", "error": "Test error"}],
        )

        assert state.adw_id == "test1234"
        assert state.task_description == "Test task"
        assert state.task_id == "task123"
        assert state.task_tags == ["opus", "urgent"]
        assert state.workflow_type == "full"
        assert state.current_phase == "implement"
        assert state.phases_completed == ["plan"]
        assert state.worktree_name == "feature-x"
        assert state.worktree_path == "/tmp/feature-x"
        assert state.branch_name == "feature-x"
        assert state.commit_hash == "abc123"
        assert state.plan_file == "plan.md"
        assert len(state.errors) == 1

    def test_timestamps_auto_generated(self):
        """Test that timestamps are automatically generated."""
        state = ADWState(adw_id="test1234")
        assert state.created_at is not None
        assert state.updated_at is not None
        # Should be valid ISO format
        datetime.fromisoformat(state.created_at)
        datetime.fromisoformat(state.updated_at)

    def test_get_path(self):
        """Test get_path class method."""
        path = ADWState.get_path("test1234")
        assert path == Path("agents/test1234/adw_state.json")

    def test_save_creates_directory(self, tmp_path):
        """Test that save creates directory structure."""
        state = ADWState(adw_id="test1234")

        # Mock get_path to use tmp_path
        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: tmp_path / "agents" / adw_id / "adw_state.json")

        try:
            path = state.save()
            assert path.exists()
            assert path.parent.exists()
        finally:
            ADWState.get_path = original_get_path

    def test_save_writes_json(self, tmp_path):
        """Test that save writes valid JSON."""
        state = ADWState(
            adw_id="test1234",
            task_description="Test task",
            current_phase="plan",
        )

        state_file = tmp_path / "adw_state.json"
        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            state.save()
            assert state_file.exists()

            # Load and verify JSON
            data = json.loads(state_file.read_text())
            assert data["adw_id"] == "test1234"
            assert data["task_description"] == "Test task"
            assert data["current_phase"] == "plan"
        finally:
            ADWState.get_path = original_get_path

    def test_save_with_phase(self, tmp_path):
        """Test save with phase parameter."""
        state = ADWState(adw_id="test1234")

        state_file = tmp_path / "adw_state.json"
        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            state.save(phase="plan")
            assert state.current_phase == "plan"
            assert "plan" in state.phases_completed

            # Save another phase
            state.save(phase="implement")
            assert state.current_phase == "implement"
            assert state.phases_completed == ["plan", "implement"]
        finally:
            ADWState.get_path = original_get_path

    def test_save_updates_timestamp(self, tmp_path):
        """Test that save updates the timestamp."""
        state = ADWState(adw_id="test1234")
        original_updated = state.updated_at

        state_file = tmp_path / "adw_state.json"
        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            import time
            time.sleep(0.01)  # Small delay to ensure timestamp changes
            state.save()
            assert state.updated_at != original_updated
        finally:
            ADWState.get_path = original_get_path

    def test_load_nonexistent(self):
        """Test loading non-existent state."""
        state = ADWState.load("nonexistent")
        assert state is None

    def test_load_existing(self, tmp_path):
        """Test loading existing state."""
        # Create state file
        state_data = {
            "adw_id": "test1234",
            "created_at": "2026-01-31T10:00:00",
            "updated_at": "2026-01-31T10:00:00",
            "task_description": "Test task",
            "task_id": None,
            "task_tags": ["opus"],
            "workflow_type": "standard",
            "current_phase": "plan",
            "phases_completed": [],
            "worktree_name": None,
            "worktree_path": None,
            "branch_name": None,
            "commit_hash": None,
            "plan_file": None,
            "errors": [],
        }

        state_file = tmp_path / "adw_state.json"
        state_file.write_text(json.dumps(state_data))

        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            state = ADWState.load("test1234")
            assert state is not None
            assert state.adw_id == "test1234"
            assert state.task_description == "Test task"
            assert state.task_tags == ["opus"]
            assert state.current_phase == "plan"
        finally:
            ADWState.get_path = original_get_path

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON returns None."""
        state_file = tmp_path / "adw_state.json"
        state_file.write_text("invalid json {{{")

        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            state = ADWState.load("test1234")
            assert state is None
        finally:
            ADWState.get_path = original_get_path

    def test_add_error(self):
        """Test adding errors to state."""
        state = ADWState(adw_id="test1234")
        assert len(state.errors) == 0

        state.add_error("plan", "Planning failed")
        assert len(state.errors) == 1
        assert state.errors[0]["phase"] == "plan"
        assert state.errors[0]["error"] == "Planning failed"
        assert "timestamp" in state.errors[0]

        state.add_error("implement", "Implementation error")
        assert len(state.errors) == 2
        assert state.errors[1]["phase"] == "implement"

    def test_save_and_load_roundtrip(self, tmp_path):
        """Test save and load roundtrip."""
        original_state = ADWState(
            adw_id="test1234",
            task_description="Test task",
            task_tags=["opus"],
            workflow_type="full",
            current_phase="implement",
            phases_completed=["plan"],
        )

        state_file = tmp_path / "adw_state.json"
        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            original_state.save()
            loaded_state = ADWState.load("test1234")

            assert loaded_state is not None
            assert loaded_state.adw_id == original_state.adw_id
            assert loaded_state.task_description == original_state.task_description
            assert loaded_state.task_tags == original_state.task_tags
            assert loaded_state.workflow_type == original_state.workflow_type
            assert loaded_state.current_phase == original_state.current_phase
            assert loaded_state.phases_completed == original_state.phases_completed
        finally:
            ADWState.get_path = original_get_path

    def test_workflow_type_validation(self):
        """Test workflow_type literal validation."""
        # Valid types
        ADWState(adw_id="test", workflow_type="simple")
        ADWState(adw_id="test", workflow_type="standard")
        ADWState(adw_id="test", workflow_type="full")
        ADWState(adw_id="test", workflow_type="prototype")

        # Invalid type should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            ADWState(adw_id="test", workflow_type="invalid")

    def test_phase_not_duplicated_in_completed(self, tmp_path):
        """Test that phases are not duplicated in phases_completed."""
        state = ADWState(adw_id="test1234")

        state_file = tmp_path / "adw_state.json"
        original_get_path = ADWState.get_path
        ADWState.get_path = classmethod(lambda cls, adw_id: state_file)

        try:
            state.save(phase="plan")
            state.save(phase="plan")  # Save same phase again
            assert state.phases_completed == ["plan"]  # Should not duplicate
        finally:
            ADWState.get_path = original_get_path
