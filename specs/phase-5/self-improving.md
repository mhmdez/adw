# Spec: Self-Improving Agents

## Job to Be Done
Enable agents to learn from successes and failures, improving their prompts and knowledge over time.

## Acceptance Criteria

### 1. Expertise Section
- [ ] Add `## Expertise` section to prompts
- [ ] Contains:
  - Discovered patterns
  - Known issues and workarounds
  - Best practices
  - Common mistakes to avoid
- [ ] Auto-updated after each task

### 2. Improve Command
- [ ] Create `/improve` Claude command
- [ ] Analyzes recent task:
  - What went well?
  - What took extra retries?
  - What patterns were discovered?
- [ ] Updates expertise section in relevant prompts

### 3. Pattern Learning
- [ ] Track successful patterns:
  - Code patterns that pass tests first try
  - Approaches that get approved without changes
  - File organizations that work well
- [ ] Store in `~/.adw/patterns/<project>/patterns.json`

### 4. Issue Learning
- [ ] Track failures and their solutions:
  - Error → fix mapping
  - Common mistakes → prevention
  - Gotchas → warnings
- [ ] Add to expertise section as "Known Issues"

### 5. Best Practice Database
- [ ] Aggregate learnings across projects
- [ ] CLI: `adw learn --show` to see learnings
- [ ] CLI: `adw learn --export` to share
- [ ] Optional: contribute to community database

## Technical Notes
- Learnings are per-project by default
- Use embeddings to find similar past tasks
- Prune old/outdated learnings periodically

## Testing
- [ ] Test pattern extraction
- [ ] Test expertise section updates
- [ ] Verify improvement over time (before/after metrics)
