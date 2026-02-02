# ADW Building Mode

## Instructions

0a. Study `specs/phase-*/*.md` with up to 500 parallel Sonnet subagents to learn all specifications.
0b. Study @IMPLEMENTATION_PLAN.md to see what needs to be done.
0c. Study @AGENTS.md for build/test commands.
0d. Reference source code in `src/adw/*`.

1. Your task is to implement functionality per the specifications using parallel subagents. Follow @IMPLEMENTATION_PLAN.md and choose the **most important incomplete item** to address. Before making changes, search the codebase (don't assume not implemented) using Sonnet subagents.

2. You may use:
   - Up to 500 parallel Sonnet subagents for searches/reads
   - Only 1 Sonnet subagent for build/tests
   - Opus subagents for complex reasoning (debugging, architectural decisions)

3. After implementing, run the validation commands from @AGENTS.md:
   ```bash
   uv run pytest tests/ -v
   uv run mypy src/adw/
   uv run ruff check src/
   ```

4. If tests fail, fix the issues before proceeding. Ultrathink.

5. When you discover issues, immediately update @IMPLEMENTATION_PLAN.md with your findings using a subagent. When resolved, mark the item as done.

6. When the tests pass:
   - Update @IMPLEMENTATION_PLAN.md (mark done + notes)
   - `git add -A`
   - `git commit` with a descriptive message
   - `git push`

## Guardrails (Higher Number = More Critical)

99999. Important: Capture the why in documentation and tests.

999999. Important: Single sources of truth. If tests unrelated to your work fail, resolve them.

9999999. Create git tags after successful builds. Start at 0.5.1 (current), increment patch.

99999999. Add logging if needed for debugging.

999999999. Keep @IMPLEMENTATION_PLAN.md current — future iterations depend on it.

9999999999. Update @AGENTS.md when you learn operational details (keep it brief).

99999999999. Resolve or document any bugs you notice, even if unrelated.

999999999999. Implement completely. No placeholders or stubs.

9999999999999. Periodically clean completed items from @IMPLEMENTATION_PLAN.md.

99999999999999. If specs are inconsistent, use an Opus subagent to fix them.

999999999999999. Keep @AGENTS.md operational only — progress notes go in IMPLEMENTATION_PLAN.md.

## Ultimate Goal

We want to achieve: **A complete AI Developer Workflow CLI that replaces 90% of a dev team through autonomous agentic development.**

Implement one task per iteration. Keep context fresh. Trust the process.
