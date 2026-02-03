"""Tests for the web dashboard module."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

from adw.dashboard import (
    DEFAULT_DASHBOARD_PORT,
    DashboardStats,
    get_dashboard_stats,
)
from adw.dashboard.server import _get_dashboard_html


# =============================================================================
# DashboardStats Tests
# =============================================================================


class TestDashboardStats:
    """Tests for DashboardStats dataclass."""

    def test_create_dashboard_stats(self) -> None:
        """Test creating DashboardStats."""
        stats = DashboardStats(
            total_events=100,
            total_sessions=10,
            active_sessions=2,
            events_by_type={"tool_start": 50, "tool_end": 50},
            recent_errors=5,
            uptime_seconds=3600.0,
        )

        assert stats.total_events == 100
        assert stats.total_sessions == 10
        assert stats.active_sessions == 2
        assert stats.events_by_type == {"tool_start": 50, "tool_end": 50}
        assert stats.recent_errors == 5
        assert stats.uptime_seconds == 3600.0

    def test_to_dict(self) -> None:
        """Test converting DashboardStats to dict."""
        stats = DashboardStats(
            total_events=100,
            total_sessions=10,
            active_sessions=2,
            events_by_type={"error": 3},
            recent_errors=3,
            uptime_seconds=1800.0,
        )

        result = stats.to_dict()

        assert isinstance(result, dict)
        assert result["total_events"] == 100
        assert result["total_sessions"] == 10
        assert result["active_sessions"] == 2
        assert result["events_by_type"] == {"error": 3}
        assert result["recent_errors"] == 3
        assert result["uptime_seconds"] == 1800.0


# =============================================================================
# Dashboard HTML Tests
# =============================================================================


class TestDashboardHTML:
    """Tests for dashboard HTML generation."""

    def test_get_dashboard_html(self) -> None:
        """Test that dashboard HTML is generated."""
        html = _get_dashboard_html()

        assert isinstance(html, str)
        assert len(html) > 1000  # Should be substantial

    def test_html_contains_required_elements(self) -> None:
        """Test that HTML contains required elements."""
        html = _get_dashboard_html()

        # Check title
        assert "<title>ADW Dashboard</title>" in html

        # Check stats containers
        assert 'id="stat-events"' in html
        assert 'id="stat-sessions"' in html
        assert 'id="stat-active"' in html
        assert 'id="stat-errors"' in html

        # Check tabs
        assert 'data-panel="events"' in html
        assert 'data-panel="sessions"' in html
        assert 'data-panel="tasks"' in html

        # Check tables
        assert 'id="events-tbody"' in html
        assert 'id="tasks-tbody"' in html
        assert 'id="sessions-list"' in html

    def test_html_contains_sse_setup(self) -> None:
        """Test that HTML includes SSE setup code."""
        html = _get_dashboard_html()

        assert "EventSource" in html
        assert "/api/events/stream" in html

    def test_html_contains_api_calls(self) -> None:
        """Test that HTML includes API call setup."""
        html = _get_dashboard_html()

        assert "fetch('/api/stats')" in html
        # Uses template literals with backticks
        assert "/api/events" in html
        assert "/api/sessions" in html
        assert "/api/tasks" in html
        assert "fetch('/api/event-types')" in html


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_default_port(self) -> None:
        """Test default dashboard port."""
        assert DEFAULT_DASHBOARD_PORT == 3939


# =============================================================================
# FastAPI App Tests (Skip if FastAPI not installed)
# =============================================================================

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")
class TestDashboardAPI:
    """Tests for the FastAPI dashboard endpoints."""

    @pytest.fixture
    def client(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "TestClient":
        """Create test client with isolated database."""
        from adw.dashboard import create_dashboard_app

        # Set up isolated event database
        db_path = tmp_path / ".adw" / "events.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

        # Create agents directory for task listing
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Change to tmp_path for relative paths
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        app = create_dashboard_app()
        yield TestClient(app)

        os.chdir(original_cwd)

    def test_root_returns_html(self, client: "TestClient") -> None:
        """Test root endpoint returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "ADW Dashboard" in response.text

    def test_health_check(self, client: "TestClient") -> None:
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"

    def test_api_stats(self, client: "TestClient") -> None:
        """Test stats API endpoint."""
        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data
        assert "total_sessions" in data
        assert "active_sessions" in data
        assert "events_by_type" in data
        assert "recent_errors" in data
        assert "uptime_seconds" in data

    def test_api_events_empty(self, client: "TestClient") -> None:
        """Test events API with empty database."""
        response = client.get("/api/events")

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert data["events"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_api_events_with_limit(self, client: "TestClient") -> None:
        """Test events API with limit parameter."""
        response = client.get("/api/events?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10

    def test_api_events_with_offset(self, client: "TestClient") -> None:
        """Test events API with offset parameter."""
        response = client.get("/api/events?offset=5")

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 5

    def test_api_sessions_empty(self, client: "TestClient") -> None:
        """Test sessions API with empty database."""
        response = client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert data["sessions"] == []
        assert data["total"] == 0

    def test_api_tasks_empty(self, client: "TestClient") -> None:
        """Test tasks API with empty agents directory."""
        response = client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_api_event_types(self, client: "TestClient") -> None:
        """Test event types API."""
        response = client.get("/api/event-types")

        assert response.status_code == 200
        data = response.json()
        assert "event_types" in data
        assert isinstance(data["event_types"], list)
        assert len(data["event_types"]) > 0
        assert "tool_start" in data["event_types"]
        assert "error" in data["event_types"]


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")
class TestDashboardAPIWithData:
    """Tests for dashboard API with actual data."""

    @pytest.fixture
    def client_with_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "TestClient":
        """Create test client with some test data."""
        from adw.dashboard import create_dashboard_app
        from adw.observability.db import EventDB
        from adw.observability.models import EventType

        # Set up isolated event database
        db_path = tmp_path / ".adw" / "events.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

        # Create agents directory with test task
        agents_dir = tmp_path / "agents" / "test1234"
        agents_dir.mkdir(parents=True, exist_ok=True)
        state_file = agents_dir / "adw_state.json"
        state_file.write_text(json.dumps({
            "adw_id": "test1234",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "task_description": "Test task",
            "current_phase": "implement",
            "phases_completed": ["plan"],
            "errors": [],
        }))

        # Change to tmp_path
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        # Add some events to database
        db = EventDB(db_path)
        db.log_event(EventType.TOOL_START, task_id="test1234", data={"tool": "Read"})
        db.log_event(EventType.TOOL_END, task_id="test1234", data={"tool": "Read"})
        db.log_event(EventType.ERROR, task_id="test1234", data={"message": "Test error"})
        session = db.start_session("session123", task_id="test1234")

        app = create_dashboard_app()
        yield TestClient(app)

        os.chdir(original_cwd)

    def test_api_events_with_data(self, client_with_data: "TestClient") -> None:
        """Test events API returns data."""
        response = client_with_data.get("/api/events")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 4  # 3 events + session_start
        assert data["total"] == 4

    def test_api_events_filter_by_type(self, client_with_data: "TestClient") -> None:
        """Test filtering events by type."""
        response = client_with_data.get("/api/events?event_type=error")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "error"

    def test_api_events_filter_by_task(self, client_with_data: "TestClient") -> None:
        """Test filtering events by task ID."""
        response = client_with_data.get("/api/events?task_id=test1234")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 4
        for event in data["events"]:
            assert event["task_id"] == "test1234"

    def test_api_sessions_with_data(self, client_with_data: "TestClient") -> None:
        """Test sessions API returns data."""
        response = client_with_data.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["id"] == "session123"
        assert data["sessions"][0]["task_id"] == "test1234"
        assert data["sessions"][0]["status"] == "running"

    def test_api_tasks_with_data(self, client_with_data: "TestClient") -> None:
        """Test tasks API returns data."""
        response = client_with_data.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == "test1234"
        assert data["tasks"][0]["current_phase"] == "implement"

    def test_api_stats_with_data(self, client_with_data: "TestClient") -> None:
        """Test stats API with data."""
        response = client_with_data.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 4
        assert data["total_sessions"] == 1
        assert data["active_sessions"] == 1


# =============================================================================
# list_adw_states Tests
# =============================================================================


class TestListAdwStates:
    """Tests for list_adw_states function."""

    def test_list_empty_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing states with no agents directory."""
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            from adw.agent.state import list_adw_states
            states = list_adw_states()
            assert states == []
        finally:
            os.chdir(original_cwd)

    def test_list_with_states(self, tmp_path: Path) -> None:
        """Test listing states with actual state files."""
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Create agents directory with test states
            agents_dir = tmp_path / "agents"
            for i, adw_id in enumerate(["abc12345", "def67890", "ghi11111"]):
                state_dir = agents_dir / adw_id
                state_dir.mkdir(parents=True, exist_ok=True)
                state_file = state_dir / "adw_state.json"
                state_file.write_text(json.dumps({
                    "adw_id": adw_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": (datetime.now() + timedelta(seconds=i)).isoformat(),
                    "task_description": f"Task {i}",
                    "current_phase": "implement",
                    "phases_completed": [],
                    "errors": [],
                }))

            from adw.agent.state import list_adw_states
            states = list_adw_states()

            assert len(states) == 3
            # Should be sorted by updated_at descending
            assert states[0].adw_id == "ghi11111"
            assert states[1].adw_id == "def67890"
            assert states[2].adw_id == "abc12345"
        finally:
            os.chdir(original_cwd)

    def test_list_with_limit(self, tmp_path: Path) -> None:
        """Test listing states with limit."""
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Create agents directory with many states
            agents_dir = tmp_path / "agents"
            for i in range(10):
                adw_id = f"state{i:04d}"
                state_dir = agents_dir / adw_id
                state_dir.mkdir(parents=True, exist_ok=True)
                state_file = state_dir / "adw_state.json"
                state_file.write_text(json.dumps({
                    "adw_id": adw_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": (datetime.now() + timedelta(seconds=i)).isoformat(),
                    "current_phase": "init",
                    "phases_completed": [],
                    "errors": [],
                }))

            from adw.agent.state import list_adw_states
            states = list_adw_states(limit=3)

            assert len(states) == 3
        finally:
            os.chdir(original_cwd)

    def test_list_ignores_invalid_states(self, tmp_path: Path) -> None:
        """Test that invalid state files are ignored."""
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            agents_dir = tmp_path / "agents"

            # Create valid state
            valid_dir = agents_dir / "valid123"
            valid_dir.mkdir(parents=True, exist_ok=True)
            (valid_dir / "adw_state.json").write_text(json.dumps({
                "adw_id": "valid123",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "current_phase": "init",
                "phases_completed": [],
                "errors": [],
            }))

            # Create invalid state (bad JSON)
            invalid_dir = agents_dir / "invalid1"
            invalid_dir.mkdir(parents=True, exist_ok=True)
            (invalid_dir / "adw_state.json").write_text("not valid json")

            # Create invalid state (missing fields)
            invalid_dir2 = agents_dir / "invalid2"
            invalid_dir2.mkdir(parents=True, exist_ok=True)
            (invalid_dir2 / "adw_state.json").write_text("{}")

            from adw.agent.state import list_adw_states
            states = list_adw_states()

            assert len(states) == 1
            assert states[0].adw_id == "valid123"
        finally:
            os.chdir(original_cwd)
