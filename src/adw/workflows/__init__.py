"""ADW Workflows.

This module provides workflow definitions and execution engines for ADW.

Primary Workflow:
- adaptive: Single unified workflow that auto-detects task complexity
  - MINIMAL complexity: Direct implementation (replaces simple)
  - STANDARD complexity: Plan + Implement (replaces standard)
  - FULL complexity: Full SDLC (replaces sdlc)

Legacy Workflows (deprecated, use adaptive instead):
- simple: Quick build-only workflow → use adaptive with complexity=minimal
- standard: Plan → Implement workflow → use adaptive with complexity=standard
- sdlc: Full SDLC workflow → use adaptive with complexity=full

Special Workflows:
- prototype: Rapid application scaffolding workflow
- bug-fix: Focused bug fixing (DSL workflow)

Workflow DSL:
The dsl module provides YAML-based workflow definitions that can be customized
without modifying ADW source code. Workflows are stored in ~/.adw/workflows/.
"""

from .adaptive import (
    AdaptiveConfig,
    AdaptivePhase,
    PhaseConfig,
    PhaseResult,
    TaskComplexity,
    detect_complexity,
    format_results_summary,
    run_adaptive_workflow,
    # Backward compatibility aliases
    run_sdlc_workflow,
    run_simple_workflow,
    run_standard_workflow,
)
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
    # Adaptive workflow (primary)
    "run_adaptive_workflow",
    "detect_complexity",
    "TaskComplexity",
    "AdaptiveConfig",
    "AdaptivePhase",
    "PhaseConfig",
    "PhaseResult",
    "format_results_summary",
    # Backward compatibility
    "run_simple_workflow",
    "run_standard_workflow",
    "run_sdlc_workflow",
    # DSL classes
    "PhaseCondition",
    "PhaseDefinition",
    "LoopCondition",
    "WorkflowDefinition",
    "PromptTemplate",
    # DSL parsing/serialization
    "parse_workflow_yaml",
    "load_workflow",
    "save_workflow",
    "serialize_workflow",
    # DSL library management
    "list_workflows",
    "get_workflow",
    "create_workflow",
    "delete_workflow",
    "get_active_workflow_name",
    "set_active_workflow",
    "get_workflows_dir",
    "ensure_builtin_workflows",
]
