# Spec: Multi-Repo Orchestration

## Job to Be Done
Enable ADW to work across multiple repositories like a real development team.

## Acceptance Criteria

### 1. Workspace Configuration
- [ ] Create `~/.adw/workspace.toml`:
  ```toml
  [workspace]
  name = "studibudi"
  
  [[repos]]
  name = "frontend"
  path = "~/Sites/studibudi-fe"
  type = "nextjs"
  
  [[repos]]
  name = "backend"
  path = "~/Sites/studibudi"
  type = "fastapi"
  
  [relationships]
  frontend.depends_on = ["backend"]
  ```
- [ ] CLI: `adw workspace init`
- [ ] CLI: `adw workspace add <path>`

### 2. Cross-Repo Task Queue
- [ ] Single task queue spans all repos
- [ ] Task specifies target repo: `{repo: "frontend"}`
- [ ] Auto-detect repo from file paths
- [ ] Show repo in task list

### 3. Task Dependencies
- [ ] Define dependencies: `{depends_on: ["task-123"]}`
- [ ] Cross-repo dependencies work
- [ ] Blocked tasks show why they're blocked
- [ ] Auto-unblock when dependency completes

### 4. Unified Context
- [ ] Agent can read files from any repo in workspace
- [ ] Understands API contracts between repos
- [ ] Shares types/interfaces when applicable
- [ ] CLAUDE.md per repo + workspace-level context

### 5. Coordinated PRs
- [ ] Create linked PRs across repos
- [ ] PR description references related PRs
- [ ] Option to merge all or none (atomic)
- [ ] CLI: `adw pr link <pr1> <pr2>`

## Technical Notes
- Repos can be on different branches
- Handle conflicts when repos are out of sync
- Support monorepos as special case

## Testing
- [ ] Test workspace config parsing
- [ ] Test cross-repo task execution
- [ ] Test PR linking
