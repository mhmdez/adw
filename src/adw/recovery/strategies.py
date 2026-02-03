"""Recovery strategies for failed tasks.

Provides different strategies for recovering from failures:
- RetryRecoveryStrategy: Simple retry with exponential backoff
- FixRecoveryStrategy: Attempt to fix based on error type
- SimplifyRecoveryStrategy: Reduce task scope
- EscalateRecoveryStrategy: Give up and notify human
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .classifier import ErrorClass, classify_error


class RecoveryStrategyType(str, Enum):
    """Types of recovery strategies."""

    RETRY = "retry"  # Simple retry with backoff
    FIX = "fix"  # Attempt to fix the error
    SIMPLIFY = "simplify"  # Reduce task scope
    ESCALATE = "escalate"  # Give up and notify human


@dataclass
class RecoveryResult:
    """Result of applying a recovery strategy."""

    success: bool
    strategy_used: RecoveryStrategyType
    message: str
    should_continue: bool  # Whether to continue with more attempts
    modified_context: dict[str, Any] | None = None  # Additional context for retry
    wait_seconds: float = 0.0  # Time to wait before next attempt


class RecoveryStrategy(ABC):
    """Base class for recovery strategies."""

    @property
    @abstractmethod
    def strategy_type(self) -> RecoveryStrategyType:
        """Return the strategy type."""
        ...

    @abstractmethod
    def apply(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Apply the recovery strategy.

        Args:
            error_message: The error that caused the failure.
            attempt_number: Current attempt number (1-indexed).
            max_attempts: Maximum allowed attempts.
            context: Optional context about the failure.

        Returns:
            RecoveryResult indicating outcome and next steps.
        """
        ...

    @abstractmethod
    def get_retry_context(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
    ) -> str:
        """Generate context to inject into retry prompt.

        Args:
            error_message: The error that caused the failure.
            attempt_number: Current attempt number.
            max_attempts: Maximum allowed attempts.

        Returns:
            Formatted string to inject into the agent's prompt.
        """
        ...


