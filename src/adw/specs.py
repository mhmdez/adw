"""Spec parsing and management for ADW."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SpecStatus(Enum):
    """Spec status values."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


@dataclass
class Spec:
    """A feature specification."""

    path: Path
    name: str
    title: str
    status: SpecStatus
    description: str = ""
    raw_content: str = ""

    @property
    def needs_approval(self) -> bool:
        """Check if spec is waiting for approval."""
        return self.status == SpecStatus.PENDING_APPROVAL


def parse_spec(content: str, path: Path) -> Spec:
    """Parse a spec from markdown content.

    Expected format:
    ```markdown
    # Feature Title

    Status: PENDING_APPROVAL

    ## Description
    ...
    ```

    Args:
        content: Raw markdown content.
        path: Path to the spec file.

    Returns:
        Parsed Spec object.
    """
    lines = content.split("\n")

    # Extract title from first H1
    title = path.stem.replace("-", " ").replace("_", " ").title()
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Extract status
    status = SpecStatus.DRAFT
    status_pattern = re.compile(r"^Status:\s*(\w+)", re.IGNORECASE)
    for line in lines:
        match = status_pattern.match(line)
        if match:
            status_str = match.group(1).lower()
            # Map common variations
            status_map = {
                "pending_approval": SpecStatus.PENDING_APPROVAL,
                "pending": SpecStatus.PENDING_APPROVAL,
                "approved": SpecStatus.APPROVED,
                "implemented": SpecStatus.IMPLEMENTED,
                "rejected": SpecStatus.REJECTED,
                "draft": SpecStatus.DRAFT,
            }
            status = status_map.get(status_str, SpecStatus.DRAFT)
            break

    # Extract description (content between ## Description and next ##)
    description = ""
    in_description = False
    desc_lines: list[str] = []
    for line in lines:
        if line.startswith("## Description"):
            in_description = True
            continue
        if in_description:
            if line.startswith("## "):
                break
            desc_lines.append(line)
    description = "\n".join(desc_lines).strip()

    return Spec(
        path=path,
        name=path.stem,
        title=title,
        status=status,
        description=description,
        raw_content=content,
    )


def load_spec(path: Path) -> Spec | None:
    """Load a spec from a file.

    Args:
        path: Path to the spec file.

    Returns:
        Parsed Spec object, or None if file doesn't exist.
    """
    if not path.exists():
        return None

    content = path.read_text()
    return parse_spec(content, path)


def load_all_specs(specs_dir: Path | None = None) -> list[Spec]:
    """Load all specs from the specs directory.

    Args:
        specs_dir: Path to specs directory. Defaults to ./specs.

    Returns:
        List of parsed Spec objects.
    """
    if specs_dir is None:
        specs_dir = Path.cwd() / "specs"

    if not specs_dir.exists():
        return []

    specs: list[Spec] = []
    for path in specs_dir.glob("*.md"):
        spec = load_spec(path)
        if spec:
            specs.append(spec)

    # Sort by name
    specs.sort(key=lambda s: s.name)
    return specs


def get_pending_specs(specs_dir: Path | None = None) -> list[Spec]:
    """Get specs that are pending approval.

    Args:
        specs_dir: Path to specs directory.

    Returns:
        List of specs with PENDING_APPROVAL status.
    """
    all_specs = load_all_specs(specs_dir)
    return [s for s in all_specs if s.needs_approval]


def update_spec_status(
    spec_path: Path,
    new_status: SpecStatus,
) -> bool:
    """Update a spec's status.

    Args:
        spec_path: Path to the spec file.
        new_status: The new status.

    Returns:
        True if spec was updated.
    """
    if not spec_path.exists():
        return False

    content = spec_path.read_text()
    lines = content.split("\n")
    updated = False

    status_pattern = re.compile(r"^(Status:\s*)(\w+)", re.IGNORECASE)

    for i, line in enumerate(lines):
        match = status_pattern.match(line)
        if match:
            prefix = match.group(1)
            lines[i] = f"{prefix}{new_status.value.upper()}"
            updated = True
            break

    if not updated:
        # Add status line after title if not found
        for i, line in enumerate(lines):
            if line.startswith("# "):
                lines.insert(i + 1, "")
                lines.insert(i + 2, f"Status: {new_status.value.upper()}")
                updated = True
                break

    if updated:
        spec_path.write_text("\n".join(lines))

    return updated
