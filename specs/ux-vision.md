# ADW UX Vision Spec

*Captured from Mo's brainstorm — 2026-02-01*

---

## 1. TUI Task Dashboard

### Current State
- Simple command-based interface
- `adw watch` shows status but no interaction

### Vision: Interactive Task Table

```
╭─────────────────────────────────────────────────────────╮
│  ADW Dashboard                              v0.3.3      │
├─────────────────────────────────────────────────────────┤
│  Welcome back! 2 tasks running, 5 pending              │
╰─────────────────────────────────────────────────────────╯

  RUNNING (2)                                    [↑↓ navigate]
  ┌──────────────────────────────────────────────────────┐
  │ ▶ [abc123] Implement user auth         3m 42s  opus  │
  │   [def456] Fix payment webhook         1m 15s  sonnet│
  └──────────────────────────────────────────────────────┘
  
  PENDING (5)                                    [+3 more...]
  ┌──────────────────────────────────────────────────────┐
  │   [ ] Add email notifications                        │
  │   [ ] Refactor database layer                        │
  └──────────────────────────────────────────────────────┘
  
  [Tab: History] [Enter: View logs] [P: Pause] [Q: Quit]
  
  > _
```

### Interactions
- **↑↓** — Navigate task list
- **Enter** — View logs for selected task
- **Tab** — Switch between Running/Pending/History
- **P** — Pause/Resume daemon
- **C** — Cancel selected task
- **R** — Retry failed task
- **A** — Add new task (opens input)
- **/** — Command mode

### Pagination Rules
- **Running**: Show all (usually ≤3)
- **Pending**: Show 3, then "+N more..." 
- **History**: Show last 5, paginated

---

## 2. History & Completed Tasks

### Where to Store?
Option A: In tasks.md (current)
- ✅ Simple
- ❌ File gets huge over time

Option B: Separate history.md
- ✅ Clean separation
- ✅ Can archive/rotate
- ❌ Another file to manage

Option C: SQLite database
- ✅ Proper querying
- ✅ Metrics/analytics
- ❌ More complex

**Recommendation**: Start with Option B, migrate to C later

### History Display
```
  HISTORY (last 7 days)                         [+42 more...]
  ┌──────────────────────────────────────────────────────┐
  │ ✓ [xyz789] Deploy v2.1.0           12:34  2m 15s     │
  │ ✗ [abc999] Fix login bug           11:22  45s  FAIL  │
  │ ✓ [def111] Update deps             10:15  1m 30s     │
  └──────────────────────────────────────────────────────┘
```

---

## 3. Navigation

### Option A: Command-only (current)
```
> /run
> /pause
> /help
```

### Option B: Hybrid Menu + Commands
```
  [1] Tasks  [2] History  [3] Agents  [4] Settings  [?] Help
  
  Currently: Tasks
  > 
```

### Option C: Tab-based Panels
```
  ┌─ Tasks ─┬─ History ─┬─ Agents ─┬─ Logs ─┐
  │ ...                                      │
```

**Recommendation**: Option B — menu hints + command power

---

## 4. Project Context Auto-Update

### Problem
After completing tasks, project understanding drifts from reality.

### Solution: Post-Task Documentation Sync

When a task completes:
1. Agent summarizes what changed
2. Updates relevant sections of CLAUDE.md
3. Optionally updates README, API docs

### Implementation
```yaml
# In agent workflow, after task completion:
post_task:
  - update_context: true
  - sections:
      - architecture
      - api_endpoints
      - dependencies
```

### What to Update
- **CLAUDE.md** — Project-specific instructions
- **API.md** — If endpoints changed
- **ARCHITECTURE.md** — If structure changed
- **CHANGELOG.md** — Always

---

## 5. .gitignore Best Practices

### What ADW Creates
```
agents/           # Agent workspaces & logs
.adw/             # State, config, daemon.json
trees/            # Git worktrees (if used)
specs/            # Feature specs (maybe keep?)
```

### Recommendation

**Add to .gitignore:**
```gitignore
# ADW - AI Developer Workflow
agents/
.adw/
trees/
*.adw.log
```

**Keep in git:**
```
specs/           # Valuable documentation
tasks.md         # Task history (or archive old)
CLAUDE.md        # Project context
```

### On `adw init`
- Auto-append to .gitignore
- Ask user: "Add ADW folders to .gitignore? (Y/n)"

---

## 6. Smart Initialization

### Current `adw init`
1. Create folders (.claude/, specs/)
2. Generate CLAUDE.md template
3. Create tasks.md

### Enhanced `adw init`

```
$ adw init

Analyzing project...
  ✓ Detected: Next.js + TypeScript + Prisma
  ✓ Found: 142 source files, 23 components
  ✓ APIs: 12 endpoints in /api
  
Generating documentation...
  ✓ CLAUDE.md — Project context (2.3KB)
  ✓ ARCHITECTURE.md — System overview
  ✓ API.md — Endpoint documentation
  
Setting up workflow...
  ✓ .claude/commands/ — 4 commands
  ✓ specs/ — Template created
  ✓ .gitignore — Updated
  
Ready! Run 'adw' to open dashboard.
```

### What Claude Code Analyzes
1. **Stack Detection** — frameworks, languages, tools
2. **Structure Mapping** — folders, key files, patterns
3. **API Discovery** — endpoints, schemas, auth
4. **Dependency Graph** — imports, external services
5. **Conventions** — naming, style, patterns

### Output
- `CLAUDE.md` — Tailored project instructions
- `ARCHITECTURE.md` — Visual + text overview
- `API.md` — Endpoint docs (if applicable)
- `.adw/project.json` — Cached analysis

---

## 7. Implementation Priority

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Interactive task table | Medium | High | P1 |
| .gitignore on init | Low | Medium | P1 |
| History separation | Low | Medium | P2 |
| Smart init analysis | High | High | P2 |
| Navigation menu | Medium | Medium | P2 |
| Auto-update context | High | High | P3 |

---

## Next Steps

1. **P1: Quick Wins**
   - Add .gitignore handling to `adw init`
   - Basic task table in TUI

2. **P2: Core UX**
   - History file + display
   - Smart init with project analysis
   - Tab navigation

3. **P3: Advanced**
   - Post-task context updates
   - Analytics dashboard
   - Multi-project support

---

*This spec is a living document. Update as we learn more.*
