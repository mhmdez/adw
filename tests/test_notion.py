"""Tests for Notion integration.

Tests cover:
- NotionConfig creation and loading
- NotionTask dataclass
- Property parsing from Notion API responses
- Status mapping between Notion and ADW
- NotionWatcher filter building
- NotionClient request building (mocked)
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from adw.integrations.notion import (
    ADW_TO_NOTION_STATUS,
    NOTION_TO_ADW_STATUS,
    NotionClient,
    NotionConfig,
    NotionTask,
    NotionWatcher,
    _extract_text_from_property,
    _parse_simple_toml,
    build_adw_id_property,
    build_status_property,
    parse_notion_page,
)

# =============================================================================
# Status Mapping Tests
# =============================================================================


class TestStatusMapping:
    """Tests for Notion <-> ADW status mappings."""

    def test_notion_to_adw_status_mapping(self) -> None:
        """Test mapping from Notion status to ADW status."""
        # Pending states
        assert NOTION_TO_ADW_STATUS["not started"] == "pending"
        assert NOTION_TO_ADW_STATUS["todo"] == "pending"
        assert NOTION_TO_ADW_STATUS["to do"] == "pending"
        assert NOTION_TO_ADW_STATUS["backlog"] == "pending"

        # In progress states
        assert NOTION_TO_ADW_STATUS["in progress"] == "in_progress"
        assert NOTION_TO_ADW_STATUS["doing"] == "in_progress"
        assert NOTION_TO_ADW_STATUS["working"] == "in_progress"

        # Completed states
        assert NOTION_TO_ADW_STATUS["done"] == "completed"
        assert NOTION_TO_ADW_STATUS["complete"] == "completed"
        assert NOTION_TO_ADW_STATUS["completed"] == "completed"

        # Failed states
        assert NOTION_TO_ADW_STATUS["canceled"] == "failed"
        assert NOTION_TO_ADW_STATUS["cancelled"] == "failed"

    def test_adw_to_notion_status_mapping(self) -> None:
        """Test mapping from ADW status to Notion status."""
        assert ADW_TO_NOTION_STATUS["pending"] == "To Do"
        assert ADW_TO_NOTION_STATUS["in_progress"] == "In Progress"
        assert ADW_TO_NOTION_STATUS["completed"] == "Done"
        assert ADW_TO_NOTION_STATUS["failed"] == "Canceled"


# =============================================================================
# NotionConfig Tests
# =============================================================================


class TestNotionConfig:
    """Tests for NotionConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = NotionConfig(
            api_key="secret_test",
            database_id="db123",
        )

        assert config.api_key == "secret_test"
        assert config.database_id == "db123"
        assert config.poll_interval == 60
        assert config.status_property == "Status"
        assert config.title_property == "Name"
        assert config.workflow_property == "Workflow"
        assert config.model_property == "Model"
        assert config.priority_property == "Priority"
        assert config.adw_id_property == "ADW ID"
        assert config.filter_status == ["To Do", "Not Started"]

    def test_custom_values(self) -> None:
        """Test config with custom values."""
        config = NotionConfig(
            api_key="secret_test",
            database_id="db123",
            poll_interval=120,
            status_property="Task Status",
            filter_status=["Ready", "Waiting"],
        )

        assert config.poll_interval == 120
        assert config.status_property == "Task Status"
        assert config.filter_status == ["Ready", "Waiting"]

    def test_from_env_missing_vars(self) -> None:
        """Test loading from env with missing variables."""
        # Clear any existing vars
        with patch.dict(os.environ, {}, clear=True):
            config = NotionConfig.from_env()
            assert config is None

    def test_from_env_with_vars(self) -> None:
        """Test loading from environment variables."""
        env = {
            "NOTION_API_KEY": "secret_from_env",
            "NOTION_DATABASE_ID": "db_from_env",
            "NOTION_POLL_INTERVAL": "180",
        }
        with patch.dict(os.environ, env, clear=True):
            config = NotionConfig.from_env()

            assert config is not None
            assert config.api_key == "secret_from_env"
            assert config.database_id == "db_from_env"
            assert config.poll_interval == 180

    def test_from_config_file_not_exists(self) -> None:
        """Test loading from non-existent config file."""
        config = NotionConfig.from_config_file(Path("/nonexistent/path/config.toml"))
        assert config is None

    def test_to_dict(self) -> None:
        """Test converting config to dictionary."""
        config = NotionConfig(
            api_key="secret_test",
            database_id="db123",
        )
        data = config.to_dict()

        assert "database_id" in data
        assert data["database_id"] == "db123"
        assert data["poll_interval"] == 60
        # API key should not be in serialization
        assert "api_key" not in data

    def test_load_prefers_env(self) -> None:
        """Test that load() prefers environment over config file."""
        env = {
            "NOTION_API_KEY": "secret_from_env",
            "NOTION_DATABASE_ID": "db_from_env",
        }
        with patch.dict(os.environ, env, clear=True):
            config = NotionConfig.load()

            assert config is not None
            assert config.api_key == "secret_from_env"


