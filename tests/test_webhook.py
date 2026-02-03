"""Tests for webhook trigger system.

Tests cover:
- API key generation, verification, and management
- Rate limiting
- Task creation request/response models
- Callback registration
- Webhook logging
- GitHub event handling
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest

from adw.triggers.webhook import (
    APIKey,
    TaskCreateRequest,
    TaskCreateResponse,
    _load_api_keys,
    _load_rate_limits,
    _save_api_keys,
    _save_rate_limits,
    check_rate_limit,
    disable_api_key,
    enable_api_key,
    generate_api_key,
    get_callback_url,
    get_webhook_logs,
    handle_github_event,
    list_api_keys,
    log_webhook_event,
    register_callback,
    revoke_api_key,
    verify_api_key,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_adw_dir(tmp_path: Path) -> Path:
    """Create a temporary .adw directory for tests."""
    adw_dir = tmp_path / ".adw"
    adw_dir.mkdir(parents=True, exist_ok=True)
    return adw_dir


@pytest.fixture
def mock_adw_dir(temp_adw_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock the ADW_DIR constant to use temp directory."""
    import adw.triggers.webhook as webhook_module

    monkeypatch.setattr(webhook_module, "ADW_DIR", temp_adw_dir)
    monkeypatch.setattr(
        webhook_module, "API_KEYS_FILE", temp_adw_dir / "webhook_keys.json"
    )
    monkeypatch.setattr(webhook_module, "WEBHOOK_LOG_FILE", temp_adw_dir / "webhooks.jsonl")
    monkeypatch.setattr(
        webhook_module, "RATE_LIMIT_FILE", temp_adw_dir / "rate_limits.json"
    )
    monkeypatch.setattr(
        webhook_module, "CALLBACKS_FILE", temp_adw_dir / "task_callbacks.json"
    )
    return temp_adw_dir


# =============================================================================
# API Key Tests
# =============================================================================


class TestAPIKey:
    """Tests for APIKey dataclass."""

    def test_api_key_creation(self) -> None:
        """Test creating an APIKey."""
        key = APIKey(
            key_id="abc12345",
            key_hash="hash123",
            name="test-key",
            created_at="2026-02-03T12:00:00",
        )
        assert key.key_id == "abc12345"
        assert key.name == "test-key"
        assert key.enabled is True
        assert key.rate_limit == 100

    def test_api_key_to_dict(self) -> None:
        """Test converting APIKey to dictionary."""
        key = APIKey(
            key_id="abc12345",
            key_hash="hash123",
            name="test-key",
            created_at="2026-02-03T12:00:00",
        )
        data = key.to_dict()
        assert data["key_id"] == "abc12345"
        assert data["name"] == "test-key"
        assert "key_hash" in data

    def test_api_key_from_dict(self) -> None:
        """Test creating APIKey from dictionary."""
        data = {
            "key_id": "abc12345",
            "key_hash": "hash123",
            "name": "test-key",
            "created_at": "2026-02-03T12:00:00",
            "expires_at": None,
            "rate_limit": 100,
            "enabled": True,
            "last_used": None,
        }
        key = APIKey.from_dict(data)
        assert key.key_id == "abc12345"
        assert key.name == "test-key"

    def test_api_key_is_expired_not_expired(self) -> None:
        """Test that key without expiration is not expired."""
        key = APIKey(
            key_id="abc12345",
            key_hash="hash123",
            name="test-key",
            created_at="2026-02-03T12:00:00",
            expires_at=None,
        )
        assert key.is_expired() is False

    def test_api_key_is_expired_future(self) -> None:
        """Test that key with future expiration is not expired."""
        future = (datetime.now() + timedelta(days=30)).isoformat()
        key = APIKey(
            key_id="abc12345",
            key_hash="hash123",
            name="test-key",
            created_at="2026-02-03T12:00:00",
            expires_at=future,
        )
        assert key.is_expired() is False

    def test_api_key_is_expired_past(self) -> None:
        """Test that key with past expiration is expired."""
        past = (datetime.now() - timedelta(days=1)).isoformat()
        key = APIKey(
            key_id="abc12345",
            key_hash="hash123",
            name="test-key",
            created_at="2026-02-03T12:00:00",
            expires_at=past,
        )
        assert key.is_expired() is True


