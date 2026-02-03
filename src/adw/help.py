"""Help and examples system for ADW CLI.

Provides a unified examples catalog with:
- Category-based organization
- Complexity levels (beginner, intermediate, advanced)
- Search functionality
- Interactive display
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum


class Complexity(Enum):
    """Example complexity levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Category(Enum):
    """Example categories."""

    QUICKSTART = "quickstart"
    TASKS = "tasks"
    WORKFLOWS = "workflows"
    GITHUB = "github"
    MONITORING = "monitoring"
    PARALLEL = "parallel"
    CONFIG = "config"
    INTEGRATIONS = "integrations"


@dataclass
class Example:
    """A single example with description and commands."""

    title: str
    description: str
    commands: list[str]
    category: Category
    complexity: Complexity
    notes: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    def format(self, verbose: bool = False) -> str:
        """Format example for display."""
        lines = []
        lines.append(f"[bold cyan]{self.title}[/bold cyan]")
        lines.append(f"[dim]{self.description}[/dim]")
        lines.append("")

        for cmd in self.commands:
            lines.append(f"  [green]$ {cmd}[/green]")

        if verbose and self.notes:
            lines.append("")
            for note in self.notes:
                lines.append(f"  [dim]→ {note}[/dim]")

        if verbose and self.related:
            lines.append("")
            lines.append(f"  [dim]Related: {', '.join(self.related)}[/dim]")

        return "\n".join(lines)


# =============================================================================
# EXAMPLES CATALOG
# =============================================================================

