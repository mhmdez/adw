"""Tests for the reports module.

Tests covering daily summaries, weekly digests, trend analysis,
metrics storage, and notifications.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adw.reports.daily import (
    DailySummary,
    _calculate_cost,
    _estimate_time_saved,
    _format_duration,
    generate_daily_summary,
    save_daily_summary,
)
from adw.reports.metrics import (
    MetricsDB,
    PhaseMetrics,
    TaskMetrics,
)
from adw.reports.notifications import (
    NotificationChannel,
    NotificationConfig,
    NotificationEvent,
    _format_discord_message,
    _format_slack_message,
    add_channel,
    list_channels,
    remove_channel,
    send_notification,
)
from adw.reports.trends import (
    TrendAnalysis,
    TrendPoint,
    TrendReport,
    _calculate_std_dev,
    _detect_anomalies,
    _determine_trend_direction,
    _generate_sparkline,
    analyze_metric,
    generate_trend_report,
)
from adw.reports.weekly import (
    WeeklyDigest,
    _calculate_comparison,
    _find_best_worst_tasks,
    _get_week_bounds,
    generate_weekly_digest,
    save_weekly_digest,
)

# =============================================================================
# Daily Summary Tests
# =============================================================================


class TestDailySummary:
    """Tests for DailySummary dataclass."""

    def test_daily_summary_creation(self) -> None:
        """Test creating a DailySummary."""
        summary = DailySummary(
            date=datetime(2026, 2, 1),
            tasks_completed=5,
            tasks_failed=1,
            total_commits=10,
        )
        assert summary.tasks_completed == 5
        assert summary.tasks_failed == 1
        assert summary.total_tasks == 6
        assert summary.date_str == "2026-02-01"

    def test_success_rate_calculation(self) -> None:
        """Test success rate calculation."""
        summary = DailySummary(
            date=datetime.now(),
            tasks_completed=8,
            tasks_failed=2,
        )
        assert summary.success_rate == 80.0

    def test_success_rate_zero_tasks(self) -> None:
        """Test success rate with zero tasks."""
        summary = DailySummary(date=datetime.now())
        assert summary.success_rate == 0.0

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        summary = DailySummary(
            date=datetime(2026, 2, 1),
            tasks_completed=5,
            total_input_tokens=1000,
            total_output_tokens=500,
        )
        result = summary.to_dict()
        assert result["date"] == "2026-02-01"
        assert result["tasks_completed"] == 5
        assert result["total_tokens"] == 1500

    def test_to_markdown(self) -> None:
        """Test markdown generation."""
        summary = DailySummary(
            date=datetime(2026, 2, 1),
            tasks_completed=5,
            tasks_failed=1,
            total_commits=10,
            estimated_cost=1.50,
        )
        md = summary.to_markdown()
        assert "# Daily Summary: 2026-02-01" in md
        assert "Tasks Completed:** 5" in md
        assert "Tasks Failed:** 1" in md
        assert "Estimated Cost:** $1.50" in md


class TestDailyHelpers:
    """Tests for daily summary helper functions."""

    def test_format_duration_seconds(self) -> None:
        """Test formatting seconds."""
        assert _format_duration(45) == "45s"

    def test_format_duration_minutes(self) -> None:
        """Test formatting minutes."""
        assert _format_duration(125) == "2m 5s"

    def test_format_duration_hours(self) -> None:
        """Test formatting hours."""
        assert _format_duration(3665) == "1h 1m"

    def test_calculate_cost(self) -> None:
        """Test cost calculation."""
        cost = _calculate_cost(1_000_000, 500_000, "sonnet")
        # Sonnet: $3/M input, $15/M output
        expected = 3.0 + 7.5
        assert cost == expected

    def test_estimate_time_saved(self) -> None:
        """Test time saved estimation."""
        hours = _estimate_time_saved(2, 100, 50)
        # 2 tasks * 2 hours + 150 lines * 0.5 min / 60
        assert hours > 4.0


# =============================================================================
# Metrics Tests
# =============================================================================


class TestPhaseMetrics:
    """Tests for PhaseMetrics dataclass."""

    def test_phase_metrics_creation(self) -> None:
        """Test creating PhaseMetrics."""
        pm = PhaseMetrics(
            name="IMPLEMENT",
            duration_seconds=120.5,
            retries=2,
            input_tokens=5000,
            output_tokens=2000,
            success=True,
        )
        assert pm.name == "IMPLEMENT"
        assert pm.duration_seconds == 120.5
        assert pm.retries == 2

    def test_phase_metrics_to_dict(self) -> None:
        """Test dictionary conversion."""
        pm = PhaseMetrics(name="TEST", retries=1)
        result = pm.to_dict()
        assert result["name"] == "TEST"
        assert result["retries"] == 1

    def test_phase_metrics_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "name": "PLAN",
            "duration_seconds": 60.0,
            "retries": 0,
            "input_tokens": 1000,
            "output_tokens": 500,
            "success": True,
        }
        pm = PhaseMetrics.from_dict(data)
        assert pm.name == "PLAN"
        assert pm.duration_seconds == 60.0


class TestTaskMetrics:
    """Tests for TaskMetrics dataclass."""

    def test_task_metrics_creation(self) -> None:
        """Test creating TaskMetrics."""
        tm = TaskMetrics(
            task_id="abc12345",
            description="Test task",
            workflow="sdlc",
            total_duration_seconds=300,
            total_retries=2,
        )
        assert tm.task_id == "abc12345"
        assert tm.workflow == "sdlc"
        assert tm.duration_str == "5m 0s"

    def test_task_metrics_total_tokens(self) -> None:
        """Test total tokens property."""
        tm = TaskMetrics(
            task_id="test",
            total_input_tokens=1000,
            total_output_tokens=500,
        )
        assert tm.total_tokens == 1500

    def test_task_metrics_calculate_cost(self) -> None:
        """Test cost calculation."""
        tm = TaskMetrics(
            task_id="test",
            total_input_tokens=1_000_000,
            total_output_tokens=500_000,
        )
        cost = tm.calculate_cost(input_price_per_mtok=3.0, output_price_per_mtok=15.0)
        assert cost == 10.5

    def test_task_metrics_to_dict(self) -> None:
        """Test dictionary conversion."""
        tm = TaskMetrics(
            task_id="test123",
            description="Test",
            phases=[PhaseMetrics(name="TEST", retries=1)],
        )
        result = tm.to_dict()
        assert result["task_id"] == "test123"
        assert "phases" in result

    def test_task_metrics_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "task_id": "test456",
            "description": "From dict",
            "workflow": "standard",
            "status": "completed",
            "start_time": "2026-02-01T10:00:00",
            "end_time": "2026-02-01T10:05:00",
            "total_duration_seconds": 300,
            "phases": "[]",
            "total_retries": 1,
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "commits_generated": 2,
            "files_modified": 5,
            "lines_added": 100,
            "lines_removed": 20,
        }
        tm = TaskMetrics.from_dict(data)
        assert tm.task_id == "test456"
        assert tm.total_retries == 1


class TestMetricsDB:
    """Tests for MetricsDB class."""

    @pytest.fixture
    def temp_db(self) -> MetricsDB:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        db = MetricsDB(db_path)
        yield db
        db.close()
        db_path.unlink(missing_ok=True)

    def test_db_initialization(self, temp_db: MetricsDB) -> None:
        """Test database initializes correctly."""
        assert temp_db.db_path.exists()

    def test_record_and_get_metrics(self, temp_db: MetricsDB) -> None:
        """Test recording and retrieving metrics."""
        metrics = TaskMetrics(
            task_id="test001",
            description="Test task",
            status="completed",
            total_duration_seconds=120,
        )
        temp_db.record_metrics(metrics)

        retrieved = temp_db.get_metrics("test001")
        assert retrieved is not None
        assert retrieved.task_id == "test001"
        assert retrieved.description == "Test task"

    def test_get_metrics_for_date(self, temp_db: MetricsDB) -> None:
        """Test getting metrics for a date."""
        today = datetime.now()
        metrics = TaskMetrics(
            task_id="today001",
            start_time=today,
            status="completed",
        )
        temp_db.record_metrics(metrics)

        results = temp_db.get_metrics_for_date(today)
        assert len(results) >= 1
        assert any(m.task_id == "today001" for m in results)

    def test_get_recent_metrics(self, temp_db: MetricsDB) -> None:
        """Test getting recent metrics."""
        for i in range(5):
            metrics = TaskMetrics(
                task_id=f"recent{i:03d}",
                status="completed",
            )
            temp_db.record_metrics(metrics)

        results = temp_db.get_recent_metrics(limit=3)
        assert len(results) == 3

    def test_get_summary_stats(self, temp_db: MetricsDB) -> None:
        """Test getting summary statistics."""
        for i in range(3):
            metrics = TaskMetrics(
                task_id=f"stat{i:03d}",
                status="completed" if i < 2 else "failed",
                total_duration_seconds=100,
            )
            temp_db.record_metrics(metrics)

        stats = temp_db.get_summary_stats()
        assert stats["total_tasks"] == 3
        assert stats["completed"] == 2
        assert stats["failed"] == 1


# =============================================================================
# Weekly Digest Tests
# =============================================================================


class TestWeeklyDigest:
    """Tests for WeeklyDigest dataclass."""

    def test_weekly_digest_creation(self) -> None:
        """Test creating WeeklyDigest."""
        digest = WeeklyDigest(
            week_start=datetime(2026, 1, 27),
            week_end=datetime(2026, 2, 2),
            tasks_completed=20,
            tasks_failed=2,
        )
        assert digest.tasks_completed == 20
        assert digest.total_tasks == 22
        assert "2026-W04" in digest.week_str or "2026-W05" in digest.week_str

    def test_success_rate(self) -> None:
        """Test success rate calculation."""
        digest = WeeklyDigest(
            week_start=datetime.now(),
            week_end=datetime.now(),
            tasks_completed=9,
            tasks_failed=1,
        )
        assert digest.success_rate == 90.0

    def test_to_markdown(self) -> None:
        """Test markdown generation."""
        digest = WeeklyDigest(
            week_start=datetime(2026, 1, 27),
            week_end=datetime(2026, 2, 2),
            tasks_completed=20,
            total_commits=50,
            estimated_cost=25.00,
        )
        md = digest.to_markdown()
        assert "# Weekly Digest:" in md
        assert "Tasks Completed:** 20" in md


class TestWeeklyHelpers:
    """Tests for weekly digest helper functions."""

    def test_get_week_bounds(self) -> None:
        """Test getting week bounds."""
        # Thursday, Jan 29, 2026
        date = datetime(2026, 1, 29, 12, 0, 0)
        monday, sunday = _get_week_bounds(date)

        assert monday.weekday() == 0  # Monday
        assert sunday.weekday() == 6  # Sunday
        assert monday.day == 26  # Jan 26
        assert sunday.day == 1  # Feb 1

    def test_calculate_comparison(self) -> None:
        """Test week-over-week comparison."""
        current = WeeklyDigest(
            week_start=datetime.now(),
            week_end=datetime.now(),
            tasks_completed=20,
            estimated_cost=50.0,
        )
        previous = WeeklyDigest(
            week_start=datetime.now() - timedelta(days=7),
            week_end=datetime.now(),
            tasks_completed=10,
            estimated_cost=40.0,
        )
        comparison = _calculate_comparison(current, previous)
        assert comparison["tasks_completed"] == 100.0  # 100% increase
        assert comparison["estimated_cost"] == 25.0  # 25% increase

    def test_find_best_worst_tasks(self) -> None:
        """Test finding best and worst tasks."""
        metrics_list = [
            TaskMetrics(task_id="fast", description="Fast task", status="completed", total_duration_seconds=60),
            TaskMetrics(task_id="slow", description="Slow task", status="completed", total_duration_seconds=600),
            TaskMetrics(task_id="failed", description="Failed task", status="failed", total_retries=5),
        ]
        best, worst = _find_best_worst_tasks(metrics_list)

        assert best is not None
        assert best["task_id"] == "fast"
        assert worst is not None
        assert worst["task_id"] == "failed"


# =============================================================================
# Trends Tests
# =============================================================================


class TestTrendPoint:
    """Tests for TrendPoint dataclass."""

    def test_trend_point_creation(self) -> None:
        """Test creating TrendPoint."""
        point = TrendPoint(
            date=datetime(2026, 2, 1),
            value=85.5,
            change=5.0,
            is_anomaly=False,
        )
        assert point.value == 85.5
        assert point.change == 5.0

    def test_trend_point_to_dict(self) -> None:
        """Test dictionary conversion."""
        point = TrendPoint(date=datetime(2026, 2, 1), value=90.0)
        result = point.to_dict()
        assert result["date"] == "2026-02-01"
        assert result["value"] == 90.0


class TestTrendAnalysis:
    """Tests for TrendAnalysis dataclass."""

    def test_trend_analysis_creation(self) -> None:
        """Test creating TrendAnalysis."""
        analysis = TrendAnalysis(
            metric_name="Success Rate",
            period_days=30,
            current_value=92.5,
            avg_value=88.0,
            trend_direction="up",
            sparkline="▁▂▃▅▇",
        )
        assert analysis.metric_name == "Success Rate"
        assert analysis.trend_direction == "up"

    def test_to_summary(self) -> None:
        """Test summary generation."""
        analysis = TrendAnalysis(
            metric_name="Success Rate",
            period_days=30,
            current_value=92.5,
            change_pct=5.0,
            trend_direction="up",
            sparkline="▁▂▃▅▇",
        )
        summary = analysis.to_summary()
        assert "Success Rate" in summary
        assert "92.5" in summary
        assert "↑" in summary


class TestTrendHelpers:
    """Tests for trend analysis helper functions."""

    def test_generate_sparkline(self) -> None:
        """Test sparkline generation."""
        values = [0, 25, 50, 75, 100]
        sparkline = _generate_sparkline(values, width=5)
        assert len(sparkline) == 5
        assert sparkline[0] == "▁"
        assert sparkline[-1] == "█"

    def test_generate_sparkline_empty(self) -> None:
        """Test sparkline with empty values."""
        assert _generate_sparkline([]) == ""

    def test_calculate_std_dev(self) -> None:
        """Test standard deviation calculation."""
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        std = _calculate_std_dev(values)
        assert 1.9 < std < 2.1  # Approximately 2

    def test_calculate_std_dev_single_value(self) -> None:
        """Test std dev with single value."""
        assert _calculate_std_dev([5]) == 0.0

    def test_detect_anomalies(self) -> None:
        """Test anomaly detection."""
        points = [
            TrendPoint(date=datetime.now() - timedelta(days=i), value=50.0)
            for i in range(10)
        ]
        # Add anomaly
        points.append(TrendPoint(date=datetime.now(), value=150.0))

        anomalies = _detect_anomalies(points, std_threshold=2.0)
        assert len(anomalies) >= 1

    def test_determine_trend_direction_up(self) -> None:
        """Test detecting upward trend."""
        # Create points in chronological order: older first, newer last
        # Values increase over time (10, 20, 30, ...)
        points = [
            TrendPoint(date=datetime.now() - timedelta(days=10 - i), value=i * 10)
            for i in range(1, 11)
        ]
        direction = _determine_trend_direction(points)
        assert direction == "up"

    def test_determine_trend_direction_down(self) -> None:
        """Test detecting downward trend."""
        # Create points in chronological order: older first, newer last
        # Values decrease over time (100, 90, 80, ...)
        points = [
            TrendPoint(date=datetime.now() - timedelta(days=10 - i), value=100 - i * 10)
            for i in range(1, 11)
        ]
        direction = _determine_trend_direction(points)
        assert direction == "down"

    def test_analyze_metric(self) -> None:
        """Test metric analysis."""
        values = [(datetime.now() - timedelta(days=i), float(50 + i)) for i in range(7)]
        analysis = analyze_metric("Test Metric", values, 7)

        assert analysis.metric_name == "Test Metric"
        assert analysis.period_days == 7
        assert len(analysis.points) == 7


class TestTrendReport:
    """Tests for TrendReport dataclass."""

    def test_trend_report_creation(self) -> None:
        """Test creating TrendReport."""
        report = TrendReport(
            period_days=30,
            alerts=["Test alert"],
        )
        assert report.period_days == 30
        assert len(report.alerts) == 1

    def test_to_markdown(self) -> None:
        """Test markdown generation."""
        report = TrendReport(
            period_days=30,
            alerts=["⚠️ Test alert"],
            success_rate=TrendAnalysis(
                metric_name="Success Rate",
                period_days=30,
                current_value=85.0,
                change_pct=5.0,
                trend_direction="up",
                sparkline="▁▂▃▅▇",
            ),
        )
        md = report.to_markdown()
        assert "# Trend Analysis Report" in md
        assert "Test alert" in md
        assert "Success Rate" in md


# =============================================================================
# Notifications Tests
# =============================================================================


class TestNotificationChannel:
    """Tests for NotificationChannel dataclass."""

    def test_channel_creation(self) -> None:
        """Test creating NotificationChannel."""
        channel = NotificationChannel(
            name="my-slack",
            type="slack",
            webhook_url="https://hooks.slack.com/...",
            enabled=True,
        )
        assert channel.name == "my-slack"
        assert channel.type == "slack"

    def test_should_notify_all_events(self) -> None:
        """Test should_notify with no event filter."""
        channel = NotificationChannel(
            name="test",
            type="slack",
            webhook_url="https://...",
            enabled=True,
            events=[],
        )
        assert channel.should_notify(NotificationEvent.TASK_COMPLETE)
        assert channel.should_notify(NotificationEvent.TASK_FAILED)

    def test_should_notify_filtered(self) -> None:
        """Test should_notify with event filter."""
        channel = NotificationChannel(
            name="test",
            type="slack",
            webhook_url="https://...",
            enabled=True,
            events=["task_failed"],
        )
        assert not channel.should_notify(NotificationEvent.TASK_COMPLETE)
        assert channel.should_notify(NotificationEvent.TASK_FAILED)

    def test_should_notify_disabled(self) -> None:
        """Test disabled channel."""
        channel = NotificationChannel(
            name="test",
            type="slack",
            webhook_url="https://...",
            enabled=False,
        )
        assert not channel.should_notify(NotificationEvent.TASK_COMPLETE)


class TestNotificationConfig:
    """Tests for NotificationConfig dataclass."""

    def test_config_creation(self) -> None:
        """Test creating NotificationConfig."""
        config = NotificationConfig(
            enabled=True,
            channels=[
                NotificationChannel(name="test", type="slack", webhook_url="https://..."),
            ],
        )
        assert config.enabled
        assert len(config.channels) == 1

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        config = NotificationConfig(
            enabled=True,
            channels=[
                NotificationChannel(name="test", type="slack", webhook_url="https://..."),
            ],
        )
        result = config.to_dict()
        assert result["enabled"]
        assert len(result["channels"]) == 1

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "enabled": False,
            "channels": [
                {"name": "test", "type": "discord", "webhook_url": "https://..."},
            ],
        }
        config = NotificationConfig.from_dict(data)
        assert not config.enabled
        assert config.channels[0].type == "discord"


class TestNotificationFormatters:
    """Tests for message formatters."""

    def test_format_slack_message(self) -> None:
        """Test Slack message formatting."""
        msg = _format_slack_message(
            title="Test Title",
            message="Test message body",
            color="#2eb67d",
            fields=[{"title": "Field1", "value": "Value1"}],
        )
        assert "attachments" in msg
        assert msg["attachments"][0]["title"] == "Test Title"
        assert msg["attachments"][0]["text"] == "Test message body"

    def test_format_discord_message(self) -> None:
        """Test Discord message formatting."""
        msg = _format_discord_message(
            title="Test Title",
            message="Test message body",
            color=3066993,
            fields=[{"title": "Field1", "value": "Value1"}],
        )
        assert "embeds" in msg
        assert msg["embeds"][0]["title"] == "Test Title"
        assert msg["embeds"][0]["description"] == "Test message body"


class TestNotificationFunctions:
    """Tests for notification functions."""

    @patch("adw.reports.notifications._load_config")
    def test_send_notification_disabled(self, mock_load: MagicMock) -> None:
        """Test sending notification when disabled."""
        mock_load.return_value = NotificationConfig(enabled=False)
        result = send_notification(
            NotificationEvent.TASK_COMPLETE,
            "Test",
            "Test message",
        )
        assert result == {}

    @patch("adw.reports.notifications._save_config")
    @patch("adw.reports.notifications._load_config")
    def test_add_channel(self, mock_load: MagicMock, mock_save: MagicMock) -> None:
        """Test adding a channel."""
        mock_load.return_value = NotificationConfig()
        add_channel("test-channel", "slack", "https://hooks.slack.com/...")
        mock_save.assert_called_once()

    @patch("adw.reports.notifications._save_config")
    @patch("adw.reports.notifications._load_config")
    def test_remove_channel(self, mock_load: MagicMock, mock_save: MagicMock) -> None:
        """Test removing a channel."""
        mock_load.return_value = NotificationConfig(
            channels=[NotificationChannel(name="test", type="slack", webhook_url="https://...")]
        )
        result = remove_channel("test")
        assert result
        mock_save.assert_called_once()

    @patch("adw.reports.notifications._load_config")
    def test_list_channels(self, mock_load: MagicMock) -> None:
        """Test listing channels."""
        mock_load.return_value = NotificationConfig(
            channels=[
                NotificationChannel(name="ch1", type="slack", webhook_url="https://..."),
                NotificationChannel(name="ch2", type="discord", webhook_url="https://..."),
            ]
        )
        channels = list_channels()
        assert len(channels) == 2
        assert channels[0]["name"] == "ch1"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for reports module."""

    @pytest.fixture
    def temp_db(self) -> MetricsDB:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        db = MetricsDB(db_path)
        yield db
        db.close()
        db_path.unlink(missing_ok=True)

    def test_daily_summary_generation(self, temp_db: MetricsDB) -> None:
        """Test full daily summary generation."""
        # Record some metrics
        for i in range(3):
            metrics = TaskMetrics(
                task_id=f"daily{i:03d}",
                status="completed" if i < 2 else "failed",
                total_duration_seconds=100,
                total_input_tokens=1000,
                total_output_tokens=500,
            )
            temp_db.record_metrics(metrics)

        summary = generate_daily_summary(db=temp_db)
        assert summary.tasks_completed == 2
        assert summary.tasks_failed == 1
        assert summary.total_input_tokens == 3000
        assert summary.total_output_tokens == 1500

    def test_weekly_digest_generation(self, temp_db: MetricsDB) -> None:
        """Test full weekly digest generation."""
        # Record metrics within the current week only
        # Get the start of the current week (Monday)
        now = datetime.now()
        monday = now - timedelta(days=now.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Record 3 tasks within this week
        for day in range(3):
            date = monday + timedelta(days=day)
            metrics = TaskMetrics(
                task_id=f"week{day:03d}",
                start_time=date,
                status="completed",
                total_duration_seconds=100,
            )
            temp_db.record_metrics(metrics)

        digest = generate_weekly_digest(db=temp_db)
        assert digest.total_tasks >= 3

    def test_trend_report_generation(self, temp_db: MetricsDB) -> None:
        """Test full trend report generation."""
        # Record metrics across multiple days
        for day in range(14):
            date = datetime.now() - timedelta(days=day)
            metrics = TaskMetrics(
                task_id=f"trend{day:03d}",
                start_time=date,
                status="completed",
                total_duration_seconds=100 + day * 10,
            )
            temp_db.record_metrics(metrics)

        report = generate_trend_report(period_days=14, db=temp_db)
        assert report.period_days == 14

    def test_save_daily_summary(self, temp_db: MetricsDB, tmp_path: Path) -> None:
        """Test saving daily summary to file."""
        summary = generate_daily_summary(db=temp_db)
        output_path = tmp_path / "daily.md"
        result = save_daily_summary(summary, output_path)

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text()
        assert "# Daily Summary:" in content

    def test_save_weekly_digest(self, temp_db: MetricsDB, tmp_path: Path) -> None:
        """Test saving weekly digest to file."""
        digest = generate_weekly_digest(db=temp_db)
        output_path = tmp_path / "weekly.md"
        result = save_weekly_digest(digest, output_path)

        assert result == output_path
        assert output_path.exists()
        content = output_path.read_text()
        assert "# Weekly Digest:" in content
