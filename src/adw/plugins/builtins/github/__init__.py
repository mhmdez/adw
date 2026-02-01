"""GitHub Plugin - PR creation and issue linking for ADW.

This plugin integrates with GitHub to:
- Auto-create PRs after task completion
- Link commits to issues
- Add task context to PR descriptions
"""

from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Any

import click

from adw.plugins.base import Plugin


class GithubPlugin(Plugin):
    """GitHub integration plugin."""
    
    name = "github"
    version = "0.1.0"
    description = "GitHub PR creation and issue linking"
    author = "StudiBudi"
    requires_external = ["gh"]
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.auto_pr = self.config.get("auto_pr", False)
        self.pr_draft = self.config.get("pr_draft", True)
        self.link_issues = self.config.get("link_issues", True)
    
    def on_complete(self, task: str, result: dict[str, Any]) -> None:
        """Create PR after task completion if enabled."""
        if not self.auto_pr:
            return
        
        if not self._is_gh_available():
            return
        
        commit_hash = result.get("commit_hash")
        branch = result.get("branch")
        
        if not branch:
            return
        
        # Create PR
        title = self._generate_pr_title(task)
        body = self._generate_pr_body(task, result)
        
        self._create_pr(branch, title, body)
    
    def _is_gh_available(self) -> bool:
        """Check if gh CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _generate_pr_title(self, task: str) -> str:
        """Generate PR title from task description."""
        # Truncate and clean up
        title = task[:50]
        if len(task) > 50:
            title += "..."
        return title
    
    def _generate_pr_body(self, task: str, result: dict[str, Any]) -> str:
        """Generate PR body with task context."""
        body = f"""## Task

{task}

## Changes

This PR was created automatically by ADW (AI Developer Workflow).

"""
        if result.get("commit_hash"):
            body += f"**Commit:** {result['commit_hash'][:8]}\n"
        
        if result.get("files_changed"):
            body += f"**Files changed:** {result['files_changed']}\n"
        
        # Extract issue references from task
        issues = re.findall(r'#(\d+)', task)
        if issues:
            body += "\n## Linked Issues\n\n"
            for issue in issues:
                body += f"- Closes #{issue}\n"
        
        return body
    
    def _create_pr(self, branch: str, title: str, body: str) -> bool:
        """Create a PR using gh CLI."""
        cmd = ["gh", "pr", "create", "--title", title, "--body", body]
        
        if self.pr_draft:
            cmd.append("--draft")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def get_commands(self) -> list:
        """Return CLI commands for github."""
        return [create_github_commands()]
    
    def status(self) -> dict[str, Any]:
        """Return plugin status."""
        base_status = super().status()
        base_status.update({
            "gh_available": self._is_gh_available(),
            "auto_pr": self.auto_pr,
            "pr_draft": self.pr_draft,
        })
        return base_status
    
    @classmethod
    def install(cls, plugin_dir: Path) -> tuple[bool, str | None]:
        """Check gh CLI is available."""
        import shutil
        if not shutil.which("gh"):
            return False, (
                "GitHub CLI (gh) not found. Install with:\n"
                "  brew install gh\n"
                "Then authenticate: gh auth login"
            )
        return True, None


def create_github_commands():
    """Create the github command group."""
    
    @click.group()
    def github():
        """GitHub integration commands."""
        pass
    
    @github.command("status")
    def github_status():
        """Show GitHub CLI status."""
        from rich.console import Console
        console = Console()
        
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print("[green]✓ GitHub CLI authenticated[/green]")
                # Parse account info
                for line in result.stderr.split("\n"):
                    if "Logged in" in line or "account" in line.lower():
                        console.print(f"  [dim]{line.strip()}[/dim]")
            else:
                console.print("[red]✗ Not authenticated[/red]")
                console.print("[dim]Run: gh auth login[/dim]")
        except FileNotFoundError:
            console.print("[red]✗ gh CLI not installed[/red]")
            console.print("[dim]Install with: brew install gh[/dim]")
    
    @github.command("pr")
    @click.option("--title", "-t", help="PR title")
    @click.option("--body", "-b", help="PR body")
    @click.option("--draft", "-d", is_flag=True, help="Create as draft")
    def github_pr(title: str | None, body: str | None, draft: bool):
        """Create a pull request."""
        from rich.console import Console
        console = Console()
        
        cmd = ["gh", "pr", "create"]
        if title:
            cmd.extend(["--title", title])
        if body:
            cmd.extend(["--body", body])
        if draft:
            cmd.append("--draft")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print("[green]✓ PR created[/green]")
                console.print(f"[dim]{result.stdout.strip()}[/dim]")
            else:
                console.print(f"[red]✗ Failed: {result.stderr}[/red]")
        except FileNotFoundError:
            console.print("[red]✗ gh CLI not installed[/red]")
    
    @github.command("issues")
    @click.option("--limit", "-n", default=10, help="Number of issues")
    @click.option("--state", "-s", default="open", help="Issue state (open/closed/all)")
    def github_issues(limit: int, state: str):
        """List repository issues."""
        from rich.console import Console
        console = Console()
        
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--limit", str(limit), "--state", state],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                console.print(f"[red]✗ {result.stderr}[/red]")
        except FileNotFoundError:
            console.print("[red]✗ gh CLI not installed[/red]")
    
    return github


# Export plugin class
plugin_class = GithubPlugin