class TestAPIKeyManagement:
    """Tests for API key management functions."""

    def test_generate_api_key(self, mock_adw_dir: Path) -> None:
        """Test generating a new API key."""
        raw_key, api_key = generate_api_key("test-key")

        assert raw_key is not None
        assert len(raw_key) > 20  # Should be a secure token
        assert api_key.name == "test-key"
        assert api_key.enabled is True
        assert api_key.rate_limit == 100

        # Verify key was saved
        keys = list_api_keys()
        assert len(keys) == 1
        assert keys[0].key_id == api_key.key_id

    def test_generate_api_key_with_rate_limit(self, mock_adw_dir: Path) -> None:
        """Test generating key with custom rate limit."""
        raw_key, api_key = generate_api_key("high-rate", rate_limit=1000)
        assert api_key.rate_limit == 1000

    def test_generate_api_key_with_expiration(self, mock_adw_dir: Path) -> None:
        """Test generating key with expiration."""
        raw_key, api_key = generate_api_key("temp-key", expires_days=30)
        assert api_key.expires_at is not None
        assert api_key.is_expired() is False

    def test_verify_api_key_valid(self, mock_adw_dir: Path) -> None:
        """Test verifying a valid API key."""
        raw_key, api_key = generate_api_key("test-key")

        verified = verify_api_key(raw_key)
        assert verified is not None
        assert verified.key_id == api_key.key_id

    def test_verify_api_key_invalid(self, mock_adw_dir: Path) -> None:
        """Test verifying an invalid API key."""
        generate_api_key("test-key")

        verified = verify_api_key("invalid-key")
        assert verified is None

    def test_verify_api_key_disabled(self, mock_adw_dir: Path) -> None:
        """Test that disabled keys fail verification."""
        raw_key, api_key = generate_api_key("test-key")
        disable_api_key(api_key.key_id)

        verified = verify_api_key(raw_key)
        assert verified is None

    def test_verify_api_key_expired(self, mock_adw_dir: Path) -> None:
        """Test that expired keys fail verification."""
        raw_key, api_key = generate_api_key("test-key", expires_days=0)

        # Manually expire the key
        keys = _load_api_keys()
        keys[api_key.key_id].expires_at = (
            datetime.now() - timedelta(days=1)
        ).isoformat()
        _save_api_keys(keys)

        verified = verify_api_key(raw_key)
        assert verified is None

    def test_list_api_keys_empty(self, mock_adw_dir: Path) -> None:
        """Test listing keys when none exist."""
        keys = list_api_keys()
        assert keys == []

    def test_list_api_keys_multiple(self, mock_adw_dir: Path) -> None:
        """Test listing multiple keys."""
        generate_api_key("key1")
        generate_api_key("key2")
        generate_api_key("key3")

        keys = list_api_keys()
        assert len(keys) == 3

    def test_revoke_api_key(self, mock_adw_dir: Path) -> None:
        """Test revoking an API key."""
        raw_key, api_key = generate_api_key("test-key")

        assert revoke_api_key(api_key.key_id) is True
        assert len(list_api_keys()) == 0

    def test_revoke_api_key_not_found(self, mock_adw_dir: Path) -> None:
        """Test revoking non-existent key."""
        assert revoke_api_key("notexist") is False

    def test_disable_enable_api_key(self, mock_adw_dir: Path) -> None:
        """Test disabling and re-enabling a key."""
        raw_key, api_key = generate_api_key("test-key")

        # Disable
        assert disable_api_key(api_key.key_id) is True
        keys = list_api_keys()
        assert keys[0].enabled is False

        # Enable
        assert enable_api_key(api_key.key_id) is True
        keys = list_api_keys()
        assert keys[0].enabled is True

    def test_disable_api_key_not_found(self, mock_adw_dir: Path) -> None:
        """Test disabling non-existent key."""
        assert disable_api_key("notexist") is False

    def test_enable_api_key_not_found(self, mock_adw_dir: Path) -> None:
        """Test enabling non-existent key."""
        assert enable_api_key("notexist") is False


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_check_rate_limit_first_request(self, mock_adw_dir: Path) -> None:
        """Test first request within limit."""
        raw_key, api_key = generate_api_key("test-key", rate_limit=100)

        allowed, remaining = check_rate_limit(api_key)
        assert allowed is True
        assert remaining == 99

    def test_check_rate_limit_multiple_requests(self, mock_adw_dir: Path) -> None:
        """Test multiple requests decrement remaining."""
        raw_key, api_key = generate_api_key("test-key", rate_limit=10)

        for i in range(10):
            allowed, remaining = check_rate_limit(api_key)
            assert allowed is True
            assert remaining == 9 - i

    def test_check_rate_limit_exceeded(self, mock_adw_dir: Path) -> None:
        """Test rate limit exceeded."""
        raw_key, api_key = generate_api_key("test-key", rate_limit=3)

        # Use all requests
        for _ in range(3):
            check_rate_limit(api_key)

        # Next request should be denied
        allowed, remaining = check_rate_limit(api_key)
        assert allowed is False
        assert remaining == 0

    def test_check_rate_limit_window_reset(self, mock_adw_dir: Path) -> None:
        """Test rate limit window resets."""

        raw_key, api_key = generate_api_key("test-key", rate_limit=3)

        # Use all requests
        for _ in range(3):
            check_rate_limit(api_key)

        # Simulate window expiration by manipulating the stored entry
        limits = _load_rate_limits()
        limits[api_key.key_id].window_start = time.time() - 4000  # Past window
        _save_rate_limits(limits)

        # Should allow again
        allowed, remaining = check_rate_limit(api_key)
        assert allowed is True


