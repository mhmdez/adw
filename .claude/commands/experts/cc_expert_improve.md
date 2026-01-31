# /experts:cc_expert:improve - Improve CC Expert Knowledge

Update the Claude Code expert system with new learnings and patterns.

## Metadata

```yaml
allowed-tools: [Read, Edit, Glob, Grep]
description: Self-improvement command for CC expert system
```

## Purpose

Allow the expert system to update its own knowledge base with discovered patterns, best practices, and solutions.

## When to Use

- After discovering new Claude Code patterns
- When solving novel problems
- After reading documentation with new insights
- When identifying reusable solutions

## Workflow

1. **Gather learnings**
   - Review recent interactions
   - Identify reusable patterns
   - Note solutions to common problems

2. **Categorize knowledge**
   - Core Patterns: Architectural patterns (hooks, commands, agents)
   - Best Practices: Proven approaches and conventions
   - Known Issues: Problems and their workarounds
   - Learnings: Insights from real usage

3. **Update expertise section**
   - Read current cc_expert.md
   - Edit Expertise section with new content
   - Keep entries concise and actionable
   - Remove placeholder comments

4. **Verify update**
   - Ensure format is consistent
   - Check that guidance is clear
   - Validate examples are correct

## Input Format

Provide one or more of:

- **Pattern**: Name and description of pattern
- **Practice**: Best practice with rationale
- **Issue**: Problem description and workaround
- **Learning**: Insight or discovery

## Example Usage

```
/experts:cc_expert:improve

Pattern: Environment filtering
- Use os.environ.copy() and filter sensitive vars
- Prevents subprocess access to credentials

Issue: Hook error handling
- Hooks that exit non-zero block execution
- Use try/except in Python hooks for graceful handling
```

## Output

- Updated cc_expert.md with new knowledge
- Summary of changes made
