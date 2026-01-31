# ADW Build Task Board

> **Zero-Touch Engineering Build**
> Building ADW using ADW principles - self-bootstrapping system

---

## Worktree: phase-01-foundation

[✅, 0885689d] Create src/adw/agent/models.py with Pydantic data models {opus}
[✅, 120c27d2] Create src/adw/agent/utils.py with ADW ID generation and helpers
[✅, db260d24] Create src/adw/agent/executor.py with Claude Code execution
[✅, 0aeb6832] Create src/adw/agent/state.py with persistent state manager
[✅, ef376abd] Create src/adw/agent/__init__.py exporting all modules
[✅, bb7373ab] Create tests/test_agent/ with unit tests for foundation
[⏰] Verify Phase 1: Run tests and validate foundation modules work

---

## Worktree: phase-02-tui-shell

[✅, 877f7075] Update pyproject.toml with textual and watchfiles dependencies
[✅, 55cf7cb5] Create src/adw/tui/__init__.py package
[✅, a645c9c3] Create src/adw/tui/styles.tcss stylesheet
[✅, be3b15e5] Create src/adw/tui/widgets/status_bar.py widget
[✅, 0c2b79bd] Create src/adw/tui/app.py with basic Textual app shell
[✅, a1a8f5d0] Update src/adw/cli.py to launch TUI as default command
[⏰] Verify Phase 2: TUI launches with placeholder panels

---

## Worktree: phase-03-task-system

[✅, 7dff1da0] Create src/adw/agent/task_parser.py to parse tasks.md
[✅, 0ad90e90] Create src/adw/agent/task_updater.py for atomic status updates
[✅, 7c99f459] Create src/adw/tui/state.py with reactive AppState
[✅, 9b013f3c] Create src/adw/tui/widgets/task_list.py widget
[✅, a669cdd4] Create src/adw/tui/widgets/task_detail.py widget
[✅, d18dde3e] Update src/adw/tui/app.py to use real task widgets
[⏰] Verify Phase 3: Tasks from tasks.md display in TUI

---

## Worktree: phase-04-agent-system

[✅, b6ebab17] Create src/adw/agent/manager.py for process management {opus}
[✅, 6b4f4182] Create src/adw/workflows/__init__.py package
[✅, a5e05f50] Create src/adw/workflows/simple.py (build-update workflow)
[✅, f5693f55] Create src/adw/workflows/standard.py (plan-implement-update) {opus}
[✅, a5f169b1] Update src/adw/tui/app.py with agent manager integration
[✅, d0350c72] Add new task spawning from TUI
[⏰] Verify Phase 4: Can spawn agent from TUI and track completion

---

## Worktree: phase-05-log-streaming

[✅, cad483ef] Create src/adw/tui/log_watcher.py with watchfiles
[✅, f048a6ce] Create src/adw/tui/log_formatter.py for event formatting
[✅, 3e2eaef6] Create src/adw/tui/log_buffer.py for buffering
[✅, 1a7ef2ab] Create src/adw/tui/widgets/log_viewer.py widget
[✅, 5e10300e] Update src/adw/tui/app.py with log watcher integration
[✅, 079ba881] Verify Phase 5: Live logs stream to TUI when agents run

---

## Worktree: phase-06-messages

[✅, af23639b] Create src/adw/protocol/messages.py with message models
[✅, e8889a66] Create .claude/hooks/check_messages.py hook
[✅, ac5c2a17] Update src/adw/tui/widgets/status_bar.py for message input
[✅, dd2b55c1] Wire message submission to write to agent message file
[✅, 348d5fef] Verify Phase 6: Can send message to running agent

---

## Worktree: phase-07-cron

[✅, ff660f13] Create src/adw/triggers/__init__.py package
[✅, 0050c905] Create src/adw/triggers/cron.py daemon {opus}
[✅, 4a334df5] Add dependency checking for blocked tasks
[✅, da46c75f] Add concurrent task limiting
[✅, dc8d457d] Add CLI command: adw run
[✅, 19ea7062] Verify Phase 7: adw run picks up and executes pending tasks

---

## Worktree: phase-08-worktrees

[✅, c662aa37] Create src/adw/agent/worktree.py for git worktree management
[✅, 6b5bc2b8] Create src/adw/agent/ports.py for port allocation
[✅, 03e166af] Create src/adw/agent/environment.py for env isolation
[✅, 077e7d8f] Add worktree creation to workflows
[✅, 5a9037d8] Add CLI commands: adw worktree list/create/remove
[✅, 04099a3c] Verify Phase 8: Tasks run in isolated worktrees

---

## Worktree: phase-09-observability

[✅, 64a0ce3f] Create .claude/settings.json template with hooks config
[✅, f217e14f] Create .claude/hooks/context_bundle_builder.py
[✅, 43618974] Create .claude/hooks/universal_logger.py
[✅, 16e9f51b] Create .claude/output-styles/concise-done.md
[✅, 435b5baa] Create .claude/output-styles/concise-ultra.md
[✅, 3ec348a1] Create .claude/commands/load_bundle.md
[⏰] Create .claude/commands/prime.md
[⏰] Verify Phase 9: Hooks capture events and context bundles work

---

## Worktree: phase-10-workflows

[✅, 39f1ef3b] Create src/adw/workflows/sdlc.py SDLC phases and imports
[✅, 3836463b] Create src/adw/workflows/sdlc.py run_sdlc_workflow function
[✅, 69cf33a6] Create src/adw/workflows/sdlc.py helper functions
[✅, 45377b99] Create src/adw/workflows/prototype.py with prototype configs
[✅, 8cdf9674] Create src/adw/agent/model_selector.py
[✅, 222e9258] Create .claude/commands/plan.md template
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
[✅, 803243c6] Create src/adw/triggers/github.py polling trigger
[✅, d7050b3a] Create src/adw/triggers/webhook.py FastAPI handler
[✅, f5b33663] Add CLI commands: adw github watch/process
[⏰] Verify Phase 11: Can trigger workflow from GitHub issue

---

## Worktree: phase-12-self-improvement

[✅, 291d0993] Create .claude/commands/experts/cc_expert.md {opus}
[✅, 892118f6] Create .claude/commands/experts/cc_expert_improve.md
[✅, 77d99349] Create .claude/commands/load_ai_docs.md
[✅, fc684509] Create .claude/commands/create_agent.md
[✅, 23466c97] Create ai_docs/README.md with documentation sources
[⏰] Verify Phase 12: Expert system can be queried and improved

---

## Worktree: final-validation

[✅, 90e11ede] Run full test suite
[✅, 793a7295] Test complete workflow: adw new "test feature" through PR
[✅, 50e5ff7f] Update README.md with new features
[✅, bac4d5de] Update CLAUDE.md with ADW orchestration docs
[🟡, a2ecdc7d] Tag release v0.2.0

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
