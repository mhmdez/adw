"""Reports and analytics module for ADW.

This module provides reporting and analytics functionality for tracking
ADW's performance over time, including daily summaries, weekly digests,
trend analysis, and notifications.
"""

from __future__ import annotations

from .daily import DailySummary, generate_daily_summary, get_daily_summary, save_daily_summary
from .metrics import (
    MetricsDB,
    PhaseMetrics,
    TaskMetrics,
    get_metrics_db,
    record_task_completion,
    record_task_metrics,
)
from .notifications import (
    NotificationChannel,
    NotificationConfig,
    NotificationEvent,
    add_channel,
    enable_notifications,
    list_channels,
    notify_anomaly,
    notify_daily_summary,
    notify_task_complete,
    notify_task_failed,
    notify_task_start,
    notify_weekly_digest,
    remove_channel,
    send_notification,
    test_channel,
)
from .trends import (
    TrendAnalysis,
    TrendPoint,
    TrendReport,
    analyze_metric,
    generate_trend_report,
    get_sparkline_summary,
)
from .weekly import WeeklyDigest, generate_weekly_digest, get_weekly_digest, save_weekly_digest

__all__ = [
    # Daily
    "DailySummary",
    "generate_daily_summary",
    "get_daily_summary",
    "save_daily_summary",
    # Weekly
    "WeeklyDigest",
    "generate_weekly_digest",
    "get_weekly_digest",
    "save_weekly_digest",
    # Metrics
    "MetricsDB",
    "PhaseMetrics",
    "TaskMetrics",
    "get_metrics_db",
    "record_task_metrics",
    "record_task_completion",
    # Trends
    "TrendAnalysis",
    "TrendPoint",
    "TrendReport",
    "analyze_metric",
    "generate_trend_report",
    "get_sparkline_summary",
    # Notifications
    "NotificationChannel",
    "NotificationConfig",
    "NotificationEvent",
    "add_channel",
    "enable_notifications",
    "list_channels",
    "notify_anomaly",
    "notify_daily_summary",
    "notify_task_complete",
    "notify_task_failed",
    "notify_task_start",
    "notify_weekly_digest",
    "remove_channel",
    "send_notification",
    "test_channel",
]
