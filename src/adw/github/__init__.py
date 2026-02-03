"""GitHub integration for ADW feedback loops."""

from .approval_gate import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalStatus,
    approve_task,
    create_approval_request,
    reject_task,
)
from .auto_fix import (
    AutoFixer,
    FixResult,
    apply_review_fixes,
)
from .comment_parser import (
    ActionableComment,
    CommentParser,
    CommentType,
    parse_review_comment,
)
from .pr_linker import (
    LinkedPR,
    LinkStatus,
    MergeResult,
    PRLinkGroup,
    create_link_group,
    get_link_group,
    list_link_groups,
    merge_link_group,
    parse_pr_url,
    refresh_link_group,
    unlink_prs,
)
from .review_watcher import (
    PRReviewWatcher,
    PRStatus,
    ReviewComment,
    get_pr_review_comments,
    get_pr_status,
)

__all__ = [
    # Review watcher
    "PRReviewWatcher",
    "ReviewComment",
    "get_pr_review_comments",
    "get_pr_status",
    "PRStatus",
    # Comment parser
    "CommentParser",
    "ActionableComment",
    "CommentType",
    "parse_review_comment",
    # Auto fix
    "AutoFixer",
    "FixResult",
    "apply_review_fixes",
    # Approval gate
    "ApprovalGate",
    "ApprovalRequest",
    "ApprovalStatus",
    "create_approval_request",
    "approve_task",
    "reject_task",
    # PR Linker
    "LinkedPR",
    "LinkStatus",
    "PRLinkGroup",
    "MergeResult",
    "create_link_group",
    "get_link_group",
    "list_link_groups",
    "merge_link_group",
    "refresh_link_group",
    "unlink_prs",
    "parse_pr_url",
]