# =============================================================================
# NotionTask Tests
# =============================================================================


class TestNotionTask:
    """Tests for NotionTask dataclass."""

    def test_default_values(self) -> None:
        """Test default task values."""
        task = NotionTask(
            page_id="page123",
            title="Test task",
        )

        assert task.page_id == "page123"
        assert task.title == "Test task"
        assert task.status == "pending"
        assert task.workflow is None
        assert task.model is None
        assert task.priority is None
        assert task.adw_id is None

    def test_to_dict(self) -> None:
        """Test converting task to dictionary."""
        now = datetime.now()
        task = NotionTask(
            page_id="page123",
            title="Test task",
            status="in_progress",
            workflow="sdlc",
            model="opus",
            priority="p1",
            adw_id="abc12345",
            created_time=now,
        )
        data = task.to_dict()

        assert data["page_id"] == "page123"
        assert data["title"] == "Test task"
        assert data["status"] == "in_progress"
        assert data["workflow"] == "sdlc"
        assert data["model"] == "opus"
        assert data["priority"] == "p1"
        assert data["adw_id"] == "abc12345"
        assert data["created_time"] == now.isoformat()

    def test_from_dict(self) -> None:
        """Test creating task from dictionary."""
        data = {
            "page_id": "page456",
            "title": "From dict task",
            "status": "completed",
            "workflow": "standard",
            "model": "sonnet",
            "created_time": "2026-01-15T10:30:00+00:00",
        }
        task = NotionTask.from_dict(data)

        assert task.page_id == "page456"
        assert task.title == "From dict task"
        assert task.status == "completed"
        assert task.workflow == "standard"
        assert task.model == "sonnet"
        assert task.created_time is not None

    def test_get_workflow_or_default_explicit(self) -> None:
        """Test getting explicitly set workflow."""
        task = NotionTask(page_id="p1", title="t1", workflow="sdlc")
        assert task.get_workflow_or_default() == "sdlc"

    def test_get_workflow_or_default_from_priority(self) -> None:
        """Test deriving workflow - defaults to adaptive for auto-detection."""
        # All priorities default to adaptive now (auto-detects complexity)
        task = NotionTask(page_id="p1", title="t1", priority="p0")
        assert task.get_workflow_or_default() == "adaptive"

        task = NotionTask(page_id="p1", title="t1", priority="p1")
        assert task.get_workflow_or_default() == "adaptive"

        # Normal priority -> adaptive
        task = NotionTask(page_id="p1", title="t1", priority="p2")
        assert task.get_workflow_or_default() == "adaptive"

    def test_get_model_or_default_explicit(self) -> None:
        """Test getting explicitly set model."""
        task = NotionTask(page_id="p1", title="t1", model="opus")
        assert task.get_model_or_default() == "opus"

    def test_get_model_or_default_from_priority(self) -> None:
        """Test deriving model from priority."""
        # P0 -> opus
        task = NotionTask(page_id="p1", title="t1", priority="p0")
        assert task.get_model_or_default() == "opus"

        # Normal -> sonnet
        task = NotionTask(page_id="p1", title="t1", priority="p2")
        assert task.get_model_or_default() == "sonnet"


# =============================================================================
# Property Parsing Tests
# =============================================================================


