"""Context bundles for ADW.

Save and restore file context from sessions.
"""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default bundles directory
DEFAULT_BUNDLES_DIR = Path(".adw/bundles")


@dataclass
class BundleFile:
    """A file included in a context bundle."""

    path: str
    lines_start: int = 1
    lines_end: int | None = None
    content_hash: str | None = None
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "lines_start": self.lines_start,
            "lines_end": self.lines_end,
            "content_hash": self.content_hash,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BundleFile:
        """Create from dictionary."""
        return cls(
            path=data["path"],
            lines_start=data.get("lines_start", 1),
            lines_end=data.get("lines_end"),
            content_hash=data.get("content_hash"),
            size_bytes=data.get("size_bytes", 0),
        )


@dataclass
class Bundle:
    """A context bundle capturing files accessed during a session."""

    task_id: str
    created_at: datetime
    files: list[BundleFile] = field(default_factory=list)
    description: str = ""
    total_lines: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat(),
            "files": [f.to_dict() for f in self.files],
            "description": self.description,
            "total_lines": self.total_lines,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bundle:
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            files=[BundleFile.from_dict(f) for f in data.get("files", [])],
            description=data.get("description", ""),
            total_lines=data.get("total_lines", 0),
            tags=data.get("tags", []),
        )

    @property
    def file_count(self) -> int:
        """Number of files in the bundle."""
        return len(self.files)

    @property
    def file_paths(self) -> set[str]:
        """Set of file paths in the bundle."""
        return {f.path for f in self.files}

    def summary(self) -> str:
        """Human-readable summary of the bundle."""
        return (
            f"Bundle {self.task_id}: {self.file_count} files, "
            f"{self.total_lines} lines ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
        )


def _get_bundles_dir(base_path: Path | None = None) -> Path:
    """Get the bundles directory, creating if needed."""
    path = base_path or Path.cwd()
    bundles_dir = path / DEFAULT_BUNDLES_DIR
    bundles_dir.mkdir(parents=True, exist_ok=True)
    return bundles_dir


def _is_binary_file(file_path: Path) -> bool:
    """Check if a file is likely binary."""
    binary_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".pyc",
        ".pyo",
        ".class",
        ".o",
        ".a",
        ".lib",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wav",
        ".ogg",
        ".webm",
        ".db",
        ".sqlite",
        ".sqlite3",
    }
    return file_path.suffix.lower() in binary_extensions


def save_bundle(
    task_id: str,
    files: list[str | Path | dict[str, Any]],
    description: str = "",
    tags: list[str] | None = None,
    base_path: Path | None = None,
) -> Bundle:
    """Save a context bundle.

    Args:
        task_id: Unique task identifier.
        files: List of file paths (strings/Paths) or dicts with path/lines info.
        description: Description of the bundle.
        tags: Optional tags for categorization.
        base_path: Base path for bundle storage.

    Returns:
        The saved Bundle object.
    """
    bundles_dir = _get_bundles_dir(base_path)
    project_path = base_path or Path.cwd()

    bundle_files = []
    total_lines = 0

    for file_entry in files:
        if isinstance(file_entry, dict):
            path_str = file_entry.get("path", "")
            lines_start = file_entry.get("lines_start", 1)
            lines_end = file_entry.get("lines_end")
        else:
            path_str = str(file_entry)
            lines_start = 1
            lines_end = None

        file_path = project_path / path_str
        if not file_path.exists():
            logger.warning(f"File not found, skipping: {path_str}")
            continue

        if _is_binary_file(file_path):
            logger.debug(f"Skipping binary file: {path_str}")
            continue

        # Calculate size and hash
        try:
            content = file_path.read_text()
            line_count = content.count("\n") + 1
            import hashlib

            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]

            bundle_files.append(
                BundleFile(
                    path=path_str,
                    lines_start=lines_start,
                    lines_end=lines_end or line_count,
                    content_hash=content_hash,
                    size_bytes=len(content.encode()),
                )
            )
            total_lines += line_count
        except (UnicodeDecodeError, PermissionError) as e:
            logger.warning(f"Could not read file {path_str}: {e}")
            continue

    bundle = Bundle(
        task_id=task_id,
        created_at=datetime.now(),
        files=bundle_files,
        description=description,
        total_lines=total_lines,
        tags=tags or [],
    )

    # Save to file
    bundle_path = bundles_dir / f"{task_id}.json"
    bundle_path.write_text(json.dumps(bundle.to_dict(), indent=2))

    logger.info(f"Saved bundle: {bundle.summary()}")
    return bundle


