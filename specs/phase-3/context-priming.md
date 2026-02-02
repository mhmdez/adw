# Spec: Context Priming Commands

## Job to Be Done
Provide dynamic context loading commands that prime agents with relevant codebase knowledge before working.

## Acceptance Criteria

### 1. Base Priming Command
- [ ] Create `.claude/commands/prime.md`
- [ ] Loads:
  - Project structure overview
  - Key architectural decisions
  - Common patterns in use
  - Important file locations
- [ ] Output: "Priming complete. Ready to work."

### 2. Specialized Priming Commands
- [ ] `/prime_bug` — Bug fixing context:
  - Error handling patterns
  - Logging conventions
  - Debug techniques
  - Common failure modes
- [ ] `/prime_feature` — Feature development context:
  - Component patterns
  - Testing conventions
  - PR checklist
- [ ] `/prime_test` — Testing context:
  - Test file locations
  - Mocking patterns
  - Coverage requirements
- [ ] `/prime_docs` — Documentation context:
  - Doc file locations
  - Style guide
  - Example docs

### 3. Project-Specific Priming
- [ ] Create `adw prime` CLI command
- [ ] Generates priming commands based on project detection
- [ ] Supports: Python, Node.js, Go, Rust
- [ ] Creates `.claude/commands/prime_*.md` files

### 4. Custom Priming
- [ ] Users can create custom prime commands
- [ ] Template: `specs/priming/my-prime.md`
- [ ] Auto-discovered from `specs/priming/` directory

### 5. Priming Refresh
- [ ] `adw prime --refresh` regenerates all priming commands
- [ ] Run after major codebase changes
- [ ] Uses Claude to analyze and summarize codebase

## Technical Notes
- Priming commands should be <2000 tokens each
- Focus on patterns, not exhaustive documentation
- Update priming when CLAUDE.md changes

## Testing
- [ ] Test priming command generation
- [ ] Verify token counts are reasonable
- [ ] Test project detection
