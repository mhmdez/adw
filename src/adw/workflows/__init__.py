"""ADW Workflows.

This module provides workflow definitions and execution engines for ADW.

Available workflows:
- simple: Quick build-only workflow
- standard: Plan → Implement → Update workflow
- sdlc: Full Software Development Lifecycle (Plan → Implement → Test → Review → Document → Release)
- prototype: Rapid prototyping workflow
- bug-fix: Focused bug fixing workflow

Workflow DSL:
The dsl module provides YAML-based workflow definitions that can be customized
without modifying ADW source code. Workflows are stored in ~/.adw/workflows/.
"""

from .dsl import (
    LoopCondition,
    # Core classes
    PhaseCondition,
    PhaseDefinition,
    PromptTemplate,
    WorkflowDefinition,
    create_workflow,
    delete_workflow,
    ensure_builtin_workflows,
    get_active_workflow_name,
    get_workflow,
    get_workflows_dir,
    # Library management
    list_workflows,
    load_workflow,
    # Parsing/serialization
    parse_workflow_yaml,
    save_workflow,
    serialize_workflow,
    set_active_workflow,
)

__all__ = [
    # Core classes
    "PhaseCondition",
    "PhaseDefinition",
    "LoopCondition",
    "WorkflowDefinition",
    "PromptTemplate",
    # Parsing/serialization
    "parse_workflow_yaml",
    "load_workflow",
    "save_workflow",
    "serialize_workflow",
    # Library management
    "list_workflows",
    "get_workflow",
    "create_workflow",
    "delete_workflow",
    "get_active_workflow_name",
    "set_active_workflow",
    "get_workflows_dir",
    "ensure_builtin_workflows",
]
