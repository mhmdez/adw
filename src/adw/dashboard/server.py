"""Web dashboard server for ADW observability.

Provides a web-based dashboard for viewing events, sessions, and task status.
Uses Server-Sent Events (SSE) for real-time updates.

Usage:
    adw dashboard --web
    adw dashboard --web --port 3939
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Dashboard port (per spec)
DEFAULT_DASHBOARD_PORT = 3939


@dataclass
class DashboardStats:
    """Statistics for dashboard overview."""

    total_events: int
    total_sessions: int
    active_sessions: int
    events_by_type: dict[str, int]
    recent_errors: int
    uptime_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


def get_dashboard_stats() -> DashboardStats:
    """Get current dashboard statistics.

    Returns:
        DashboardStats with current metrics.
    """
    from datetime import timedelta

    from ..observability.db import get_db
    from ..observability.models import EventFilter, EventType, SessionStatus

    db = get_db()

    # Get total events
    total_events = db.get_event_count()

    # Get sessions
    all_sessions = db.get_sessions(limit=1000)
    total_sessions = len(all_sessions)
    active_sessions = sum(1 for s in all_sessions if s.status == SessionStatus.RUNNING)

    # Get event summary
    events_by_type = db.get_event_summary()

    # Get recent errors (last hour)
    one_hour_ago = datetime.now() - timedelta(hours=1)
    error_filter = EventFilter(
        event_types=[EventType.ERROR, EventType.TOOL_ERROR],
        since=one_hour_ago,
    )
    recent_errors = db.get_event_count(error_filter)

    # Calculate uptime (time since first event)
    first_events = db.get_events(EventFilter(limit=1, offset=total_events - 1 if total_events > 0 else 0))
    if first_events:
        uptime = (datetime.now() - first_events[0].timestamp).total_seconds()
    else:
        uptime = 0.0

    return DashboardStats(
        total_events=total_events,
        total_sessions=total_sessions,
        active_sessions=active_sessions,
        events_by_type=events_by_type,
        recent_errors=recent_errors,
        uptime_seconds=uptime,
    )


def create_dashboard_app() -> Any:
    """Create FastAPI app for web dashboard.

    Returns:
        FastAPI application with dashboard endpoints.
    """
    from fastapi import FastAPI, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, StreamingResponse

    app = FastAPI(
        title="ADW Dashboard",
        description="Web dashboard for ADW observability",
        version="1.0.0",
    )

    # Enable CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------------
    # Dashboard HTML
    # -------------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)  # type: ignore[untyped-decorator]
    async def dashboard_home() -> HTMLResponse:
        """Serve the main dashboard HTML."""
        html_content = _get_dashboard_html()
        return HTMLResponse(content=html_content)

    # -------------------------------------------------------------------------
    # API Endpoints
    # -------------------------------------------------------------------------

    @app.get("/api/stats")  # type: ignore[untyped-decorator]
    async def api_stats() -> dict[str, Any]:
        """Get dashboard statistics."""
        stats = get_dashboard_stats()
        return stats.to_dict()

    @app.get("/api/events")  # type: ignore[untyped-decorator]
    async def api_events(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        event_type: str | None = Query(None),
        task_id: str | None = Query(None),
        session_id: str | None = Query(None),
        since: str | None = Query(None, description="Time ago string like '1h', '30m', '7d'"),
    ) -> dict[str, Any]:
        """Get events with filtering.

        Args:
            limit: Maximum events to return.
            offset: Number of events to skip.
            event_type: Filter by event type.
            task_id: Filter by task ID.
            session_id: Filter by session ID.
            since: Time ago string (e.g., '1h', '30m', '7d').

        Returns:
            Dictionary with events and pagination info.
        """
        from ..observability.db import get_db
        from ..observability.models import EventFilter, EventType

        filter_kwargs: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if event_type:
            try:
                filter_kwargs["event_types"] = [EventType(event_type)]
            except ValueError:
                pass

        if task_id:
            filter_kwargs["task_id"] = task_id

        if session_id:
            filter_kwargs["session_id"] = session_id

        if since:
            try:
                filter_kwargs["since"] = EventFilter.from_time_string(since)
            except ValueError:
                pass

        db = get_db()
        event_filter = EventFilter(**filter_kwargs)
        events = db.get_events(event_filter)
        count_filter_kwargs = {k: v for k, v in filter_kwargs.items() if k not in ("limit", "offset")}
        total = db.get_event_count(EventFilter(**count_filter_kwargs))

        return {
            "events": [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "session_id": e.session_id,
                    "task_id": e.task_id,
                    "data": e.data,
                }
                for e in events
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(events) < total,
        }

    @app.get("/api/sessions")  # type: ignore[untyped-decorator]
    async def api_sessions(
        limit: int = Query(50, ge=1, le=200),
        task_id: str | None = Query(None),
        status: str | None = Query(None),
    ) -> dict[str, Any]:
        """Get sessions with filtering.

        Args:
            limit: Maximum sessions to return.
            task_id: Filter by task ID.
            status: Filter by status.

        Returns:
            Dictionary with sessions.
        """
        from ..observability.db import get_db
        from ..observability.models import SessionStatus

        db = get_db()

        status_filter = None
        if status:
            try:
                status_filter = SessionStatus(status)
            except ValueError:
                pass

        sessions = db.get_sessions(task_id=task_id, status=status_filter, limit=limit)

        return {
            "sessions": [
                {
                    "id": s.id,
                    "task_id": s.task_id,
                    "status": s.status.value,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                    "duration": s.duration_str,
                    "metadata": s.metadata,
                }
                for s in sessions
            ],
            "total": len(sessions),
        }

    @app.get("/api/tasks")  # type: ignore[untyped-decorator]
    async def api_tasks(
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        """Get recent task status from ADW state.

        Args:
            limit: Maximum tasks to return.

        Returns:
            Dictionary with tasks.
        """
        from ..agent.state import list_adw_states

        states = list_adw_states(limit=limit)

        return {
            "tasks": [
                {
                    "task_id": s.adw_id,
                    "current_phase": s.current_phase,
                    "phases_completed": s.phases_completed,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "errors": s.errors,
                    "worktree_path": s.worktree_path,
                }
                for s in states
            ],
            "total": len(states),
        }

    @app.get("/api/event-types")  # type: ignore[untyped-decorator]
    async def api_event_types() -> dict[str, Any]:
        """Get list of all event types."""
        from ..observability.models import EventType

        return {
            "event_types": [e.value for e in EventType],
        }

    # -------------------------------------------------------------------------
    # Server-Sent Events (SSE) for live streaming
    # -------------------------------------------------------------------------

    @app.get("/api/events/stream")  # type: ignore[untyped-decorator]
    async def events_stream(request: Request) -> StreamingResponse:
        """Stream events in real-time using Server-Sent Events.

        Returns:
            StreamingResponse with SSE format.
        """
        from ..observability.db import get_db

        async def event_generator() -> Any:
            """Generate SSE events."""
            db = get_db()
            last_event_id = 0

            # Get initial last event ID
            initial_events = db.get_events()
            if initial_events:
                last_event_id = initial_events[0].id or 0

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Poll for new events
                from ..observability.models import EventFilter

                new_events = db.get_events(EventFilter(limit=50))
                for event in reversed(new_events):
                    if event.id and event.id > last_event_id:
                        last_event_id = event.id
                        event_data = {
                            "id": event.id,
                            "timestamp": event.timestamp.isoformat(),
                            "event_type": event.event_type.value,
                            "session_id": event.session_id,
                            "task_id": event.task_id,
                            "data": event.data,
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"

                # Send heartbeat every 15 seconds
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    @app.get("/health")  # type: ignore[untyped-decorator]
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
        }

    return app


def _get_dashboard_html() -> str:
    """Get the dashboard HTML content.

    Returns:
        HTML string for the dashboard.
    """
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADW Dashboard</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --border-color: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-cyan: #58a6ff;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-yellow: #d29922;
            --accent-purple: #a371f7;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
        }

        h1 {
            font-size: 24px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        h1 .logo {
            color: var(--accent-cyan);
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: var(--text-secondary);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .stat-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 16px;
        }

        .stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }

        .stat-value {
            font-size: 28px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .stat-value.error { color: var(--accent-red); }
        .stat-value.active { color: var(--accent-green); }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 4px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 16px;
        }

        .tab {
            padding: 12px 16px;
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 14px;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab:hover {
            color: var(--text-primary);
        }

        .tab.active {
            color: var(--text-primary);
            border-bottom-color: var(--accent-cyan);
        }

        /* Event Table */
        .event-table-container {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow: hidden;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
        }

        .table-title {
            font-size: 14px;
            font-weight: 600;
        }

        .filter-controls {
            display: flex;
            gap: 8px;
        }

        .filter-select {
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-primary);
            padding: 6px 12px;
            font-size: 13px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 10px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            font-size: 13px;
        }

        th {
            background-color: var(--bg-tertiary);
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }

        tr:hover {
            background-color: var(--bg-tertiary);
        }

        .event-type {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }

        .event-type.tool_start, .event-type.tool_end {
            background-color: rgba(88, 166, 255, 0.2);
            color: var(--accent-cyan);
        }
        .event-type.error, .event-type.tool_error {
            background-color: rgba(248, 81, 73, 0.2);
            color: var(--accent-red);
        }
        .event-type.task_completed, .event-type.session_end {
            background-color: rgba(63, 185, 80, 0.2);
            color: var(--accent-green);
        }
        .event-type.warning {
            background-color: rgba(210, 153, 34, 0.2);
            color: var(--accent-yellow);
        }
        .event-type.safety_block {
            background-color: rgba(163, 113, 247, 0.2);
            color: var(--accent-purple);
        }

        .task-id, .session-id {
            font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 12px;
            color: var(--text-secondary);
        }

        .timestamp {
            color: var(--text-muted);
            font-size: 12px;
        }

        /* Sessions Panel */
        .session-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 12px;
        }

        .session-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .session-id {
            font-family: monospace;
            color: var(--accent-cyan);
        }

        .session-status {
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }

        .session-status.running {
            background-color: rgba(63, 185, 80, 0.2);
            color: var(--accent-green);
        }

        .session-status.completed {
            background-color: rgba(88, 166, 255, 0.2);
            color: var(--accent-cyan);
        }

        .session-status.failed {
            background-color: rgba(248, 81, 73, 0.2);
            color: var(--accent-red);
        }

        .session-meta {
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--text-secondary);
        }

        /* Panel */
        .panel {
            display: none;
        }

        .panel.active {
            display: block;
        }

        /* Load More */
        .load-more {
            display: block;
            width: 100%;
            padding: 12px;
            background-color: var(--bg-tertiary);
            border: none;
            color: var(--accent-cyan);
            cursor: pointer;
            font-size: 13px;
        }

        .load-more:hover {
            background-color: var(--border-color);
        }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 48px 24px;
            color: var(--text-secondary);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        /* Data Preview */
        .data-preview {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: monospace;
            font-size: 11px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <span class="logo">⚡</span>
                ADW Dashboard
            </h1>
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span id="connection-status">Connected</span>
            </div>
        </header>

        <div class="stats-grid" id="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Events</div>
                <div class="stat-value" id="stat-events">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Sessions</div>
                <div class="stat-value" id="stat-sessions">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Active Sessions</div>
                <div class="stat-value active" id="stat-active">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Errors (1h)</div>
                <div class="stat-value error" id="stat-errors">-</div>
            </div>
        </div>

        <div class="tabs">
            <button class="tab active" data-panel="events">Events</button>
            <button class="tab" data-panel="sessions">Sessions</button>
            <button class="tab" data-panel="tasks">Tasks</button>
        </div>

        <div class="panel active" id="events-panel">
            <div class="event-table-container">
                <div class="table-header">
                    <span class="table-title">Event Stream</span>
                    <div class="filter-controls">
                        <select class="filter-select" id="event-type-filter">
                            <option value="">All Types</option>
                        </select>
                        <select class="filter-select" id="time-filter">
                            <option value="">All Time</option>
                            <option value="1h">Last Hour</option>
                            <option value="24h">Last 24 Hours</option>
                            <option value="7d">Last 7 Days</option>
                        </select>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Type</th>
                            <th>Task</th>
                            <th>Session</th>
                            <th>Data</th>
                        </tr>
                    </thead>
                    <tbody id="events-tbody">
                    </tbody>
                </table>
                <button class="load-more" id="load-more-events">Load More</button>
            </div>
        </div>

        <div class="panel" id="sessions-panel">
            <div id="sessions-list">
            </div>
        </div>

        <div class="panel" id="tasks-panel">
            <div class="event-table-container">
                <div class="table-header">
                    <span class="table-title">Task Status</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Task ID</th>
                            <th>Phase</th>
                            <th>Created</th>
                            <th>Updated</th>
                            <th>Errors</th>
                        </tr>
                    </thead>
                    <tbody id="tasks-tbody">
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // State
        let eventsOffset = 0;
        const eventsLimit = 50;
        let eventSource = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadStats();
            loadEventTypes();
            loadEvents();
            loadSessions();
            loadTasks();
            setupTabs();
            setupFilters();
            setupSSE();

            // Refresh stats every 30 seconds
            setInterval(loadStats, 30000);
        });

        // Load statistics
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                document.getElementById('stat-events').textContent = stats.total_events.toLocaleString();
                document.getElementById('stat-sessions').textContent = stats.total_sessions.toLocaleString();
                document.getElementById('stat-active').textContent = stats.active_sessions.toLocaleString();
                document.getElementById('stat-errors').textContent = stats.recent_errors.toLocaleString();
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        }

        // Load event types for filter
        async function loadEventTypes() {
            try {
                const response = await fetch('/api/event-types');
                const data = await response.json();
                const select = document.getElementById('event-type-filter');
                data.event_types.forEach(type => {
                    const option = document.createElement('option');
                    option.value = type;
                    option.textContent = type.replace(/_/g, ' ');
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Failed to load event types:', error);
            }
        }

        // Load events
        async function loadEvents(append = false) {
            try {
                const eventType = document.getElementById('event-type-filter').value;
                const since = document.getElementById('time-filter').value;

                let url = `/api/events?limit=${eventsLimit}&offset=${eventsOffset}`;
                if (eventType) url += `&event_type=${eventType}`;
                if (since) url += `&since=${since}`;

                const response = await fetch(url);
                const data = await response.json();

                const tbody = document.getElementById('events-tbody');
                if (!append) {
                    tbody.innerHTML = '';
                }

                if (data.events.length === 0 && !append) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="5" class="empty-state">
                                <div class="empty-state-icon">📭</div>
                                No events found
                            </td>
                        </tr>
                    `;
                    return;
                }

                data.events.forEach(event => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="timestamp">${formatTimestamp(event.timestamp)}</td>
                        <td><span class="event-type ${event.event_type}">${event.event_type}</span></td>
                        <td class="task-id">${event.task_id || '-'}</td>
                        <td class="session-id">${event.session_id ? event.session_id.substring(0, 8) : '-'}</td>
                        <td class="data-preview">${formatData(event.data)}</td>
                    `;
                    tbody.appendChild(row);
                });

                // Show/hide load more button
                const loadMoreBtn = document.getElementById('load-more-events');
                loadMoreBtn.style.display = data.has_more ? 'block' : 'none';
            } catch (error) {
                console.error('Failed to load events:', error);
            }
        }

        // Load sessions
        async function loadSessions() {
            try {
                const response = await fetch('/api/sessions?limit=50');
                const data = await response.json();

                const container = document.getElementById('sessions-list');
                container.innerHTML = '';

                if (data.sessions.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📭</div>
                            No sessions found
                        </div>
                    `;
                    return;
                }

                data.sessions.forEach(session => {
                    const card = document.createElement('div');
                    card.className = 'session-card';
                    card.innerHTML = `
                        <div class="session-header">
                            <span class="session-id">${session.id}</span>
                            <span class="session-status ${session.status}">${session.status}</span>
                        </div>
                        <div class="session-meta">
                            <span>Task: ${session.task_id || 'N/A'}</span>
                            <span>Duration: ${session.duration}</span>
                            <span>Started: ${formatTimestamp(session.start_time)}</span>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (error) {
                console.error('Failed to load sessions:', error);
            }
        }

        // Load tasks
        async function loadTasks() {
            try {
                const response = await fetch('/api/tasks?limit=50');
                const data = await response.json();

                const tbody = document.getElementById('tasks-tbody');
                tbody.innerHTML = '';

                if (data.tasks.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="5" class="empty-state">
                                <div class="empty-state-icon">📭</div>
                                No tasks found
                            </td>
                        </tr>
                    `;
                    return;
                }

                data.tasks.forEach(task => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="task-id">${task.task_id}</td>
                        <td><span class="event-type">${task.current_phase}</span></td>
                        <td class="timestamp">${formatTimestamp(task.created_at)}</td>
                        <td class="timestamp">${formatTimestamp(task.updated_at)}</td>
                        <td>${task.errors.length}</td>
                    `;
                    tbody.appendChild(row);
                });
            } catch (error) {
                console.error('Failed to load tasks:', error);
            }
        }

        // Setup tabs
        function setupTabs() {
            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    // Update active tab
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');

                    // Update active panel
                    const panelId = tab.dataset.panel + '-panel';
                    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                    document.getElementById(panelId).classList.add('active');
                });
            });
        }

        // Setup filters
        function setupFilters() {
            document.getElementById('event-type-filter').addEventListener('change', () => {
                eventsOffset = 0;
                loadEvents();
            });

            document.getElementById('time-filter').addEventListener('change', () => {
                eventsOffset = 0;
                loadEvents();
            });

            document.getElementById('load-more-events').addEventListener('click', () => {
                eventsOffset += eventsLimit;
                loadEvents(true);
            });
        }

        // Setup Server-Sent Events
        function setupSSE() {
            eventSource = new EventSource('/api/events/stream');

            eventSource.onmessage = (event) => {
                if (event.data.startsWith(':')) return; // heartbeat

                try {
                    const eventData = JSON.parse(event.data);
                    prependEvent(eventData);
                    loadStats(); // Refresh stats on new event
                } catch (e) {
                    // Ignore parse errors
                }
            };

            eventSource.onerror = () => {
                document.getElementById('connection-status').textContent = 'Reconnecting...';
                setTimeout(() => {
                    document.getElementById('connection-status').textContent = 'Connected';
                }, 3000);
            };

            eventSource.onopen = () => {
                document.getElementById('connection-status').textContent = 'Connected';
            };
        }

        // Prepend new event to table
        function prependEvent(event) {
            const tbody = document.getElementById('events-tbody');
            const emptyRow = tbody.querySelector('.empty-state');
            if (emptyRow) {
                tbody.innerHTML = '';
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="timestamp">${formatTimestamp(event.timestamp)}</td>
                <td><span class="event-type ${event.event_type}">${event.event_type}</span></td>
                <td class="task-id">${event.task_id || '-'}</td>
                <td class="session-id">${event.session_id ? event.session_id.substring(0, 8) : '-'}</td>
                <td class="data-preview">${formatData(event.data)}</td>
            `;

            // Highlight new row briefly
            row.style.backgroundColor = 'rgba(88, 166, 255, 0.1)';
            setTimeout(() => {
                row.style.backgroundColor = '';
            }, 2000);

            tbody.insertBefore(row, tbody.firstChild);
        }

        // Format timestamp
        function formatTimestamp(isoString) {
            if (!isoString) return '-';
            const date = new Date(isoString);
            return date.toLocaleTimeString() + ' ' + date.toLocaleDateString();
        }

        // Format data preview
        function formatData(data) {
            if (!data || Object.keys(data).length === 0) return '-';
            return JSON.stringify(data).substring(0, 100);
        }
    </script>
</body>
</html>'''


def start_dashboard_server(
    host: str = "0.0.0.0",
    port: int = DEFAULT_DASHBOARD_PORT,
    reload: bool = False,
) -> None:
    """Start the web dashboard server.

    Args:
        host: Host to bind to.
        port: Port to listen on (default: 3939).
        reload: Enable auto-reload for development.
    """
    import uvicorn

    uvicorn.run(
        "adw.dashboard.server:create_dashboard_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )
