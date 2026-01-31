# ADW Build Task Board

> **Zero-Touch Engineering Build**
> Building ADW using ADW principles - self-bootstrapping system

---

## Worktree: phase-01-foundation

[✅, 0885689d] Create src/adw/agent/models.py with Pydantic data models {opus}
[✅, 120c27d2] Create src/adw/agent/utils.py with ADW ID generation and helpers
[⏰] Create src/adw/agent/executor.py with Claude Code execution
[⏰] Create src/adw/agent/state.py with persistent state manager
[⏰] Create src/adw/agent/__init__.py exporting all modules
[⏰] Create tests/test_agent/ with unit tests for foundation
[⏰] Verify Phase 1: Run tests and validate foundation modules work

---

## Worktree: phase-02-tui-shell

[✅, 877f7075] Update pyproject.toml with textual and watchfiles dependencies
[✅, 55cf7cb5] Create src/adw/tui/__init__.py package
[⏰] Create src/adw/tui/styles.tcss stylesheet
[⏰] Create src/adw/tui/widgets/status_bar.py widget
[⏰] Create src/adw/tui/app.py with basic Textual app shell
[⏰] Update src/adw/cli.py to launch TUI as default command
[⏰] Verify Phase 2: TUI launches with placeholder panels

---

## Worktree: phase-03-task-system

[✅, 7dff1da0] Create src/adw/agent/task_parser.py to parse tasks.md
[✅, 0ad90e90] Create src/adw/agent/task_updater.py for atomic status updates
[⏰] Create src/adw/tui/state.py with reactive AppState
[⏰] Create src/adw/tui/widgets/task_list.py widget
[⏰] Create src/adw/tui/widgets/task_detail.py widget
[⏰] Update src/adw/tui/app.py to use real task widgets
[⏰] Verify Phase 3: Tasks from tasks.md display in TUI

---

## Worktree: phase-04-agent-system

[✅, b6ebab17] Create src/adw/agent/manager.py for process management {opus}
[✅, 6b4f4182] Create src/adw/workflows/__init__.py package
[⏰] Create src/adw/workflows/simple.py (build-update workflow)
[⏰] Create src/adw/workflows/standard.py (plan-implement-update) {opus}
[⏰] Update src/adw/tui/app.py with agent manager integration
[⏰] Add new task spawning from TUI
[⏰] Verify Phase 4: Can spawn agent from TUI and track completion

---

## Worktree: phase-05-log-streaming

[✅, cad483ef] Create src/adw/tui/log_watcher.py with watchfiles
[✅, f048a6ce] Create src/adw/tui/log_formatter.py for event formatting
[⏰] Create src/adw/tui/log_buffer.py for buffering
[⏰] Create src/adw/tui/widgets/log_viewer.py widget
[⏰] Update src/adw/tui/app.py with log watcher integration
[⏰] Verify Phase 5: Live logs stream to TUI when agents run

---

## Worktree: phase-06-messages

[✅, af23639b] Create src/adw/protocol/messages.py with message models
[✅, e8889a66] Create .claude/hooks/check_messages.py hook
[⏰] Update src/adw/tui/widgets/status_bar.py for message input
[⏰] Wire message submission to write to agent message file
[⏰] Verify Phase 6: Can send message to running agent

---

## Worktree: phase-07-cron

[✅, ff660f13] Create src/adw/triggers/__init__.py package
[✅, 0050c905] Create src/adw/triggers/cron.py daemon {opus}
[⏰] Add dependency checking for blocked tasks
[⏰] Add concurrent task limiting
[⏰] Add CLI command: adw run
[⏰] Verify Phase 7: adw run picks up and executes pending tasks

---

## Worktree: phase-08-worktrees

[✅, c662aa37] Create src/adw/agent/worktree.py for git worktree management
[✅, 6b5bc2b8] Create src/adw/agent/ports.py for port allocation
[⏰] Create src/adw/agent/environment.py for env isolation
[⏰] Add worktree creation to workflows
[⏰] Add CLI commands: adw worktree list/create/remove
[⏰] Verify Phase 8: Tasks run in isolated worktrees

---

## Worktree: phase-09-observability

[✅, 64a0ce3f] Create .claude/settings.json template with hooks config
[✅, f217e14f] Create .claude/hooks/context_bundle_builder.py
[⏰] Create .claude/hooks/universal_logger.py
[⏰] Create .claude/output-styles/concise-done.md
[⏰] Create .claude/output-styles/concise-ultra.md
[⏰] Create .claude/commands/load_bundle.md
[⏰] Create .claude/commands/prime.md
[⏰] Verify Phase 9: Hooks capture events and context bundles work

---

## Worktree: phase-10-workflows

[✅, 39f1ef3b] Create src/adw/workflows/sdlc.py SDLC phases and imports
[✅, 3836463b] Create src/adw/workflows/sdlc.py run_sdlc_workflow function
[⏰] Create src/adw/workflows/sdlc.py helper functions
[⏰] Create src/adw/workflows/prototype.py with prototype configs
[⏰] Create src/adw/agent/model_selector.py
[⏰] Create .claude/commands/plan.md template
[⏰] Create .claude/commands/implement.md template
[⏰] Create .claude/commands/test.md template
[⏰] Create .claude/commands/review.md template
[⏰] Create .claude/commands/document.md template
[⏰] Create .claude/commands/plan_vite_vue.md prototype template
[⏰] Verify Phase 10: Full SDLC workflow executes end-to-end

---

## Worktree: phase-11-github

[✅, 87a9aa38] Create src/adw/integrations/__init__.py package
[✅, 51565d9c] Create src/adw/integrations/github.py API wrapper
[⏰] Create src/adw/triggers/github.py polling trigger
[⏰] Create src/adw/triggers/webhook.py FastAPI handler
[⏰] Add CLI commands: adw github watch/process
[⏰] Verify Phase 11: Can trigger workflow from GitHub issue

---

## Worktree: phase-12-self-improvement

[✅, 291d0993] Create .claude/commands/experts/cc_expert.md {opus}
[✅, 892118f6] Create .claude/commands/experts/cc_expert_improve.md
[⏰] Create .claude/commands/load_ai_docs.md
[⏰] Create .claude/commands/create_agent.md
[⏰] Create ai_docs/README.md with documentation sources
[⏰] Verify Phase 12: Expert system can be queried and improved

---

## Worktree: final-validation

[✅, 90e11ede] Run full test suite
[✅, 793a7295] Test complete workflow: adw new "test feature" through PR
[⏰] Update README.md with new features
[⏰] Update CLAUDE.md with ADW orchestration docs
[⏰] Tag release v0.2.0

---

## Legend

- `[]` = Ready to start
- `[⏰]` = Blocked (waiting for tasks above to complete)
- `[🟡, adw_id]` = In progress
- `[✅ commit, adw_id]` = Completed
- `[❌, adw_id]` = Failed

## Tags

- `{opus}` = Use Opus model for complex reasoning
- `{sonnet}` = Use Sonnet model (default)
