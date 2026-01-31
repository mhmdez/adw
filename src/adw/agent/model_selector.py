"""Model selection strategy for ADW agents.

This module provides intelligent model selection based on:
- Slash command type
- Task complexity heuristics
- Explicit tag overrides
- Model set (base vs heavy)
"""

from __future__ import annotations
from typing import Literal


# Model selection based on slash command and model set
SLASH_COMMAND_MODEL_MAP: dict[str, dict[str, str]] = {
    # Planning commands - complex reasoning benefits from Opus
    "/plan": {"base": "sonnet", "heavy": "opus"},
    "/discuss": {"base": "sonnet", "heavy": "opus"},
    "/feature": {"base": "sonnet", "heavy": "opus"},
    "/bug": {"base": "sonnet", "heavy": "opus"},
    "/chore": {"base": "sonnet", "heavy": "sonnet"},

    # Implementation - can use Opus for complex code
    "/implement": {"base": "sonnet", "heavy": "opus"},
    "/build": {"base": "sonnet", "heavy": "opus"},

    # Testing - Sonnet is usually sufficient
    "/test": {"base": "sonnet", "heavy": "sonnet"},
    "/resolve_failed_test": {"base": "sonnet", "heavy": "opus"},

    # Review - benefits from deeper reasoning
    "/review": {"base": "sonnet", "heavy": "opus"},
    "/verify": {"base": "sonnet", "heavy": "opus"},

    # Documentation - Opus for comprehensive docs
    "/document": {"base": "sonnet", "heavy": "opus"},

    # Simple operations - Haiku is sufficient
    "/status": {"base": "haiku", "heavy": "haiku"},
    "/update_task": {"base": "haiku", "heavy": "sonnet"},
    "/mark_in_progress": {"base": "haiku", "heavy": "haiku"},

    # Prototypes - complex scaffolding
    "/plan_vite_vue": {"base": "sonnet", "heavy": "opus"},
    "/plan_uv_script": {"base": "sonnet", "heavy": "opus"},
    "/plan_bun_scripts": {"base": "sonnet", "heavy": "opus"},
}


# Workflow phase model selection
PHASE_MODEL_MAP: dict[str, dict[str, str]] = {
    "plan": {"base": "sonnet", "heavy": "opus"},
    "implement": {"base": "sonnet", "heavy": "opus"},
    "test": {"base": "sonnet", "heavy": "sonnet"},
    "review": {"base": "sonnet", "heavy": "opus"},
    "document": {"base": "sonnet", "heavy": "opus"},
    "build": {"base": "sonnet", "heavy": "opus"},
}


def get_model_for_command(
    slash_command: str,
    model_set: Literal["base", "heavy"] = "base",
    override: str | None = None,
) -> str:
    """Get appropriate model for a slash command.

    Args:
        slash_command: The slash command being executed.
        model_set: Whether to use base or heavy models.
        override: Explicit model override from tags.

    Returns:
        Model name: "haiku", "sonnet", or "opus".
    """
    # Explicit override takes precedence
    if override and override in ("haiku", "sonnet", "opus"):
        return override

    # Look up in command map
    command_config = SLASH_COMMAND_MODEL_MAP.get(
        slash_command,
        {"base": "sonnet", "heavy": "sonnet"}  # Default
    )

    return command_config.get(model_set, "sonnet")


def get_model_for_phase(
    phase: str,
    model_set: Literal["base", "heavy"] = "base",
    override: str | None = None,
) -> str:
    """Get appropriate model for a workflow phase.

    Args:
        phase: The workflow phase (plan, implement, test, etc.).
        model_set: Whether to use base or heavy models.
        override: Explicit model override from tags.

    Returns:
        Model name: "haiku", "sonnet", or "opus".
    """
    # Explicit override takes precedence
    if override and override in ("haiku", "sonnet", "opus"):
        return override

    # Look up in phase map
    phase_config = PHASE_MODEL_MAP.get(
        phase,
        {"base": "sonnet", "heavy": "sonnet"}  # Default
    )

    return phase_config.get(model_set, "sonnet")


def get_model_from_tags(tags: list[str]) -> str | None:
    """Extract model override from task tags.

    Args:
        tags: List of task tags.

    Returns:
        Model name if specified, None otherwise.
    """
    for tag in tags:
        if tag in ("opus", "sonnet", "haiku"):
            return tag
    return None


def should_use_heavy_model(task_description: str, tags: list[str]) -> bool:
    """Determine if heavy model set should be used.

    Heuristics:
    - Explicit {opus} tag
    - Complex keywords in description
    - Prototype tasks

    Args:
        task_description: The task description.
        tags: Task tags.

    Returns:
        True if heavy model set recommended.
    """
    # Explicit tag
    if "opus" in tags:
        return True

    # Prototype tasks are complex
    if any(t.startswith("prototype:") for t in tags):
        return True

    # Keywords suggesting complexity
    complex_keywords = [
        "architecture", "redesign", "refactor", "migrate",
        "security", "authentication", "authorization",
        "performance", "optimization", "scale",
        "database", "schema", "migration",
        "api design", "system design",
    ]

    description_lower = task_description.lower()
    if any(kw in description_lower for kw in complex_keywords):
        return True

    return False


def select_model(
    task_description: str,
    tags: list[str] | None = None,
    slash_command: str | None = None,
    phase: str | None = None,
) -> str:
    """Unified model selection function.

    Determines the best model to use based on available context.

    Priority order:
    1. Explicit model tag in tags ({opus}, {sonnet}, {haiku})
    2. Slash command mapping with complexity heuristics
    3. Phase mapping with complexity heuristics
    4. Default to sonnet

    Args:
        task_description: The task description.
        tags: Optional task tags.
        slash_command: Optional slash command being executed.
        phase: Optional workflow phase.

    Returns:
        Model name: "haiku", "sonnet", or "opus".
    """
    tags = tags or []

    # Check for explicit override
    override = get_model_from_tags(tags)
    if override:
        return override

    # Determine model set based on complexity
    model_set: Literal["base", "heavy"] = "heavy" if should_use_heavy_model(task_description, tags) else "base"

    # Use slash command mapping if available
    if slash_command:
        return get_model_for_command(slash_command, model_set)

    # Use phase mapping if available
    if phase:
        return get_model_for_phase(phase, model_set)

    # Default based on complexity
    return "opus" if model_set == "heavy" else "sonnet"
