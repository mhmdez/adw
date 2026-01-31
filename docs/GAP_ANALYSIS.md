# ADW Gap Analysis: User Flow Audit

**Date**: 2026-01-31
**Auditor**: studbot (via deep code exploration)

---

## Executive Summary

ADW has excellent foundations but the **user-facing flow is incomplete**. The core pieces exist (agent spawning, worktree isolation, log streaming, message injection) but they're not wired together into a cohesive interactive experience.

**Main Issue**: The tool assumes users will jump between CLI, TUI, and Claude Code manually. There's no unified flow where users can stay in the TUI and complete the full cycle: discuss → spec → approve → execute → monitor.

---

## Intended User Flow

```
1. Install:     pip install adw
2. Init:        adw init (in project)
3. Start:       adw (opens TUI)
4. New Task:    /new "add user auth"
5. Discuss:     → Claude asks questions → creates spec
6. Approve:     → User reviews spec → approves
7. Execute:     → Tasks spawned in worktrees
8. Monitor:     → Live logs, can inject messages
9. Complete:    → PR created
```

---

## Gap Analysis

### 🔴 Critical Gaps

#### 1. TUI doesn't implement full discuss flow

**Current**: `/new <desc>` in TUI spawns a simple prompt:
```python
# From app.py line 570
prompt=f"Task ID: {adw_id}\n\nPlease complete this task:\n\n{description}\n\n..."
```

**Expected**: Should use the `/discuss` workflow that:
- Reads CLAUDE.md for context
- Explores codebase
- **Asks clarifying questions** (blocks for user input!)
- Creates spec with PENDING_APPROVAL status

**Impact**: Users get a fire-and-forget experience instead of interactive planning.

---

#### 2. No mechanism for agent → user questions

**Current**: No way for a running agent to:
- Pause execution
- Ask user a question
- Wait for response
- Resume

**The `/discuss` command says**:
```markdown
3. **Ask clarifying questions**
   - Use AskUserQuestion for ambiguous requirements
```

But there's no `AskUserQuestion` implementation that bridges to TUI!

**Needed**:
- Special message type: `QUESTION_PENDING`
- TUI widget to show pending questions
- Input flow for user to answer
- Message injection to resume agent

---

#### 3. Spec approval not in TUI

**Current**: 
- `adw approve <spec>` exists in CLI only
- TUI has no `/approve` command
- No view for pending specs
- No review/approve/reject flow

**Needed**:
```
/specs           # List specs with status
/approve <name>  # Approve spec, create tasks
/reject <name>   # Reject with reason
```

Plus a specs panel or modal in TUI.

---

#### 4. BLOCKED tasks have no context

**Current** in tasks.md:
```markdown
[⏰] Add OAuth integration (blocked)
```

**Missing**:
- WHY is it blocked?
- What does it need from user?
- When can it resume?

**Needed** - extended format:
```markdown
[⏰] Add OAuth integration
  - Blocked: Waiting for OAuth provider credentials
  - Needs: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  - Unblock: /unblock <task-id> with env vars
```

---

### 🟡 Important Gaps

#### 5. No attention/notification system

**Current**: If an agent needs input, user has to notice in logs.

**Needed**:
- Visual indicator in TUI (bell icon, flashing status)
- Sound/notification option
- `/attention` command to see what needs user action

---

#### 6. Task phases not visible in TUI

**Current**: `TaskState` has `phase` field but it's not populated or shown.

**Needed**:
```
Task abc123 [🟡 IMPLEMENTING]
  Phase: implement (2/4)
  Activity: Writing tests...
  Duration: 3m 22s
```

---

#### 7. Daemon doesn't handle blocked → ready transitions

**Current** `_daemon_tick`:
```python
eligible = [t for t in self.state.tasks.values() if t.status == TaskStatus.PENDING]
```

**Missing**: No logic to:
- Check if blocked tasks are now unblocked
- Notify user of unblocked tasks
- Auto-resume when dependencies complete

---

### 🟢 Nice-to-Have Gaps

#### 8. No task dependency visualization

User can't see which tasks depend on which. Would help understanding why something is blocked.

#### 9. No worktree management in TUI

`adw worktree list` exists in CLI but not in TUI.

#### 10. No history/timeline view

Can't see what happened, when, in what order.

---

## Suggested Architecture for Fixes

### Message Protocol Extension

Add new message types to `protocol/messages.py`:

```python
class MessageType(str, Enum):
    USER_MESSAGE = "user_message"      # Existing
    QUESTION = "question"              # Agent asks user
    ANSWER = "answer"                  # User answers agent
    ATTENTION = "attention"            # Agent needs user
    STATUS = "status"                  # Phase update

class AgentQuestion(BaseModel):
    """Question from agent needing user input."""
    question: str
    context: str | None = None
    options: list[str] | None = None  # Multiple choice
    required: bool = True
    timeout_action: str = "block"     # block | skip | default
```

### TUI State Extension

```python
@dataclass
class TaskState:
    # ... existing ...
    pending_question: AgentQuestion | None = None
    blocked_reason: str | None = None
    blocked_needs: list[str] | None = None
```

### New TUI Components

1. **QuestionModal**: Pop-up when agent asks question
2. **SpecsPanel**: Shows specs awaiting approval
3. **AttentionIndicator**: Badge/icon for items needing action
4. **TaskDetailView**: Full task info with phases, deps, history

### New Commands

```
/specs              # List specs
/approve <name>     # Approve spec
/reject <name>      # Reject spec
/unblock <task-id>  # Provide blocked info
/attention          # What needs me?
/deps <task-id>     # Show dependencies
```

---

## Implementation Priority

### Phase 1: User Input Flow (Critical)
1. Add `QUESTION` message type
2. Implement question detection in log watcher
3. Add QuestionModal to TUI
4. Wire answer back to agent

### Phase 2: Spec Management
1. Add `/specs` command to TUI
2. Add `/approve` and `/reject`
3. Show pending specs count in status line

### Phase 3: Blocked Task Handling
1. Extend tasks.md format for blocked reason
2. Add `blocked_reason` to TaskState
3. Implement `/unblock` command
4. Add attention indicator

### Phase 4: Polish
1. Task phases in UI
2. Dependency visualization
3. Timeline/history view
4. Notifications

---

## Questions for Mo

1. **How should questions block?** Modal that steals focus? Or just highlight in log and wait?

2. **Multi-agent questions**: If 3 agents ask questions simultaneously, queue them? Show all?

3. **Spec approval detail**: Just approve/reject? Or allow inline edits to spec?

4. **Persistence**: Should pending questions survive TUI restart? (Currently messages.jsonl persists but TUI state doesn't)

---

## Appendix: Current File Structure

```
src/adw/
├── agent/
│   ├── executor.py      # Claude Code subprocess
│   ├── manager.py       # Process management
│   ├── state.py         # ADWState persistence
│   ├── task_updater.py  # tasks.md atomic updates
│   └── models.py        # Pydantic models
├── protocol/
│   └── messages.py      # Agent communication
├── tui/
│   ├── app.py           # Main TUI app
│   ├── state.py         # Reactive state
│   ├── commands.py      # Slash command handlers
│   └── widgets/         # UI components
├── workflows/
│   ├── simple.py        # Build only
│   └── standard.py      # Plan → Implement
├── cli.py               # CLI entry point
├── init.py              # Project initialization
├── specs.py             # Spec parsing
└── tasks.py             # Task parsing
```

---

*Generated by studbot after deep exploration of ~/Sites/adw*
