"""GitHub issue template parsing for ADW.

Parses structured data from GitHub issue bodies, supporting:
1. YAML frontmatter (--- delimited)
2. Markdown section headers (## Field Name)
3. Inline tags ({opus}, {sdlc}, etc.)

This enables workflow customization based on issue templates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IssueType(Enum):
    """Supported issue types."""

    BUG = "bug"
    FEATURE = "feature"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"
    UNKNOWN = "unknown"


class Priority(Enum):
    """Issue priority levels."""

    P0 = "p0"  # Critical
    P1 = "p1"  # High
    P2 = "p2"  # Medium
    P3 = "p3"  # Low


@dataclass
class ParsedIssueTemplate:
    """Parsed issue template data.

    Contains structured metadata extracted from issue body.
    """

    # Core fields
    issue_type: IssueType = IssueType.UNKNOWN
    priority: Priority = Priority.P1
    workflow: str | None = None  # simple, standard, sdlc
    model: str | None = None  # sonnet, opus, haiku

    # Bug-specific fields
    steps_to_reproduce: str | None = None
    expected_behavior: str | None = None
    actual_behavior: str | None = None
    affected_versions: list[str] = field(default_factory=list)

    # Feature-specific fields
    acceptance_criteria: list[str] = field(default_factory=list)
    design_notes: str | None = None

    # General fields
    description: str | None = None
    context: str | None = None
    tags: list[str] = field(default_factory=list)

    # Raw data for access to any custom fields
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)
    raw_sections: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issue_type": self.issue_type.value,
            "priority": self.priority.value,
            "workflow": self.workflow,
            "model": self.model,
            "steps_to_reproduce": self.steps_to_reproduce,
            "expected_behavior": self.expected_behavior,
            "actual_behavior": self.actual_behavior,
            "affected_versions": self.affected_versions,
            "acceptance_criteria": self.acceptance_criteria,
            "design_notes": self.design_notes,
            "description": self.description,
            "context": self.context,
            "tags": self.tags,
            "raw_frontmatter": self.raw_frontmatter,
            "raw_sections": self.raw_sections,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedIssueTemplate:
        """Create from dictionary."""
        return cls(
            issue_type=IssueType(data.get("issue_type", "unknown")),
            priority=Priority(data.get("priority", "p1")),
            workflow=data.get("workflow"),
            model=data.get("model"),
            steps_to_reproduce=data.get("steps_to_reproduce"),
            expected_behavior=data.get("expected_behavior"),
            actual_behavior=data.get("actual_behavior"),
            affected_versions=data.get("affected_versions", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            design_notes=data.get("design_notes"),
            description=data.get("description"),
            context=data.get("context"),
            tags=data.get("tags", []),
            raw_frontmatter=data.get("raw_frontmatter", {}),
            raw_sections=data.get("raw_sections", {}),
        )

    def get_workflow_or_default(self) -> str:
        """Get workflow, or determine from issue type if not specified."""
        if self.workflow:
            return self.workflow

        # Map issue types to default workflows
        workflow_map = {
            IssueType.BUG: "bug-fix",  # Use focused bug-fix workflow
            IssueType.FEATURE: "sdlc",
            IssueType.REFACTOR: "standard",
            IssueType.DOCS: "simple",
            IssueType.TEST: "standard",
            IssueType.CHORE: "simple",
            IssueType.UNKNOWN: "standard",
        }
        return workflow_map.get(self.issue_type, "standard")

    def get_model_or_default(self) -> str:
        """Get model, or determine from priority/type if not specified."""
        if self.model:
            return self.model

        # P0 and complex features get opus
        if self.priority == Priority.P0:
            return "opus"
        if self.issue_type == IssueType.FEATURE and self.priority == Priority.P1:
            return "sonnet"
        # Docs and chores get haiku
        if self.issue_type in (IssueType.DOCS, IssueType.CHORE):
            return "haiku"

        return "sonnet"

    def build_context_prompt(self) -> str:
        """Build a context prompt section for the agent.

        Returns formatted string to inject into agent prompts.
        """
        sections = []

        if self.issue_type != IssueType.UNKNOWN:
            sections.append(f"**Issue Type**: {self.issue_type.value}")

        if self.priority:
            sections.append(f"**Priority**: {self.priority.value}")

        if self.description:
            sections.append(f"**Description**:\n{self.description}")

        if self.context:
            sections.append(f"**Context**:\n{self.context}")

        # Bug-specific sections
        if self.steps_to_reproduce:
            sections.append(f"**Steps to Reproduce**:\n{self.steps_to_reproduce}")

        if self.expected_behavior:
            sections.append(f"**Expected Behavior**:\n{self.expected_behavior}")

        if self.actual_behavior:
            sections.append(f"**Actual Behavior**:\n{self.actual_behavior}")

        if self.affected_versions:
            versions = ", ".join(self.affected_versions)
            sections.append(f"**Affected Versions**: {versions}")

        # Feature-specific sections
        if self.acceptance_criteria:
            criteria = "\n".join(f"- {c}" for c in self.acceptance_criteria)
            sections.append(f"**Acceptance Criteria**:\n{criteria}")

        if self.design_notes:
            sections.append(f"**Design Notes**:\n{self.design_notes}")

        if self.tags:
            sections.append(f"**Tags**: {', '.join(self.tags)}")

        if not sections:
            return ""

        return "## Issue Template Data\n\n" + "\n\n".join(sections)


# =============================================================================
# Parsing Functions
# =============================================================================


def parse_yaml_frontmatter(body: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from issue body.

    Expects format:
    ---
    type: bug
    priority: p0
    workflow: sdlc
    ---
    Rest of body...

    Args:
        body: Issue body text.

    Returns:
        Tuple of (frontmatter_dict, remaining_body).
    """
    if not body or not body.strip().startswith("---"):
        return {}, body

    # Find the closing ---
    lines = body.split("\n")
    end_index = -1

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index == -1:
        return {}, body

    # Parse YAML content (simple key: value parsing, no full YAML library)
    frontmatter = {}
    yaml_lines = lines[1:end_index]

    for line in yaml_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            key, value_str = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_").replace("-", "_")
            value_str = value_str.strip()

            # Parse value to appropriate type
            parsed_value: str | list[str] | bool

            # Handle lists (simple inline format: [a, b, c])
            if value_str.startswith("[") and value_str.endswith("]"):
                items = value_str[1:-1].split(",")
                parsed_value = [item.strip().strip("\"'") for item in items if item.strip()]
            # Handle quoted strings
            elif value_str.startswith('"') and value_str.endswith('"'):
                parsed_value = value_str[1:-1]
            elif value_str.startswith("'") and value_str.endswith("'"):
                parsed_value = value_str[1:-1]
            # Handle booleans
            elif value_str.lower() in ("true", "yes"):
                parsed_value = True
            elif value_str.lower() in ("false", "no"):
                parsed_value = False
            else:
                parsed_value = value_str

            frontmatter[key] = parsed_value

    remaining_body = "\n".join(lines[end_index + 1 :]).strip()
    return frontmatter, remaining_body


