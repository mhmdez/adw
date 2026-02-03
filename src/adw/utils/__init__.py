"""ADW utility modules."""

from .errors import (
    ErrorCategory,
    ErrorInfo,
    classify_exception,
    error_config_invalid,
    error_dependency_missing,
    error_file_not_found,
    error_git_operation,
    error_internal,
    error_network,
    error_task_not_found,
    error_workflow,
    format_error,
    handle_exception,
    is_debug_mode,
    set_debug_mode,
)
from .screenshot import (
    attach_screenshots_to_pr,
    capture_browser_screenshot,
    capture_screenshot,
    detect_dev_server_ports,
    get_dev_server_url,
    is_dev_server_running,
)

__all__ = [
    # Error handling
    "ErrorCategory",
    "ErrorInfo",
    "format_error",
    "handle_exception",
    "classify_exception",
    "error_file_not_found",
    "error_dependency_missing",
    "error_config_invalid",
    "error_task_not_found",
    "error_git_operation",
    "error_network",
    "error_workflow",
    "error_internal",
    "set_debug_mode",
    "is_debug_mode",
    # Screenshot utilities
    "capture_screenshot",
    "capture_browser_screenshot",
    "is_dev_server_running",
    "detect_dev_server_ports",
    "get_dev_server_url",
    "attach_screenshots_to_pr",
]
