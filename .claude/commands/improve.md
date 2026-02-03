# /improve - Analyze and Record Learnings from Recent Tasks

Analyze the recent task execution and extract learnings to improve future performance.

## Purpose

After completing a task, use this command to:
1. Reflect on what went well
2. Identify patterns that worked
3. Document issues encountered and how they were resolved
4. Record mistakes to avoid in the future

## What I'll Analyze

I will examine:
- **Files modified** during this session
- **Test results** - did tests pass first try or require retries?
- **Retry patterns** - what caused retries and how were issues fixed?
- **Code patterns** - successful approaches worth remembering
- **Errors encountered** - and their solutions

## Learning Categories

### Patterns (What Worked)
Code structures, file organizations, and approaches that led to success:
- Tests passing first try
- Clean code review
- Efficient implementation

### Issues (Problems & Workarounds)
Problems discovered and how to solve them:
- Error messages and their fixes
- Configuration gotchas
- Integration issues

### Best Practices (Proven Approaches)
Recommended ways to handle common scenarios:
- Coding conventions
- Testing strategies
- Documentation patterns

### Mistakes to Avoid
Common errors that caused problems:
- Anti-patterns discovered
- Configuration mistakes
- Common oversights

## How to Use

After completing your current task, I'll:

1. **Review the session** - Examine files changed and outcomes
2. **Extract learnings** - Identify patterns, issues, and insights
3. **Record to knowledge base** - Store in `~/.adw/learning/`
4. **Update expertise** - Make learnings available for future tasks

## Reflection Prompts

To help me extract the most valuable learnings, consider:

1. **What went smoothly?** What approaches worked well that you'd use again?

2. **What was tricky?** Were there any unexpected challenges or gotchas?

3. **What would you do differently?** Any approaches that didn't work well?

4. **What patterns emerged?** Any reusable patterns worth documenting?

5. **What errors occurred?** And how were they resolved?

## Output

I'll generate a summary of learnings extracted and stored:

```markdown
## Learnings Recorded

### Patterns (3 new)
- [frontend] Use compound components for complex forms
- [backend] FastAPI dependency injection for database sessions
- [general] Run linter before commit

### Issues (1 new)
- **TypeScript strict mode errors**: Enable `skipLibCheck` for third-party types

### Mistakes to Avoid (1 new)
- ❌ Don't use `any` type for API responses

Total: 5 learnings added to project knowledge base.
```

## Storage Location

Learnings are stored in:
- **Project-specific**: `~/.adw/learning/<project>/patterns.json`
- **Global**: `~/.adw/learning/global/patterns.json`

Use `adw learn --show` to view accumulated learnings.

---

## Start Analysis

Let me analyze your recent work and extract learnings. I'll need to:

1. Check which files were modified
2. Review any test outputs
3. Look for patterns in the changes
4. Ask clarifying questions if needed

What aspects of this task would you like me to focus on for learnings?
