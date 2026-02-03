"""Self-improving agent learning system.

This module provides:
- Pattern learning from successful task completions
- Issue learning from failures and their solutions
- Expertise section injection into agent prompts
- Learning persistence and aggregation
"""

from .expertise import (
    build_expertise_section,
    get_combined_expertise,
    inject_expertise_into_prompt,
)
from .patterns import (
    Learning,
    LearningType,
    PatternStore,
    extract_learnings_from_feedback,
    get_default_pattern_store,
    record_task_outcome,
)

__all__ = [
    # Patterns
    "Learning",
    "LearningType",
    "PatternStore",
    "extract_learnings_from_feedback",
    "get_default_pattern_store",
    "record_task_outcome",
    # Expertise
    "build_expertise_section",
    "get_combined_expertise",
    "inject_expertise_into_prompt",
]
