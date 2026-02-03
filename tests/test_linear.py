"""Tests for Linear integration.

Tests cover:
- LinearConfig creation and loading
- LinearIssue dataclass
- Status mapping between Linear and ADW
- LinearClient GraphQL requests (mocked)
- LinearWatcher filter and processing
- Issue parsing from API responses
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adw.integrations.linear import (
    ADW_TO_LINEAR_STATUS,
    LINEAR_TO_ADW_STATUS,
    LinearClient,
    LinearConfig,
    LinearIssue,
    LinearWatcher,
    _parse_simple_toml,
    parse_linear_issue,
)


# =============================================================================
# Status Mapping Tests
# =============================================================================


class TestStatusMapping:
    """Tests for Linear <-> ADW status mappings."""

    def test_linear_to_adw_status_pending(self) -> None:
        """Test mapping pending states from Linear to ADW."""
        assert LINEAR_TO_ADW_STATUS["backlog"] == "pending"
        assert LINEAR_TO_ADW_STATUS["unstarted"] == "pending"
        assert LINEAR_TO_ADW_STATUS["triage"] == "pending"
        assert LINEAR_TO_ADW_STATUS["todo"] == "pending"

    def test_linear_to_adw_status_in_progress(self) -> None:
        """Test mapping in-progress states from Linear to ADW."""
        assert LINEAR_TO_ADW_STATUS["in progress"] == "in_progress"
        assert LINEAR_TO_ADW_STATUS["in review"] == "in_progress"

    def test_linear_to_adw_status_completed(self) -> None:
        """Test mapping completed states from Linear to ADW."""
        assert LINEAR_TO_ADW_STATUS["done"] == "completed"
        assert LINEAR_TO_ADW_STATUS["completed"] == "completed"

    def test_linear_to_adw_status_failed(self) -> None:
        """Test mapping failed states from Linear to ADW."""
        assert LINEAR_TO_ADW_STATUS["canceled"] == "failed"
        assert LINEAR_TO_ADW_STATUS["cancelled"] == "failed"
        assert LINEAR_TO_ADW_STATUS["duplicate"] == "failed"

    def test_adw_to_linear_status_mapping(self) -> None:
        """Test mapping from ADW status to Linear status names."""
        assert ADW_TO_LINEAR_STATUS["pending"] == "Todo"
        assert ADW_TO_LINEAR_STATUS["in_progress"] == "In Progress"
        assert ADW_TO_LINEAR_STATUS["completed"] == "Done"
        assert ADW_TO_LINEAR_STATUS["failed"] == "Canceled"


# =============================================================================
# LinearConfig Tests
# =============================================================================


class TestLinearConfig:
    """Tests for LinearConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = LinearConfig(api_key="lin_api_test123")

        assert config.api_key == "lin_api_test123"
        assert config.team_id is None
        assert config.poll_interval == 60
        assert config.filter_states == ["Backlog", "Todo", "Triage"]
        assert config.sync_comments is True
        assert config.label_filter == []

    def test_custom_values(self) -> None:
        """Test config with custom values."""
        config = LinearConfig(
            api_key="lin_api_test123",
            team_id="team_abc123",
            poll_interval=120,
            filter_states=["Ready", "Waiting"],
            sync_comments=False,
            label_filter=["adw", "automated"],
        )

        assert config.team_id == "team_abc123"
        assert config.poll_interval == 120
        assert config.filter_states == ["Ready", "Waiting"]
        assert config.sync_comments is False
        assert config.label_filter == ["adw", "automated"]

    def test_from_env_missing_vars(self) -> None:
        """Test loading from env with missing variables."""
        with patch.dict(os.environ, {}, clear=True):
            config = LinearConfig.from_env()
            assert config is None

    def test_from_env_with_api_key(self) -> None:
        """Test loading from environment variables."""
        env = {
            "LINEAR_API_KEY": "lin_api_from_env",
            "LINEAR_TEAM_ID": "team_from_env",
            "LINEAR_POLL_INTERVAL": "180",
        }
        with patch.dict(os.environ, env, clear=True):
            config = LinearConfig.from_env()

            assert config is not None
            assert config.api_key == "lin_api_from_env"
            assert config.team_id == "team_from_env"
            assert config.poll_interval == 180

    def test_from_env_api_key_only(self) -> None:
        """Test loading with just API key (team_id optional)."""
        env = {"LINEAR_API_KEY": "lin_api_minimal"}
        with patch.dict(os.environ, env, clear=True):
            config = LinearConfig.from_env()

            assert config is not None
            assert config.api_key == "lin_api_minimal"
            assert config.team_id is None

    def test_from_config_file_not_exists(self) -> None:
        """Test loading from non-existent config file."""
        config = LinearConfig.from_config_file(Path("/nonexistent/path/config.toml"))
        assert config is None

    def test_from_config_file_simple_toml(self) -> None:
        """Test loading from simple TOML config file."""
        toml_content = """
[linear]
api_key = "lin_api_from_file"
team_id = "team_from_file"
poll_interval = 90
sync_comments = false
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                config = LinearConfig.from_config_file(Path(f.name))

                assert config is not None
                assert config.api_key == "lin_api_from_file"
                assert config.team_id == "team_from_file"
                assert config.poll_interval == 90
            finally:
                os.unlink(f.name)

    def test_to_dict(self) -> None:
        """Test converting config to dictionary."""
        config = LinearConfig(
            api_key="lin_api_test",
            team_id="team123",
        )
        data = config.to_dict()

        assert "team_id" in data
        assert data["team_id"] == "team123"
        assert data["poll_interval"] == 60
        assert data["sync_comments"] is True
        # API key should not be in serialization
        assert "api_key" not in data

    def test_load_prefers_env(self) -> None:
        """Test that load() prefers environment over config file."""
        env = {"LINEAR_API_KEY": "lin_api_from_env"}
        with patch.dict(os.environ, env, clear=True):
            config = LinearConfig.load()

            assert config is not None
            assert config.api_key == "lin_api_from_env"


# =============================================================================
# LinearIssue Tests
# =============================================================================


class TestLinearIssue:
    """Tests for LinearIssue dataclass."""

    def test_default_values(self) -> None:
        """Test default issue values."""
        issue = LinearIssue(
            id="issue123",
            identifier="TEAM-123",
            title="Test issue",
        )

        assert issue.id == "issue123"
        assert issue.identifier == "TEAM-123"
        assert issue.title == "Test issue"
        assert issue.description == ""
        assert issue.state == "Backlog"
        assert issue.state_id == ""
        assert issue.priority == 0
        assert issue.labels == []
        assert issue.adw_id is None

    def test_to_dict(self) -> None:
        """Test converting issue to dictionary."""
        now = datetime.now()
        issue = LinearIssue(
            id="issue123",
            identifier="TEAM-123",
            title="Test issue",
            description="Issue description",
            state="In Progress",
            state_id="state_abc",
            priority=2,
            url="https://linear.app/team/issue/TEAM-123",
            labels=["bug", "urgent"],
            team_id="team_abc",
            adw_id="abc12345",
            created_at=now,
        )
        data = issue.to_dict()

        assert data["id"] == "issue123"
        assert data["identifier"] == "TEAM-123"
        assert data["title"] == "Test issue"
        assert data["description"] == "Issue description"
        assert data["state"] == "In Progress"
        assert data["priority"] == 2
        assert data["labels"] == ["bug", "urgent"]
        assert data["adw_id"] == "abc12345"
        assert data["created_at"] == now.isoformat()

    def test_from_dict(self) -> None:
        """Test creating issue from dictionary."""
        data = {
            "id": "issue123",
            "identifier": "TEAM-456",
            "title": "From dict",
            "state": "Done",
            "priority": 1,
            "labels": ["feature"],
            "adw_id": "def67890",
        }
        issue = LinearIssue.from_dict(data)

        assert issue.id == "issue123"
        assert issue.identifier == "TEAM-456"
        assert issue.title == "From dict"
        assert issue.state == "Done"
        assert issue.priority == 1
        assert issue.labels == ["feature"]
        assert issue.adw_id == "def67890"

    def test_get_workflow_or_default_from_labels(self) -> None:
        """Test workflow detection from labels."""
        # SDLC label
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", labels=["sdlc"]
        )
        assert issue.get_workflow_or_default() == "sdlc"

        # workflow:simple label
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", labels=["workflow:simple"]
        )
        assert issue.get_workflow_or_default() == "simple"

        # workflow:standard label
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", labels=["workflow:standard"]
        )
        assert issue.get_workflow_or_default() == "standard"

    def test_get_workflow_or_default_from_priority(self) -> None:
        """Test workflow defaults to adaptive for auto-detection."""
        # All priorities default to adaptive now (auto-detects complexity)
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=1
        )
        assert issue.get_workflow_or_default() == "adaptive"

        # High priority -> adaptive
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=2
        )
        assert issue.get_workflow_or_default() == "adaptive"

        # Medium priority -> adaptive
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=3
        )
        assert issue.get_workflow_or_default() == "adaptive"

        # No priority -> adaptive
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=0
        )
        assert issue.get_workflow_or_default() == "adaptive"

    def test_get_model_or_default_from_labels(self) -> None:
        """Test model detection from labels."""
        # opus label
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", labels=["opus"]
        )
        assert issue.get_model_or_default() == "opus"

        # model:haiku label
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", labels=["model:haiku"]
        )
        assert issue.get_model_or_default() == "haiku"

        # model:sonnet label
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", labels=["model:sonnet"]
        )
        assert issue.get_model_or_default() == "sonnet"

    def test_get_model_or_default_from_priority(self) -> None:
        """Test model defaults based on priority."""
        # Urgent priority -> opus
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=1
        )
        assert issue.get_model_or_default() == "opus"

        # Other priorities -> sonnet
        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=2
        )
        assert issue.get_model_or_default() == "sonnet"

        issue = LinearIssue(
            id="1", identifier="T-1", title="Test", priority=0
        )
        assert issue.get_model_or_default() == "sonnet"

    def test_get_priority_string(self) -> None:
        """Test priority conversion to ADW format."""
        assert LinearIssue(
            id="1", identifier="T-1", title="T", priority=1
        ).get_priority_string() == "p0"

        assert LinearIssue(
            id="1", identifier="T-1", title="T", priority=2
        ).get_priority_string() == "p1"

        assert LinearIssue(
            id="1", identifier="T-1", title="T", priority=3
        ).get_priority_string() == "p2"

        assert LinearIssue(
            id="1", identifier="T-1", title="T", priority=4
        ).get_priority_string() == "p3"

        # No priority defaults to p2
        assert LinearIssue(
            id="1", identifier="T-1", title="T", priority=0
        ).get_priority_string() == "p2"


# =============================================================================
# Issue Parsing Tests
# =============================================================================


class TestParseLinearIssue:
    """Tests for parsing Linear API responses into LinearIssue."""

    def test_parse_minimal_issue(self) -> None:
        """Test parsing issue with minimal data."""
        data = {
            "id": "issue_123",
            "identifier": "TEAM-1",
            "title": "Minimal issue",
        }

        issue = parse_linear_issue(data)

        assert issue.id == "issue_123"
        assert issue.identifier == "TEAM-1"
        assert issue.title == "Minimal issue"
        assert issue.state == "Backlog"
        assert issue.labels == []

    def test_parse_full_issue(self) -> None:
        """Test parsing issue with all fields."""
        data = {
            "id": "issue_456",
            "identifier": "ENG-42",
            "title": "Full issue",
            "description": "Full description\n\nADW: abc12345",
            "priority": 2,
            "url": "https://linear.app/team/issue/ENG-42",
            "createdAt": "2026-01-15T10:30:00Z",
            "updatedAt": "2026-01-16T14:20:00Z",
            "state": {
                "id": "state_xyz",
                "name": "In Progress",
            },
            "team": {
                "id": "team_abc",
                "key": "ENG",
            },
            "assignee": {
                "id": "user_123",
                "name": "Test User",
            },
            "labels": {
                "nodes": [
                    {"name": "bug"},
                    {"name": "urgent"},
                ]
            },
        }

        issue = parse_linear_issue(data)

        assert issue.id == "issue_456"
        assert issue.identifier == "ENG-42"
        assert issue.title == "Full issue"
        assert issue.description == "Full description\n\nADW: abc12345"
        assert issue.state == "In Progress"
        assert issue.state_id == "state_xyz"
        assert issue.priority == 2
        assert issue.url == "https://linear.app/team/issue/ENG-42"
        assert issue.team_id == "team_abc"
        assert issue.assignee_id == "user_123"
        assert issue.labels == ["bug", "urgent"]
        assert issue.adw_id == "abc12345"
        assert issue.created_at is not None
        assert issue.updated_at is not None

    def test_parse_extracts_adw_id_from_description(self) -> None:
        """Test ADW ID extraction from description."""
        data = {
            "id": "1",
            "identifier": "T-1",
            "title": "Test",
            "description": "Some description\n\n---\nADW: deadbeef",
        }

        issue = parse_linear_issue(data)
        assert issue.adw_id == "deadbeef"

    def test_parse_handles_missing_nested_fields(self) -> None:
        """Test parsing handles null nested objects."""
        data = {
            "id": "1",
            "identifier": "T-1",
            "title": "Test",
            "state": None,
            "team": None,
            "assignee": None,
            "labels": None,
        }

        issue = parse_linear_issue(data)

        assert issue.state == "Backlog"
        assert issue.team_id == ""
        assert issue.assignee_id is None
        assert issue.labels == []

    def test_parse_handles_empty_labels(self) -> None:
        """Test parsing with empty labels array."""
        data = {
            "id": "1",
            "identifier": "T-1",
            "title": "Test",
            "labels": {"nodes": []},
        }

        issue = parse_linear_issue(data)
        assert issue.labels == []


# =============================================================================
# LinearClient Tests
# =============================================================================


class TestLinearClient:
    """Tests for LinearClient GraphQL operations."""

    def test_client_initialization(self) -> None:
        """Test client initializes with API key."""
        client = LinearClient("lin_api_test")

        assert client.api_key == "lin_api_test"
        assert client.API_URL == "https://api.linear.app/graphql"
        assert client._rate_limit_reset == 0

    @patch("urllib.request.urlopen")
    def test_get_viewer_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful viewer query."""
        response_data = {
            "data": {
                "viewer": {
                    "id": "user_123",
                    "name": "Test User",
                    "email": "test@example.com",
                }
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("lin_api_test")
        viewer = client.get_viewer()

        assert viewer is not None
        assert viewer["id"] == "user_123"
        assert viewer["name"] == "Test User"

    @patch("urllib.request.urlopen")
    def test_get_teams_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful teams query."""
        response_data = {
            "data": {
                "teams": {
                    "nodes": [
                        {"id": "team_1", "key": "ENG", "name": "Engineering"},
                        {"id": "team_2", "key": "DES", "name": "Design"},
                    ]
                }
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("lin_api_test")
        teams = client.get_teams()

        assert len(teams) == 2
        assert teams[0]["key"] == "ENG"
        assert teams[1]["key"] == "DES"
        # Check caching
        assert client._team_cache["team_1"] == "ENG"
        assert client._team_cache["team_2"] == "DES"

    @patch("urllib.request.urlopen")
    def test_get_team_states(self, mock_urlopen: MagicMock) -> None:
        """Test fetching workflow states for a team."""
        response_data = {
            "data": {
                "team": {
                    "states": {
                        "nodes": [
                            {"id": "state_1", "name": "Backlog", "type": "backlog", "position": 0},
                            {"id": "state_2", "name": "In Progress", "type": "started", "position": 1},
                            {"id": "state_3", "name": "Done", "type": "completed", "position": 2},
                        ]
                    }
                }
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("lin_api_test")
        states = client.get_team_states("team_1")

        assert len(states) == 3
        assert states[0]["name"] == "Backlog"
        # Check caching
        assert client._state_cache["team_1"]["backlog"] == "state_1"
        assert client._state_cache["team_1"]["in progress"] == "state_2"
        assert client._state_cache["team_1"]["done"] == "state_3"

    @patch("urllib.request.urlopen")
    def test_find_state_id(self, mock_urlopen: MagicMock) -> None:
        """Test finding state ID by name."""
        response_data = {
            "data": {
                "team": {
                    "states": {
                        "nodes": [
                            {"id": "state_progress", "name": "In Progress", "type": "started", "position": 1},
                        ]
                    }
                }
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("lin_api_test")

        # First call fetches and caches
        state_id = client.find_state_id("team_1", "In Progress")
        assert state_id == "state_progress"

        # Second call uses cache (no new request)
        mock_urlopen.reset_mock()
        state_id = client.find_state_id("team_1", "in progress")
        assert state_id == "state_progress"

    @patch("urllib.request.urlopen")
    def test_update_issue(self, mock_urlopen: MagicMock) -> None:
        """Test updating an issue."""
        response_data = {
            "data": {
                "issueUpdate": {
                    "success": True
                }
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("lin_api_test")
        success = client.update_issue("issue_1", state_id="state_progress")

        assert success is True

    @patch("urllib.request.urlopen")
    def test_add_comment(self, mock_urlopen: MagicMock) -> None:
        """Test adding a comment to an issue."""
        response_data = {
            "data": {
                "commentCreate": {
                    "success": True
                }
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("lin_api_test")
        success = client.add_comment("issue_1", "Test comment")

        assert success is True

    @patch("urllib.request.urlopen")
    def test_handles_graphql_errors(self, mock_urlopen: MagicMock) -> None:
        """Test handling GraphQL errors in response."""
        response_data = {
            "errors": [
                {"message": "Authentication required"}
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = LinearClient("invalid_key")
        viewer = client.get_viewer()

        assert viewer is None

    @patch("urllib.request.urlopen")
    def test_handles_http_error(self, mock_urlopen: MagicMock) -> None:
        """Test handling HTTP errors."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.linear.app/graphql",
            401,
            "Unauthorized",
            {},
            None,
        )

        client = LinearClient("invalid_key")
        viewer = client.get_viewer()

        assert viewer is None


# =============================================================================
# LinearWatcher Tests
# =============================================================================


class TestLinearWatcher:
    """Tests for LinearWatcher polling and processing."""

    def test_watcher_initialization(self) -> None:
        """Test watcher initializes correctly."""
        config = LinearConfig(api_key="lin_api_test", team_id="team_123")
        watcher = LinearWatcher(config)

        assert watcher.config == config
        assert watcher._team_id == "team_123"
        assert len(watcher._processed_ids) == 0

    @patch.object(LinearClient, "get_teams")
    def test_ensure_team_id_auto_detect(self, mock_get_teams: MagicMock) -> None:
        """Test auto-detection of team ID."""
        mock_get_teams.return_value = [
            {"id": "auto_team", "key": "AUTO", "name": "Auto Team"}
        ]

        config = LinearConfig(api_key="lin_api_test")  # No team_id
        watcher = LinearWatcher(config)

        team_id = watcher._ensure_team_id()

        assert team_id == "auto_team"
        assert watcher._team_id == "auto_team"

    @patch.object(LinearClient, "get_teams")
    def test_ensure_team_id_no_teams(self, mock_get_teams: MagicMock) -> None:
        """Test handling when no teams found."""
        mock_get_teams.return_value = []

        config = LinearConfig(api_key="lin_api_test")
        watcher = LinearWatcher(config)

        team_id = watcher._ensure_team_id()

        assert team_id is None

    @patch.object(LinearClient, "get_issues")
    @patch.object(LinearWatcher, "_ensure_team_id")
    def test_get_pending_issues(
        self, mock_ensure_team: MagicMock, mock_get_issues: MagicMock
    ) -> None:
        """Test fetching pending issues."""
        mock_ensure_team.return_value = "team_123"
        mock_get_issues.return_value = [
            {
                "id": "issue_1",
                "identifier": "T-1",
                "title": "Issue 1",
                "state": {"id": "s1", "name": "Backlog"},
                "team": {"id": "team_123", "key": "T"},
                "labels": {"nodes": []},
            },
            {
                "id": "issue_2",
                "identifier": "T-2",
                "title": "Issue 2",
                "description": "ADW: deadbeef",  # Already has ADW ID (8 hex chars)
                "state": {"id": "s1", "name": "Backlog"},
                "team": {"id": "team_123", "key": "T"},
                "labels": {"nodes": []},
            },
        ]

        config = LinearConfig(api_key="lin_api_test", team_id="team_123")
        watcher = LinearWatcher(config)

        issues = watcher.get_pending_issues()

        # Should only return issue without ADW ID
        assert len(issues) == 1
        assert issues[0].identifier == "T-1"

    @patch.object(LinearClient, "get_issues")
    @patch.object(LinearWatcher, "_ensure_team_id")
    def test_get_pending_issues_skips_processed(
        self, mock_ensure_team: MagicMock, mock_get_issues: MagicMock
    ) -> None:
        """Test that already processed issues are skipped."""
        mock_ensure_team.return_value = "team_123"
        mock_get_issues.return_value = [
            {
                "id": "issue_1",
                "identifier": "T-1",
                "title": "Issue 1",
                "state": {"id": "s1", "name": "Backlog"},
                "team": {"id": "team_123", "key": "T"},
                "labels": {"nodes": []},
            },
        ]

        config = LinearConfig(api_key="lin_api_test", team_id="team_123")
        watcher = LinearWatcher(config)

        # Mark as processed
        watcher._processed_ids.add("issue_1")

        issues = watcher.get_pending_issues()

        assert len(issues) == 0

    @patch.object(LinearClient, "add_comment")
    @patch.object(LinearClient, "update_issue")
    @patch.object(LinearClient, "find_state_id")
    def test_mark_issue_started(
        self,
        mock_find_state: MagicMock,
        mock_update: MagicMock,
        mock_comment: MagicMock,
    ) -> None:
        """Test marking an issue as started."""
        mock_find_state.return_value = "state_progress"
        mock_update.return_value = True
        mock_comment.return_value = True

        config = LinearConfig(api_key="lin_api_test", team_id="team_123")
        watcher = LinearWatcher(config)

        issue = LinearIssue(
            id="issue_1",
            identifier="T-1",
            title="Test",
            team_id="team_123",
        )

        success = watcher.mark_issue_started(issue, "abc12345")

        assert success is True
        assert "issue_1" in watcher._processed_ids
        mock_update.assert_called_once()
        mock_comment.assert_called_once()

    @patch.object(LinearClient, "add_comment")
    @patch.object(LinearClient, "update_issue")
    @patch.object(LinearClient, "find_state_id")
    def test_mark_issue_completed(
        self,
        mock_find_state: MagicMock,
        mock_update: MagicMock,
        mock_comment: MagicMock,
    ) -> None:
        """Test marking an issue as completed."""
        mock_find_state.return_value = "state_done"
        mock_update.return_value = True
        mock_comment.return_value = True

        config = LinearConfig(api_key="lin_api_test", team_id="team_123")
        watcher = LinearWatcher(config)

        issue = LinearIssue(
            id="issue_1",
            identifier="T-1",
            title="Test",
            team_id="team_123",
        )

        success = watcher.mark_issue_completed(issue)

        assert success is True
        mock_find_state.assert_called()
        mock_update.assert_called()

    @patch.object(LinearClient, "add_comment")
    @patch.object(LinearClient, "update_issue")
    @patch.object(LinearClient, "find_state_id")
    def test_mark_issue_failed(
        self,
        mock_find_state: MagicMock,
        mock_update: MagicMock,
        mock_comment: MagicMock,
    ) -> None:
        """Test marking an issue as failed."""
        mock_find_state.return_value = "state_canceled"
        mock_update.return_value = True
        mock_comment.return_value = True

        config = LinearConfig(api_key="lin_api_test", team_id="team_123")
        watcher = LinearWatcher(config)

        issue = LinearIssue(
            id="issue_1",
            identifier="T-1",
            title="Test",
            team_id="team_123",
        )

        success = watcher.mark_issue_failed(issue, "Test error message")

        assert success is True
        # Should include error in comment
        mock_comment.assert_called_once()
        call_args = mock_comment.call_args
        assert "Test error message" in call_args[0][1]


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_simple_toml_basic(self) -> None:
        """Test simple TOML parsing."""
        toml_content = """
[linear]
api_key = "test_key"
team_id = "team_123"
poll_interval = 120
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                result = _parse_simple_toml(Path(f.name))

                assert "linear" in result
                assert result["linear"]["api_key"] == "test_key"
                assert result["linear"]["team_id"] == "team_123"
                assert result["linear"]["poll_interval"] == 120
            finally:
                os.unlink(f.name)

    def test_parse_simple_toml_list_values(self) -> None:
        """Test TOML parsing with list values."""
        toml_content = """
[linear]
api_key = "test_key"
filter_states = ["Backlog", "Todo"]
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                result = _parse_simple_toml(Path(f.name))

                assert result["linear"]["filter_states"] == ["Backlog", "Todo"]
            finally:
                os.unlink(f.name)

    def test_parse_simple_toml_comments(self) -> None:
        """Test TOML parsing ignores comments."""
        toml_content = """
# This is a comment
[linear]
# Another comment
api_key = "test_key"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                result = _parse_simple_toml(Path(f.name))

                assert result["linear"]["api_key"] == "test_key"
            finally:
                os.unlink(f.name)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests with mocked external services."""

    @patch.object(LinearClient, "get_viewer")
    @patch.object(LinearClient, "get_teams")
    def test_test_linear_connection_success(
        self, mock_get_teams: MagicMock, mock_get_viewer: MagicMock
    ) -> None:
        """Test successful connection test."""
        from adw.integrations.linear import test_linear_connection

        mock_get_viewer.return_value = {
            "id": "user_1",
            "name": "Test User",
            "email": "test@example.com",
        }
        mock_get_teams.return_value = [
            {"id": "team_1", "key": "ENG", "name": "Engineering"}
        ]

        config = LinearConfig(api_key="lin_api_test")
        success = test_linear_connection(config)

        assert success is True

    @patch.object(LinearClient, "get_viewer")
    def test_test_linear_connection_failure(
        self, mock_get_viewer: MagicMock
    ) -> None:
        """Test failed connection test."""
        from adw.integrations.linear import test_linear_connection

        mock_get_viewer.return_value = None

        config = LinearConfig(api_key="invalid_key")
        success = test_linear_connection(config)

        assert success is False