# =============================================================================
# Task Request/Response Tests
# =============================================================================


class TestTaskCreateRequest:
    """Tests for TaskCreateRequest model."""

    def test_from_dict_minimal(self) -> None:
        """Test creating request with minimal data."""
        data = {"description": "Test task"}
        request = TaskCreateRequest.from_dict(data)

        assert request.description == "Test task"
        assert request.workflow == "adaptive"  # Default is now adaptive
        assert request.priority == "p1"
        assert request.model == "sonnet"

    def test_from_dict_full(self) -> None:
        """Test creating request with all fields."""
        data = {
            "description": "Test task",
            "workflow": "sdlc",
            "repo": "myrepo",
            "priority": "p0",
            "tags": ["auth", "security"],
            "callback_url": "https://example.com/callback",
            "model": "opus",
            "worktree_name": "custom-worktree",
        }
        request = TaskCreateRequest.from_dict(data)

        assert request.description == "Test task"
        assert request.workflow == "sdlc"
        assert request.repo == "myrepo"
        assert request.priority == "p0"
        assert request.tags == ["auth", "security"]
        assert request.callback_url == "https://example.com/callback"
        assert request.model == "opus"
        assert request.worktree_name == "custom-worktree"

    def test_validate_valid_request(self) -> None:
        """Test validating a valid request."""
        request = TaskCreateRequest(description="Test task")
        errors = request.validate()
        assert errors == []

    def test_validate_missing_description(self) -> None:
        """Test validation fails without description."""
        request = TaskCreateRequest(description="")
        errors = request.validate()
        assert "description is required" in errors

    def test_validate_invalid_workflow(self) -> None:
        """Test validation fails with invalid workflow (non-identifier)."""
        request = TaskCreateRequest(description="Test", workflow="has spaces!")
        errors = request.validate()
        # Workflow validation now allows any valid identifier or known workflow
        assert any("workflow" in e.lower() for e in errors)

    def test_validate_invalid_priority(self) -> None:
        """Test validation fails with invalid priority."""
        request = TaskCreateRequest(description="Test", priority="p99")
        errors = request.validate()
        assert any("priority must be one of" in e for e in errors)

    def test_validate_invalid_model(self) -> None:
        """Test validation fails with invalid model."""
        request = TaskCreateRequest(description="Test", model="gpt4")
        errors = request.validate()
        assert any("model must be one of" in e for e in errors)

    def test_validate_invalid_callback_url(self) -> None:
        """Test validation fails with invalid callback URL."""
        request = TaskCreateRequest(
            description="Test", callback_url="not-a-url"
        )
        errors = request.validate()
        assert any("callback_url must be a valid" in e for e in errors)

    def test_validate_valid_callback_url(self) -> None:
        """Test validation passes with valid callback URL."""
        request = TaskCreateRequest(
            description="Test", callback_url="https://example.com/callback"
        )
        errors = request.validate()
        assert errors == []


