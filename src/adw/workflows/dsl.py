"""Workflow DSL - YAML-based workflow definitions.

This module provides a domain-specific language for defining custom workflows
without modifying ADW source code. Workflows are defined in YAML format and
stored in ~/.adw/workflows/.

Example workflow definition:
```yaml
name: my-custom-workflow
description: Custom workflow for my project
version: "1.0.0"
phases:
  - name: plan
    prompt: prompts/plan.md
    model: opus
    required: true
  - name: implement
    prompt: prompts/implement.md
    model: sonnet
    required: true
    tests: npm test
  - name: review
    prompt: prompts/review.md
    model: sonnet
    required: false
    condition: has_changes
```
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Type aliases
ModelType = Literal["haiku", "sonnet", "opus"]


class PhaseCondition(Enum):
    """Conditions for phase execution."""

    ALWAYS = "always"  # Always execute (default)
    HAS_CHANGES = "has_changes"  # Only if git has changes
    TESTS_PASSED = "tests_passed"  # Only if previous tests passed
    TESTS_FAILED = "tests_failed"  # Only if previous tests failed
    FILE_EXISTS = "file_exists"  # Only if a specific file exists
    ENV_SET = "env_set"  # Only if an environment variable is set


class LoopCondition(Enum):
    """Conditions for phase looping."""

    NONE = "none"  # No looping (default)
    UNTIL_SUCCESS = "until_success"  # Loop until phase succeeds
    UNTIL_TESTS_PASS = "until_tests_pass"  # Loop until tests pass
    FIXED_COUNT = "fixed_count"  # Loop a fixed number of times


@dataclass
class PhaseDefinition:
    """Definition of a single workflow phase."""

    name: str
    prompt: str  # Path to prompt file or inline prompt text
    model: ModelType = "sonnet"
    required: bool = True
    timeout_seconds: int = 600
    max_retries: int = 2

    # Conditional execution
    condition: PhaseCondition = PhaseCondition.ALWAYS
    condition_value: str | None = None  # For FILE_EXISTS, ENV_SET conditions

    # Looping
    loop: LoopCondition = LoopCondition.NONE
    loop_max: int = 3  # Maximum loop iterations

    # Testing
    tests: str | None = None  # Test command to run after phase
    test_timeout: int = 300  # Timeout for test execution

    # Parallel execution (experimental)
    parallel_with: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate phase definition."""
        if not self.name:
            raise ValueError("Phase name is required")
        if not self.prompt:
            raise ValueError(f"Phase '{self.name}' requires a prompt")
        if self.model not in ("haiku", "sonnet", "opus"):
            raise ValueError(f"Invalid model '{self.model}' for phase '{self.name}'")
        if self.timeout_seconds <= 0:
            raise ValueError(f"Invalid timeout for phase '{self.name}'")
        if self.max_retries < 0:
            raise ValueError(f"Invalid max_retries for phase '{self.name}'")
        if self.loop_max <= 0:
            raise ValueError(f"Invalid loop_max for phase '{self.name}'")


