"""GitHub integration for ADW."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class GitHubIssue:
    """Represents a GitHub issue."""
    number: int
    title: str
    body: str
    labels: list[str]
    state: str


def get_issue(issue_number: int) -> GitHubIssue | None:
    """Fetch a GitHub issue.

    Args:
        issue_number: The issue number.

    Returns:
        GitHubIssue or None if not found.
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json",
             "number,title,body,labels,state"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            labels=[l["name"] for l in data.get("labels", [])],
            state=data["state"],
        )

    except Exception:
        return None


def add_issue_comment(issue_number: int, comment: str, adw_id: str) -> bool:
    """Add a comment to a GitHub issue.

    Args:
        issue_number: The issue number.
        comment: Comment text.
        adw_id: ADW ID for tracking (prevents webhook loops).

    Returns:
        True if successful.
    """
    # Prefix with ADW identifier to prevent webhook loops
    full_comment = f"<!-- ADW:{adw_id} -->\n{comment}"

    try:
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--body", full_comment],
            capture_output=True,
        )
        return result.returncode == 0

    except Exception:
        return False


def create_pull_request(
    title: str,
    body: str,
    branch: str,
    base: str = "main",
) -> str | None:
    """Create a pull request.

    Args:
        title: PR title.
        body: PR body.
        branch: Source branch.
        base: Target branch.

    Returns:
        PR URL or None if failed.
    """
    try:
        result = subprocess.run(
            [
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--head", branch,
                "--base", base,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return result.stdout.strip()

    except Exception:
        pass

    return None


def get_open_issues_with_label(label: str) -> list[GitHubIssue]:
    """Get all open issues with a specific label.

    Args:
        label: Label to filter by.

    Returns:
        List of matching issues.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", label,
                "--state", "open",
                "--json", "number,title,body,labels,state",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        return [
            GitHubIssue(
                number=item["number"],
                title=item["title"],
                body=item.get("body", ""),
                labels=[l["name"] for l in item.get("labels", [])],
                state=item["state"],
            )
            for item in data
        ]

    except Exception:
        return []
