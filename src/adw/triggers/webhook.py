"""Webhook handler for real-time events.

Provides:
1. GitHub webhook endpoint (/gh-webhook) for GitHub events
2. Generic task API endpoint (/api/tasks) for any client
3. API key authentication system
4. Rate limiting per API key
5. Callback URL support for task completion notifications
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Storage paths
ADW_DIR = Path.home() / ".adw"
API_KEYS_FILE = ADW_DIR / "webhook_keys.json"
WEBHOOK_LOG_FILE = ADW_DIR / "webhooks.jsonl"
RATE_LIMIT_FILE = ADW_DIR / "rate_limits.json"

# Rate limiting defaults
DEFAULT_RATE_LIMIT = 100  # requests per hour
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


# =============================================================================
# API Key Management
# =============================================================================


@dataclass
class APIKey:
    """API key for webhook authentication."""

    key_id: str  # Short identifier (first 8 chars of key hash)
    key_hash: str  # SHA-256 hash of the actual key
    name: str  # Human-readable name for the key
    created_at: str  # ISO timestamp
    expires_at: str | None = None  # ISO timestamp, None = never expires
    rate_limit: int = DEFAULT_RATE_LIMIT  # Requests per hour
    enabled: bool = True
    last_used: str | None = None  # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> APIKey:
        """Create from dictionary."""
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()


def _ensure_adw_dir() -> None:
    """Ensure ~/.adw directory exists."""
    ADW_DIR.mkdir(parents=True, exist_ok=True)


def _load_api_keys() -> dict[str, APIKey]:
    """Load API keys from storage.

    Returns:
        Dictionary mapping key_id to APIKey.
    """
    if not API_KEYS_FILE.exists():
        return {}

    try:
        with open(API_KEYS_FILE) as f:
            data = json.load(f)
        return {k: APIKey.from_dict(v) for k, v in data.items()}
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load API keys: {e}")
        return {}


def _save_api_keys(keys: dict[str, APIKey]) -> None:
    """Save API keys to storage."""
    _ensure_adw_dir()
    with open(API_KEYS_FILE, "w") as f:
        json.dump({k: v.to_dict() for k, v in keys.items()}, f, indent=2)


def generate_api_key(
    name: str,
    rate_limit: int = DEFAULT_RATE_LIMIT,
    expires_days: int | None = None,
) -> tuple[str, APIKey]:
    """Generate a new API key.

    Args:
        name: Human-readable name for the key.
        rate_limit: Max requests per hour (default: 100).
        expires_days: Number of days until expiration (None = never).

    Returns:
        Tuple of (raw_key, APIKey). The raw_key is only returned once!
    """
    # Generate secure random key
    raw_key = secrets.token_urlsafe(32)

    # Hash for storage (never store raw key)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = key_hash[:8]

    # Calculate expiration
    expires_at = None
    if expires_days is not None:
        from datetime import timedelta

        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

    api_key = APIKey(
        key_id=key_id,
        key_hash=key_hash,
        name=name,
        created_at=datetime.now().isoformat(),
        expires_at=expires_at,
        rate_limit=rate_limit,
        enabled=True,
    )

    # Save to storage
    keys = _load_api_keys()
    keys[key_id] = api_key
    _save_api_keys(keys)

    return raw_key, api_key


def verify_api_key(raw_key: str) -> APIKey | None:
    """Verify an API key and return the key object if valid.

    Args:
        raw_key: The raw API key to verify.

    Returns:
        APIKey if valid, None if invalid or expired.
    """
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = key_hash[:8]

    keys = _load_api_keys()
    api_key = keys.get(key_id)

    if api_key is None:
        return None

    # Verify hash matches
    if not hmac.compare_digest(api_key.key_hash, key_hash):
        return None

    # Check if enabled
    if not api_key.enabled:
        return None

    # Check expiration
    if api_key.is_expired():
        return None

    # Update last used timestamp
    api_key.last_used = datetime.now().isoformat()
    keys[key_id] = api_key
    _save_api_keys(keys)

    return api_key


def list_api_keys() -> list[APIKey]:
    """List all API keys (without revealing actual keys)."""
    return list(_load_api_keys().values())


def revoke_api_key(key_id: str) -> bool:
    """Revoke an API key by ID.

    Args:
        key_id: The key ID (first 8 chars of key hash).

    Returns:
        True if revoked, False if not found.
    """
    keys = _load_api_keys()
    if key_id not in keys:
        return False

    del keys[key_id]
    _save_api_keys(keys)
    return True


def disable_api_key(key_id: str) -> bool:
    """Disable an API key without deleting it.

    Args:
        key_id: The key ID (first 8 chars of key hash).

    Returns:
        True if disabled, False if not found.
    """
    keys = _load_api_keys()
    if key_id not in keys:
        return False

    keys[key_id].enabled = False
    _save_api_keys(keys)
    return True


def enable_api_key(key_id: str) -> bool:
    """Re-enable a disabled API key.

    Args:
        key_id: The key ID (first 8 chars of key hash).

    Returns:
        True if enabled, False if not found.
    """
    keys = _load_api_keys()
    if key_id not in keys:
        return False

    keys[key_id].enabled = True
    _save_api_keys(keys)
    return True


# =============================================================================
# Rate Limiting
# =============================================================================


@dataclass
class RateLimitEntry:
    """Track rate limit state for a key."""

    key_id: str
    window_start: float  # Unix timestamp
    request_count: int


def _load_rate_limits() -> dict[str, RateLimitEntry]:
    """Load rate limit state from storage."""
    if not RATE_LIMIT_FILE.exists():
        return {}

    try:
        with open(RATE_LIMIT_FILE) as f:
            data = json.load(f)
        return {
            k: RateLimitEntry(**v)
            for k, v in data.items()
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def _save_rate_limits(limits: dict[str, RateLimitEntry]) -> None:
    """Save rate limit state to storage."""
    _ensure_adw_dir()
    with open(RATE_LIMIT_FILE, "w") as f:
        json.dump({k: asdict(v) for k, v in limits.items()}, f)


def check_rate_limit(api_key: APIKey) -> tuple[bool, int]:
    """Check if an API key is within rate limits.

    Args:
        api_key: The APIKey to check.

    Returns:
        Tuple of (allowed: bool, remaining: int requests remaining).
    """
    limits = _load_rate_limits()
    now = time.time()

    entry = limits.get(api_key.key_id)

    # Reset window if expired
    if entry is None or (now - entry.window_start) >= RATE_LIMIT_WINDOW:
        entry = RateLimitEntry(
            key_id=api_key.key_id,
            window_start=now,
            request_count=0,
        )

    remaining = api_key.rate_limit - entry.request_count

    if entry.request_count >= api_key.rate_limit:
        return False, 0

    # Increment count
    entry.request_count += 1
    limits[api_key.key_id] = entry
    _save_rate_limits(limits)

    return True, remaining - 1


# =============================================================================
# Webhook Logging
# =============================================================================


def log_webhook_event(
    event_type: str,
    source: str,
    key_id: str | None,
    payload: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Log webhook event to JSONL file.

    Args:
        event_type: Type of event (e.g., "task_created", "github_issue").
        source: Source endpoint (e.g., "/api/tasks", "/gh-webhook").
        key_id: API key ID used (None for GitHub webhooks).
        payload: Request payload (sanitized).
        result: Response/result data.
    """
    _ensure_adw_dir()

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "source": source,
        "key_id": key_id,
        "payload": payload,
        "result": result,
    }

    with open(WEBHOOK_LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def get_webhook_logs(
    limit: int = 100,
    key_id: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent webhook logs.

    Args:
        limit: Maximum number of entries to return.
        key_id: Filter by API key ID.
        event_type: Filter by event type.

    Returns:
        List of log entries (most recent first).
    """
    if not WEBHOOK_LOG_FILE.exists():
        return []

    logs = []
    with open(WEBHOOK_LOG_FILE) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if key_id and entry.get("key_id") != key_id:
                    continue
                if event_type and entry.get("event_type") != event_type:
                    continue
                logs.append(entry)
            except json.JSONDecodeError:
                continue

    # Return most recent first
    return list(reversed(logs[-limit:]))


# =============================================================================
# Task Creation Request/Response Models
# =============================================================================


@dataclass
class TaskCreateRequest:
    """Request to create a new task via API."""

    description: str
    workflow: str = "standard"  # simple, standard, sdlc
    repo: str | None = None
    priority: str = "p1"  # p0, p1, p2
    tags: list[str] = field(default_factory=list)
    callback_url: str | None = None  # URL to POST completion notification
    model: str = "sonnet"  # sonnet, opus, haiku
    worktree_name: str | None = None  # Optional custom worktree name

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskCreateRequest:
        """Create from request dictionary."""
        return cls(
            description=data.get("description", ""),
            workflow=data.get("workflow", "standard"),
            repo=data.get("repo"),
            priority=data.get("priority", "p1"),
            tags=data.get("tags", []),
            callback_url=data.get("callback_url"),
            model=data.get("model", "sonnet"),
            worktree_name=data.get("worktree_name"),
        )

    def validate(self) -> list[str]:
        """Validate the request and return list of errors."""
        errors = []

        if not self.description or not self.description.strip():
            errors.append("description is required")

        if self.workflow not in ("simple", "standard", "sdlc"):
            errors.append("workflow must be one of: simple, standard, sdlc")

        if self.priority not in ("p0", "p1", "p2"):
            errors.append("priority must be one of: p0, p1, p2")

        if self.model not in ("sonnet", "opus", "haiku"):
            errors.append("model must be one of: sonnet, opus, haiku")

        if self.callback_url:
            # Basic URL validation
            if not (
                self.callback_url.startswith("http://")
                or self.callback_url.startswith("https://")
            ):
                errors.append("callback_url must be a valid HTTP(S) URL")

        return errors


@dataclass
class TaskCreateResponse:
    """Response for task creation."""

    task_id: str
    status: str
    created_at: str
    workflow: str
    callback_registered: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to response dictionary."""
        return asdict(self)


# =============================================================================
# Callback System
# =============================================================================


CALLBACKS_FILE = ADW_DIR / "task_callbacks.json"


def register_callback(task_id: str, callback_url: str) -> None:
    """Register a callback URL for task completion.

    Args:
        task_id: The ADW task ID.
        callback_url: URL to POST completion notification.
    """
    _ensure_adw_dir()

    callbacks = {}
    if CALLBACKS_FILE.exists():
        try:
            with open(CALLBACKS_FILE) as f:
                callbacks = json.load(f)
        except json.JSONDecodeError:
            callbacks = {}

    callbacks[task_id] = {
        "url": callback_url,
        "registered_at": datetime.now().isoformat(),
        "retries": 0,
    }

    with open(CALLBACKS_FILE, "w") as f:
        json.dump(callbacks, f, indent=2)


def get_callback_url(task_id: str) -> str | None:
    """Get registered callback URL for a task.

    Args:
        task_id: The ADW task ID.

    Returns:
        Callback URL or None if not registered.
    """
    if not CALLBACKS_FILE.exists():
        return None

    try:
        with open(CALLBACKS_FILE) as f:
            callbacks = json.load(f)
        entry = callbacks.get(task_id)
        return entry["url"] if entry else None
    except (json.JSONDecodeError, KeyError):
        return None


def send_callback(
    task_id: str,
    status: str,
    result: dict[str, Any],
) -> bool:
    """Send callback notification for task completion.

    Args:
        task_id: The ADW task ID.
        status: Task status (completed, failed).
        result: Result data to include.

    Returns:
        True if callback sent successfully.
    """
    import urllib.request
    from urllib.error import URLError

    callback_url = get_callback_url(task_id)
    if not callback_url:
        return False

    payload = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        req = urllib.request.Request(
            callback_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ADW-Webhook/1.0",
                "X-ADW-Task-ID": task_id,
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            success: bool = resp.status < 400

        # Remove callback if successful
        if success:
            _remove_callback(task_id)

        return success
    except (URLError, TimeoutError) as e:
        logger.warning(f"Failed to send callback for {task_id}: {e}")
        return False


def _remove_callback(task_id: str) -> None:
    """Remove a callback entry after successful delivery."""
    if not CALLBACKS_FILE.exists():
        return

    try:
        with open(CALLBACKS_FILE) as f:
            callbacks = json.load(f)

        if task_id in callbacks:
            del callbacks[task_id]

            with open(CALLBACKS_FILE, "w") as f:
                json.dump(callbacks, f, indent=2)
    except (json.JSONDecodeError, KeyError):
        pass


# =============================================================================
# FastAPI Application
# =============================================================================


def create_webhook_app() -> Any:
    """Create FastAPI app for webhook handling.

    Returns:
        FastAPI application with all endpoints configured.
    """
    from fastapi import Depends, FastAPI, HTTPException, Request
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    app = FastAPI(
        title="ADW Webhook Handler",
        description="API for creating ADW tasks and receiving GitHub webhooks",
        version="1.0.0",
    )

    security = HTTPBearer(auto_error=False)

    async def get_api_key(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> APIKey:
        """Dependency to validate API key from Authorization header."""
        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        api_key = verify_api_key(credentials.credentials)
        if api_key is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check rate limit
        allowed, remaining = check_rate_limit(api_key)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"X-RateLimit-Remaining": "0"},
            )

        return api_key

    # -------------------------------------------------------------------------
    # Generic Task API
    # -------------------------------------------------------------------------

    @app.post("/api/tasks", response_model=dict)  # type: ignore[untyped-decorator]
    async def create_task(
        request: Request,
        api_key: APIKey = Depends(get_api_key),
    ) -> dict[str, Any]:
        """Create a new ADW task.

        Requires Bearer token authentication with a valid API key.

        Request body:
        ```json
        {
            "description": "Fix authentication bug",
            "workflow": "sdlc",
            "repo": "myapp",
            "priority": "p0",
            "tags": ["auth", "security"],
            "callback_url": "https://example.com/webhook/callback",
            "model": "sonnet"
        }
        ```

        Returns:
        ```json
        {
            "task_id": "abc123de",
            "status": "pending",
            "created_at": "2026-02-03T12:34:56Z",
            "workflow": "sdlc",
            "callback_registered": true
        }
        ```
        """
        from ..agent.utils import generate_adw_id

        payload = await request.json()
        task_request = TaskCreateRequest.from_dict(payload)

        # Validate request
        errors = task_request.validate()
        if errors:
            log_webhook_event(
                event_type="task_create_error",
                source="/api/tasks",
                key_id=api_key.key_id,
                payload={"description": task_request.description[:100]},
                result={"errors": errors},
            )
            raise HTTPException(status_code=400, detail={"errors": errors})

        # Generate task ID
        adw_id = generate_adw_id()

        # Register callback if provided
        callback_registered = False
        if task_request.callback_url:
            register_callback(adw_id, task_request.callback_url)
            callback_registered = True

        # Trigger workflow
        worktree_name = task_request.worktree_name or f"api-{adw_id}"
        _trigger_workflow_async(
            task=task_request.description,
            body="",  # API tasks don't have a body
            adw_id=adw_id,
            workflow=task_request.workflow,
            model=task_request.model,
            worktree_name=worktree_name,
        )

        response = TaskCreateResponse(
            task_id=adw_id,
            status="pending",
            created_at=datetime.now().isoformat(),
            workflow=task_request.workflow,
            callback_registered=callback_registered,
        )

        # Log the event
        log_webhook_event(
            event_type="task_created",
            source="/api/tasks",
            key_id=api_key.key_id,
            payload={
                "description": task_request.description[:100],
                "workflow": task_request.workflow,
                "priority": task_request.priority,
            },
            result={"task_id": adw_id},
        )

        return response.to_dict()

    @app.get("/api/tasks/{task_id}")  # type: ignore[untyped-decorator]
    async def get_task_status(
        task_id: str,
        api_key: APIKey = Depends(get_api_key),
    ) -> dict[str, Any]:
        """Get task status.

        Returns current status of a task created via the API.
        """
        from ..agent.state import ADWState

        try:
            state = ADWState.load(task_id)
            if state is None:
                raise HTTPException(status_code=404, detail="Task not found")

            # Derive status from current_phase
            status = "in_progress"
            if state.current_phase == "complete":
                status = "completed"
            elif state.current_phase == "failed":
                status = "failed"
            elif state.current_phase == "init":
                status = "pending"

            return {
                "task_id": task_id,
                "status": status,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "current_phase": state.current_phase,
                "phases_completed": state.phases_completed,
                "errors": state.errors,
            }
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Task not found")

    # -------------------------------------------------------------------------
    # GitHub Webhook (No API key required, uses signature verification)
    # -------------------------------------------------------------------------

    @app.post("/gh-webhook")  # type: ignore[untyped-decorator]
    async def github_webhook(request: Request) -> dict[str, Any]:
        """Handle GitHub webhook events.

        Uses X-Hub-Signature-256 header for verification instead of API key.
        Set GITHUB_WEBHOOK_SECRET environment variable to enable verification.
        """
        # Verify signature
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        if secret:
            signature = request.headers.get("X-Hub-Signature-256", "")
            body = await request.body()

            expected = "sha256=" + hmac.new(
                secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected):
                raise HTTPException(status_code=401, detail="Invalid signature")

        payload = await request.json()
        event_type = request.headers.get("X-GitHub-Event", "unknown")

        result = handle_github_event(event_type, payload)

        # Log the event
        log_webhook_event(
            event_type=f"github_{event_type}",
            source="/gh-webhook",
            key_id=None,
            payload={"event_type": event_type},
            result=result,
        )

        return result

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    @app.get("/health")  # type: ignore[untyped-decorator]
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
        }

    @app.get("/")  # type: ignore[untyped-decorator]
    async def root() -> dict[str, Any]:
        """Root endpoint with API info."""
        return {
            "name": "ADW Webhook Handler",
            "version": "1.0.0",
            "endpoints": {
                "/api/tasks": "POST - Create a new task (requires API key)",
                "/api/tasks/{task_id}": "GET - Get task status (requires API key)",
                "/gh-webhook": "POST - GitHub webhook endpoint",
                "/health": "GET - Health check",
            },
        }

    return app


# =============================================================================
# GitHub Event Handler (unchanged, preserved for backward compatibility)
# =============================================================================


def handle_github_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Handle a GitHub event.

    Args:
        event_type: The event type (issues, issue_comment, etc.)
        payload: The webhook payload.

    Returns:
        Response dict.
    """
    from ..agent.utils import generate_adw_id
    from ..integrations.issue_parser import (
        extract_config_from_labels,
        merge_template_with_labels,
        parse_issue_body,
    )

    if event_type == "issues":
        action = payload.get("action")
        if action == "labeled":
            label = payload.get("label", {}).get("name")
            if label == "adw":
                issue = payload.get("issue", {})
                adw_id = generate_adw_id()

                # Extract all labels
                labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]

                # Parse issue template
                title = issue.get("title", "")
                body = issue.get("body", "") or ""
                template = parse_issue_body(body, title)

                # Merge with label configuration (labels take precedence)
                template = merge_template_with_labels(template, labels)

                # Determine workflow and model
                workflow = template.get_workflow_or_default()
                model = template.get_model_or_default()

                # Build enhanced context for the agent
                context_prompt = template.build_context_prompt()
                full_body = f"{body}\n\n{context_prompt}" if context_prompt else body

                # Trigger async workflow
                _trigger_workflow_async(
                    task=title,
                    body=full_body,
                    adw_id=adw_id,
                    workflow=workflow,
                    model=model,
                    worktree_name=f"issue-{issue.get('number')}-{adw_id}",
                )

                return {
                    "status": "triggered",
                    "adw_id": adw_id,
                    "workflow": workflow,
                    "model": model,
                    "issue_type": template.issue_type.value,
                    "priority": template.priority.value,
                }

    elif event_type == "issue_comment":
        action = payload.get("action")
        if action == "created":
            comment = payload.get("comment", {}).get("body", "")

            # Check for ADW commands in comment
            if comment.strip().lower().startswith("adw "):
                # Skip if this is our own comment
                if "<!-- ADW:" in comment:
                    return {"status": "skipped", "reason": "own comment"}

                issue = payload.get("issue", {})
                adw_id = generate_adw_id()

                # Extract labels for configuration
                labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
                label_config = extract_config_from_labels(labels)

                # Use label config or defaults
                workflow = label_config["workflow"] or "standard"
                model = label_config["model"] or "sonnet"

                _trigger_workflow_async(
                    task=comment[4:],  # Remove "adw " prefix
                    body=issue.get("body", "") or "",
                    adw_id=adw_id,
                    workflow=workflow,
                    model=model,
                    worktree_name=f"issue-{issue.get('number')}-{adw_id}",
                )

                return {
                    "status": "triggered",
                    "adw_id": adw_id,
                    "workflow": workflow,
                    "model": model,
                }

    return {"status": "ignored"}


def _trigger_workflow_async(
    task: str,
    body: str,
    adw_id: str,
    workflow: str = "standard",
    model: str = "sonnet",
    worktree_name: str | None = None,
) -> None:
    """Trigger workflow in background process.

    Args:
        task: Task description.
        body: Additional context/body.
        adw_id: ADW task ID.
        workflow: Workflow type (simple, standard, sdlc).
        model: Model to use (sonnet, opus, haiku).
        worktree_name: Optional worktree name.
    """
    import subprocess
    import sys

    full_task = f"{task}\n\n{body}" if body else task
    wt_name = worktree_name or f"api-{adw_id}"

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            f"adw.workflows.{workflow}",
            "--adw-id",
            adw_id,
            "--worktree-name",
            wt_name,
            "--task",
            full_task,
            "--model",
            model,
        ],
        start_new_session=True,
    )


# =============================================================================
# CLI Helper Functions
# =============================================================================


def start_webhook_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
) -> None:
    """Start the webhook server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload for development.
    """
    import uvicorn

    uvicorn.run(
        "adw.triggers.webhook:create_webhook_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )
