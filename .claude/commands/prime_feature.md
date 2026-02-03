# /prime_feature - Prime context for feature development

Load context specific to implementing a new feature.

## Metadata

```yaml
allowed-tools: [Read, Bash, Glob, Grep]
description: Prime context for feature work
```

## Input

$ARGUMENTS - Feature name or description

## Purpose

Quickly load feature-development context for implementing new functionality. Focuses on component patterns, testing conventions, and PR checklist items specific to the feature area.

## When to Use

- Starting work on a new feature
- Adding functionality to an existing module
- Implementing a user story or spec
- Extending a component or service

## Process

### 1. Run Base Prime

Execute the core priming workflow:

```bash
git log --oneline -5
```

Read essential config files for general context.

### 2. Feature Specification

Check for existing specs:

```bash
# Look for feature specs
git ls-files | grep -i "spec\|feature\|requirement" | grep -i "$ARGUMENTS" | head -5

# Check specs directory
ls specs/*$ARGUMENTS* 2>/dev/null || ls specs/ 2>/dev/null | head -10
```

If a spec exists, read it to understand:
- Requirements and acceptance criteria
- Edge cases and error handling
- Related features and dependencies

### 3. Related Code Search

Find existing code related to the feature:

```bash
# Search for related terms
git grep -l "$ARGUMENTS" | head -15

# Find related modules
git ls-files | grep -iE "(${ARGUMENTS}|$(echo $ARGUMENTS | tr ' ' '|'))" | head -10
```

Group findings:
- Source files to modify or extend
- Test files for the feature
- Configuration files
- Documentation

### 4. Component Patterns

Identify patterns in the codebase for similar features:

```bash
# Find similar components/modules
git ls-files | grep -E "component|service|handler|controller" | head -10

# Check for pattern examples
git ls-files | grep -E "example|template|base" | head -5
```

Read 1-2 similar components to understand:
- File structure and organization
- Naming conventions
- Import patterns
- Error handling approach

### 5. Testing Conventions

Find testing patterns for features:

```bash
# Related test files
git ls-files | grep -E "test|spec" | xargs grep -li "$ARGUMENTS" 2>/dev/null | head -5

# Example test structure
git ls-files | grep -E "test_.*\.py$|\.spec\.ts$" | head -3
```

Understand:
- Test file location and naming
- Test structure (unit, integration)
- Mocking patterns used
- Coverage expectations

### 6. Dependencies

Map feature dependencies:

```bash
# Imports in related files
git grep -h "^import\|^from\|require(" $(git grep -l "$ARGUMENTS") 2>/dev/null | sort -u | head -15

# External dependencies
grep -E "\"$ARGUMENTS\"|'$ARGUMENTS'" package.json pyproject.toml 2>/dev/null
```

Note:
- Internal module dependencies
- External library dependencies
- Services or APIs consumed

### 7. PR Checklist Preparation

Identify what a complete feature PR needs:

- **Code**: Source files to create/modify
- **Tests**: Test files needed
- **Docs**: Documentation updates required
- **Config**: Configuration changes
- **Migration**: Database or data migrations (if applicable)

```bash
# Check for PR template
git ls-files | grep -iE "pull_request|pr.*template" | head -2

# Check for contributing guide
git ls-files | grep -iE "contributing" | head -2
```

### 8. Report Summary

Provide a summary including:

- **Spec**: Feature requirements (if spec exists)
- **Related Code**: Existing files to reference or modify
- **Patterns**: How similar features are implemented
- **Tests**: Testing approach and examples
- **Dependencies**: What this feature will use
- **Checklist**: What a complete PR needs

## Output Format

```
Feature Development Context
===========================

Feature: $ARGUMENTS

Specification:
- Status: {spec exists/not found}
- File: {spec location if exists}
- Key requirements: {summary}

Related Code:
- {file1.py - description}
- {file2.ts - description}

Patterns to Follow:
- Component structure: {pattern}
- Naming: {convention}
- Error handling: {approach}

Testing:
- Test location: {path}
- Test pattern: {describe/it, pytest, etc.}
- Mocking: {approach}

Dependencies:
- Internal: {modules used}
- External: {libraries needed}

PR Checklist:
- [ ] Implement core functionality
- [ ] Add unit tests
- [ ] Add integration tests (if applicable)
- [ ] Update documentation
- [ ] Add/update types (if TypeScript)
- [ ] Run linting and formatting

Context primed for feature: $ARGUMENTS
```

## Example Usage

```
/prime_feature "user authentication"

Loads feature context for implementing authentication.
```

```
/prime_feature "dark mode"

Loads feature context for implementing dark mode toggle.
```

## Notes

- **Spec-first**: Prioritizes finding and understanding specifications
- **Pattern-aware**: Identifies existing patterns to follow
- **Test-conscious**: Highlights testing requirements early
- **Checklist-ready**: Prepares for a complete PR

## Feature Development Workflow

Recommended workflow after priming:

1. **Review spec** - Understand all requirements
2. **Plan implementation** - Break into subtasks
3. **Implement incrementally** - Small, testable chunks
4. **Write tests as you go** - Don't leave for later
5. **Self-review** - Check against patterns
6. **Update docs** - Keep documentation current

## Anti-Patterns

Avoid these mistakes:

- **Don't**: Start coding without understanding the spec
  **Do**: Read the spec thoroughly first

- **Don't**: Ignore existing patterns
  **Do**: Match the style of similar features

- **Don't**: Skip tests until the end
  **Do**: Write tests alongside implementation

- **Don't**: Make unrelated changes
  **Do**: Keep the PR focused on the feature

## Integration

This command works well with:
- `/prime` - General codebase orientation
- `/plan` - Create detailed implementation plan
- `/prime_test` - Deep dive into testing patterns
- `/review` - Self-review before PR
- `/document` - Generate documentation