def load_bundle(task_id: str, base_path: Path | None = None) -> Bundle | None:
    """Load a context bundle by task ID.

    Args:
        task_id: The task ID to load.
        base_path: Base path for bundle storage.

    Returns:
        The Bundle object, or None if not found.
    """
    bundles_dir = _get_bundles_dir(base_path)

    # Try regular JSON first
    bundle_path = bundles_dir / f"{task_id}.json"
    if bundle_path.exists():
        try:
            data = json.loads(bundle_path.read_text())
            return Bundle.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load bundle {task_id}: {e}")
            return None

    # Try compressed version
    compressed_path = bundles_dir / f"{task_id}.json.gz"
    if compressed_path.exists():
        try:
            with gzip.open(compressed_path, "rt") as f:
                data = json.load(f)
            return Bundle.from_dict(data)
        except (json.JSONDecodeError, gzip.BadGzipFile, KeyError) as e:
            logger.error(f"Failed to load compressed bundle {task_id}: {e}")
            return None

    return None


def list_bundles(
    base_path: Path | None = None,
    limit: int | None = None,
) -> list[Bundle]:
    """List all context bundles.

    Args:
        base_path: Base path for bundle storage.
        limit: Maximum number of bundles to return.

    Returns:
        List of Bundle objects, sorted by creation date (newest first).
    """
    bundles_dir = _get_bundles_dir(base_path)
    bundles = []

    for path in bundles_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            bundles.append(Bundle.from_dict(data))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Skipping invalid bundle {path.name}: {e}")

    # Also check compressed bundles
    for path in bundles_dir.glob("*.json.gz"):
        try:
            with gzip.open(path, "rt") as f:
                data = json.load(f)
            bundles.append(Bundle.from_dict(data))
        except (json.JSONDecodeError, gzip.BadGzipFile, KeyError) as e:
            logger.warning(f"Skipping invalid bundle {path.name}: {e}")

    # Sort by creation date, newest first
    bundles.sort(key=lambda b: b.created_at, reverse=True)

    if limit:
        return bundles[:limit]
    return bundles


@dataclass
class BundleDiff:
    """Difference between two bundles."""

    bundle1_id: str
    bundle2_id: str
    added: list[str]  # Files in bundle2 but not bundle1
    removed: list[str]  # Files in bundle1 but not bundle2
    common: list[str]  # Files in both bundles

    def summary(self) -> str:
        """Human-readable summary of the diff."""
        return (
            f"Diff {self.bundle1_id} → {self.bundle2_id}: +{len(self.added)} -{len(self.removed)} ={len(self.common)}"
        )


def diff_bundles(
    task_id1: str,
    task_id2: str,
    base_path: Path | None = None,
) -> BundleDiff | None:
    """Compare two bundles and show differences.

    Args:
        task_id1: First bundle's task ID.
        task_id2: Second bundle's task ID.
        base_path: Base path for bundle storage.

    Returns:
        BundleDiff object, or None if either bundle not found.
    """
    bundle1 = load_bundle(task_id1, base_path)
    bundle2 = load_bundle(task_id2, base_path)

    if not bundle1 or not bundle2:
        logger.error("Could not load one or both bundles")
        return None

    paths1 = bundle1.file_paths
    paths2 = bundle2.file_paths

    return BundleDiff(
        bundle1_id=task_id1,
        bundle2_id=task_id2,
        added=sorted(list(paths2 - paths1)),
        removed=sorted(list(paths1 - paths2)),
        common=sorted(list(paths1 & paths2)),
    )


