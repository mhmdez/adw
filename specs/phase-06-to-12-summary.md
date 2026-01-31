# Phases 6-12: Summary Specifications

These phases build on the foundation. Each gets a detailed spec when we reach it.

---

## Phase 6: Message Injection

**Dependencies**: Phase 1-5

**Objective**: Enable bidirectional communication with running agents.

**Key Deliverables**:
- Message file protocol (`agents/{adw_id}/adw_messages.jsonl`)
- Hook to check for messages (`check_messages.py`)
- TUI message input wiring
- Priority system (normal, high, interrupt)

**Files**:
- `src/adw/protocol/messages.py`
- `.claude/hooks/check_messages.py`
- Update `src/adw/tui/widgets/status_bar.py`

---

## Phase 7: Autonomous Execution (Cron)

**Dependencies**: Phase 1-6

**Objective**: Automatic task pickup and execution.

**Key Deliverables**:
- Cron trigger daemon
- Task eligibility checking
- Dependency enforcement (blocked tasks)
- Concurrent task limits
- CLI command: `adw run`

**Files**:
- `src/adw/triggers/cron.py`
- `src/adw/triggers/__init__.py`
- Update `src/adw/cli.py`

---

## Phase 8: Parallel Isolation (Worktrees)

**Dependencies**: Phase 1-7

**Objective**: Git worktree management for parallel execution.

**Key Deliverables**:
- Worktree create/remove/list
- Sparse checkout support
- Port allocation
- Environment isolation
- CLI commands: `adw worktree *`

**Files**:
- `src/adw/agent/worktree.py`
- `src/adw/agent/ports.py`
- `src/adw/agent/environment.py`

---

## Phase 9: Observability (Hooks)

**Dependencies**: Phase 1-8

**Objective**: Hook system for full observability.

**Key Deliverables**:
- Hook configuration (`.claude/settings.json`)
- Context bundle builder hook
- Universal logger hook
- Output styles
- Load bundle command

**Files**:
- `.claude/settings.json` template
- `.claude/hooks/context_bundle_builder.py`
- `.claude/hooks/universal_logger.py`
- `.claude/output-styles/*.md`
- `.claude/commands/load_bundle.md`

---

## Phase 10: Advanced Workflows

**Dependencies**: Phase 1-9

**Objective**: Full SDLC and prototype workflows.

**Key Deliverables**:
- Full SDLC workflow (6 phases)
- Prototype workflows (vite_vue, uv_script, bun_scripts)
- Slash command templates (all)
- Model selection strategy

**Files**:
- `src/adw/workflows/sdlc.py`
- `src/adw/workflows/prototype.py`
- `.claude/commands/*.md` (all templates)
- `src/adw/agent/model_selector.py`

---

## Phase 11: GitHub Integration

**Dependencies**: Phase 1-10

**Objective**: GitHub-triggered workflows.

**Key Deliverables**:
- GitHub API integration
- Issue fetcher
- PR creator
- GitHub trigger (polling)
- Webhook handler
- CLI: `adw github *`

**Files**:
- `src/adw/integrations/github.py`
- `src/adw/triggers/github.py`
- `src/adw/triggers/webhook.py`

---

## Phase 12: Self-Improvement

**Dependencies**: Phase 1-11

**Objective**: Self-improving expert system.

**Key Deliverables**:
- Expert system framework
- AI docs loader
- Meta-agent generator
- Expert commands

**Files**:
- `.claude/commands/experts/cc_expert.md`
- `.claude/commands/experts/cc_expert_improve.md`
- `.claude/commands/load_ai_docs.md`
- `.claude/commands/create_agent.md`

---

## Build Order Summary

```
Phase 1: Foundation           ← Core models, executor, state
Phase 2: TUI Shell            ← Empty dashboard layout
Phase 3: Task System          ← Parser, widgets, state sync
Phase 4: Agent System         ← Spawn, manage, workflows
Phase 5: Log Streaming        ← Watch files, display logs
Phase 6: Message Injection    ← User → Agent messages
Phase 7: Cron Trigger         ← Autonomous execution
Phase 8: Worktrees            ← Parallel isolation
Phase 9: Hooks                ← Observability
Phase 10: Advanced Workflows  ← SDLC, prototypes
Phase 11: GitHub              ← External integration
Phase 12: Self-Improvement    ← Expert systems
```

Each phase builds on previous phases. Dependencies are strict - a phase cannot start until all its dependencies are complete.