@dataclass
class WorkflowDefinition:
    """Complete workflow definition."""

    name: str
    phases: list[PhaseDefinition]
    description: str = ""
    version: str = "1.0.0"
    author: str = ""

    # Default settings for all phases (can be overridden per-phase)
    default_model: ModelType = "sonnet"
    default_timeout: int = 600
    default_max_retries: int = 2

    # Workflow-level settings
    fail_fast: bool = True  # Stop on first required phase failure
    skip_optional_on_failure: bool = True  # Skip optional phases if any required failed

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate workflow definition."""
        if not self.name:
            raise ValueError("Workflow name is required")
        if not self.phases:
            raise ValueError(f"Workflow '{self.name}' has no phases")

        # Validate phase names are unique
        names = [p.name for p in self.phases]
        if len(names) != len(set(names)):
            raise ValueError(f"Workflow '{self.name}' has duplicate phase names")

        # Validate parallel_with references exist
        for phase in self.phases:
            for ref in phase.parallel_with:
                if ref not in names:
                    raise ValueError(f"Phase '{phase.name}' references unknown parallel phase '{ref}'")

    def get_phase(self, name: str) -> PhaseDefinition | None:
        """Get phase by name."""
        return next((p for p in self.phases if p.name == name), None)

    def get_required_phases(self) -> list[PhaseDefinition]:
        """Get all required phases."""
        return [p for p in self.phases if p.required]

    def get_optional_phases(self) -> list[PhaseDefinition]:
        """Get all optional phases."""
        return [p for p in self.phases if not p.required]


def parse_phase_yaml(data: dict[str, Any], defaults: dict[str, Any]) -> PhaseDefinition:
    """Parse a phase definition from YAML data.

    Args:
        data: Phase YAML data.
        defaults: Default values from workflow level.

    Returns:
        PhaseDefinition instance.

    Raises:
        ValueError: If phase data is invalid.
    """
    # Handle condition enum
    condition = PhaseCondition.ALWAYS
    condition_value = None
    if "condition" in data:
        cond_str = data["condition"]
        # Check for condition with value (e.g., "file_exists:README.md")
        if ":" in cond_str:
            cond_type, cond_value = cond_str.split(":", 1)
            condition = PhaseCondition(cond_type)
            condition_value = cond_value
        else:
            condition = PhaseCondition(cond_str)

    # Handle loop enum
    loop = LoopCondition.NONE
    if "loop" in data:
        loop = LoopCondition(data["loop"])

    return PhaseDefinition(
        name=data.get("name", ""),
        prompt=data.get("prompt", ""),
        model=data.get("model", defaults.get("default_model", "sonnet")),
        required=data.get("required", True),
        timeout_seconds=data.get("timeout", defaults.get("default_timeout", 600)),
        max_retries=data.get("max_retries", defaults.get("default_max_retries", 2)),
        condition=condition,
        condition_value=condition_value,
        loop=loop,
        loop_max=data.get("loop_max", 3),
        tests=data.get("tests"),
        test_timeout=data.get("test_timeout", 300),
        parallel_with=data.get("parallel_with", []),
    )


def parse_workflow_yaml(yaml_content: str) -> WorkflowDefinition:
    """Parse a workflow definition from YAML content.

    Args:
        yaml_content: YAML string containing workflow definition.

    Returns:
        WorkflowDefinition instance.

    Raises:
        ValueError: If YAML is invalid or missing required fields.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        # Fall back to basic YAML parsing if PyYAML not available
        raise ImportError("PyYAML is required for workflow DSL. Install with: pip install pyyaml")

    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise ValueError("Workflow must be a YAML mapping")

    if "name" not in data:
        raise ValueError("Workflow 'name' is required")

    if "phases" not in data or not data["phases"]:
        raise ValueError("Workflow must have at least one phase")

    # Extract defaults
    defaults = {
        "default_model": data.get("default_model", "sonnet"),
        "default_timeout": data.get("default_timeout", 600),
        "default_max_retries": data.get("default_max_retries", 2),
    }

    # Parse phases
    phases = []
    for phase_data in data["phases"]:
        phases.append(parse_phase_yaml(phase_data, defaults))

    return WorkflowDefinition(
        name=data["name"],
        phases=phases,
        description=data.get("description", ""),
        version=data.get("version", "1.0.0"),
        author=data.get("author", ""),
        default_model=defaults["default_model"],
        default_timeout=defaults["default_timeout"],
        default_max_retries=defaults["default_max_retries"],
        fail_fast=data.get("fail_fast", True),
        skip_optional_on_failure=data.get("skip_optional_on_failure", True),
        tags=data.get("tags", []),
    )