class TestPropertyParsing:
    """Tests for Notion property extraction."""

    def test_extract_text_from_title(self) -> None:
        """Test extracting text from title property."""
        prop = {
            "type": "title",
            "title": [
                {"plain_text": "Hello "},
                {"plain_text": "World"},
            ],
        }
        assert _extract_text_from_property(prop) == "Hello World"

    def test_extract_text_from_rich_text(self) -> None:
        """Test extracting text from rich_text property."""
        prop = {
            "type": "rich_text",
            "rich_text": [
                {"plain_text": "Some text"},
            ],
        }
        assert _extract_text_from_property(prop) == "Some text"

    def test_extract_text_from_select(self) -> None:
        """Test extracting text from select property."""
        prop = {
            "type": "select",
            "select": {"name": "Option A"},
        }
        assert _extract_text_from_property(prop) == "Option A"

        # Null select
        prop = {
            "type": "select",
            "select": None,
        }
        assert _extract_text_from_property(prop) == ""

    def test_extract_text_from_multi_select(self) -> None:
        """Test extracting text from multi_select property."""
        prop = {
            "type": "multi_select",
            "multi_select": [
                {"name": "Tag1"},
                {"name": "Tag2"},
            ],
        }
        assert _extract_text_from_property(prop) == "Tag1, Tag2"

    def test_extract_text_from_status(self) -> None:
        """Test extracting text from status property."""
        prop = {
            "type": "status",
            "status": {"name": "In Progress"},
        }
        assert _extract_text_from_property(prop) == "In Progress"

    def test_extract_text_from_number(self) -> None:
        """Test extracting text from number property."""
        prop = {
            "type": "number",
            "number": 42,
        }
        assert _extract_text_from_property(prop) == "42"

    def test_extract_text_from_checkbox(self) -> None:
        """Test extracting text from checkbox property."""
        prop = {"type": "checkbox", "checkbox": True}
        assert _extract_text_from_property(prop) == "true"

        prop = {"type": "checkbox", "checkbox": False}
        assert _extract_text_from_property(prop) == "false"

    def test_extract_text_from_date(self) -> None:
        """Test extracting text from date property."""
        prop = {
            "type": "date",
            "date": {"start": "2026-01-15"},
        }
        assert _extract_text_from_property(prop) == "2026-01-15"

    def test_extract_text_from_url(self) -> None:
        """Test extracting text from URL property."""
        prop = {
            "type": "url",
            "url": "https://example.com",
        }
        assert _extract_text_from_property(prop) == "https://example.com"

    def test_extract_text_unknown_type(self) -> None:
        """Test extracting text from unknown property type."""
        prop = {
            "type": "unknown_type",
            "data": "something",
        }
        assert _extract_text_from_property(prop) == ""