class TestTaskCreateResponse:
    """Tests for TaskCreateResponse model."""

    def test_to_dict(self) -> None:
        """Test converting response to dictionary."""
        response = TaskCreateResponse(
            task_id="abc12345",
            status="pending",
            created_at="2026-02-03T12:00:00",
            workflow="standard",
            callback_registered=True,
        )
        data = response.to_dict()

        assert data["task_id"] == "abc12345"
        assert data["status"] == "pending"
        assert data["workflow"] == "standard"
        assert data["callback_registered"] is True


# =============================================================================
# Callback System Tests
# =============================================================================


class TestCallbackSystem:
    """Tests for callback registration and retrieval."""

    def test_register_callback(self, mock_adw_dir: Path) -> None:
        """Test registering a callback URL."""
        register_callback("task123", "https://example.com/callback")

        url = get_callback_url("task123")
        assert url == "https://example.com/callback"

    def test_get_callback_not_found(self, mock_adw_dir: Path) -> None:
        """Test getting callback for non-existent task."""
        url = get_callback_url("nonexistent")
        assert url is None

    def test_register_multiple_callbacks(self, mock_adw_dir: Path) -> None:
        """Test registering multiple callbacks."""
        register_callback("task1", "https://example.com/callback1")
        register_callback("task2", "https://example.com/callback2")

        assert get_callback_url("task1") == "https://example.com/callback1"
        assert get_callback_url("task2") == "https://example.com/callback2"


# =============================================================================
# Webhook Logging Tests
# =============================================================================


class TestWebhookLogging:
    """Tests for webhook event logging."""

    def test_log_webhook_event(self, mock_adw_dir: Path) -> None:
        """Test logging a webhook event."""
        log_webhook_event(
            event_type="task_created",
            source="/api/tasks",
            key_id="abc123",
            payload={"description": "Test"},
            result={"task_id": "xyz789"},
        )

        logs = get_webhook_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]["event_type"] == "task_created"
        assert logs[0]["key_id"] == "abc123"

    def test_get_webhook_logs_empty(self, mock_adw_dir: Path) -> None:
        """Test getting logs when none exist."""
        logs = get_webhook_logs()
        assert logs == []

    def test_get_webhook_logs_filtered_by_key(self, mock_adw_dir: Path) -> None:
        """Test filtering logs by key ID."""
        log_webhook_event("event1", "/api", "key1", {}, {})
        log_webhook_event("event2", "/api", "key2", {}, {})
        log_webhook_event("event3", "/api", "key1", {}, {})

        logs = get_webhook_logs(key_id="key1")
        assert len(logs) == 2

    def test_get_webhook_logs_filtered_by_event_type(
        self, mock_adw_dir: Path
    ) -> None:
        """Test filtering logs by event type."""
        log_webhook_event("task_created", "/api", "key1", {}, {})
        log_webhook_event("task_error", "/api", "key1", {}, {})
        log_webhook_event("task_created", "/api", "key1", {}, {})

        logs = get_webhook_logs(event_type="task_created")
        assert len(logs) == 2

    def test_get_webhook_logs_limit(self, mock_adw_dir: Path) -> None:
        """Test limiting number of log entries."""
        for i in range(20):
            log_webhook_event(f"event{i}", "/api", "key1", {}, {})

        logs = get_webhook_logs(limit=5)
        assert len(logs) == 5


# =============================================================================
# GitHub Event Handler Tests
# =============================================================================