def load_workflow(path: Path | str) -> WorkflowDefinition:
    """Load a workflow definition from a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        WorkflowDefinition instance.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file content is invalid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    content = path.read_text(encoding="utf-8")
    return parse_workflow_yaml(content)


def serialize_workflow(workflow: WorkflowDefinition) -> str:
    """Serialize a workflow definition to YAML.

    Args:
        workflow: WorkflowDefinition to serialize.

    Returns:
        YAML string.
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for workflow DSL. Install with: pip install pyyaml")

    # Build data structure
    data: dict[str, Any] = {
        "name": workflow.name,
        "description": workflow.description,
        "version": workflow.version,
    }

    if workflow.author:
        data["author"] = workflow.author

    # Add defaults if they differ from standard defaults
    if workflow.default_model != "sonnet":
        data["default_model"] = workflow.default_model
    if workflow.default_timeout != 600:
        data["default_timeout"] = workflow.default_timeout
    if workflow.default_max_retries != 2:
        data["default_max_retries"] = workflow.default_max_retries

    # Add workflow-level settings if non-default
    if not workflow.fail_fast:
        data["fail_fast"] = False
    if not workflow.skip_optional_on_failure:
        data["skip_optional_on_failure"] = False

    if workflow.tags:
        data["tags"] = workflow.tags

    # Serialize phases
    phases_data = []
    for phase in workflow.phases:
        phase_data: dict[str, Any] = {
            "name": phase.name,
            "prompt": phase.prompt,
        }

        # Only include non-default values
        if phase.model != workflow.default_model:
            phase_data["model"] = phase.model
        if not phase.required:
            phase_data["required"] = False
        if phase.timeout_seconds != workflow.default_timeout:
            phase_data["timeout"] = phase.timeout_seconds
        if phase.max_retries != workflow.default_max_retries:
            phase_data["max_retries"] = phase.max_retries
        if phase.condition != PhaseCondition.ALWAYS:
            if phase.condition_value:
                phase_data["condition"] = f"{phase.condition.value}:{phase.condition_value}"
            else:
                phase_data["condition"] = phase.condition.value
        if phase.loop != LoopCondition.NONE:
            phase_data["loop"] = phase.loop.value
            if phase.loop_max != 3:
                phase_data["loop_max"] = phase.loop_max
        if phase.tests:
            phase_data["tests"] = phase.tests
            if phase.test_timeout != 300:
                phase_data["test_timeout"] = phase.test_timeout
        if phase.parallel_with:
            phase_data["parallel_with"] = phase.parallel_with

        phases_data.append(phase_data)

    data["phases"] = phases_data

    result: str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return result


