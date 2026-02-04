# Features to Add to ADW Roadmap

*Consolidated from TAC-8 analysis.*

**Last verified:** 2026-02-04

> NOTE: This file was originally a “future backlog”. As of **2026-02-04**, many items are already shipped.
> The table below is the **source of truth** (legacy duplicated sections removed to avoid drift).

## Status Legend

- ✅ Implemented
- ⚠️ Partial / differs from original intent
- ❌ Not implemented

## Roadmap Table (Source of Truth)

| # | Priority | Feature | Status | Evidence / Notes |
|---:|:--:|---|:--:|---|
| 1 | P0 | Claude Code Hooks (safety + audit trail) | ✅ | `.claude/hooks/pre_tool_use.py`, `.claude/hooks/post_tool_use.py`, `.claude/settings.json` |
| 2 | P0 | Screenshot Capture (auto + CLI) | ⚠️ | Auto on dev‑server start: `.claude/hooks/post_tool_use.py`<br>CLI + utils: `src/adw/cli.py`, `src/adw/utils/screenshot.py`<br>Missing: auto “after tests/UI tests” capture |
| 3 | P1 | Context Priming (`/prime_*`) | ✅ | Claude cmds: `.claude/commands/prime*.md`<br>CLI priming: `src/adw/cli.py` |
| 4 | P1 | Context Bundles (save/restore) | ✅ | ADW bundles: `src/adw/context/bundles.py`, `src/adw/cli.py` (`adw bundle …`)<br>Also session file-op tracking: `.claude/hooks/context_bundle_builder.py` |
| 5 | P1 | Self‑Improving Expertise (learning loop) | ⚠️ | Learning store: `src/adw/learning/patterns.py` + `adw learn …` (`src/adw/cli.py`)<br>Expertise injection: `src/adw/learning/expertise.py`<br>Missing: automatic “run /improve after each task” wiring |
| 6 | P1 | Specialized Planners (`/plan_fastapi`, `/plan_react`, etc.) | ✅ | `.claude/commands/plan_fastapi.md`, `.claude/commands/plan_react.md`, `.claude/commands/plan_nextjs.md`, `.claude/commands/plan_supabase.md` |
| 7 | P1 | Output Styles (concise vs verbose) | ⚠️ | Present: `.claude/output-styles/concise-done.md`, `.claude/output-styles/concise-ultra.md`<br>Missing: `verbose-structured.md` (and/or documented switching) |
| 8 | P1 | Commit Hash in Task Status | ✅ | Commit capture: `src/adw/workflows/adaptive.py`<br>Marker format: `src/adw/agent/task_updater.py` |
| 9 | P2 | Agent Experts (frontend/backend/ai) | ✅ | `src/adw/experts/*` (selection: `src/adw/experts/selector.py`) |
| 10 | P2 | Notion Integration | ✅ | `src/adw/integrations/notion.py` + CLI: `src/adw/cli.py` (`adw notion …`) |
| 11 | P2 | Real‑Time Observability Dashboard (web) | ✅ | Web dashboard: `src/adw/dashboard/server.py` (`adw dashboard --web`)<br>DB/events: `src/adw/observability/db.py` |
| 12 | P2 | Workflow Tags (model/workflow/priority) | ✅ | Parse: `src/adw/agent/task_parser.py`<br>Semantics: `src/adw/agent/models.py` |
| 13 | P2 | Issue Classification (bug/feature/chore) | ✅ | Intake parsing: `src/adw/integrations/issue_parser.py` (used by `src/adw/triggers/github.py`) |
| 14 | P2 | Human‑in‑the‑Loop Gates (approval) | ⚠️ | Approval system + CLI: `src/adw/github/approval_gate.py`, `src/adw/cli.py` (`approve-task`, `reject-task`, `pending-approvals`)<br>Missing: enforced by default workflow/daemon |
| 15 | P2 | Continue Prompts (iterative refinement) | ⚠️ | Supported for approvals: `src/adw/github/approval_gate.py`, `src/adw/cli.py` (`continue-task`)<br>Missing: `continue - …` parsing in `tasks.md` |
| 16 | P3 | Webhook Trigger (HTTP API) | ✅ | `src/adw/triggers/webhook.py` + CLI: `src/adw/cli.py` (`adw webhook start/test`) |
| 17 | P3 | AI Summarization (PRs/reports) | ⚠️ | Reports exist: `src/adw/reports/*` + `adw report …` (`src/adw/cli.py`)<br>Missing: LLM-generated PR body summaries from agent logs by default |

## Maintenance

- Update this table when behavior changes (and bump **Last verified**).
- Keep “Evidence / Notes” concrete (file path or CLI command) to reduce ambiguity.