def parse_markdown_sections(body: str) -> dict[str, str]:
    """Parse markdown sections from issue body.

    Expects format:
    ## Section Name
    Section content...

    ## Another Section
    More content...

    Args:
        body: Issue body text.

    Returns:
        Dictionary mapping section names (lowercase, underscored) to content.
    """
    sections: dict[str, str] = {}
    current_section = None
    current_content: list[str] = []

    for line in body.split("\n"):
        # Check for H2 or H3 headers
        header_match = re.match(r"^#{2,3}\s+(.+)$", line)

        if header_match:
            # Save previous section
            if current_section is not None:
                sections[current_section] = "\n".join(current_content).strip()

            # Start new section
            section_name = header_match.group(1).strip()
            current_section = section_name.lower().replace(" ", "_").replace("-", "_")
            current_content = []
        elif current_section is not None:
            current_content.append(line)

    # Save last section
    if current_section is not None:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def extract_inline_tags(text: str) -> list[str]:
    """Extract inline tags from text.

    Looks for patterns like {opus}, {sdlc}, {p0}, etc.

    Args:
        text: Text to search.

    Returns:
        List of extracted tags (without braces).
    """
    # Match {tag} patterns
    pattern = r"\{([a-zA-Z0-9_-]+)\}"
    matches = re.findall(pattern, text)
    return [m.lower() for m in matches]


