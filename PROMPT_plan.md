# ADW Planning Mode

## Instructions

0a. Study `specs/phase-*/*.md` with up to 250 parallel Sonnet subagents to learn all phase specifications.
0b. Study @IMPLEMENTATION_PLAN.md (if present) to understand the plan so far.
0c. Study `src/adw/*` with up to 250 parallel Sonnet subagents to understand the existing codebase.
0d. Reference @AGENTS.md for build/test commands.

1. Study @IMPLEMENTATION_PLAN.md (if present; it may be incorrect) and use up to 500 Sonnet subagents to study existing source code in `src/adw/*` and compare it against `specs/phase-*/*.md`. Use an Opus subagent to analyze findings, prioritize tasks, and create/update @IMPLEMENTATION_PLAN.md as a bullet point list sorted by phase and priority.

2. Ultrathink. Consider:
   - Missing functionality vs specs
   - TODO comments, minimal implementations, placeholders
   - Skipped/flaky tests
   - Inconsistent patterns
   - Dependencies between phases

3. For each phase (0-11), list tasks in priority order:
   ```markdown
   ## Phase X: Name
   
   - [ ] Task 1 (spec: phase-X/foo.md)
   - [ ] Task 2 (spec: phase-X/bar.md)
   - [x] Task 3 (DONE - commit abc123)
   ```

4. Keep @IMPLEMENTATION_PLAN.md current using subagents.

## Important

- **PLAN ONLY. Do NOT implement anything.**
- Do NOT assume functionality is missing; confirm with code search first.
- Treat `src/adw/` as the project structure.
- If you create a new spec, document the plan for it.

## Ultimate Goal

We want to achieve: **A complete AI Developer Workflow CLI that replaces 90% of a dev team through autonomous agentic development.**

The roadmap has 11 phases covering:
- Phase 0: Validation
- Phase 1: Observability & Safety (hooks, screenshots, dashboard)
- Phase 2: Quality Gates (test validation, smart retry)
- Phase 3: Context Engineering (priming, bundles)
- Phase 4: Feedback Loops (PR review, HIL gates)
- Phase 5: Specialized Agents (experts, self-improving)
- Phase 6: Multi-Repo Orchestration
- Phase 7: Entry Points (GitHub, Slack, Linear, webhooks)
- Phase 8: Failure Recovery
- Phase 9: Reporting & Analytics
- Phase 10: Workflow Customization
- Phase 11: Simplification & Polish

Plan each phase systematically. Phase 0 first, then 1, etc.