class TestParseNotionPage:
    """Tests for parsing full Notion page objects."""

    def test_parse_minimal_page(self) -> None:
        """Test parsing a minimal page."""
        page = {
            "id": "page123",
            "url": "https://notion.so/page123",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Task"}],
                },
                "Status": {
                    "type": "status",
                    "status": {"name": "To Do"},
                },
            },
        }
        config = NotionConfig(api_key="test", database_id="db")

        task = parse_notion_page(page, config)

        assert task.page_id == "page123"
        assert task.title == "Test Task"
        assert task.status == "pending"  # "to do" maps to pending
        assert task.url == "https://notion.so/page123"

    def test_parse_page_with_workflow(self) -> None:
        """Test parsing a page with workflow property."""
        page = {
            "id": "page456",
            "url": "",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Feature Task"}],
                },
                "Status": {
                    "type": "status",
                    "status": {"name": "In Progress"},
                },
                "Workflow": {
                    "type": "select",
                    "select": {"name": "SDLC"},
                },
                "Model": {
                    "type": "select",
                    "select": {"name": "Opus"},
                },
                "Priority": {
                    "type": "select",
                    "select": {"name": "P0"},
                },
            },
        }
        config = NotionConfig(api_key="test", database_id="db")

        task = parse_notion_page(page, config)

        assert task.status == "in_progress"
        assert task.workflow == "sdlc"
        assert task.model == "opus"
        assert task.priority == "p0"

    def test_parse_page_with_adw_id(self) -> None:
        """Test parsing a page that already has an ADW ID."""
        page = {
            "id": "page789",
            "url": "",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "In Progress Task"}],
                },
                "Status": {
                    "type": "status",
                    "status": {"name": "Done"},
                },
                "ADW ID": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "abc12345"}],
                },
            },
        }
        config = NotionConfig(api_key="test", database_id="db")

        task = parse_notion_page(page, config)

        assert task.adw_id == "abc12345"
        assert task.status == "completed"

    def test_parse_page_with_timestamps(self) -> None:
        """Test parsing page timestamps."""
        page = {
            "id": "page_time",
            "url": "",
            "created_time": "2026-01-15T10:30:00.000Z",
            "last_edited_time": "2026-01-16T14:45:00.000Z",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Timed Task"}],
                },
                "Status": {
                    "type": "status",
                    "status": {"name": "To Do"},
                },
            },
        }
        config = NotionConfig(api_key="test", database_id="db")

        task = parse_notion_page(page, config)

        assert task.created_time is not None
        assert task.last_edited_time is not None
        assert task.created_time.year == 2026

    def test_parse_page_priority_mapping(self) -> None:
        """Test priority text to p-level mapping."""
        page = {
            "id": "page_priority",
            "url": "",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Priority Task"}],
                },
                "Status": {
                    "type": "status",
                    "status": {"name": "To Do"},
                },
                "Priority": {
                    "type": "select",
                    "select": {"name": "Critical"},
                },
            },
        }
        config = NotionConfig(api_key="test", database_id="db")

        task = parse_notion_page(page, config)

        # "Critical" should map to "p0"
        assert task.priority == "p0"


# =============================================================================
# Property Building Tests
# =============================================================================


class TestPropertyBuilding:
    """Tests for building Notion property updates."""

    def test_build_status_property(self) -> None:
        """Test building status update property."""
        config = NotionConfig(api_key="test", database_id="db")

        prop = build_status_property("in_progress", config)
        assert prop == {"status": {"name": "In Progress"}}

        prop = build_status_property("completed", config)
        assert prop == {"status": {"name": "Done"}}

        prop = build_status_property("failed", config)
        assert prop == {"status": {"name": "Canceled"}}

    def test_build_adw_id_property(self) -> None:
        """Test building ADW ID update property."""
        prop = build_adw_id_property("abc12345")

        assert prop == {
            "rich_text": [{"text": {"content": "abc12345"}}],
        }


# =============================================================================
# NotionWatcher Tests
# =============================================================================


class TestNotionWatcher:
    """Tests for NotionWatcher class."""

    def test_build_filter_single_status(self) -> None:
        """Test building filter with single status."""
        config = NotionConfig(
            api_key="test",
            database_id="db",
            filter_status=["To Do"],
        )
        watcher = NotionWatcher(config)

        filter_obj = watcher.build_filter()

        assert filter_obj == {
            "property": "Status",
            "status": {"equals": "To Do"},
        }

    def test_build_filter_multiple_status(self) -> None:
        """Test building filter with multiple statuses."""
        config = NotionConfig(
            api_key="test",
            database_id="db",
            filter_status=["To Do", "Not Started"],
        )
        watcher = NotionWatcher(config)

        filter_obj = watcher.build_filter()

        assert filter_obj is not None
        assert "or" in filter_obj
        assert len(filter_obj["or"]) == 2

    def test_build_filter_no_status(self) -> None:
        """Test building filter with no status filter."""
        config = NotionConfig(
            api_key="test",
            database_id="db",
            filter_status=[],
        )
        watcher = NotionWatcher(config)

        filter_obj = watcher.build_filter()

        assert filter_obj is None


# =============================================================================
# NotionClient Tests
# =============================================================================


