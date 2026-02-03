"""Context engineering for ADW.

Provides context priming, context bundles, and session restoration.
"""

from .bundles import (
    Bundle,
    BundleFile,
    delete_bundle,
    diff_bundles,
    get_bundle_file_contents,
    list_bundles,
    load_bundle,
    save_bundle,
    suggest_bundles,
)
from .priming import (
    PRIME_TEMPLATES,
    ProjectType,
    detect_project_type,
    generate_all_prime_commands,
    generate_prime_command,
)

__all__ = [
    # Priming
    "detect_project_type",
    "generate_prime_command",
    "generate_all_prime_commands",
    "PRIME_TEMPLATES",
    "ProjectType",
    # Bundles
    "save_bundle",
    "load_bundle",
    "list_bundles",
    "diff_bundles",
    "suggest_bundles",
    "get_bundle_file_contents",
    "delete_bundle",
    "Bundle",
    "BundleFile",
]