class RetryRecoveryStrategy(RecoveryStrategy):
    """Simple retry with exponential backoff.

    Best for: Network errors, rate limits, temporary failures.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
    ):
        """Initialize retry strategy.

        Args:
            base_delay: Initial delay in seconds.
            max_delay: Maximum delay cap.
            backoff_factor: Multiplier for exponential backoff.
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    @property
    def strategy_type(self) -> RecoveryStrategyType:
        return RecoveryStrategyType.RETRY

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)

    def apply(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        remaining = max_attempts - attempt_number
        delay = self._calculate_delay(attempt_number)

        if remaining <= 0:
            return RecoveryResult(
                success=False,
                strategy_used=self.strategy_type,
                message=f"Max retries ({max_attempts}) exhausted",
                should_continue=False,
                wait_seconds=0,
            )

        return RecoveryResult(
            success=True,
            strategy_used=self.strategy_type,
            message=f"Retrying after {delay:.1f}s delay ({remaining} attempts remaining)",
            should_continue=True,
            wait_seconds=delay,
            modified_context={"retry_reason": "transient_error"},
        )

    def get_retry_context(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
    ) -> str:
        remaining = max_attempts - attempt_number
        return (
            f"⚠️ RETRY ATTEMPT {attempt_number} of {max_attempts}\n\n"
            f"Previous attempt failed with a transient error:\n"
            f"  {error_message}\n\n"
            f"This appears to be a temporary issue. Please try again.\n"
            f"You have {remaining} attempt(s) remaining."
        )


class FixRecoveryStrategy(RecoveryStrategy):
    """Attempt to fix the error based on its type.

    Best for: Test failures, lint errors, syntax errors.
    """

    @property
    def strategy_type(self) -> RecoveryStrategyType:
        return RecoveryStrategyType.FIX

    def apply(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        classification = classify_error(error_message)
        remaining = max_attempts - attempt_number

        if remaining <= 0:
            return RecoveryResult(
                success=False,
                strategy_used=self.strategy_type,
                message="Max fix attempts exhausted",
                should_continue=False,
            )

        return RecoveryResult(
            success=True,
            strategy_used=self.strategy_type,
            message=f"Attempting to fix: {classification.reason}",
            should_continue=True,
            modified_context={
                "fix_reason": classification.reason,
                "suggested_action": classification.suggested_action,
            },
        )

    def get_retry_context(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
    ) -> str:
        classification = classify_error(error_message)
        remaining = max_attempts - attempt_number

        return (
            f"⚠️ FIX REQUIRED - Attempt {attempt_number} of {max_attempts}\n\n"
            f"Error Type: {classification.reason}\n"
            f"Confidence: {classification.confidence:.0%}\n\n"
            f"Error Details:\n"
            f"  {error_message}\n\n"
            f"Suggested Action: {classification.suggested_action}\n\n"
            f"Please analyze the error and fix the issue.\n"
            f"You have {remaining} attempt(s) remaining.\n\n"
            f"Focus on:\n"
            f"  1. Understanding the root cause\n"
            f"  2. Making targeted fixes\n"
            f"  3. Verifying the fix resolves the issue"
        )


class SimplifyRecoveryStrategy(RecoveryStrategy):
    """Reduce task scope to make progress.

    Best for: Complex tasks that keep failing, scope creep issues.
    """

    @property
    def strategy_type(self) -> RecoveryStrategyType:
        return RecoveryStrategyType.SIMPLIFY

    def apply(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        remaining = max_attempts - attempt_number

        if remaining <= 0:
            return RecoveryResult(
                success=False,
                strategy_used=self.strategy_type,
                message="Unable to simplify further",
                should_continue=False,
            )

        return RecoveryResult(
            success=True,
            strategy_used=self.strategy_type,
            message="Simplifying task scope",
            should_continue=True,
            modified_context={
                "simplification_requested": True,
                "original_error": error_message,
            },
        )

    def get_retry_context(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
    ) -> str:
        return (
            f"⚠️ SIMPLIFICATION REQUIRED - Attempt {attempt_number} of {max_attempts}\n\n"
            f"Multiple attempts have failed. The task may be too complex.\n\n"
            f"Last Error:\n"
            f"  {error_message}\n\n"
            f"This is your last chance. Please SIMPLIFY the approach:\n\n"
            f"  1. Implement only the CORE functionality\n"
            f"  2. Skip edge cases and error handling for now\n"
            f"  3. Use the simplest possible solution\n"
            f"  4. Add TODO comments for deferred work\n"
            f"  5. Break into smaller, testable pieces\n\n"
            f"It's better to deliver partial working code than nothing.\n"
            f"Focus on making SOMETHING work first."
        )


class EscalateRecoveryStrategy(RecoveryStrategy):
    """Give up and notify human.

    Best for: Fatal errors, unrecoverable failures.
    """

    def __init__(
        self,
        notify_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        """Initialize escalation strategy.

        Args:
            notify_callback: Optional callback to notify human.
                             Called with (message, context) args.
        """
        self.notify_callback = notify_callback

    @property
    def strategy_type(self) -> RecoveryStrategyType:
        return RecoveryStrategyType.ESCALATE

    def apply(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        classification = classify_error(error_message)

        # Notify human if callback provided
        if self.notify_callback:
            self.notify_callback(
                f"Task escalated: {classification.reason}",
                {
                    "error": error_message,
                    "classification": classification._asdict(),
                    "context": context,
                },
            )

        return RecoveryResult(
            success=False,
            strategy_used=self.strategy_type,
            message=f"Escalating to human: {classification.reason}",
            should_continue=False,
            modified_context={
                "escalation_reason": classification.reason,
                "suggested_action": classification.suggested_action,
            },
        )

    def get_retry_context(
        self,
        error_message: str,
        attempt_number: int,
        max_attempts: int,
    ) -> str:
        classification = classify_error(error_message)
        return (
            f"❌ ESCALATION - Task requires human intervention\n\n"
            f"Error Type: {classification.reason}\n\n"
            f"Error Details:\n"
            f"  {error_message}\n\n"
            f"This error cannot be automatically recovered. "
            f"Human review is required.\n\n"
            f"Suggested Action: {classification.suggested_action}\n\n"
            f"Please save your work and document what was attempted."
        )


def select_recovery_strategy(
    error_message: str,
    attempt_number: int,
    max_attempts: int = 3,
) -> RecoveryStrategy:
    """Select the appropriate recovery strategy based on error and attempt.

    Strategy selection logic:
    - Attempt 1-2: Based on error classification
        - Retriable → RetryRecoveryStrategy
        - Fixable → FixRecoveryStrategy
        - Fatal → EscalateRecoveryStrategy
        - Unknown → FixRecoveryStrategy (assume fixable)
    - Attempt 3: SimplifyRecoveryStrategy
    - Attempt 4+: EscalateRecoveryStrategy

    Args:
        error_message: The error that caused the failure.
        attempt_number: Current attempt number (1-indexed).
        max_attempts: Maximum allowed attempts.

    Returns:
        Appropriate RecoveryStrategy instance.
    """
    # Always escalate after max attempts
    if attempt_number > max_attempts:
        return EscalateRecoveryStrategy()

    # Final attempt: try to simplify
    if attempt_number == max_attempts:
        return SimplifyRecoveryStrategy()

    # Classify the error
    classification = classify_error(error_message)

    # Select strategy based on classification
    if classification.error_class == ErrorClass.RETRIABLE:
        return RetryRecoveryStrategy()
    elif classification.error_class == ErrorClass.FIXABLE:
        return FixRecoveryStrategy()
    elif classification.error_class == ErrorClass.FATAL:
        return EscalateRecoveryStrategy()
    else:
        # Unknown errors: try to fix on early attempts
        if attempt_number <= 2:
            return FixRecoveryStrategy()
        else:
            return SimplifyRecoveryStrategy()


@dataclass
class RecoveryOrchestrator:
    """Orchestrates recovery attempts across multiple strategies.

    Provides a higher-level interface for managing the recovery process.
    """

    max_attempts: int = 3
    retry_strategy: RetryRecoveryStrategy = field(default_factory=RetryRecoveryStrategy)
    fix_strategy: FixRecoveryStrategy = field(default_factory=FixRecoveryStrategy)
    simplify_strategy: SimplifyRecoveryStrategy = field(default_factory=SimplifyRecoveryStrategy)
    escalate_strategy: EscalateRecoveryStrategy = field(default_factory=EscalateRecoveryStrategy)
    current_attempt: int = 0
    attempt_history: list[dict[str, Any]] = field(default_factory=list)

    def get_strategy(self, error_message: str) -> RecoveryStrategy:
        """Get the appropriate strategy for the current state.

        Args:
            error_message: The error to recover from.

        Returns:
            The appropriate RecoveryStrategy.
        """
        return select_recovery_strategy(
            error_message,
            self.current_attempt,
            self.max_attempts,
        )

    def attempt_recovery(
        self,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """Attempt recovery from an error.

        Args:
            error_message: The error to recover from.
            context: Optional context about the failure.

        Returns:
            RecoveryResult indicating outcome and next steps.
        """
        self.current_attempt += 1

        strategy = self.get_strategy(error_message)
        result = strategy.apply(
            error_message,
            self.current_attempt,
            self.max_attempts,
            context,
        )

        # Record attempt
        self.attempt_history.append(
            {
                "attempt": self.current_attempt,
                "strategy": strategy.strategy_type.value,
                "error": error_message,
                "success": result.success,
                "message": result.message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return result

    def get_retry_context(self, error_message: str) -> str:
        """Get retry context for the current attempt.

        Args:
            error_message: The error to include in context.

        Returns:
            Formatted retry context string.
        """
        strategy = self.get_strategy(error_message)
        return strategy.get_retry_context(
            error_message,
            self.current_attempt,
            self.max_attempts,
        )

    def reset(self) -> None:
        """Reset the orchestrator for a new task."""
        self.current_attempt = 0
        self.attempt_history = []

    @property
    def should_escalate(self) -> bool:
        """Check if we should escalate to human."""
        return self.current_attempt >= self.max_attempts

    @property
    def attempts_remaining(self) -> int:
        """Get the number of attempts remaining."""
        return max(0, self.max_attempts - self.current_attempt)
