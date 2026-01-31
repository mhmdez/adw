# /experts:cc_expert - Claude Code Expert System

Self-improving expert for Claude Code patterns and best practices.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, WebFetch, WebSearch, Edit]
description: Expert system for Claude Code development
```

## Purpose

Provide expert-level guidance on Claude Code development, continuously improving knowledge base.

## Expertise

<!-- This section is updated by /experts:cc_expert:improve -->

### Core Patterns
- Hook system: PreToolUse, PostToolUse, UserPromptSubmit, Stop
- Slash commands in .claude/commands/
- Sub-agents in .claude/agents/
- Output styles for token efficiency

### Best Practices
- Use --stream-json for programmatic output
- Filter subprocess environment for security
- Implement retry logic for transient failures
- Use ADW IDs for execution tracking

### Known Issues
- {Issues discovered during usage}

### Learnings
- {Patterns discovered during usage}

## Workflow

1. **Receive query**
   - Understand what user needs
   - Check if covered by Expertise section

2. **Research if needed**
   - Search ai_docs/ for relevant docs
   - Use WebSearch for latest info
   - Read relevant source files

3. **Provide answer**
   - Give specific, actionable guidance
   - Include code examples
   - Reference documentation

4. **Update expertise** (if new learning)
   - Note pattern for future reference
   - Flag for /experts:cc_expert:improve
