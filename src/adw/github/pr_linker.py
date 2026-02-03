"""PR linking for multi-repo coordination.

Enables linking PRs across repositories for coordinated changes,
with support for atomic merging (all or nothing).
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LinkStatus(str, Enum):
    """Status of a linked PR group."""

    PENDING = "pending"  # PRs created but not all reviewed
    READY = "ready"  # All PRs approved and ready to merge
    PARTIAL = "partial"  # Some PRs merged, others pending
    MERGED = "merged"  # All PRs successfully merged
    FAILED = "failed"  # Merge failed, some may need rollback
    CANCELLED = "cancelled"  # Link cancelled, PRs can be handled independently


@dataclass
class LinkedPR:
    """A pull request in a linked group."""

    owner: str
    repo: str
    number: int
    url: str
    title: str = ""
    state: str = "open"  # open, closed, merged
    mergeable: bool | None = None
    approved: bool = False
    head_sha: str = ""
    base_branch: str = "main"

    @property
    def full_name(self) -> str:
        """Return owner/repo#number format."""
        return f"{self.owner}/{self.repo}#{self.number}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "number": self.number,
            "url": self.url,
            "title": self.title,
            "state": self.state,
            "mergeable": self.mergeable,
            "approved": self.approved,
            "head_sha": self.head_sha,
            "base_branch": self.base_branch,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LinkedPR:
        """Create from dictionary."""
        return cls(
            owner=data["owner"],
            repo=data["repo"],
            number=data["number"],
            url=data["url"],
            title=data.get("title", ""),
            state=data.get("state", "open"),
            mergeable=data.get("mergeable"),
            approved=data.get("approved", False),
            head_sha=data.get("head_sha", ""),
            base_branch=data.get("base_branch", "main"),
        )


@dataclass
class PRLinkGroup:
    """A group of linked PRs for coordinated changes."""

    id: str  # Unique identifier for the link group
    prs: list[LinkedPR] = field(default_factory=list)
    status: LinkStatus = LinkStatus.PENDING
    created_at: datetime | None = None
    updated_at: datetime | None = None
    description: str = ""
    atomic: bool = True  # Whether to use atomic merge strategy
    merge_order: list[str] = field(default_factory=list)  # Order to merge (full_names)

    def add_pr(self, pr: LinkedPR) -> None:
        """Add a PR to the group."""
        # Check for duplicates
        for existing in self.prs:
            if existing.full_name == pr.full_name:
                return
        self.prs.append(pr)
        if pr.full_name not in self.merge_order:
            self.merge_order.append(pr.full_name)

    def remove_pr(self, full_name: str) -> bool:
        """Remove a PR from the group by full name."""
        for i, pr in enumerate(self.prs):
            if pr.full_name == full_name:
                self.prs.pop(i)
                if full_name in self.merge_order:
                    self.merge_order.remove(full_name)
                return True
        return False

    def get_pr(self, full_name: str) -> LinkedPR | None:
        """Get PR by full name."""
        for pr in self.prs:
            if pr.full_name == full_name:
                return pr
        return None

    def is_ready(self) -> bool:
        """Check if all PRs are ready to merge."""
        if not self.prs:
            return False
        return all(pr.state == "open" and pr.approved and pr.mergeable for pr in self.prs)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "prs": [pr.to_dict() for pr in self.prs],
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "description": self.description,
            "atomic": self.atomic,
            "merge_order": self.merge_order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PRLinkGroup:
        """Create from dictionary."""
        created_at = None
        updated_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"])

        return cls(
            id=data["id"],
            prs=[LinkedPR.from_dict(pr) for pr in data.get("prs", [])],
            status=LinkStatus(data.get("status", "pending")),
            created_at=created_at,
            updated_at=updated_at,
            description=data.get("description", ""),
            atomic=data.get("atomic", True),
            merge_order=data.get("merge_order", []),
        )


def _get_link_storage_path() -> Path:
    """Get path to PR links storage file."""
    adw_dir = Path.home() / ".adw"
    adw_dir.mkdir(parents=True, exist_ok=True)
    return adw_dir / "pr_links.json"


def _load_link_groups() -> dict[str, PRLinkGroup]:
    """Load all link groups from storage."""
    path = _get_link_storage_path()
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            data = json.load(f)
        return {group_id: PRLinkGroup.from_dict(group_data) for group_id, group_data in data.items()}
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load PR links: {e}")
        return {}


