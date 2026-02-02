from pathlib import Path

from .loader import SpecLoader
from .models import Spec, SpecStatus

__all__ = [
    "Spec",
    "SpecStatus",
    "SpecLoader",
    "get_pending_specs",
    "load_all_specs",
    "load_spec",
    "parse_spec",
]


def load_all_specs() -> list[Spec]:
    """Load all specs from the specs directory."""
    loader = SpecLoader()
    return loader.load_all()


def get_pending_specs() -> list[Spec]:
    """Get specs that are pending approval."""
    return [s for s in load_all_specs() if s.status == SpecStatus.PENDING]


def load_spec(path: Path) -> Spec | None:
    """Load a spec from a file path.

    Args:
        path: Path to the spec file.

    Returns:
        Spec object if found, None otherwise.
    """
    if not path.exists():
        return None
    loader = SpecLoader(specs_dir=path.parent)
    spec_id = path.stem
    return loader.get_spec(spec_id)


def parse_spec(path: Path) -> Spec | None:
    """Parse a spec file.

    Args:
        path: Path to the spec file.

    Returns:
        Spec object if successfully parsed, None otherwise.
    """
    return load_spec(path)
