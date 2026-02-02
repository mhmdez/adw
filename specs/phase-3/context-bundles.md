# Spec: Context Bundles

## Job to Be Done
Automatically capture files accessed during agent sessions and enable session restoration.

## Acceptance Criteria

### 1. File Access Tracking
- [ ] Track all files read during a session via hooks
- [ ] Store in `agents/<task_id>/context_bundle.jsonl`
- [ ] Format per line:
  ```json
  {"timestamp": "...", "action": "read", "path": "src/foo.py", "lines": [1, 50]}
  ```
- [ ] Deduplicate repeated accesses

### 2. Bundle Storage
- [ ] Create `src/adw/context/bundles.py`
- [ ] Function: `save_bundle(task_id: str, files: list)`
- [ ] Function: `load_bundle(task_id: str) -> list`
- [ ] Store bundles in `.adw/bundles/`

### 3. Load Bundle Command
- [ ] Add `/load_bundle <task_id>` Claude command
- [ ] Reads all files from bundle into context
- [ ] Shows: "Loaded context bundle: 12 files, 3,400 lines"
- [ ] CLI: `adw bundle load <task_id>`

### 4. Bundle Diffing
- [ ] `adw bundle diff <task1> <task2>`
- [ ] Show files added/removed/changed
- [ ] Useful for understanding session differences

### 5. Smart Bundle Selection
- [ ] `adw bundle suggest "implement auth"`
- [ ] Find bundles from similar past tasks
- [ ] Rank by file overlap and task similarity
- [ ] Suggest top 3 bundles to load

## Technical Notes
- Bundles are read-only snapshots
- Don't include binary files
- Compress bundles older than 7 days

## Testing
- [ ] Test bundle save/load
- [ ] Test diffing
- [ ] Test suggestion ranking