EXAMPLES: list[Example] = [
    # -------------------------------------------------------------------------
    # Quick Start Examples
    # -------------------------------------------------------------------------
    Example(
        title="Initialize a New Project",
        description="Set up ADW in your current project directory",
        commands=[
            "adw init",
            "adw init --smart  # Deep analysis with Claude Code",
        ],
        category=Category.QUICKSTART,
        complexity=Complexity.BEGINNER,
        notes=[
            "Creates .claude/, tasks.md, and specs/ directories",
            "Use --smart for better context (takes ~30-60s)",
        ],
        related=["adw refresh", "adw status"],
    ),
    Example(
        title="Start a New Task",
        description="Create a task and start working on it interactively",
        commands=[
            'adw new "Add user authentication"',
            'adw new "Fix login bug" --workflow simple',
        ],
        category=Category.QUICKSTART,
        complexity=Complexity.BEGINNER,
        notes=[
            "Opens an interactive session with Claude Code",
            "Task is tracked in tasks.md automatically",
        ],
        related=["adw run", "adw status"],
    ),
    Example(
        title="Run Autonomous Mode",
        description="Let ADW work through tasks automatically",
        commands=[
            "adw run",
            "adw run --limit 5  # Process up to 5 tasks",
        ],
        category=Category.QUICKSTART,
        complexity=Complexity.BEGINNER,
        notes=[
            "Processes pending tasks from tasks.md",
            "Respects dependencies and concurrent limits",
            "Press Ctrl+C to stop gracefully",
        ],
        related=["adw pause", "adw resume", "adw status"],
    ),
    Example(
        title="Open TUI Dashboard",
        description="Interactive terminal interface for monitoring",
        commands=[
            "adw",
            "adw dashboard",
        ],
        category=Category.QUICKSTART,
        complexity=Complexity.BEGINNER,
        notes=[
            "Real-time log streaming",
            "Press 'm' to send messages to agents",
            "Press '?' for keyboard shortcuts",
        ],
    ),
    # -------------------------------------------------------------------------
    # Task Management Examples
    # -------------------------------------------------------------------------
    Example(
        title="Add Tasks to Queue",
        description="Add tasks to tasks.md for later processing",
        commands=[
            'adw add "Implement search feature"',
            'adw add "Fix performance issue" --priority p0',
            'adw add "Add dark mode" --model opus',
        ],
        category=Category.TASKS,
        complexity=Complexity.BEGINNER,
        notes=[
            "Tasks are added to tasks.md",
            "Use --priority for urgency (p0=highest)",
            "Use --model for complexity (opus for complex reasoning)",
        ],
        related=["adw list", "adw run"],
    ),
    Example(
        title="View and Manage Tasks",
        description="List, cancel, or retry tasks",
        commands=[
            "adw list",
            "adw list --status running",
            "adw cancel abc123de",
            "adw retry abc123de",
        ],
        category=Category.TASKS,
        complexity=Complexity.BEGINNER,
        notes=[
            "Task IDs are 8-character hex strings",
            "Find task IDs with 'adw list'",
        ],
        related=["adw status", "adw history"],
    ),
    Example(
        title="Task Dependencies",
        description="Create ordered task sequences",
        commands=[
            "# In tasks.md:",
            "# [] First task",
            "# [⏰] Second task  ← Blocked until first completes",
            "# [⏰] Third task   ← Blocked until both complete",
        ],
        category=Category.TASKS,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "[⏰] means blocked/waiting",
            "Tasks unblock automatically when dependencies complete",
            "Order in file determines dependency chain",
        ],
    ),
    Example(
        title="Task Tags and Models",
        description="Control how tasks are executed",
        commands=[
            "# In tasks.md:",
            "# [] Complex feature {opus}    ← Use Opus model",
            "# [] Quick fix {haiku}         ← Use Haiku model",
            "# [] Standard task {sonnet}    ← Use Sonnet (default)",
        ],
        category=Category.TASKS,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Tags are in curly braces at end of task",
            "opus: Best for complex reasoning",
            "sonnet: Good balance (default)",
            "haiku: Fast for simple tasks",
        ],
    ),
    # -------------------------------------------------------------------------
    # Workflow Examples
    # -------------------------------------------------------------------------
    Example(
        title="Choose a Workflow",
        description="Select workflow based on task complexity",
        commands=[
            'adw new "Task" --workflow simple   # Build only',
            'adw new "Task" --workflow standard # Plan → Build → Update',
            'adw new "Task" --workflow sdlc     # Full lifecycle',
        ],
        category=Category.WORKFLOWS,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "simple: Quick fixes, no planning",
            "standard: Features needing planning",
            "sdlc: Complex features with full review cycle",
        ],
        related=["adw workflow list", "adw workflow show"],
    ),
    Example(
        title="Custom Workflows",
        description="Create and use custom workflow definitions",
        commands=[
            "adw workflow list",
            "adw workflow show sdlc",
            "adw workflow create my-workflow --from sdlc",
            "adw workflow use my-workflow",
        ],
        category=Category.WORKFLOWS,
        complexity=Complexity.ADVANCED,
        notes=[
            "Workflows are YAML files in ~/.adw/workflows/",
            "Customize phases, conditions, and loops",
        ],
        related=["adw prompt create"],
    ),
    Example(
        title="Validate Workflow",
        description="Check workflow YAML syntax and structure",
        commands=[
            "adw workflow validate ~/.adw/workflows/my-workflow.yaml",
        ],
        category=Category.WORKFLOWS,
        complexity=Complexity.ADVANCED,
    ),
    # -------------------------------------------------------------------------
    # GitHub Integration Examples
    # -------------------------------------------------------------------------
    Example(
        title="Watch GitHub Issues",
        description="Auto-process GitHub issues as tasks",
        commands=[
            "adw github watch",
            "adw github watch --interval 300  # Check every 5 min",
            "adw github watch --label adw",
        ],
        category=Category.GITHUB,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Watches for issues with 'adw' label by default",
            "Creates tasks and PRs automatically",
            "Requires GITHUB_TOKEN environment variable",
        ],
        related=["adw github process"],
    ),
    Example(
        title="Process Specific Issue",
        description="Handle a single GitHub issue",
        commands=[
            "adw github process 123",
            "adw github process owner/repo#123",
        ],
        category=Category.GITHUB,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Creates task from issue",
            "Links PR back to issue when done",
        ],
    ),
    Example(
        title="Fix PR Review Comments",
        description="Auto-fix actionable review feedback",
        commands=[
            "adw github watch-pr 456",
            "adw github fix-comments 456",
        ],
        category=Category.GITHUB,
        complexity=Complexity.ADVANCED,
        notes=[
            "Parses review comments for actionable items",
            "Creates fix commits automatically",
            "Filters out non-actionable comments (LGTM, questions)",
        ],
    ),
    Example(
        title="Link PRs Across Repos",
        description="Coordinate multi-repo changes",
        commands=[
            "adw pr link owner/frontend#10 owner/backend#20",
            "adw pr list",
            "adw pr merge group-id",
        ],
        category=Category.GITHUB,
        complexity=Complexity.ADVANCED,
        notes=[
            "Links PRs for atomic merge",
            "Ensures all PRs are approved before merging",
            "Rolls back on failure",
        ],
    ),
    # -------------------------------------------------------------------------
    # Monitoring Examples
    # -------------------------------------------------------------------------
    Example(
        title="Watch Agent Logs",
        description="Stream real-time agent activity",
        commands=[
            "adw logs abc123de",
            "adw logs abc123de --follow",
            "adw watch",
        ],
        category=Category.MONITORING,
        complexity=Complexity.BEGINNER,
        notes=[
            "Logs are in JSONL format",
            "Use --follow for continuous streaming",
            "'adw watch' shows all active agents",
        ],
        related=["adw events", "adw sessions"],
    ),
    Example(
        title="View Events and Sessions",
        description="Query observability database",
        commands=[
            "adw events",
            "adw events --type tool --since 1h",
            "adw sessions",
        ],
        category=Category.MONITORING,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Events stored in .adw/events.db",
            "Filter by type, session, or time range",
        ],
    ),
    Example(
        title="Generate Reports",
        description="View task metrics and trends",
        commands=[
            "adw report daily",
            "adw report weekly",
            "adw report trends",
            "adw metrics --summary",
            "adw costs --period week",
        ],
        category=Category.MONITORING,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Tracks tasks completed, costs, time saved",
            "Sparklines show trends visually",
        ],
        related=["adw alerts"],
    ),
    # -------------------------------------------------------------------------
    # Parallel Execution Examples
    # -------------------------------------------------------------------------
    Example(
        title="Create Isolated Worktrees",
        description="Run tasks in parallel without conflicts",
        commands=[
            "adw worktree create feature-auth",
            "adw worktree list",
            "adw worktree remove feature-auth",
        ],
        category=Category.PARALLEL,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Each worktree has independent git state",
            "Perfect for parallel feature development",
            "Auto-cleanup on task completion",
        ],
    ),
    Example(
        title="Multi-Repo Workspace",
        description="Orchestrate tasks across repositories",
        commands=[
            "adw workspace init my-project",
            "adw workspace add ../frontend",
            "adw workspace add ../backend --type fastapi",
            "adw workspace list",
        ],
        category=Category.PARALLEL,
        complexity=Complexity.ADVANCED,
        notes=[
            "Config stored in ~/.adw/workspace.toml",
            "Cross-repo dependencies supported",
        ],
        related=["adw workspace depend", "adw pr link"],
    ),
    # -------------------------------------------------------------------------
    # Configuration Examples
    # -------------------------------------------------------------------------
    Example(
        title="View and Edit Config",
        description="Manage ADW settings",
        commands=[
            "adw config show",
            "adw config get core.default_model",
            "adw config set core.default_model opus",
            "adw config edit  # Opens in $EDITOR",
        ],
        category=Category.CONFIG,
        complexity=Complexity.BEGINNER,
        notes=[
            "Config file: ~/.adw/config.toml",
            "Sections: core, daemon, ui, workflow, workspace",
        ],
        related=["adw config keys", "adw config reset"],
    ),
    Example(
        title="Setup Notifications",
        description="Configure Slack/Discord alerts",
        commands=[
            "adw alerts add slack https://hooks.slack.com/... --events task_complete,task_failed",
            "adw alerts list",
            "adw alerts test my-slack",
        ],
        category=Category.CONFIG,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Supports Slack and Discord webhooks",
            "Events: task_start, task_complete, task_failed, daily_summary",
        ],
    ),
    # -------------------------------------------------------------------------
    # Integration Examples
    # -------------------------------------------------------------------------
    Example(
        title="Linear Integration",
        description="Process Linear issues as tasks",
        commands=[
            "adw linear test",
            "adw linear watch",
            "adw linear sync PROJ-123",
        ],
        category=Category.INTEGRATIONS,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Set LINEAR_API_KEY environment variable",
            "Config via config.toml [linear] section",
        ],
    ),
    Example(
        title="Notion Integration",
        description="Process Notion database items as tasks",
        commands=[
            "adw notion test",
            "adw notion watch",
        ],
        category=Category.INTEGRATIONS,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Set NOTION_API_KEY and NOTION_DATABASE_ID",
            "Status syncs bidirectionally",
        ],
    ),
    Example(
        title="Slack Bot",
        description="Interact via Slack slash commands",
        commands=[
            "adw slack start --port 8080",
            "/adw create Add user search feature",
            "/adw status",
        ],
        category=Category.INTEGRATIONS,
        complexity=Complexity.ADVANCED,
        notes=[
            "Requires Slack app configuration",
            "Commands: /adw create, /adw status, /adw approve",
        ],
    ),
    Example(
        title="Webhook API",
        description="Create tasks via REST API",
        commands=[
            "adw webhook start --port 9000",
            "adw webhook key generate my-key",
            'curl -X POST http://localhost:9000/api/tasks \\',
            '  -H "Authorization: Bearer $API_KEY" \\',
            '  -d \'{"description": "Add feature X"}\'',
        ],
        category=Category.INTEGRATIONS,
        complexity=Complexity.ADVANCED,
        notes=[
            "RESTful API for task creation",
            "Supports callback URLs for completion notification",
        ],
    ),
    # -------------------------------------------------------------------------
    # Recovery Examples
    # -------------------------------------------------------------------------
    Example(
        title="Recover from Failures",
        description="Rollback or resume failed tasks",
        commands=[
            "adw checkpoints abc123de",
            "adw rollback abc123de",
            "adw resume-task abc123de",
            "adw escalation abc123de",
        ],
        category=Category.TASKS,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Checkpoints save task state periodically",
            "Rollback undoes all task changes",
            "Resume continues from last checkpoint",
            "Escalation shows detailed failure report",
        ],
    ),
    # -------------------------------------------------------------------------
    # Context Examples
    # -------------------------------------------------------------------------
    Example(
        title="Context Priming",
        description="Pre-load project context for better results",
        commands=[
            "adw prime generate",
            "adw prime show",
            "adw prime refresh",
        ],
        category=Category.CONFIG,
        complexity=Complexity.INTERMEDIATE,
        notes=[
            "Auto-detects project type (React, FastAPI, etc.)",
            "Generates .claude/commands/*_auto.md files",
        ],
    ),
    Example(
        title="Context Bundles",
        description="Save and restore session context",
        commands=[
            "adw bundle list",
            "adw bundle save my-session file1.py file2.py",
            "adw bundle load my-session",
            "adw bundle suggest 'user authentication'",
        ],
        category=Category.CONFIG,
        complexity=Complexity.ADVANCED,
        notes=[
            "Bundles store file references for session restoration",
            "Suggest finds relevant past bundles",
        ],
    ),
]


