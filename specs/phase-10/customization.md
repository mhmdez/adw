# Spec: Workflow Customization

## Job to Be Done
Allow users to define their own workflows without modifying ADW source code.

## Acceptance Criteria

### 1. Workflow DSL
- [ ] Create `src/adw/workflows/dsl.py`
- [ ] Support YAML workflow definitions:
  ```yaml
  name: my-workflow
  phases:
    - name: plan
      prompt: prompts/plan.md
      model: opus
    - name: implement
      prompt: prompts/implement.md
      model: sonnet
      tests: npm test
    - name: review
      prompt: prompts/review.md
      optional: true
  ```
- [ ] Validate workflow at load time
- [ ] Store in `~/.adw/workflows/`

### 2. Custom Phases
- [ ] Users can add/remove/reorder phases
- [ ] Support conditional phases: `if: tests_failed`
- [ ] Support parallel phases
- [ ] Support loop phases: `while: not_done`

### 3. Custom Prompts
- [ ] Each phase references a prompt file
- [ ] Prompts support variables: `{{task_description}}`
- [ ] Include other prompts: `{{include common/safety.md}}`
- [ ] CLI: `adw prompt create <name>`

### 4. Workflow Library
- [ ] Ship common workflows:
  - `sdlc` — Full software lifecycle
  - `simple` — Just implement
  - `prototype` — Quick and dirty
  - `bug-fix` — Focused bug fixing
- [ ] CLI: `adw workflow list`
- [ ] CLI: `adw workflow use <name>`

### 5. Task Configuration
- [ ] Per-task overrides:
  ```yaml
  - task: Add login
    workflow: sdlc
    model: opus
    skip_phases: [review]
  ```
- [ ] Inline tags: `{opus, skip_review}`
- [ ] Priority levels: `p0`, `p1`, `p2`

## Technical Notes
- Workflows are validated at parse time
- Hot-reload workflows without restart
- Version workflows with project

## Testing
- [ ] Test DSL parsing
- [ ] Test custom workflow execution
- [ ] Test variable substitution
