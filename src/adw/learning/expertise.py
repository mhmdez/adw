"""Expertise section building and injection for agent prompts.

This module provides functions to build and inject expertise sections
into agent prompts, combining domain expert knowledge with learned patterns.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .patterns import (
    Learning,
    LearningType,
    get_default_pattern_store,
)

if TYPE_CHECKING:
    from ..experts.base import Expert

logger = logging.getLogger(__name__)


def build_expertise_section(
    patterns: list[Learning] | None = None,
    issues: list[Learning] | None = None,
    best_practices: list[Learning] | None = None,
    mistakes: list[Learning] | None = None,
    domain: str = "general",
    include_stats: bool = False,
) -> str:
    """Build a formatted expertise section for agent prompts.

    Creates a markdown-formatted section documenting discovered patterns,
    known issues, best practices, and mistakes to avoid.

    Args:
        patterns: Successful code patterns.
        issues: Known issues and workarounds.
        best_practices: Proven approaches.
        mistakes: Common mistakes to avoid.
        domain: Domain name for the section header.
        include_stats: Whether to include usage statistics.

    Returns:
        Markdown-formatted expertise section.
    """
    lines = [f"## Expertise ({domain})"]
    lines.append("")

    # Patterns
    if patterns:
        lines.append("### Discovered Patterns")
        for p in patterns[:7]:  # Limit to prevent token bloat
            stat = f" (used {p.success_count}x)" if include_stats else ""
            lines.append(f"- {p.content}{stat}")
        lines.append("")

    # Best practices
    if best_practices:
        lines.append("### Best Practices")
        for bp in best_practices[:5]:
            lines.append(f"- {bp.content}")
        lines.append("")

    # Known issues
    if issues:
        lines.append("### Known Issues")
        for issue in issues[:5]:
            # Context often contains the workaround
            workaround = f": {issue.context}" if issue.context else ""
            lines.append(f"- **{issue.content}**{workaround}")
        lines.append("")

    # Mistakes to avoid
    if mistakes:
        lines.append("### Mistakes to Avoid")
        for m in mistakes[:5]:
            lines.append(f"- ❌ {m.content}")
        lines.append("")

    # If no content, return empty
    if len(lines) <= 2:
        return ""

    return "\n".join(lines)


def get_combined_expertise(
    domain: str | None = None,
    expert: Expert | None = None,
    project: str | None = None,
    files: list[str] | None = None,
    include_global: bool = True,
) -> str:
    """Get combined expertise from expert system and learned patterns.

    Merges domain expert knowledge with project-specific learnings.

    Args:
        domain: Domain to get expertise for (frontend, backend, ai).
        expert: Optional Expert instance to include context from.
        project: Project name for project-specific learnings.
        files: Files being worked on (for domain detection).
        include_global: Whether to include global learnings.

    Returns:
        Combined expertise section.
    """
    sections = []

    # Get domain expert context if available
    if expert:
        expert_context = expert.get_context()
        if expert_context:
            sections.append(expert_context)

    # Get project-specific learnings
    store = get_default_pattern_store(project=project)

    patterns = store.get_top_patterns(limit=5, domain=domain)
    issues = store.get_known_issues(domain=domain)
    mistakes = store.get_mistakes_to_avoid(domain=domain)
    best_practices = store.get_learnings_by_type(LearningType.BEST_PRACTICE)

    if domain:
        best_practices = [
            bp for bp in best_practices
            if bp.domain == domain or bp.domain == "general"
        ]

    learned_section = build_expertise_section(
        patterns=patterns,
        issues=issues,
        best_practices=best_practices[:5],
        mistakes=mistakes,
        domain=f"{project or 'Project'} Learnings",
        include_stats=True,
    )

    if learned_section:
        sections.append(learned_section)

    # Optionally include global learnings
    if include_global and project != "global":
        global_store = get_default_pattern_store(project="global")
        global_patterns = global_store.get_top_patterns(limit=3, domain=domain)

        if global_patterns:
            global_section = build_expertise_section(
                patterns=global_patterns,
                domain="Global Patterns",
            )
            if global_section:
                sections.append(global_section)

    return "\n\n".join(sections)


def inject_expertise_into_prompt(
    prompt: str,
    domain: str | None = None,
    expert: Expert | None = None,
    project: str | None = None,
    position: str = "start",
) -> str:
    """Inject expertise section into a prompt.

    Args:
        prompt: Original prompt text.
        domain: Domain for expertise (auto-detected if None).
        expert: Optional Expert instance.
        project: Project name.
        position: Where to inject - "start", "end", or "after_task".

    Returns:
        Prompt with expertise section injected.
    """
    expertise = get_combined_expertise(
        domain=domain,
        expert=expert,
        project=project,
    )

    if not expertise:
        return prompt

    if position == "start":
        return f"{expertise}\n\n---\n\n{prompt}"
    elif position == "end":
        return f"{prompt}\n\n---\n\n{expertise}"
    elif position == "after_task":
        # Try to find task description and inject after it
        # Look for common task section patterns
        task_markers = ["## Task", "### Task", "**Task:**", "Task Description:"]
        for marker in task_markers:
            if marker in prompt:
                parts = prompt.split(marker, 1)
                if len(parts) == 2:
                    # Find end of task section (next header or double newline)
                    task_part = parts[1]
                    insert_pos = task_part.find("\n\n")
                    if insert_pos == -1:
                        insert_pos = len(task_part)

                    return (
                        parts[0]
                        + marker
                        + task_part[:insert_pos]
                        + "\n\n"
                        + expertise
                        + task_part[insert_pos:]
                    )

        # Fallback to start position
        return f"{expertise}\n\n---\n\n{prompt}"

    return prompt


def generate_expertise_report(
    project: str | None = None,
    include_global: bool = True,
) -> str:
    """Generate a full expertise report for review.

    Creates a comprehensive markdown report of all learnings.

    Args:
        project: Project to report on.
        include_global: Whether to include global learnings.

    Returns:
        Markdown-formatted report.
    """
    lines = ["# Expertise Report"]
    lines.append("")
    lines.append(f"Generated: {__import__('datetime').datetime.now().isoformat()}")
    lines.append("")

    store = get_default_pattern_store(project=project)
    stats = store.get_statistics()

    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- **Total Learnings:** {stats['total_learnings']}")
    lines.append(f"- **Patterns:** {stats['patterns']}")
    lines.append(f"- **Issues:** {stats['issues']}")
    lines.append(f"- **Best Practices:** {stats['best_practices']}")
    lines.append(f"- **Mistakes to Avoid:** {stats['mistakes']}")
    lines.append(f"- **Domains:** {', '.join(stats['domains']) if stats['domains'] else 'none'}")
    lines.append("")

    # Patterns by domain
    for domain in stats["domains"] or ["general"]:
        lines.append(f"## Domain: {domain}")
        lines.append("")

        patterns = store.get_top_patterns(limit=10, domain=domain)
        if patterns:
            lines.append("### Top Patterns")
            for p in patterns:
                lines.append(f"- {p.content} (used {p.success_count}x)")
            lines.append("")

        issues = store.get_known_issues(domain=domain)
        if issues:
            lines.append("### Known Issues")
            for issue in issues:
                lines.append(f"- **{issue.content}**")
                if issue.context:
                    lines.append(f"  - Workaround: {issue.context}")
            lines.append("")

        mistakes = store.get_mistakes_to_avoid(domain=domain)
        if mistakes:
            lines.append("### Mistakes to Avoid")
            for m in mistakes:
                lines.append(f"- ❌ {m.content}")
            lines.append("")

    # Global learnings
    if include_global and project and project != "global":
        lines.append("## Global Learnings")
        lines.append("")
        global_store = get_default_pattern_store(project="global")
        global_patterns = global_store.get_top_patterns(limit=5)
        if global_patterns:
            for p in global_patterns:
                lines.append(f"- {p.content}")
        else:
            lines.append("_No global learnings recorded yet._")
        lines.append("")

    return "\n".join(lines)