def suggest_bundles(
    description: str,
    base_path: Path | None = None,
    top_n: int = 3,
) -> list[tuple[Bundle, float]]:
    """Suggest bundles similar to a given description.

    Uses simple keyword matching to find relevant bundles.

    Args:
        description: Description to match against.
        base_path: Base path for bundle storage.
        top_n: Number of suggestions to return.

    Returns:
        List of (Bundle, score) tuples, sorted by relevance.
    """
    bundles = list_bundles(base_path)
    if not bundles:
        return []

    # Tokenize description
    keywords = set(description.lower().split())

    scored_bundles = []
    for bundle in bundles:
        score = 0.0

        # Match against description
        bundle_words = set(bundle.description.lower().split())
        desc_overlap = len(keywords & bundle_words)
        if desc_overlap:
            score += desc_overlap * 2

        # Match against tags
        for tag in bundle.tags:
            if any(kw in tag.lower() for kw in keywords):
                score += 3

        # Match against file paths
        for bf in bundle.files:
            path_parts = set(bf.path.lower().replace("/", " ").replace("_", " ").split())
            path_overlap = len(keywords & path_parts)
            if path_overlap:
                score += path_overlap * 0.5

        if score > 0:
            scored_bundles.append((bundle, score))

    # Sort by score (descending) and return top N
    scored_bundles.sort(key=lambda x: x[1], reverse=True)
    return scored_bundles[:top_n]


def compress_old_bundles(
    days: int = 7,
    base_path: Path | None = None,
) -> int:
    """Compress bundles older than specified days.

    Args:
        days: Age threshold in days.
        base_path: Base path for bundle storage.

    Returns:
        Number of bundles compressed.
    """
    from datetime import timedelta

    bundles_dir = _get_bundles_dir(base_path)
    cutoff = datetime.now() - timedelta(days=days)
    compressed_count = 0

    for path in bundles_dir.glob("*.json"):
        if path.suffix == ".gz":
            continue

        try:
            data = json.loads(path.read_text())
            created_at = datetime.fromisoformat(data.get("created_at", ""))

            if created_at < cutoff:
                # Compress the file
                compressed_path = path.with_suffix(".json.gz")
                with gzip.open(compressed_path, "wt") as f:
                    json.dump(data, f)

                # Remove original
                path.unlink()
                compressed_count += 1
                logger.info(f"Compressed bundle: {path.name}")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"Failed to compress {path.name}: {e}")

    return compressed_count


def delete_bundle(task_id: str, base_path: Path | None = None) -> bool:
    """Delete a bundle by task ID.

    Args:
        task_id: The task ID of the bundle to delete.
        base_path: Base path for bundle storage.

    Returns:
        True if deleted, False if not found.
    """
    bundles_dir = _get_bundles_dir(base_path)

    bundle_path = bundles_dir / f"{task_id}.json"
    if bundle_path.exists():
        bundle_path.unlink()
        logger.info(f"Deleted bundle: {task_id}")
        return True

    compressed_path = bundles_dir / f"{task_id}.json.gz"
    if compressed_path.exists():
        compressed_path.unlink()
        logger.info(f"Deleted compressed bundle: {task_id}")
        return True

    return False


def get_bundle_file_contents(
    bundle: Bundle,
    base_path: Path | None = None,
) -> dict[str, str]:
    """Load actual file contents for a bundle.

    Args:
        bundle: The bundle to load files for.
        base_path: Project base path.

    Returns:
        Dict mapping file paths to their contents.
    """
    project_path = base_path or Path.cwd()
    contents = {}

    for bf in bundle.files:
        file_path = project_path / bf.path
        if not file_path.exists():
            logger.warning(f"Bundle file no longer exists: {bf.path}")
            continue

        try:
            text = file_path.read_text()
            lines = text.split("\n")

            # Extract specified line range
            start = max(0, bf.lines_start - 1)
            end = bf.lines_end if bf.lines_end else len(lines)
            contents[bf.path] = "\n".join(lines[start:end])
        except (UnicodeDecodeError, PermissionError) as e:
            logger.warning(f"Could not read bundle file {bf.path}: {e}")

    return contents