class TestNotionClient:
    """Tests for NotionClient class."""

    def test_client_initialization(self) -> None:
        """Test client initializes with API key."""
        client = NotionClient("secret_test_key")

        assert client.api_key == "secret_test_key"
        assert client.BASE_URL == "https://api.notion.com/v1"
        assert client.API_VERSION == "2022-06-28"

    @patch("urllib.request.urlopen")
    def test_query_database_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful database query."""
        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "results": [
                    {"id": "page1", "properties": {}},
                    {"id": "page2", "properties": {}},
                ],
                "has_more": False,
            }
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = NotionClient("secret_test")
        results = client.query_database("db123")

        assert len(results) == 2
        assert results[0]["id"] == "page1"

    @patch("urllib.request.urlopen")
    def test_query_database_with_filter(self, mock_urlopen: MagicMock) -> None:
        """Test database query with filter."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "results": [],
                "has_more": False,
            }
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = NotionClient("secret_test")
        filter_obj = {"property": "Status", "status": {"equals": "To Do"}}
        client.query_database("db123", filter_obj=filter_obj)

        # Verify the request was made with filter in body
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert "filter" in body

    @patch("urllib.request.urlopen")
    def test_update_page_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful page update."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "id": "page123",
                "properties": {"Status": {"status": {"name": "Done"}}},
            }
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = NotionClient("secret_test")
        result = client.update_page("page123", {"Status": {"status": {"name": "Done"}}})

        assert result is not None
        assert result["id"] == "page123"


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_simple_toml(self) -> None:
        """Test simple TOML parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[notion]
api_key = "secret_test"
database_id = "db123"
poll_interval = 120

[other]
setting = "value"
""")
            f.flush()

            config = _parse_simple_toml(Path(f.name))

            assert "notion" in config
            assert config["notion"]["api_key"] == "secret_test"
            assert config["notion"]["database_id"] == "db123"
            assert config["notion"]["poll_interval"] == 120
            assert "other" in config

            os.unlink(f.name)

    def test_parse_simple_toml_with_comments(self) -> None:
        """Test TOML parsing handles comments."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
# This is a comment
[notion]
# Another comment
api_key = "test"
""")
            f.flush()

            config = _parse_simple_toml(Path(f.name))

            assert config["notion"]["api_key"] == "test"

            os.unlink(f.name)


# =============================================================================
# Integration Tests (Mocked)
# =============================================================================


class TestIntegration:
    """Integration tests with mocked API calls."""

    @patch("urllib.request.urlopen")
    def test_get_pending_tasks(self, mock_urlopen: MagicMock) -> None:
        """Test getting pending tasks from watcher."""
        # Mock API response with tasks
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "results": [
                    {
                        "id": "page1",
                        "url": "https://notion.so/page1",
                        "created_time": "2026-01-15T10:00:00.000Z",
                        "last_edited_time": "2026-01-15T10:00:00.000Z",
                        "properties": {
                            "Name": {
                                "type": "title",
                                "title": [{"plain_text": "Task 1"}],
                            },
                            "Status": {
                                "type": "status",
                                "status": {"name": "To Do"},
                            },
                        },
                    },
                    {
                        "id": "page2",
                        "url": "https://notion.so/page2",
                        "created_time": "2026-01-15T11:00:00.000Z",
                        "last_edited_time": "2026-01-15T11:00:00.000Z",
                        "properties": {
                            "Name": {
                                "type": "title",
                                "title": [{"plain_text": "Task 2"}],
                            },
                            "Status": {
                                "type": "status",
                                "status": {"name": "To Do"},
                            },
                            "ADW ID": {
                                "type": "rich_text",
                                "rich_text": [{"plain_text": "abc12345"}],
                            },
                        },
                    },
                ],
                "has_more": False,
            }
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = NotionConfig(api_key="test", database_id="db123")
        watcher = NotionWatcher(config)
        tasks = watcher.get_pending_tasks()

        # Should only return task without ADW ID
        assert len(tasks) == 1
        assert tasks[0].title == "Task 1"

    @patch("urllib.request.urlopen")
    def test_mark_task_started(self, mock_urlopen: MagicMock) -> None:
        """Test marking a task as started."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "id": "page1",
                "properties": {},
            }
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = NotionConfig(api_key="test", database_id="db123")
        watcher = NotionWatcher(config)

        task = NotionTask(page_id="page1", title="Test")
        result = watcher.mark_task_started(task, "newadwid")

        assert result is True
        assert task.page_id in watcher._processed_ids
