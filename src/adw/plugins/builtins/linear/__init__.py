"""Linear Plugin - Task sync for ADW.

Sync ADW tasks with Linear issues.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError

import click

from adw.plugins.base import Plugin


class LinearPlugin(Plugin):
    """Linear integration plugin."""
    
    name = "linear"
    version = "0.1.0"
    description = "Linear task synchronization"
    author = "StudiBudi"
    requires_external = []
    
    API_URL = "https://api.linear.app/graphql"
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key") or os.environ.get("LINEAR_API_KEY")
        self.team_id = self.config.get("team_id") or os.environ.get("LINEAR_TEAM_ID")
        self.auto_update = self.config.get("auto_update", True)
        self.state_mapping = self.config.get("state_mapping", {
            "complete": "Done",
            "fail": "Backlog",
        })
    
    def on_complete(self, task: str, result: dict[str, Any]) -> None:
        """Update Linear issue on task completion."""
        if not self.auto_update or not self.api_key:
            return
        
        # Extract issue ID from task (e.g., "STU-123")
        issue_id = self._extract_issue_id(task)
        if not issue_id:
            return
        
        # Update issue status
        done_state = self.state_mapping.get("complete", "Done")
        self._update_issue_state(issue_id, done_state)
        
        # Add comment with result
        commit = result.get("commit_hash", "")[:8] if result.get("commit_hash") else ""
        comment = f"✅ Task completed by ADW"
        if commit:
            comment += f"\n\nCommit: `{commit}`"
        
        self._add_comment(issue_id, comment)
    
    def on_fail(self, task: str, error: str) -> None:
        """Update Linear issue on task failure."""
        if not self.auto_update or not self.api_key:
            return
        
        issue_id = self._extract_issue_id(task)
        if not issue_id:
            return
        
        # Add comment with error
        comment = f"❌ Task failed\n\n```\n{error[:500]}\n```"
        self._add_comment(issue_id, comment)
    
    def _extract_issue_id(self, text: str) -> str | None:
        """Extract Linear issue ID from text (e.g., STU-123)."""
        match = re.search(r'([A-Z]+-\d+)', text)
        return match.group(1) if match else None
    
    def _graphql(self, query: str, variables: dict | None = None) -> dict | None:
        """Execute GraphQL query."""
        if not self.api_key:
            return None
        
        try:
            data = json.dumps({
                "query": query,
                "variables": variables or {},
            }).encode("utf-8")
            
            request = Request(
                self.API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self.api_key,
                },
            )
            
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, Exception):
            return None
    
    def _update_issue_state(self, issue_id: str, state_name: str) -> bool:
        """Update issue state by name."""
        # First, get the state ID
        query = """
        query($teamId: String!) {
            workflowStates(filter: { team: { id: { eq: $teamId } } }) {
                nodes { id name }
            }
        }
        """
        
        result = self._graphql(query, {"teamId": self.team_id})
        if not result:
            return False
        
        states = result.get("data", {}).get("workflowStates", {}).get("nodes", [])
        state_id = None
        for state in states:
            if state["name"].lower() == state_name.lower():
                state_id = state["id"]
                break
        
        if not state_id:
            return False
        
        # Update the issue
        mutation = """
        mutation($issueId: String!, $stateId: String!) {
            issueUpdate(id: $issueId, input: { stateId: $stateId }) {
                success
            }
        }
        """
        
        # Get issue UUID from identifier
        issue_query = """
        query($id: String!) {
            issue(id: $id) { id }
        }
        """
        issue_result = self._graphql(issue_query, {"id": issue_id})
        if not issue_result:
            return False
        
        issue_uuid = issue_result.get("data", {}).get("issue", {}).get("id")
        if not issue_uuid:
            return False
        
        result = self._graphql(mutation, {"issueId": issue_uuid, "stateId": state_id})
        return result.get("data", {}).get("issueUpdate", {}).get("success", False) if result else False
    
    def _add_comment(self, issue_id: str, body: str) -> bool:
        """Add comment to issue."""
        # Get issue UUID
        query = """
        query($id: String!) {
            issue(id: $id) { id }
        }
        """
        result = self._graphql(query, {"id": issue_id})
        if not result:
            return False
        
        issue_uuid = result.get("data", {}).get("issue", {}).get("id")
        if not issue_uuid:
            return False
        
        mutation = """
        mutation($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
            }
        }
        """
        
        result = self._graphql(mutation, {"issueId": issue_uuid, "body": body})
        return result.get("data", {}).get("commentCreate", {}).get("success", False) if result else False
    
    def get_commands(self) -> list:
        """Return CLI commands."""
        return [create_linear_commands(self)]
    
    def status(self) -> dict[str, Any]:
        """Return plugin status."""
        base_status = super().status()
        base_status.update({
            "api_key_configured": bool(self.api_key),
            "team_id": self.team_id,
            "auto_update": self.auto_update,
        })
        return base_status


def create_linear_commands(plugin: LinearPlugin):
    """Create the linear command group."""
    
    @click.group()
    def linear():
        """Linear integration commands."""
        pass
    
    @linear.command("status")
    def linear_status():
        """Show Linear configuration status."""
        from rich.console import Console
        console = Console()
        
        if plugin.api_key:
            console.print("[green]✓ API key configured[/green]")
        else:
            console.print("[yellow]○ No API key[/yellow]")
            console.print("[dim]Set LINEAR_API_KEY environment variable[/dim]")
        
        if plugin.team_id:
            console.print(f"  Team ID: {plugin.team_id}")
        
        console.print(f"  Auto-update: {plugin.auto_update}")
    
    @linear.command("issues")
    @click.option("--limit", "-n", default=10, help="Number of issues")
    def linear_issues(limit: int):
        """List recent issues."""
        from rich.console import Console
        console = Console()
        
        if not plugin.api_key:
            console.print("[red]✗ No API key configured[/red]")
            return
        
        query = """
        query($first: Int!) {
            issues(first: $first, orderBy: updatedAt) {
                nodes {
                    identifier
                    title
                    state { name }
                }
            }
        }
        """
        
        result = plugin._graphql(query, {"first": limit})
        if not result:
            console.print("[red]✗ Failed to fetch issues[/red]")
            return
        
        issues = result.get("data", {}).get("issues", {}).get("nodes", [])
        
        if not issues:
            console.print("[yellow]No issues found[/yellow]")
            return
        
        for issue in issues:
            state = issue.get("state", {}).get("name", "?")
            console.print(f"[bold]{issue['identifier']}[/bold] [{state}] {issue['title'][:50]}")
    
    return linear


# Export plugin class
plugin_class = LinearPlugin
