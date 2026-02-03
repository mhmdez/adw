"""Trend analysis for ADW metrics.

This module provides functionality for analyzing trends in ADW metrics
over time, including anomaly detection and sparkline visualization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .metrics import MetricsDB, get_metrics_db

# Sparkline characters for terminal visualization
SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"


@dataclass
class TrendPoint:
    """A single point in a trend series.

    Attributes:
        date: Date of the data point.
        value: Metric value.
        change: Percentage change from previous point.
        is_anomaly: Whether this point is anomalous.
    """

    date: datetime
    value: float
    change: float = 0.0
    is_anomaly: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "value": self.value,
            "change": self.change,
            "is_anomaly": self.is_anomaly,
        }


@dataclass
class TrendAnalysis:
    """Analysis of a metric trend over time.

    Attributes:
        metric_name: Name of the metric being analyzed.
        period_days: Number of days in the analysis period.
        points: List of trend points.
        current_value: Most recent value.
        previous_value: Previous period's value.
        change_pct: Percentage change from previous period.
        avg_value: Average value over the period.
        min_value: Minimum value in the period.
        max_value: Maximum value in the period.
        std_dev: Standard deviation of values.
        trend_direction: 'up', 'down', or 'stable'.
        anomalies: List of anomalous points.
        sparkline: ASCII sparkline visualization.
    """

    metric_name: str
    period_days: int
    points: list[TrendPoint] = field(default_factory=list)
    current_value: float = 0.0
    previous_value: float = 0.0
    change_pct: float = 0.0
    avg_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    std_dev: float = 0.0
    trend_direction: str = "stable"
    anomalies: list[TrendPoint] = field(default_factory=list)
    sparkline: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "period_days": self.period_days,
            "points": [p.to_dict() for p in self.points],
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "change_pct": self.change_pct,
            "avg_value": self.avg_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "std_dev": self.std_dev,
            "trend_direction": self.trend_direction,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "sparkline": self.sparkline,
        }

    def to_summary(self) -> str:
        """Generate a summary string."""
        direction_emoji = {"up": "↑", "down": "↓", "stable": "→"}[self.trend_direction]
        return (
            f"{self.metric_name}: {self.current_value:.1f} "
            f"{direction_emoji} ({self.change_pct:+.1f}%) "
            f"[{self.sparkline}]"
        )


@dataclass
class TrendReport:
    """Complete trend report with multiple metrics.

    Attributes:
        period_days: Number of days analyzed.
        generated_at: When the report was generated.
        success_rate: Success rate trend.
        avg_duration: Average task duration trend.
        cost_per_task: Cost per task trend.
        retries_per_task: Retries per task trend.
        tasks_per_day: Tasks per day trend.
        alerts: List of anomaly alerts.
    """

    period_days: int
    generated_at: datetime = field(default_factory=datetime.now)
    success_rate: TrendAnalysis | None = None
    avg_duration: TrendAnalysis | None = None
    cost_per_task: TrendAnalysis | None = None
    retries_per_task: TrendAnalysis | None = None
    tasks_per_day: TrendAnalysis | None = None
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_days": self.period_days,
            "generated_at": self.generated_at.isoformat(),
            "success_rate": self.success_rate.to_dict() if self.success_rate else None,
            "avg_duration": self.avg_duration.to_dict() if self.avg_duration else None,
            "cost_per_task": self.cost_per_task.to_dict() if self.cost_per_task else None,
            "retries_per_task": self.retries_per_task.to_dict() if self.retries_per_task else None,
            "tasks_per_day": self.tasks_per_day.to_dict() if self.tasks_per_day else None,
            "alerts": self.alerts,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Trend Analysis Report",
            f"**Period:** Last {self.period_days} days",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Alerts section
        if self.alerts:
            lines.extend(
                [
                    "## ⚠️ Alerts",
                    "",
                ]
            )
            for alert in self.alerts:
                lines.append(f"- {alert}")
            lines.append("")

        # Metrics section
        lines.extend(
            [
                "## Metrics Overview",
                "",
            ]
        )

        metrics = [
            ("Success Rate", self.success_rate, "%"),
            ("Avg Duration", self.avg_duration, "s"),
            ("Cost/Task", self.cost_per_task, "$"),
            ("Retries/Task", self.retries_per_task, ""),
            ("Tasks/Day", self.tasks_per_day, ""),
        ]

        for name, trend, unit in metrics:
            if trend:
                direction = {"up": "↑", "down": "↓", "stable": "→"}[trend.trend_direction]
                lines.extend(
                    [
                        f"### {name}",
                        f"Current: {trend.current_value:.1f}{unit} {direction} ({trend.change_pct:+.1f}%)",
                        f"Average: {trend.avg_value:.1f}{unit} | "
                        f"Range: {trend.min_value:.1f}-{trend.max_value:.1f}{unit}",
                        f"Sparkline: {trend.sparkline}",
                        "",
                    ]
                )

        lines.extend(
            [
                "---",
                f"*Generated by ADW at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ]
        )

        return "\n".join(lines)


def _generate_sparkline(values: list[float], width: int = 10) -> str:
    """Generate an ASCII sparkline from values.

    Args:
        values: List of numeric values.
        width: Target width of the sparkline.

    Returns:
        ASCII sparkline string.
    """
    if not values:
        return ""

    # Resample to target width if needed
    if len(values) > width:
        step = len(values) / width
        resampled = [values[int(i * step)] for i in range(width)]
        values = resampled
    elif len(values) < width:
        # Pad with zeros or repeat last value
        values = values + [values[-1]] * (width - len(values))

    min_val = min(values)
    max_val = max(values)
    value_range = max_val - min_val

    if value_range == 0:
        return SPARKLINE_CHARS[4] * len(values)

    # Map values to sparkline characters
    chars = []
    for val in values:
        normalized = (val - min_val) / value_range
        idx = int(normalized * (len(SPARKLINE_CHARS) - 1))
        chars.append(SPARKLINE_CHARS[idx])

    return "".join(chars)


def _calculate_std_dev(values: list[float]) -> float:
    """Calculate standard deviation.

    Args:
        values: List of numeric values.

    Returns:
        Standard deviation.
    """
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return float(variance**0.5)


def _detect_anomalies(
    points: list[TrendPoint],
    std_threshold: float = 2.0,
) -> list[TrendPoint]:
    """Detect anomalous points using z-score method.

    Args:
        points: List of trend points.
        std_threshold: Number of standard deviations for anomaly threshold.

    Returns:
        List of anomalous points.
    """
    if len(points) < 3:
        return []

    values = [p.value for p in points]
    mean = sum(values) / len(values)
    std_dev = _calculate_std_dev(values)

    if std_dev == 0:
        return []

    anomalies = []
    for point in points:
        z_score = abs(point.value - mean) / std_dev
        if z_score > std_threshold:
            point.is_anomaly = True
            anomalies.append(point)

    return anomalies


def _determine_trend_direction(points: list[TrendPoint]) -> str:
    """Determine overall trend direction.

    Uses simple linear regression to determine if trend is
    increasing, decreasing, or stable.

    Args:
        points: List of trend points.

    Returns:
        'up', 'down', or 'stable'.
    """
    if len(points) < 2:
        return "stable"

    values = [p.value for p in points]

    # Simple linear regression slope
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable"

    slope = numerator / denominator

    # Normalize slope by mean to get percentage change
    if y_mean != 0:
        normalized_slope = slope / abs(y_mean) * 100
    else:
        normalized_slope = slope

    # Threshold for determining direction
    if normalized_slope > 5:  # 5% increase per period
        return "up"
    elif normalized_slope < -5:  # 5% decrease per period
        return "down"
    return "stable"


def analyze_metric(
    metric_name: str,
    values: list[tuple[datetime, float]],
    period_days: int,
) -> TrendAnalysis:
    """Analyze a single metric's trend.

    Args:
        metric_name: Name of the metric.
        values: List of (date, value) tuples.
        period_days: Number of days in the period.

    Returns:
        TrendAnalysis for the metric.
    """
    if not values:
        return TrendAnalysis(
            metric_name=metric_name,
            period_days=period_days,
        )

    # Sort by date
    values = sorted(values, key=lambda x: x[0])

    # Create trend points
    points = []
    prev_value = None
    for date, value in values:
        change = 0.0
        if prev_value is not None and prev_value != 0:
            change = ((value - prev_value) / prev_value) * 100
        points.append(TrendPoint(date=date, value=value, change=change))
        prev_value = value

    # Calculate statistics
    raw_values = [p.value for p in points]
    current_value = raw_values[-1] if raw_values else 0.0
    previous_value = raw_values[-2] if len(raw_values) >= 2 else 0.0
    avg_value = sum(raw_values) / len(raw_values) if raw_values else 0.0
    min_value = min(raw_values) if raw_values else 0.0
    max_value = max(raw_values) if raw_values else 0.0
    std_dev = _calculate_std_dev(raw_values)

    # Calculate overall change
    change_pct = 0.0
    if previous_value != 0:
        change_pct = ((current_value - previous_value) / previous_value) * 100

    # Detect anomalies
    anomalies = _detect_anomalies(points)

    # Determine trend direction
    trend_direction = _determine_trend_direction(points)

    # Generate sparkline
    sparkline = _generate_sparkline(raw_values)

    return TrendAnalysis(
        metric_name=metric_name,
        period_days=period_days,
        points=points,
        current_value=current_value,
        previous_value=previous_value,
        change_pct=change_pct,
        avg_value=avg_value,
        min_value=min_value,
        max_value=max_value,
        std_dev=std_dev,
        trend_direction=trend_direction,
        anomalies=anomalies,
        sparkline=sparkline,
    )


def generate_trend_report(
    period_days: int = 30,
    db: MetricsDB | None = None,
) -> TrendReport:
    """Generate a complete trend report.

    Args:
        period_days: Number of days to analyze.
        db: MetricsDB instance (default: global instance).

    Returns:
        TrendReport with all metric trends.
    """
    if db is None:
        db = get_metrics_db()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    # Get daily aggregates for the period
    aggregates = db.get_daily_aggregates_range(start_date, end_date)

    # Prepare data series for each metric
    success_rates: list[tuple[datetime, float]] = []
    avg_durations: list[tuple[datetime, float]] = []
    costs_per_task: list[tuple[datetime, float]] = []
    retries_per_task: list[tuple[datetime, float]] = []
    tasks_per_day: list[tuple[datetime, float]] = []

    for agg in aggregates:
        date = datetime.strptime(agg["date"], "%Y-%m-%d")
        total_tasks = agg.get("tasks_completed", 0) + agg.get("tasks_failed", 0)

        # Success rate
        if total_tasks > 0:
            success_rate = (agg.get("tasks_completed", 0) / total_tasks) * 100
            success_rates.append((date, success_rate))

            # Average duration
            avg_duration = agg.get("total_duration_seconds", 0) / total_tasks
            avg_durations.append((date, avg_duration))

            # Cost per task (using Sonnet pricing)
            input_tokens = agg.get("total_input_tokens", 0)
            output_tokens = agg.get("total_output_tokens", 0)
            cost = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
            cost_per_task = cost / total_tasks
            costs_per_task.append((date, cost_per_task))

            # Retries per task
            retries = agg.get("total_retries", 0) / total_tasks
            retries_per_task.append((date, retries))

        # Tasks per day (always track even if 0)
        tasks_per_day.append((date, float(total_tasks)))

    # Analyze each metric
    success_rate_trend = analyze_metric("Success Rate", success_rates, period_days)
    avg_duration_trend = analyze_metric("Avg Duration", avg_durations, period_days)
    cost_trend = analyze_metric("Cost/Task", costs_per_task, period_days)
    retries_trend = analyze_metric("Retries/Task", retries_per_task, period_days)
    tasks_trend = analyze_metric("Tasks/Day", tasks_per_day, period_days)

    # Generate alerts
    alerts = []

    # Alert on declining success rate
    if success_rate_trend.trend_direction == "down" and success_rate_trend.change_pct < -10:
        alerts.append(
            f"⚠️ Success rate declining: {success_rate_trend.change_pct:.1f}% over {period_days} days"
        )

    # Alert on increasing costs
    if cost_trend.trend_direction == "up" and cost_trend.change_pct > 20:
        alerts.append(f"💰 Cost per task increasing: +{cost_trend.change_pct:.1f}%")

    # Alert on increasing retries
    if retries_trend.trend_direction == "up" and retries_trend.change_pct > 30:
        alerts.append(f"🔄 Retries per task increasing: +{retries_trend.change_pct:.1f}%")

    # Alert on anomalies
    for trend in [success_rate_trend, cost_trend, retries_trend]:
        if trend.anomalies:
            for anomaly in trend.anomalies:
                alerts.append(
                    f"🔍 Anomaly detected in {trend.metric_name} on "
                    f"{anomaly.date.strftime('%Y-%m-%d')}: {anomaly.value:.1f}"
                )

    return TrendReport(
        period_days=period_days,
        success_rate=success_rate_trend,
        avg_duration=avg_duration_trend,
        cost_per_task=cost_trend,
        retries_per_task=retries_trend,
        tasks_per_day=tasks_trend,
        alerts=alerts,
    )


def get_sparkline_summary(
    db: MetricsDB | None = None,
    period_days: int = 14,
) -> str:
    """Get a compact sparkline summary of key metrics.

    Args:
        db: MetricsDB instance (default: global instance).
        period_days: Number of days to include.

    Returns:
        Multi-line sparkline summary string.
    """
    report = generate_trend_report(period_days, db)

    lines = []
    if report.success_rate:
        lines.append(report.success_rate.to_summary())
    if report.avg_duration:
        lines.append(report.avg_duration.to_summary())
    if report.cost_per_task:
        lines.append(report.cost_per_task.to_summary())
    if report.tasks_per_day:
        lines.append(report.tasks_per_day.to_summary())

    return "\n".join(lines)
