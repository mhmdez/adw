# Spec: Screenshot Capture System

## Job to Be Done
Automatically capture screenshots when building UI features, attaching them to PRs as visual proof of what was built.

## Acceptance Criteria

### 1. macOS Screenshot Utility
- [ ] Create `src/adw/utils/screenshot.py`
- [ ] Function: `capture_screenshot(output_path: str) -> Path`
- [ ] Use `screencapture -x` (silent, no sound)
- [ ] Support custom regions via coordinates
- [ ] Return path to captured image

### 2. Dev Server Detection
- [ ] Function: `is_dev_server_running(port: int) -> bool`
- [ ] Check common ports: 3000, 5173, 8000, 8080
- [ ] Parse output of `lsof -i` or `netstat`

### 3. Auto-Capture in Hooks
- [ ] In `post_tool_use.py`, detect dev server start commands:
  - `npm run dev`
  - `bun run dev`
  - `pnpm dev`
  - `python -m http.server`
  - `uvicorn`, `flask run`
- [ ] Wait 2-3 seconds for server to start
- [ ] Capture screenshot to `agents/<task_id>/screenshots/`
- [ ] Name: `screenshot-{timestamp}.png`

### 4. PR Attachment
- [ ] Function: `attach_screenshots_to_pr(pr_number: int, screenshots: list[Path])`
- [ ] Upload images to PR body or comments
- [ ] Use GitHub API to update PR description
- [ ] Markdown format: `![Screenshot](url)`

### 5. Manual Command
- [ ] Add `adw screenshot` CLI command
- [ ] Options: `--port`, `--delay`, `--output`
- [ ] Opens browser to localhost:PORT, captures, closes

## Technical Notes
- Use Playwright for browser-based screenshots (more reliable)
- Fallback to `screencapture` for desktop capture
- Store screenshots in `.adw/screenshots/` by default

## Testing
- [ ] Unit test for screenshot utility
- [ ] Test dev server detection
- [ ] Integration test with mock PR
