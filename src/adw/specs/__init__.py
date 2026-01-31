from .models import Spec, SpecStatus
from .loader import SpecLoader

__all__ = ["Spec", "SpecStatus", "SpecLoader", "get_pending_specs", "load_all_specs"]


def load_all_specs() -> list[Spec]:
    """Load all specs from the specs directory."""
    loader = SpecLoader()
    return loader.load_all()


def get_pending_specs() -> list[Spec]:
    """Get specs that are pending approval."""
    return [s for s in load_all_specs() if s.status == SpecStatus.PENDING]