def save_workflow(workflow: WorkflowDefinition, path: Path | str) -> None:
    """Save a workflow definition to a YAML file.

    Args:
        workflow: WorkflowDefinition to save.
        path: Output file path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = serialize_workflow(workflow)
    path.write_text(content, encoding="utf-8")


# ============================================================================
# Prompt Templating
# ============================================================================


class PromptTemplate:
    """Template engine for workflow prompts.

    Supports:
    - Variable substitution: {{variable_name}}
    - Include directives: {{include path/to/file.md}}
    - Conditional blocks: {{#if condition}}...{{/if}}
    """

    VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")
    INCLUDE_PATTERN = re.compile(r"\{\{include\s+([^\}]+)\}\}")
    CONDITIONAL_PATTERN = re.compile(r"\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}", re.DOTALL)

    def __init__(
        self,
        template: str,
        base_path: Path | None = None,
        max_includes: int = 10,
    ):
        """Initialize template.

        Args:
            template: Template string or path to template file.
            base_path: Base path for resolving includes.
            max_includes: Maximum number of includes to prevent recursion.
        """
        self.base_path = base_path or Path.cwd()
        self.max_includes = max_includes
        self._include_count = 0

        # Load template from file if it's a path
        if template.endswith((".md", ".txt", ".tmpl")):
            template_path = self._resolve_path(template)
            if template_path.exists():
                template = template_path.read_text(encoding="utf-8")

        self.template = template

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path relative to base_path."""
        path = Path(path_str)
        if path.is_absolute():
            return path
        return self.base_path / path

    def _process_includes(self, content: str) -> str:
        """Process include directives."""

        def replace_include(match: re.Match[str]) -> str:
            if self._include_count >= self.max_includes:
                logger.warning("Max includes reached, skipping: %s", match.group(1))
                return f"<!-- Include limit reached: {match.group(1)} -->"

            include_path = self._resolve_path(match.group(1).strip())
            if not include_path.exists():
                logger.warning("Include file not found: %s", include_path)
                return f"<!-- Include not found: {match.group(1)} -->"

            self._include_count += 1
            included = include_path.read_text(encoding="utf-8")
            # Recursively process includes in the included content
            return self._process_includes(included)

        return self.INCLUDE_PATTERN.sub(replace_include, content)

    def _process_conditionals(self, content: str, context: dict[str, Any]) -> str:
        """Process conditional blocks."""

        def replace_conditional(match: re.Match[str]) -> str:
            condition_var = match.group(1)
            block_content = match.group(2)

            # Evaluate condition
            value = context.get(condition_var)
            if value:
                return str(block_content.strip())
            return ""

        return str(self.CONDITIONAL_PATTERN.sub(replace_conditional, content))

    def _process_variables(self, content: str, context: dict[str, Any]) -> str:
        """Process variable substitutions."""

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            value = context.get(var_name)
            if value is None:
                logger.debug("Undefined variable: %s", var_name)
                return match.group(0)  # Keep original if not found
            return str(value)

        return str(self.VAR_PATTERN.sub(replace_var, content))

    def render(self, **context: Any) -> str:
        """Render the template with the given context.

        Args:
            **context: Variables for substitution.

        Returns:
            Rendered template string.
        """
        self._include_count = 0

        # Process in order: includes, conditionals, variables
        content = self._process_includes(self.template)
        content = self._process_conditionals(content, context)
        content = self._process_variables(content, context)

        return content

    @classmethod
    def from_file(cls, path: Path | str, base_path: Path | None = None) -> PromptTemplate:
        """Create a template from a file.

        Args:
            path: Path to template file.
            base_path: Base path for resolving includes.

        Returns:
            PromptTemplate instance.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Template file not found: {path}")

        content = path.read_text(encoding="utf-8")
        return cls(content, base_path=base_path or path.parent)


# ============================================================================
# Workflow Library Management
# ============================================================================


def get_workflows_dir() -> Path:
    """Get the directory for user-defined workflows.

    Returns:
        Path to ~/.adw/workflows/
    """
    return Path.home() / ".adw" / "workflows"


def get_builtin_workflows_dir() -> Path:
    """Get the directory for built-in workflows.

    Returns:
        Path to the built-in workflows directory (in package).
    """
    # Built-in workflows are stored alongside this module
    return Path(__file__).parent / "builtin"


def list_workflows(include_builtin: bool = True) -> list[tuple[str, Path, bool]]:
    """List all available workflows.

    Args:
        include_builtin: Whether to include built-in workflows.

    Returns:
        List of (name, path, is_builtin) tuples.
    """
    workflows = []

    # User workflows take precedence
    user_dir = get_workflows_dir()
    if user_dir.exists():
        for path in user_dir.glob("*.yaml"):
            name = path.stem
            workflows.append((name, path, False))
        for path in user_dir.glob("*.yml"):
            name = path.stem
            if not any(w[0] == name for w in workflows):
                workflows.append((name, path, False))

    # Add built-in workflows
    if include_builtin:
        builtin_dir = get_builtin_workflows_dir()
        if builtin_dir.exists():
            for path in builtin_dir.glob("*.yaml"):
                name = path.stem
                # Don't add if user has same name
                if not any(w[0] == name for w in workflows):
                    workflows.append((name, path, True))
            for path in builtin_dir.glob("*.yml"):
                name = path.stem
                if not any(w[0] == name for w in workflows):
                    workflows.append((name, path, True))

    return sorted(workflows, key=lambda x: x[0])


def get_workflow(name: str) -> WorkflowDefinition | None:
    """Get a workflow by name.

    Args:
        name: Workflow name.

    Returns:
        WorkflowDefinition or None if not found.
    """
    # Check user workflows first
    user_dir = get_workflows_dir()
    for ext in (".yaml", ".yml"):
        user_path = user_dir / f"{name}{ext}"
        if user_path.exists():
            return load_workflow(user_path)

    # Check built-in workflows
    builtin_dir = get_builtin_workflows_dir()
    for ext in (".yaml", ".yml"):
        builtin_path = builtin_dir / f"{name}{ext}"
        if builtin_path.exists():
            return load_workflow(builtin_path)

    return None


def create_workflow(
    name: str,
    phases: list[dict[str, Any]],
    description: str = "",
    overwrite: bool = False,
) -> Path:
    """Create a new user workflow.

    Args:
        name: Workflow name.
        phases: List of phase definitions.
        description: Workflow description.
        overwrite: Whether to overwrite existing workflow.

    Returns:
        Path to the created workflow file.

    Raises:
        FileExistsError: If workflow exists and overwrite=False.
    """
    user_dir = get_workflows_dir()
    user_dir.mkdir(parents=True, exist_ok=True)

    path = user_dir / f"{name}.yaml"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Workflow '{name}' already exists")

    # Parse phases
    parsed_phases = [parse_phase_yaml(p, {}) for p in phases]

    workflow = WorkflowDefinition(
        name=name,
        phases=parsed_phases,
        description=description,
    )

    save_workflow(workflow, path)
    return path


def delete_workflow(name: str) -> bool:
    """Delete a user workflow.

    Args:
        name: Workflow name.

    Returns:
        True if deleted, False if not found.

    Raises:
        ValueError: If trying to delete a built-in workflow.
    """
    # Check if it's a built-in workflow
    builtin_dir = get_builtin_workflows_dir()
    for ext in (".yaml", ".yml"):
        if (builtin_dir / f"{name}{ext}").exists():
            raise ValueError(f"Cannot delete built-in workflow '{name}'")

    # Delete user workflow
    user_dir = get_workflows_dir()
    for ext in (".yaml", ".yml"):
        path = user_dir / f"{name}{ext}"
        if path.exists():
            path.unlink()
            return True

    return False


def get_active_workflow_name() -> str | None:
    """Get the currently active workflow name.

    Returns:
        Active workflow name or None.
    """
    config_path = Path.home() / ".adw" / "config.toml"
    if not config_path.exists():
        return None

    try:
        content = config_path.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if line.startswith("active_workflow"):
                # Parse: active_workflow = "sdlc"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    value = parts[1].strip().strip('"').strip("'")
                    return value
    except Exception as e:
        logger.debug("Error reading active workflow: %s", e)

    return None


def set_active_workflow(name: str) -> None:
    """Set the active workflow.

    Args:
        name: Workflow name.

    Raises:
        ValueError: If workflow doesn't exist.
    """
    # Verify workflow exists
    if get_workflow(name) is None:
        raise ValueError(f"Workflow '{name}' not found")

    config_path = Path.home() / ".adw" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or create new
    content = ""
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")

    # Update or add active_workflow setting
    lines = content.split("\n")
    found = False
    for i, line in enumerate(lines):
        if line.startswith("active_workflow"):
            lines[i] = f'active_workflow = "{name}"'
            found = True
            break

    if not found:
        # Add to end
        if lines and lines[-1]:
            lines.append("")  # Add blank line
        lines.append(f'active_workflow = "{name}"')

    config_path.write_text("\n".join(lines), encoding="utf-8")


# ============================================================================
# Built-in Workflow Definitions
# ============================================================================

BUILTIN_SDLC = """
name: sdlc
description: Full Software Development Lifecycle workflow
version: "1.0.0"
author: ADW
tags: [development, testing, review]

default_model: sonnet
default_timeout: 600
fail_fast: true

phases:
  - name: plan
    prompt: /plan {{task_description}}
    model: opus
    required: true
    timeout: 900

  - name: implement
    prompt: /implement {{task_description}}
    model: sonnet
    required: true
    timeout: 1200
    loop: until_tests_pass
    loop_max: 3

  - name: test
    prompt: /test {{task_description}}
    model: sonnet
    required: true
    timeout: 600
    tests: "auto"

  - name: review
    prompt: /review {{task_description}}
    model: opus
    required: true
    timeout: 600

  - name: document
    prompt: /document {{task_description}}
    model: haiku
    required: false
    timeout: 300

  - name: release
    prompt: /release {{task_description}}
    model: sonnet
    required: false
    timeout: 300
    condition: has_changes
"""

BUILTIN_SIMPLE = """
name: simple
description: Quick build-only workflow for simple tasks
version: "1.0.0"
author: ADW
tags: [quick, simple]

default_model: sonnet
default_timeout: 600
fail_fast: true

phases:
  - name: build
    prompt: |
      Build the following:
      {{task_description}}

      Execute the task directly without planning.
    model: sonnet
    required: true
    timeout: 900
"""

BUILTIN_PROTOTYPE = """
name: prototype
description: Rapid prototyping workflow
version: "1.0.0"
author: ADW
tags: [prototype, rapid, scaffolding]

default_model: sonnet
default_timeout: 600
fail_fast: false

phases:
  - name: scaffold
    prompt: |
      Create a quick prototype for:
      {{task_description}}

      Focus on speed over perfection. Create working code quickly.
    model: sonnet
    required: true
    timeout: 600

  - name: verify
    prompt: |
      Verify the prototype works:
      {{task_description}}

      Run any available tests or manual verification.
    model: haiku
    required: false
    timeout: 300
"""

BUILTIN_BUGFIX = """
name: bug-fix
description: Focused bug fixing workflow
version: "1.0.0"
author: ADW
tags: [bugfix, debugging, maintenance]

default_model: sonnet
default_timeout: 600
fail_fast: true

phases:
  - name: investigate
    prompt: |
      Investigate the following bug:
      {{task_description}}

      1. Reproduce the issue
      2. Identify the root cause
      3. Document your findings
    model: opus
    required: true
    timeout: 600

  - name: fix
    prompt: |
      Fix the bug based on your investigation:
      {{task_description}}

      Make minimal, targeted changes to fix the issue.
    model: sonnet
    required: true
    timeout: 900
    loop: until_tests_pass
    loop_max: 3

  - name: verify
    prompt: |
      Verify the fix:
      {{task_description}}

      Run tests and confirm the bug is resolved.
    model: sonnet
    required: true
    timeout: 600
    tests: "auto"

  - name: document
    prompt: |
      Document the fix:
      {{task_description}}

      Add comments explaining the fix and why it was needed.
    model: haiku
    required: false
    timeout: 300
"""


def ensure_builtin_workflows() -> None:
    """Ensure built-in workflow files exist."""
    builtin_dir = get_builtin_workflows_dir()
    builtin_dir.mkdir(parents=True, exist_ok=True)

    builtins = {
        "sdlc.yaml": BUILTIN_SDLC,
        "simple.yaml": BUILTIN_SIMPLE,
        "prototype.yaml": BUILTIN_PROTOTYPE,
        "bug-fix.yaml": BUILTIN_BUGFIX,
    }

    for filename, content in builtins.items():
        path = builtin_dir / filename
        if not path.exists():
            path.write_text(content.strip() + "\n", encoding="utf-8")
            logger.debug("Created built-in workflow: %s", filename)


# Initialize built-in workflows on module import
try:
    ensure_builtin_workflows()
except Exception as e:
    logger.debug("Could not create built-in workflows: %s", e)
