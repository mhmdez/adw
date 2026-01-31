"""Webhook handler for real-time GitHub events."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

# Note: Requires fastapi and uvicorn
# pip install fastapi uvicorn


def create_webhook_app():
    """Create FastAPI app for webhook handling."""
    from fastapi import FastAPI, Request, HTTPException

    app = FastAPI(title="ADW Webhook Handler")

    @app.post("/gh-webhook")
    async def github_webhook(request: Request):
        """Handle GitHub webhook events."""
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

        return handle_github_event(event_type, payload)

    return app


def handle_github_event(event_type: str, payload: dict[str, Any]) -> dict:
    """Handle a GitHub event.

    Args:
        event_type: The event type (issues, issue_comment, etc.)
        payload: The webhook payload.

    Returns:
        Response dict.
    """
    from ..agent.executor import generate_adw_id

    if event_type == "issues":
        action = payload.get("action")
        if action == "labeled":
            label = payload.get("label", {}).get("name")
            if label == "adw":
                issue = payload.get("issue", {})
                adw_id = generate_adw_id()

                # Trigger async workflow
                _trigger_workflow_async(
                    task=issue.get("title", ""),
                    body=issue.get("body", ""),
                    issue_number=issue.get("number"),
                    adw_id=adw_id,
                )

                return {"status": "triggered", "adw_id": adw_id}

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

                _trigger_workflow_async(
                    task=comment[4:],  # Remove "adw " prefix
                    body=issue.get("body", ""),
                    issue_number=issue.get("number"),
                    adw_id=adw_id,
                )

                return {"status": "triggered", "adw_id": adw_id}

    return {"status": "ignored"}


def _trigger_workflow_async(
    task: str,
    body: str,
    issue_number: int,
    adw_id: str,
) -> None:
    """Trigger workflow in background process."""
    import subprocess
    import sys

    subprocess.Popen(
        [
            sys.executable,
            "-m", "adw.workflows.standard",
            "--adw-id", adw_id,
            "--worktree-name", f"issue-{issue_number}-{adw_id}",
            "--task", f"{task}\n\n{body}",
        ],
        start_new_session=True,
    )
