# /load_ai_docs - Load AI Documentation into Expert System

Load Claude Code documentation into the expert system knowledge base.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, WebFetch, WebSearch, Edit]
description: Load and index AI documentation for expert system
```

## Purpose

Populate the expert system with Claude Code documentation, official guides, and community best practices to enhance the knowledge base.

## When to Use

- Setting up expert system for the first time
- Updating expert knowledge with latest documentation
- Adding new documentation sources
- Refreshing knowledge after Claude Code updates

## Workflow

1. **Discover documentation sources**
   - Check for local ai_docs/ directory
   - Search for Claude Code documentation files
   - Look for README, guides, and spec files
   - Identify external documentation URLs

2. **Load documentation**
   - Read local markdown files
   - Fetch remote documentation via WebFetch
   - Extract key patterns and practices
   - Identify code examples and usage patterns

3. **Process and categorize**
   - Extract core concepts and patterns
   - Identify best practices and conventions
   - Note common issues and solutions
   - Catalog useful examples

4. **Update expert system**
   - Use /experts:cc_expert:improve to add learnings
   - Organize by category (Patterns, Practices, Issues, Learnings)
   - Ensure information is actionable and concise
   - Remove redundant or outdated information

## Input Format

Provide one or more of:

- **Path**: Local directory or file path to documentation
- **URL**: Remote documentation URL
- **Topic**: Specific topic to focus on (hooks, commands, agents, etc.)

## Example Usage

```
/load_ai_docs docs/

Loads all documentation from the docs/ directory
```

```
/load_ai_docs https://github.com/anthropics/anthropic-sdk-python

Fetches and processes Python SDK documentation
```

```
/load_ai_docs ai_docs/hooks/ --topic hooks

Loads only hook-related documentation
```

## Output

- Summary of documentation loaded
- Key patterns and practices discovered
- Count of updates made to expert system
- Suggestions for further documentation to add

## Notes

- Prioritize official Claude Code documentation
- Focus on actionable patterns over theory
- Keep expert knowledge concise and searchable
- Update incrementally to avoid overwhelming the knowledge base
