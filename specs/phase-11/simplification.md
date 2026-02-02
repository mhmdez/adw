# Spec: Simplification & Polish

## Job to Be Done
Remove unnecessary complexity and polish the user experience.

## Acceptance Criteria

### 1. Consolidate Workflows
- [ ] Merge workflow types into one adaptive workflow
- [ ] Single workflow adjusts based on task complexity
- [ ] Remove: `simple`, `prototype`, `standard` distinction
- [ ] Keep: one configurable SDLC workflow

### 2. Simplify Plugin System
- [ ] Inline qmd integration (remove plugin abstraction)
- [ ] Remove unused plugin infrastructure
- [ ] Keep extension points but simplify API
- [ ] Document how to extend

### 3. TUI Cleanup
- [ ] Remove unused Textual widgets
- [ ] Simplify dashboard layout
- [ ] Remove ASCII art logo (or make it optional)
- [ ] Focus on: task list, logs, status

### 4. Config Consolidation
- [ ] Single config file: `~/.adw/config.toml`
- [ ] Remove scattered settings
- [ ] Clear defaults for everything
- [ ] CLI: `adw config show`

### 5. Error Messages
- [ ] Human-friendly error messages
- [ ] Include suggested fixes
- [ ] Link to relevant docs
- [ ] No stack traces by default

### 6. Help Text
- [ ] Improve `--help` for all commands
- [ ] Include examples in help
- [ ] Add `adw examples` command
- [ ] Better command discovery

### 7. Documentation
- [ ] Getting started guide (< 5 minutes)
- [ ] Full reference docs
- [ ] Common recipes
- [ ] Troubleshooting guide
- [ ] Video walkthrough

## Technical Notes
- Simplification is about removing, not adding
- Each removal should be justified
- Keep backward compatibility where possible

## Testing
- [ ] Test CLI usability with new users
- [ ] Measure time to first successful task
- [ ] Documentation review
