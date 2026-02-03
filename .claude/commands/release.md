# /release - Prepare release artifacts

Prepare the implementation for release: version updates, changelog, and commit.

## Metadata

```yaml
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, TodoWrite]
description: Prepare release artifacts
model: sonnet
```

## Purpose

Finalize the implementation after documentation by preparing release artifacts. This phase focuses on version updates, changelog entries, git commits, and tagging. This is the final phase of the SDLC workflow.

## When to Use

- After completing documentation with `/document`
- Following SDLC workflow as the final phase
- When a feature is ready for release/merge
- For preparing versioned releases

## Input

$ARGUMENTS - Spec file path, task description, or empty for most recent documented implementation

- **Spec file**: `specs/feature-name.md`
- **Task description**: "Release user authentication feature"
- **Empty**: Prepares release for the most recently documented feature

## Process

### 1. Load Context

- Read the spec file from `specs/` (if available)
- Identify all files created or modified in implementation
- Review documentation updates
- Check current version in pyproject.toml or package.json
- Note any existing changelog entries

### 2. Create Todo List

Use TodoWrite to track release tasks:
- Validate all tests pass
- Update changelog (if exists)
- Create git commit with descriptive message
- Verify files to be committed
- Mark initial task as in_progress

### 3. Validate Pre-Release State

Ensure the implementation is ready for release:

```bash
# Python projects
uv run pytest tests/ -v
uv run ruff check src/

# Node.js projects
npm test
npm run lint
```

**Check**:
- All tests pass
- No lint errors
- Documentation updated
- No uncommitted changes to unrelated files

### 4. Update Changelog (If Exists)

If CHANGELOG.md exists, add entry:

```markdown
## [Unreleased]

### Added
- {Feature description} ({reference})

### Changed
- {Change description}

### Fixed
- {Fix description}
```

Follow [Keep a Changelog](https://keepachangelog.com/) format.

### 5. Stage and Review Files

Review the files to be committed:

```bash
git status
git diff --cached
```

**Verify**:
- Only relevant files are staged
- No sensitive files (secrets, credentials)
- No build artifacts or generated files
- All expected changes are present

### 6. Create Commit

Create a descriptive commit:

```bash
git add -A
git commit -m "feat: {Feature description}

- {Key change 1}
- {Key change 2}

Refs: {issue or spec reference}"
```

**Commit message guidelines**:
- Use conventional commits format (feat, fix, chore, docs, etc.)
- First line: type and brief description (max 72 chars)
- Body: key changes and context
- Footer: references to issues or specs

### 7. Output Summary

Report:
- Files committed
- Tests validated
- Changelog updated (if applicable)
- Commit hash
- Next steps (push, PR, or tag)

## Example Usage

```
/release specs/user-authentication.md

Prepares release for the authentication feature.
```

```
/release Add user profile endpoint

Searches for matching spec and prepares release.
```

```
/release

Prepares release for the most recently documented feature.
```

## Response Format

```
Release preparation complete: {feature name}

Pre-Release Validation:
- Tests: PASS ({N} tests)
- Lint: PASS
- Documentation: Updated

Files Committed:
- {file1}
- {file2}
- ... ({N} total files)

Commit: {hash} - {message}

Changelog: {Updated / Not applicable}

Next Steps:
- Push to remote: git push origin {branch}
- Create PR: gh pr create
- Or tag release: git tag v{version}
```

## Notes

- **Model**: Use Sonnet (no complex reasoning needed)
- **Validation**: Run tests before committing
- **Clean Commits**: Only commit relevant files
- **Messages**: Write clear, descriptive commit messages
- **Convention**: Follow project's existing commit style
- **Changelog**: Update if the project maintains one
- **No Secrets**: Never commit sensitive files

## Anti-Patterns

Avoid these common mistakes:

- **Don't**: Commit without running tests
  **Do**: Validate tests pass before committing

- **Don't**: Include unrelated changes in commit
  **Do**: Stage only relevant files

- **Don't**: Write vague commit messages
  **Do**: Describe what and why

- **Don't**: Commit build artifacts
  **Do**: Check .gitignore covers generated files

- **Don't**: Skip changelog updates
  **Do**: Document changes in changelog if one exists

- **Don't**: Force push without reason
  **Do**: Use standard push unless rebasing

## Release Checklist

### Pre-Commit
- [ ] All tests pass
- [ ] Lint checks pass
- [ ] Documentation updated
- [ ] No unrelated changes staged

### Commit
- [ ] Files reviewed
- [ ] Commit message is descriptive
- [ ] Conventional commit format used
- [ ] No sensitive files included

### Post-Commit
- [ ] Changelog updated (if applicable)
- [ ] Ready for push/PR/tag

## Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no code change)
- `refactor`: Code change (no feature or fix)
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples**:

```
feat(auth): add JWT token authentication

- Implement token generation and validation
- Add refresh token support
- Include rate limiting

Closes #123
```

```
fix(api): resolve race condition in user lookup

The user service was returning stale data when
multiple requests arrived simultaneously.

Fixes #456
```

## Integration

This command is phase 6 of workflows:
- **SDLC workflow**: /plan → /implement → /test → /review → /document → **/release**

The documented implementation from `/document` is input for this command.
After release preparation, the feature is ready for merge/deploy.

## Success Criteria

Release phase is complete when:
- [ ] All tests pass
- [ ] Lint checks pass
- [ ] Files staged and reviewed
- [ ] Commit created with proper message
- [ ] Changelog updated (if applicable)
- [ ] Summary provided
- [ ] Ready for push/PR

## Version Management

If the project uses semantic versioning:

**Patch version** (1.0.x): Bug fixes, minor changes
**Minor version** (1.x.0): New features, backwards compatible
**Major version** (x.0.0): Breaking changes

Check version files:
- Python: `pyproject.toml`, `__init__.py`
- Node.js: `package.json`
- Go: `version.go`
- Rust: `Cargo.toml`

Note: Version bumps are typically done in dedicated version release workflows, not per-feature releases.