class TestGitHubEventHandler:
    """Tests for GitHub event handling."""

    def test_handle_issues_labeled_adw(self) -> None:
        """Test handling issue labeled with 'adw'."""
        payload = {
            "action": "labeled",
            "label": {"name": "adw"},
            "issue": {
                "number": 123,
                "title": "Fix bug",
                "body": "Description here",
            },
        }

        with mock.patch(
            "adw.triggers.webhook._trigger_workflow_async"
        ) as mock_trigger:
            result = handle_github_event("issues", payload)

        assert result["status"] == "triggered"
        assert "adw_id" in result
        mock_trigger.assert_called_once()

    def test_handle_issues_labeled_other(self) -> None:
        """Test handling issue labeled with non-adw label."""
        payload = {
            "action": "labeled",
            "label": {"name": "bug"},
            "issue": {"number": 123, "title": "Fix bug"},
        }

        result = handle_github_event("issues", payload)
        assert result["status"] == "ignored"

    def test_handle_issue_comment_adw_command(self) -> None:
        """Test handling comment with adw command."""
        payload = {
            "action": "created",
            "comment": {"body": "adw implement this feature"},
            "issue": {"number": 123, "body": "Issue body"},
        }

        with mock.patch(
            "adw.triggers.webhook._trigger_workflow_async"
        ) as mock_trigger:
            result = handle_github_event("issue_comment", payload)

        assert result["status"] == "triggered"
        mock_trigger.assert_called_once()

    def test_handle_issue_comment_own_comment(self) -> None:
        """Test skipping own comments."""
        payload = {
            "action": "created",
            "comment": {"body": "adw task <!-- ADW: abc123 -->"},
            "issue": {"number": 123, "body": ""},
        }

        result = handle_github_event("issue_comment", payload)
        assert result["status"] == "skipped"
        assert result["reason"] == "own comment"

    def test_handle_issue_comment_normal(self) -> None:
        """Test ignoring normal comments."""
        payload = {
            "action": "created",
            "comment": {"body": "This is a normal comment"},
            "issue": {"number": 123, "body": ""},
        }

        result = handle_github_event("issue_comment", payload)
        assert result["status"] == "ignored"

    def test_handle_unknown_event(self) -> None:
        """Test handling unknown event type."""
        result = handle_github_event("push", {"ref": "refs/heads/main"})
        assert result["status"] == "ignored"


# =============================================================================
# Integration Tests (require FastAPI)
# =============================================================================


class TestWebhookAppIntegration:
    """Integration tests for the FastAPI webhook app."""

    @pytest.fixture
    def app(self, mock_adw_dir: Path):
        """Create test app instance."""
        try:
            from adw.triggers.webhook import create_webhook_app

            return create_webhook_app()
        except ImportError:
            pytest.skip("fastapi not installed")

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        try:
            from fastapi.testclient import TestClient

            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi not installed")

    def test_health_check(self, client) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_endpoint(self, client) -> None:
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data

    def test_create_task_no_auth(self, client) -> None:
        """Test task creation without auth fails."""
        response = client.post(
            "/api/tasks",
            json={"description": "Test task"},
        )
        assert response.status_code == 401

    def test_create_task_invalid_key(self, client, mock_adw_dir: Path) -> None:
        """Test task creation with invalid key fails."""
        response = client.post(
            "/api/tasks",
            json={"description": "Test task"},
            headers={"Authorization": "Bearer invalid-key"},
        )
        assert response.status_code == 401

    def test_create_task_valid_key(self, client, mock_adw_dir: Path) -> None:
        """Test task creation with valid key succeeds."""
        raw_key, _ = generate_api_key("test-key")

        with mock.patch(
            "adw.triggers.webhook._trigger_workflow_async"
        ):
            response = client.post(
                "/api/tasks",
                json={"description": "Test task"},
                headers={"Authorization": f"Bearer {raw_key}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_create_task_validation_error(
        self, client, mock_adw_dir: Path
    ) -> None:
        """Test task creation with invalid data fails."""
        raw_key, _ = generate_api_key("test-key")

        response = client.post(
            "/api/tasks",
            json={"description": "", "workflow": "invalid"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        assert response.status_code == 400

    def test_create_task_rate_limited(
        self, client, mock_adw_dir: Path
    ) -> None:
        """Test rate limiting on task creation."""
        raw_key, _ = generate_api_key("test-key", rate_limit=2)

        with mock.patch(
            "adw.triggers.webhook._trigger_workflow_async"
        ):
            # First two requests should succeed
            for _ in range(2):
                response = client.post(
                    "/api/tasks",
                    json={"description": "Test task"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
                assert response.status_code == 200

            # Third request should be rate limited
            response = client.post(
                "/api/tasks",
                json={"description": "Test task"},
                headers={"Authorization": f"Bearer {raw_key}"},
            )
            assert response.status_code == 429

    def test_github_webhook_valid(self, client) -> None:
        """Test GitHub webhook with valid payload."""
        payload = {
            "action": "labeled",
            "label": {"name": "adw"},
            "issue": {"number": 123, "title": "Test", "body": ""},
        }

        with mock.patch(
            "adw.triggers.webhook._trigger_workflow_async"
        ):
            response = client.post(
                "/gh-webhook",
                json=payload,
                headers={"X-GitHub-Event": "issues"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
