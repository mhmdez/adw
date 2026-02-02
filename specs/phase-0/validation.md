# Phase 0: Foundation Validation

## Job to Be Done
Prove the existing SDLC workflow (plan → implement → test → review → document → commit) actually works end-to-end before building more features.

## Acceptance Criteria

1. **SDLC Test Task**: Create a simple test task that exercises all workflow phases
   - [ ] Task: "Add a `--version` flag to the CLI that shows the current version"
   - [ ] Plan phase generates a valid spec
   - [ ] Implement phase creates the code
   - [ ] Test phase runs pytest
   - [ ] Review phase provides feedback
   - [ ] Document phase updates README
   - [ ] Commit phase creates a proper git commit

2. **Validation Report**: Document what works and what breaks
   - [ ] Create `docs/VALIDATION_REPORT.md`
   - [ ] List each phase with pass/fail status
   - [ ] Document error messages for failures
   - [ ] Note any manual interventions required

3. **Fix Critical Blockers**: Patch anything that prevents completion
   - [ ] Each blocker gets a GitHub issue
   - [ ] Minimal fix to unblock (don't over-engineer)

## Success Metrics
- Task completes end-to-end without manual intervention
- All tests pass after implementation
- Git commit is created with proper message
- Time to complete < 10 minutes

## Non-Goals
- Don't add new features
- Don't refactor existing code
- Don't optimize performance
