# Workflow Guide

Understanding and customizing ADW workflows.

## Built-in Workflows

ADW includes four workflow types:

| Workflow | Phases | Best For |
|----------|--------|----------|
| `simple` | Build → Update | Quick fixes, typos, small changes |
| `standard` | Plan → Implement → Update | Most features |
| `sdlc` | Plan → Implement → Test → Review → Document → Update | Complex features |
| `prototype` | Scaffold → Verify | Project scaffolding |

## Choosing a Workflow

### Simple Workflow

```bash
adw new "Fix typo in README" --workflow simple
```

Use for:
- Bug fixes
- Typo corrections
- Config changes
- Small refactors

Skips planning - goes straight to implementation.

### Standard Workflow

```bash
adw new "Add user search feature" --workflow standard
```

Use for:
- New features
- Enhancements
- Moderate refactors

Includes planning phase to ensure good design.

### SDLC Workflow

```bash
adw new "Implement authentication system" --workflow sdlc
```

Use for:
- Complex features
- Security-sensitive code
- Features requiring documentation
- Code needing thorough review

Full software development lifecycle.

### Prototype Workflow

```bash
adw workflow use prototype
```

Use for:
- Project scaffolding
- Boilerplate generation
- Template-based creation

## Workflow Details

### Simple Workflow Phases

1. **Build** - Execute task directly
2. **Update** - Mark complete in tasks.md

### Standard Workflow Phases

1. **Plan** - Create implementation plan
2. **Implement** - Execute the plan
3. **Update** - Mark complete, commit changes

### SDLC Workflow Phases

1. **Plan** - Detailed technical design
2. **Implement** - Write the code
3. **Test** - Create and run tests
4. **Review** - Security and code quality review
5. **Document** - Generate documentation
6. **Update** - Commit and finalize

## Viewing Workflows

### List Available

```bash
adw workflow list
```

### Show Details

```bash
adw workflow show sdlc
adw workflow show sdlc --yaml  # Raw YAML
```

### Set Default

```bash
adw workflow use sdlc  # Set as default
```

## Custom Workflows

### Create from Template

```bash
adw workflow create my-workflow --from sdlc
```

This creates `~/.adw/workflows/my-workflow.yaml`.

### Workflow YAML Format

```yaml
name: my-workflow
description: Custom workflow for my team
version: "1.0"

phases:
  - name: plan
    prompt: plan.md
    model: sonnet

  - name: implement
    prompt: implement.md
    model: sonnet

  - name: test
    prompt: test.md
    model: haiku
    condition: has_changes

  - name: custom-review
    prompt: custom-review.md
    model: opus
```

### Phase Options

```yaml
phases:
  - name: phase-name
    prompt: path/to/prompt.md    # Prompt template
    model: sonnet                 # Model to use
    condition: always             # When to run
    loop: none                    # Loop behavior
    max_retries: 3                # Retry count
```

### Conditions

- `always` - Always run
- `has_changes` - Only if git has changes
- `tests_passed` - Only if tests passed
- `tests_failed` - Only if tests failed
- `file_exists` - Only if file exists
- `env_set` - Only if env var is set

### Loop Behavior

- `none` - Run once
- `until_success` - Retry until success
- `until_tests_pass` - Retry until tests pass
- `fixed_count` - Run N times

### Parallel Phases

```yaml
phases:
  - name: lint
    prompt: lint.md
    parallel_with: [test]

  - name: test
    prompt: test.md
```

## Prompt Templates

### Variable Substitution

```markdown
# Task: {{task_description}}

Implement the following feature:
{{task_description}}

Project: {{project_name}}
Model: {{model}}
```

### Include Directives

```markdown
# Common Safety Rules
{{include common/safety.md}}

# Task-Specific Instructions
...
```

### Conditional Blocks

```markdown
{{#if has_tests}}
Run the existing tests first.
{{/if}}

{{#if is_typescript}}
Use TypeScript best practices.
{{/if}}
```

### Create Prompt Template

```bash
adw prompt create my-template --template implement
```

### List Templates

```bash
adw prompt list
```

## Validate Workflows

```bash
adw workflow validate ~/.adw/workflows/my-workflow.yaml
```

## Workflow Examples

### Minimal Bug-Fix Workflow

```yaml
name: bug-fix
description: Fast bug fixing workflow

phases:
  - name: fix
    prompt: fix-bug.md
    model: sonnet

  - name: test
    prompt: run-tests.md
    model: haiku
    condition: has_changes
```

### Review-Heavy Workflow

```yaml
name: secure-review
description: Security-focused workflow

phases:
  - name: plan
    prompt: plan.md
    model: opus

  - name: implement
    prompt: implement.md
    model: sonnet

  - name: security-review
    prompt: security-review.md
    model: opus

  - name: code-review
    prompt: code-review.md
    model: opus

  - name: test
    prompt: test.md
    model: sonnet
```

### Test-Driven Workflow

```yaml
name: tdd
description: Test-first development

phases:
  - name: write-tests
    prompt: write-tests.md
    model: sonnet

  - name: implement
    prompt: implement.md
    model: sonnet
    loop: until_tests_pass
    max_retries: 5

  - name: refactor
    prompt: refactor.md
    model: sonnet
    condition: tests_passed
```

## Best Practices

1. **Start simple** - Use built-in workflows first
2. **Customize incrementally** - Copy and modify existing workflows
3. **Match complexity** - Use heavier workflows for complex tasks
4. **Test workflows** - Validate before using
5. **Use appropriate models** - Opus for complex reasoning, Haiku for simple tasks
6. **Document custom workflows** - Future you will thank you