def parse_issue_body(body: str, title: str = "") -> ParsedIssueTemplate:
    """Parse a GitHub issue body into structured template data.

    Supports:
    1. YAML frontmatter
    2. Markdown sections
    3. Inline tags in title or body

    Args:
        body: Issue body text.
        title: Issue title (optional, for tag extraction).

    Returns:
        ParsedIssueTemplate with extracted data.
    """
    if not body:
        body = ""

    template = ParsedIssueTemplate()

    # Parse YAML frontmatter
    frontmatter, remaining_body = parse_yaml_frontmatter(body)
    template.raw_frontmatter = frontmatter

    # Parse markdown sections from remaining body
    sections = parse_markdown_sections(remaining_body)
    template.raw_sections = sections

    # Extract inline tags from title and body
    all_text = f"{title} {body}"
    inline_tags = extract_inline_tags(all_text)

    # Process frontmatter fields
    _apply_frontmatter(template, frontmatter)

    # Process markdown sections
    _apply_sections(template, sections)

    # Process inline tags (can override frontmatter)
    _apply_inline_tags(template, inline_tags)

    return template


def _apply_frontmatter(template: ParsedIssueTemplate, frontmatter: dict[str, Any]) -> None:
    """Apply frontmatter data to template."""
    # Issue type
    if "type" in frontmatter:
        try:
            template.issue_type = IssueType(frontmatter["type"].lower())
        except ValueError:
            pass

    # Priority
    if "priority" in frontmatter:
        priority_str = str(frontmatter["priority"]).lower()
        if not priority_str.startswith("p"):
            priority_str = f"p{priority_str}"
        try:
            template.priority = Priority(priority_str)
        except ValueError:
            pass

    # Workflow (supports all built-in workflows)
    if "workflow" in frontmatter:
        wf = frontmatter["workflow"].lower()
        # Normalize aliases
        if wf in ("bugfix", "bug_fix"):
            wf = "bug-fix"
        if wf in ("simple", "standard", "sdlc", "bug-fix", "prototype"):
            template.workflow = wf

    # Model
    if "model" in frontmatter:
        model = frontmatter["model"].lower()
        if model in ("sonnet", "opus", "haiku"):
            template.model = model

    # Tags
    if "tags" in frontmatter:
        tags = frontmatter["tags"]
        if isinstance(tags, list):
            template.tags.extend(tags)
        elif isinstance(tags, str):
            template.tags.extend([t.strip() for t in tags.split(",")])

    # Affected versions
    if "affected_versions" in frontmatter:
        versions = frontmatter["affected_versions"]
        if isinstance(versions, list):
            template.affected_versions = versions
        elif isinstance(versions, str):
            template.affected_versions = [v.strip() for v in versions.split(",")]


def _apply_sections(template: ParsedIssueTemplate, sections: dict[str, str]) -> None:
    """Apply markdown sections to template."""
    # Map common section names to template fields
    section_mappings = {
        "description": "description",
        "summary": "description",
        "overview": "description",
        "context": "context",
        "background": "context",
        "steps_to_reproduce": "steps_to_reproduce",
        "reproduction_steps": "steps_to_reproduce",
        "how_to_reproduce": "steps_to_reproduce",
        "expected_behavior": "expected_behavior",
        "expected": "expected_behavior",
        "actual_behavior": "actual_behavior",
        "actual": "actual_behavior",
        "current_behavior": "actual_behavior",
        "acceptance_criteria": "acceptance_criteria",
        "requirements": "acceptance_criteria",
        "design_notes": "design_notes",
        "technical_notes": "design_notes",
        "implementation_notes": "design_notes",
    }

    for section_name, content in sections.items():
        if not content:
            continue

        mapped_field = section_mappings.get(section_name)
        if mapped_field:
            if mapped_field == "acceptance_criteria":
                # Parse as list (one item per line starting with - or *)
                criteria = []
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith(("-", "*", "•")):
                        criteria.append(line.lstrip("-*• ").strip())
                    elif line and not criteria:
                        # First line without bullet
                        criteria.append(line)
                template.acceptance_criteria = criteria
            else:
                setattr(template, mapped_field, content)


