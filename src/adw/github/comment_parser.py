"""Comment parser for PR review feedback.

Extracts actionable feedback from review comments.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .review_watcher import ReviewComment

logger = logging.getLogger(__name__)


class CommentType(str, Enum):
    """Type of review comment."""

    ACTIONABLE = "actionable"  # Requires code changes
    QUESTION = "question"  # Asking for clarification
    APPROVAL = "approval"  # Positive feedback
    DISCUSSION = "discussion"  # General discussion
    ADW_GENERATED = "adw_generated"  # Comment from ADW itself


class ActionPriority(str, Enum):
    """Priority level for actionable comments."""

    HIGH = "high"  # Must be addressed
    MEDIUM = "medium"  # Should be addressed
    LOW = "low"  # Nice to have


@dataclass
class ActionableComment:
    """A parsed actionable comment from a review."""

    original_comment: ReviewComment
    comment_type: CommentType
    action_description: str
    priority: ActionPriority = ActionPriority.MEDIUM
    file_path: str | None = None
    line_number: int | None = None
    suggested_change: str | None = None
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "comment_id": self.original_comment.id,
            "comment_type": self.comment_type.value,
            "action_description": self.action_description,
            "priority": self.priority.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "suggested_change": self.suggested_change,
            "keywords": self.keywords,
            "author": self.original_comment.author,
        }

    @property
    def is_actionable(self) -> bool:
        """Check if this comment requires action."""
        return self.comment_type == CommentType.ACTIONABLE


# Patterns that indicate actionable feedback
ACTIONABLE_PATTERNS = [
    # Direct requests
    (r"please\s+(change|update|fix|add|remove|rename|refactor)", ActionPriority.HIGH),
    (r"can\s+you\s+(change|update|fix|add|remove|rename|refactor)", ActionPriority.MEDIUM),
    (r"could\s+you\s+(change|update|fix|add|remove|rename|refactor)", ActionPriority.MEDIUM),
    (r"would\s+you\s+(change|update|fix|add|remove|rename|refactor)", ActionPriority.LOW),
    # Imperative commands
    (
        r"^(change|update|fix|add|remove|rename|refactor|move|extract|inline)\s+",
        ActionPriority.HIGH,
    ),
    # Suggestions
    (r"this\s+should\s+(be|have|use|return|include)", ActionPriority.MEDIUM),
    (
        r"(should|must|need\s+to)\s+(be\s+)?(changed|updated|fixed|added|removed)",
        ActionPriority.HIGH,
    ),
    (r"consider\s+(changing|updating|adding|removing|using)", ActionPriority.LOW),
    # Specific patterns
    (r"add\s+error\s+handling", ActionPriority.HIGH),
    (r"add\s+(null|undefined)\s+check", ActionPriority.HIGH),
    (r"add\s+(type|types|typing)", ActionPriority.MEDIUM),
    (r"add\s+(test|tests|testing)", ActionPriority.MEDIUM),
    (r"add\s+(comment|comments|documentation|docs)", ActionPriority.LOW),
    # Negative feedback
    (r"(this|that)\s+is\s+(wrong|incorrect|broken|buggy)", ActionPriority.HIGH),
    (r"(this|that)\s+(doesn't|does\s+not)\s+work", ActionPriority.HIGH),
    (r"(there's|there\s+is)\s+a\s+(bug|issue|problem|error)", ActionPriority.HIGH),
    # Style/formatting
    (r"(missing|needs)\s+(semicolon|comma|bracket|parenthesis)", ActionPriority.MEDIUM),
    (r"(indent|indentation|formatting)\s+(is|should|needs)", ActionPriority.LOW),
]

# Patterns that indicate non-actionable comments
NON_ACTIONABLE_PATTERNS = [
    r"^\s*\?\s*$",  # Just a question mark
    r"^\s*lgtm\s*$",  # Looks good to me
    r"^\s*\+1\s*$",  # Thumbs up
    r"^(nice|great|good|awesome|excellent|perfect)\s*(work|job|code)?[!\s]*$",  # Praise
    r"^(thanks|thank\s+you|ty)[!\s]*$",  # Thanks
    r"^\s*👍|✅|🎉|💯",  # Emoji approval
]

# Patterns that indicate questions
QUESTION_PATTERNS = [
    r"\?\s*$",  # Ends with question mark
    r"^(why|what|how|when|where|which|who)\s+",  # Question words
    r"^(is|are|was|were|do|does|did|can|could|would|should)\s+",  # Question starters
    r"(curious|wondering|confused|unclear)",  # Uncertainty expressions
]

# ADW marker pattern
ADW_MARKER_PATTERN = r"<!--\s*ADW:[a-f0-9]+\s*-->"


def parse_review_comment(comment: ReviewComment) -> ActionableComment:
    """Parse a review comment to determine its type and extract action.

    Args:
        comment: The ReviewComment to parse.

    Returns:
        ActionableComment with parsed information.
    """
    body = comment.body.strip()
    body_lower = body.lower()

    # Check if it's an ADW-generated comment
    if re.search(ADW_MARKER_PATTERN, body, re.IGNORECASE):
        return ActionableComment(
            original_comment=comment,
            comment_type=CommentType.ADW_GENERATED,
            action_description="",
            file_path=comment.path,
            line_number=comment.line,
        )

    # Check for non-actionable patterns first
    for pattern in NON_ACTIONABLE_PATTERNS:
        if re.match(pattern, body_lower, re.IGNORECASE):
            return ActionableComment(
                original_comment=comment,
                comment_type=CommentType.APPROVAL,
                action_description="",
                file_path=comment.path,
                line_number=comment.line,
            )

    # Check for questions
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, body_lower, re.IGNORECASE):
            # Questions might still be actionable if they contain action patterns
            has_action = False
            for action_pattern, _ in ACTIONABLE_PATTERNS:
                if re.search(action_pattern, body_lower, re.IGNORECASE):
                    has_action = True
                    break

            if not has_action:
                return ActionableComment(
                    original_comment=comment,
                    comment_type=CommentType.QUESTION,
                    action_description=body,
                    file_path=comment.path,
                    line_number=comment.line,
                )

    # Check for actionable patterns
    priority = ActionPriority.MEDIUM
    keywords = []

    for pattern, pat_priority in ACTIONABLE_PATTERNS:
        match = re.search(pattern, body_lower, re.IGNORECASE)
        if match:
            keywords.append(match.group(0))
            # Use the highest priority found
            if pat_priority == ActionPriority.HIGH:
                priority = ActionPriority.HIGH
            elif pat_priority == ActionPriority.LOW and priority != ActionPriority.HIGH:
                priority = ActionPriority.LOW

    if keywords:
        # Extract suggested change if present
        suggested_change = _extract_suggestion(body)

        return ActionableComment(
            original_comment=comment,
            comment_type=CommentType.ACTIONABLE,
            action_description=body,
            priority=priority,
            file_path=comment.path,
            line_number=comment.line,
            suggested_change=suggested_change,
            keywords=keywords,
        )

    # Default to discussion
    return ActionableComment(
        original_comment=comment,
        comment_type=CommentType.DISCUSSION,
        action_description=body,
        file_path=comment.path,
        line_number=comment.line,
    )


def _extract_suggestion(body: str) -> str | None:
    """Extract code suggestion from comment body.

    GitHub suggestions are in a special format:
    ```suggestion
    code here
    ```

    Args:
        body: Comment body text.

    Returns:
        Suggested code or None.
    """
    # GitHub suggestion block
    match = re.search(r"```suggestion\s*\n(.*?)\n```", body, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Code block that might be a suggestion
    match = re.search(r"```\w*\s*\n(.*?)\n```", body, re.DOTALL)
    if match:
        # Only return if the comment indicates it's a suggestion
        if re.search(r"(should\s+be|change\s+to|try\s+this|like\s+this)", body.lower()):
            return match.group(1).strip()

    # Inline code that might be a suggestion
    match = re.search(r"`([^`]+)`", body)
    if match and re.search(r"(change|rename|use|should\s+be)", body.lower()):
        return match.group(1)

    return None


@dataclass
class CommentParser:
    """Parser for batches of review comments."""

    comments: list[ReviewComment] = field(default_factory=list)

    def parse_all(self) -> list[ActionableComment]:
        """Parse all comments.

        Returns:
            List of ActionableComment objects.
        """
        return [parse_review_comment(c) for c in self.comments]

    def get_actionable(self) -> list[ActionableComment]:
        """Get only actionable comments.

        Returns:
            List of actionable comments.
        """
        return [c for c in self.parse_all() if c.is_actionable]

    def get_by_file(self) -> dict[str, list[ActionableComment]]:
        """Group comments by file path.

        Returns:
            Dict mapping file paths to comments.
        """
        by_file: dict[str, list[ActionableComment]] = {}

        for parsed in self.parse_all():
            path = parsed.file_path or "__general__"
            if path not in by_file:
                by_file[path] = []
            by_file[path].append(parsed)

        return by_file

    def get_high_priority(self) -> list[ActionableComment]:
        """Get high priority actionable comments.

        Returns:
            List of high priority comments.
        """
        return [c for c in self.get_actionable() if c.priority == ActionPriority.HIGH]

    def group_related_comments(self) -> list[list[ActionableComment]]:
        """Group related comments together.

        Comments are related if they:
        - Are on the same file
        - Are replies to each other
        - Have similar keywords

        Returns:
            List of comment groups.
        """
        parsed = self.get_actionable()
        if not parsed:
            return []

        # Group by file path first
        by_file = self.get_by_file()
        groups = []

        for path, comments in by_file.items():
            if path == "__general__":
                # General comments are each their own group
                for c in comments:
                    if c.is_actionable:
                        groups.append([c])
            else:
                # File comments can be grouped by proximity
                actionable = [c for c in comments if c.is_actionable]
                if actionable:
                    groups.append(actionable)

        return groups

    def summary(self) -> str:
        """Get a summary of parsed comments.

        Returns:
            Human-readable summary.
        """
        parsed = self.parse_all()
        actionable = [c for c in parsed if c.is_actionable]
        questions = [c for c in parsed if c.comment_type == CommentType.QUESTION]
        approvals = [c for c in parsed if c.comment_type == CommentType.APPROVAL]

        return (
            f"Comments: {len(parsed)} total, "
            f"{len(actionable)} actionable, "
            f"{len(questions)} questions, "
            f"{len(approvals)} approvals"
        )