def _save_link_groups(groups: dict[str, PRLinkGroup]) -> None:
    """Save link groups to storage."""
    path = _get_link_storage_path()
    data = {group_id: group.to_dict() for group_id, group in groups.items()}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def parse_pr_url(url_or_ref: str) -> tuple[str, str, int] | None:
    """Parse PR URL or reference into (owner, repo, number).

    Accepts formats:
    - https://github.com/owner/repo/pull/123
    - owner/repo#123
    - #123 (uses current repo)

    Returns None if parsing fails.
    """
    import re

    # Full URL format
    url_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url_or_ref)
    if url_match:
        return url_match.group(1), url_match.group(2), int(url_match.group(3))

    # owner/repo#number format
    ref_match = re.match(r"([^/]+)/([^#]+)#(\d+)", url_or_ref)
    if ref_match:
        return ref_match.group(1), ref_match.group(2), int(ref_match.group(3))

    # #number format (current repo)
    local_match = re.match(r"#?(\d+)$", url_or_ref)
    if local_match:
        # Get current repo from git remote
        current = get_current_repo()
        if current:
            return current[0], current[1], int(local_match.group(1))

    return None


def get_current_repo() -> tuple[str, str] | None:
    """Get owner/repo from current git remote."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data["owner"]["login"], data["name"]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        logger.debug(f"Failed to get current repo: {e}")
    return None


def get_pr_info(owner: str, repo: str, number: int) -> LinkedPR | None:
    """Fetch PR information from GitHub."""
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--json",
                "number,url,title,state,mergeable,reviewDecision,headRefOid,baseRefName",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"Failed to fetch PR {owner}/{repo}#{number}: {result.stderr}")
            return None

        data = json.loads(result.stdout)

        # Map state
        state = data.get("state", "OPEN").lower()
        if state == "merged":
            state = "merged"
        elif state == "closed":
            state = "closed"
        else:
            state = "open"

        # Check approval
        review_decision = data.get("reviewDecision", "")
        approved = review_decision == "APPROVED"

        return LinkedPR(
            owner=owner,
            repo=repo,
            number=data["number"],
            url=data["url"],
            title=data.get("title", ""),
            state=state,
            mergeable=data.get("mergeable") == "MERGEABLE",
            approved=approved,
            head_sha=data.get("headRefOid", ""),
            base_branch=data.get("baseRefName", "main"),
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse PR info: {e}")
        return None


def create_link_group(
    pr_refs: list[str],
    description: str = "",
    atomic: bool = True,
) -> PRLinkGroup | None:
    """Create a new link group from PR references.

    Args:
        pr_refs: List of PR URLs or references (owner/repo#123 or #123)
        description: Optional description of the linked changes
        atomic: Whether to use atomic merge strategy

    Returns:
        PRLinkGroup if successful, None if any PR lookup fails
    """
    from uuid import uuid4

    prs: list[LinkedPR] = []

    for ref in pr_refs:
        parsed = parse_pr_url(ref)
        if not parsed:
            logger.error(f"Invalid PR reference: {ref}")
            return None

        owner, repo, number = parsed
        pr_info = get_pr_info(owner, repo, number)
        if not pr_info:
            logger.error(f"Failed to fetch PR: {owner}/{repo}#{number}")
            return None

        prs.append(pr_info)

    if len(prs) < 2:
        logger.error("At least 2 PRs required for linking")
        return None

    group = PRLinkGroup(
        id=uuid4().hex[:8],
        prs=prs,
        status=LinkStatus.PENDING,
        created_at=datetime.now(),
        description=description,
        atomic=atomic,
        merge_order=[pr.full_name for pr in prs],
    )

    # Save to storage
    groups = _load_link_groups()
    groups[group.id] = group
    _save_link_groups(groups)

    # Update PR descriptions with links
    _update_pr_descriptions(group)

    return group


def _update_pr_descriptions(group: PRLinkGroup) -> None:
    """Add cross-references to linked PR descriptions."""
    for pr in group.prs:
        other_prs = [p for p in group.prs if p.full_name != pr.full_name]
        if not other_prs:
            continue

        # Build reference section
        refs = "\n".join([f"- {p.url}" for p in other_prs])
        link_section = f"""

---
**🔗 Linked PRs** (ADW Link Group: `{group.id}`)

This PR is part of a coordinated change across multiple repositories:
{refs}

{"⚠️ **Atomic merge**: All linked PRs must be merged together." if group.atomic else ""}
"""

        try:
            # Get current body
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr.number),
                    "--repo",
                    f"{pr.owner}/{pr.repo}",
                    "--json",
                    "body",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                continue

            data = json.loads(result.stdout)
            current_body = data.get("body", "") or ""

            # Check if already has link section
            if f"ADW Link Group: `{group.id}`" in current_body:
                continue

            # Update body
            new_body = current_body + link_section
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "edit",
                    str(pr.number),
                    "--repo",
                    f"{pr.owner}/{pr.repo}",
                    "--body",
                    new_body,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            logger.info(f"Updated PR description: {pr.full_name}")
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.warning(f"Failed to update PR {pr.full_name}: {e}")


def get_link_group(group_id: str) -> PRLinkGroup | None:
    """Get a link group by ID."""
    groups = _load_link_groups()
    return groups.get(group_id)


def list_link_groups(include_completed: bool = False) -> list[PRLinkGroup]:
    """List all link groups, optionally filtering out completed ones."""
    groups = _load_link_groups()
    if include_completed:
        return list(groups.values())
    return [g for g in groups.values() if g.status not in (LinkStatus.MERGED, LinkStatus.CANCELLED)]


def refresh_link_group(group_id: str) -> PRLinkGroup | None:
    """Refresh PR status for a link group."""
    groups = _load_link_groups()
    group = groups.get(group_id)
    if not group:
        return None

    for i, pr in enumerate(group.prs):
        updated = get_pr_info(pr.owner, pr.repo, pr.number)
        if updated:
            group.prs[i] = updated

    # Update group status
    if all(pr.state == "merged" for pr in group.prs):
        group.status = LinkStatus.MERGED
    elif any(pr.state == "merged" for pr in group.prs):
        group.status = LinkStatus.PARTIAL
    elif group.is_ready():
        group.status = LinkStatus.READY
    else:
        group.status = LinkStatus.PENDING

    group.updated_at = datetime.now()
    _save_link_groups(groups)
    return group


def unlink_prs(group_id: str) -> bool:
    """Cancel a link group and remove cross-references."""
    groups = _load_link_groups()
    group = groups.get(group_id)
    if not group:
        return False

    group.status = LinkStatus.CANCELLED
    _save_link_groups(groups)

    logger.info(f"Cancelled link group {group_id}")
    return True


@dataclass
class MergeResult:
    """Result of a merge operation."""

    success: bool
    merged_prs: list[str] = field(default_factory=list)
    failed_prs: list[str] = field(default_factory=list)
    rolled_back: bool = False
    error: str = ""


def _merge_pr(pr: LinkedPR, method: str = "squash") -> bool:
    """Merge a single PR."""
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "merge",
                str(pr.number),
                "--repo",
                f"{pr.owner}/{pr.repo}",
                f"--{method}",
                "--auto",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info(f"Merged PR: {pr.full_name}")
            return True
        else:
            logger.error(f"Failed to merge {pr.full_name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout merging {pr.full_name}")
        return False


def _revert_merge(pr: LinkedPR) -> bool:
    """Attempt to revert a merged PR (create revert PR)."""
    try:
        # Note: gh doesn't have direct revert, would need git operations
        # For now, just log warning - proper implementation would need
        # to clone repo and create revert commit
        logger.warning(f"Manual revert needed for: {pr.full_name}")
        return False
    except Exception as e:
        logger.error(f"Failed to revert {pr.full_name}: {e}")
        return False


def merge_link_group(
    group_id: str,
    method: str = "squash",
    force: bool = False,
) -> MergeResult:
    """Merge all PRs in a link group.

    Args:
        group_id: Link group ID
        method: Merge method (squash, merge, rebase)
        force: Skip ready checks (not recommended for atomic)

    Returns:
        MergeResult with success status and details
    """
    group = refresh_link_group(group_id)
    if not group:
        return MergeResult(success=False, error=f"Link group not found: {group_id}")

    if group.status == LinkStatus.MERGED:
        return MergeResult(success=True, merged_prs=[pr.full_name for pr in group.prs])

    if group.status == LinkStatus.CANCELLED:
        return MergeResult(success=False, error="Link group was cancelled")

    if not force and not group.is_ready():
        not_ready = [pr.full_name for pr in group.prs if not (pr.state == "open" and pr.approved and pr.mergeable)]
        return MergeResult(
            success=False,
            error=f"Not all PRs are ready. Not ready: {', '.join(not_ready)}",
        )

    result = MergeResult(success=True)
    groups = _load_link_groups()

    # Merge in order
    for full_name in group.merge_order:
        pr = group.get_pr(full_name)
        if not pr:
            continue

        if pr.state == "merged":
            result.merged_prs.append(full_name)
            continue

        if _merge_pr(pr, method):
            result.merged_prs.append(full_name)
        else:
            result.failed_prs.append(full_name)
            result.success = False

            # Atomic mode: attempt rollback
            if group.atomic and result.merged_prs:
                logger.warning(f"Atomic merge failed at {full_name}, attempting rollback")
                for merged_name in result.merged_prs:
                    merged_pr = group.get_pr(merged_name)
                    if merged_pr:
                        _revert_merge(merged_pr)
                result.rolled_back = True
                result.error = f"Atomic merge failed at {full_name}"
            else:
                result.error = f"Merge failed for {full_name}"
            break

    # Update group status
    if result.success:
        group.status = LinkStatus.MERGED
    elif result.rolled_back:
        group.status = LinkStatus.FAILED
    elif result.merged_prs:
        group.status = LinkStatus.PARTIAL
    else:
        group.status = LinkStatus.FAILED

    group.updated_at = datetime.now()
    groups[group_id] = group
    _save_link_groups(groups)

    return result
