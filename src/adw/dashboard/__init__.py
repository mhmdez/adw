"""Web dashboard for ADW observability.

This module provides a web-based dashboard for monitoring ADW events,
sessions, and task status.
"""

from .server import (
    DEFAULT_DASHBOARD_PORT,
    DashboardStats,
    create_dashboard_app,
    get_dashboard_stats,
    start_dashboard_server,
)

__all__ = [
    "DEFAULT_DASHBOARD_PORT",
    "DashboardStats",
    "create_dashboard_app",
    "get_dashboard_stats",
    "start_dashboard_server",
]
