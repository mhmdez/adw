# Spec: Event Dashboard

## Job to Be Done
Provide real-time visibility into what ADW agents are doing via a web dashboard and TUI improvements.

## Acceptance Criteria

### 1. Event Database
- [ ] Create `src/adw/observability/db.py`
- [ ] SQLite database at `.adw/events.db`
- [ ] Tables:
  - `events`: id, timestamp, type, session_id, data (JSON)
  - `sessions`: id, start_time, end_time, task_id, status
- [ ] Functions: `log_event()`, `get_events()`, `get_session()`

### 2. TUI Event Feed
- [ ] Add event stream panel to existing Textual TUI
- [ ] Show last 50 events in real-time
- [ ] Color-code by type (tool=cyan, error=red, success=green)
- [ ] Keyboard: `E` to toggle event panel

### 3. Web Dashboard (Stretch)
- [ ] Create `src/adw/dashboard/server.py`
- [ ] FastAPI server on port 3939
- [ ] Routes:
  - `GET /` — Dashboard HTML
  - `GET /api/events` — JSON event list
  - `GET /api/sessions` — Session list
  - `WS /ws` — WebSocket for live updates
- [ ] Simple Vue.js or vanilla JS frontend
- [ ] Command: `adw dashboard --web`

### 4. Event Filtering
- [ ] Filter by: event_type, session_id, time_range
- [ ] CLI: `adw events --type tool --since 1h`
- [ ] Web: Dropdown filters

### 5. Session Replay (Stretch)
- [ ] View all events for a specific session
- [ ] Step through events chronologically
- [ ] Show file diffs at each step

## Technical Notes
- Keep dashboard lightweight (no heavy deps)
- Use Server-Sent Events (SSE) as alternative to WebSocket
- Dashboard should work offline (local files)

## Testing
- [ ] Unit tests for database operations
- [ ] Integration test for event logging flow