def _apply_inline_tags(template: ParsedIssueTemplate, tags: list[str]) -> None:
    """Apply inline tags to template."""
    # Workflow aliases for normalization
    workflow_aliases = {
        "bugfix": "bug-fix",
        "bug_fix": "bug-fix",
    }

    for tag in tags:
        # Normalize tag
        normalized = workflow_aliases.get(tag, tag)

        # Workflow tags (all built-in workflows)
        if normalized in ("simple", "standard", "sdlc", "bug-fix", "prototype"):
            template.workflow = normalized
        # Model tags
        elif tag in ("sonnet", "opus", "haiku"):
            template.model = tag
        # Priority tags
        elif tag in ("p0", "p1", "p2", "p3"):
            try:
                template.priority = Priority(tag)
            except ValueError:
                pass
        # Issue type tags
        elif tag in ("bug", "feature", "refactor", "docs", "test", "chore"):
            try:
                template.issue_type = IssueType(tag)
            except ValueError:
                pass
        # Add to general tags
        else:
            if tag not in template.tags:
                template.tags.append(tag)


# =============================================================================
# Label-Based Configuration
# =============================================================================


def extract_config_from_labels(labels: list[str]) -> dict[str, str | None]:
    """Extract workflow and model configuration from GitHub labels.

    Supports label formats:
    - workflow:simple, workflow:standard, workflow:sdlc
    - model:sonnet, model:opus, model:haiku
    - priority:p0, priority:p1, priority:p2
    - type:bug, type:feature, etc.

    Args:
        labels: List of GitHub label names.

    Returns:
        Dictionary with workflow, model, priority, and type (or None if not found).
    """
    config: dict[str, str | None] = {
        "workflow": None,
        "model": None,
        "priority": None,
        "type": None,
    }

    # Valid workflow names (all built-in workflows)
    valid_workflows = ("simple", "standard", "sdlc", "bug-fix", "prototype")
    # Workflow aliases
    workflow_aliases = {"bugfix": "bug-fix", "bug_fix": "bug-fix"}

    for label in labels:
        label_lower = label.lower()

        # Check for prefixed labels (workflow:sdlc, model:opus, etc.)
        if ":" in label_lower:
            prefix, value = label_lower.split(":", 1)
            # Normalize workflow aliases
            if prefix == "workflow":
                value = workflow_aliases.get(value, value)
                if value in valid_workflows:
                    config["workflow"] = value
            elif prefix == "model" and value in ("sonnet", "opus", "haiku"):
                config["model"] = value
            elif prefix == "priority" and value in ("p0", "p1", "p2", "p3"):
                config["priority"] = value
            elif prefix == "type" and value in ("bug", "feature", "refactor", "docs", "test", "chore"):
                config["type"] = value

        # Check for direct label matches (e.g., label named "sdlc" or "opus")
        else:
            # Normalize workflow aliases
            normalized = workflow_aliases.get(label_lower, label_lower)
            if normalized in valid_workflows:
                config["workflow"] = normalized
            elif label_lower in ("sonnet", "opus", "haiku"):
                config["model"] = label_lower
            elif label_lower in ("p0", "p1", "p2", "p3"):
                config["priority"] = label_lower
            elif label_lower in ("bug", "feature", "refactor", "docs", "test", "chore"):
                config["type"] = label_lower

    return config


def merge_template_with_labels(
    template: ParsedIssueTemplate,
    labels: list[str],
) -> ParsedIssueTemplate:
    """Merge label configuration into template.

    Labels take precedence over template body values.

    Args:
        template: Parsed issue template.
        labels: GitHub labels.

    Returns:
        Updated template with label overrides applied.
    """
    label_config = extract_config_from_labels(labels)

    # Labels override template values
    if label_config["workflow"]:
        template.workflow = label_config["workflow"]

    if label_config["model"]:
        template.model = label_config["model"]

    if label_config["priority"]:
        try:
            template.priority = Priority(label_config["priority"])
        except ValueError:
            pass

    if label_config["type"]:
        try:
            template.issue_type = IssueType(label_config["type"])
        except ValueError:
            pass

    return template