def get_examples_by_category(category: Category) -> list[Example]:
    """Get all examples in a category."""
    return [e for e in EXAMPLES if e.category == category]


def get_examples_by_complexity(complexity: Complexity) -> list[Example]:
    """Get all examples at a complexity level."""
    return [e for e in EXAMPLES if e.complexity == complexity]


def search_examples(query: str) -> list[Example]:
    """Search examples by keyword."""
    query = query.lower()
    results = []
    for example in EXAMPLES:
        # Search in title, description, and commands
        searchable = (
            example.title.lower()
            + " "
            + example.description.lower()
            + " "
            + " ".join(example.commands).lower()
            + " "
            + " ".join(example.notes).lower()
        )
        if query in searchable:
            results.append(example)
    return results


def get_category_summary() -> dict[Category, int]:
    """Get count of examples per category."""
    summary = {}
    for cat in Category:
        summary[cat] = len(get_examples_by_category(cat))
    return summary


def iter_examples() -> Iterator[Example]:
    """Iterate over all examples."""
    yield from EXAMPLES


def format_category_name(category: Category) -> str:
    """Format category name for display."""
    names = {
        Category.QUICKSTART: "Quick Start",
        Category.TASKS: "Task Management",
        Category.WORKFLOWS: "Workflows",
        Category.GITHUB: "GitHub Integration",
        Category.MONITORING: "Monitoring & Reports",
        Category.PARALLEL: "Parallel Execution",
        Category.CONFIG: "Configuration",
        Category.INTEGRATIONS: "External Integrations",
    }
    return names.get(category, category.value.title())


def format_complexity_name(complexity: Complexity) -> str:
    """Format complexity name for display."""
    colors = {
        Complexity.BEGINNER: "[green]Beginner[/green]",
        Complexity.INTERMEDIATE: "[yellow]Intermediate[/yellow]",
        Complexity.ADVANCED: "[red]Advanced[/red]",
    }
    return colors.get(complexity, complexity.value.title())
