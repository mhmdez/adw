"""Failure recovery system for ADW.

This module provides:
- Error classification for appropriate recovery strategies
- Recovery strategies (retry, fix, simplify, escalate)
- Checkpoint system for task state persistence
- Rollback capability for undoing task changes
"""

from .checkpoints import (
    Checkpoint,
    CheckpointManager,
    get_last_checkpoint,
    list_checkpoints,
    load_checkpoint,
    save_checkpoint,
)
from .classifier import ErrorClass, classify_error
from .strategies import (
    EscalateRecoveryStrategy,
    FixRecoveryStrategy,
    RecoveryStrategy,
    RetryRecoveryStrategy,
    SimplifyRecoveryStrategy,
    select_recovery_strategy,
)

__all__ = [
    # Classifier
    "ErrorClass",
    "classify_error",
    # Strategies
    "RecoveryStrategy",
    "RetryRecoveryStrategy",
    "FixRecoveryStrategy",
    "SimplifyRecoveryStrategy",
    "EscalateRecoveryStrategy",
    "select_recovery_strategy",
    # Checkpoints
    "Checkpoint",
    "CheckpointManager",
    "save_checkpoint",
    "load_checkpoint",
    "list_checkpoints",
    "get_last_checkpoint",
]
