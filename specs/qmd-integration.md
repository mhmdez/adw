# QMD Integration Spec

## Summary

Integrate qmd (Query Markup Documents) into ADW to provide semantic search capabilities for agents. This enables smarter context injection during task planning and execution.

## Motivation

Currently, ADW agents work with whatever context is in CLAUDE.md and the immediate task description. They often need to find relevant documentation, prior decisions, or code patterns that exist elsewhere in the codebase. qmd solves this by providing:

1. **Semantic search** - Find docs by meaning, not just keywords
2. **Local execution** - No API calls, runs on-device with GGUF models
3. **MCP integration** - Claude Code can use qmd tools directly

## Design

### Three Integration Points

#### 1. `adw init --qmd` - Project Bootstrap

When initializing a project, optionally create a qmd collection:

```bash
adw init --qmd          # Auto-detect and index project
adw init --no-qmd       # Skip qmd setup
```

**Behavior:**
- Check if qmd is installed (`which qmd`)
- Create collection named after project directory
- Index `**/*.md` by default (can customize via config)
- Add context description from CLAUDE.md summary
- Run `qmd embed` to generate vectors

**Output:**
```
✓ Created qmd collection: my-project
  Indexed: 47 files
  Embedded: 112 chunks
```

#### 2. Context Injection (Pre-Planner)

Before the planner phase, query qmd for relevant context based on the task description:

```python
# In workflow/planner.py or agent/manager.py
def get_task_context(task: str, project_path: Path, max_results: int = 5) -> str:
    """Query qmd for task-relevant context."""
    result = subprocess.run(
        ["qmd", "search", task, "-n", str(max_results), "--json"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        docs = json.loads(result.stdout)
        return format_context(docs)
    return ""
```

**Injection point:** Append to planner prompt as:
```
## Relevant Context (from project docs)

{qmd_results}
```

#### 3. MCP Server Configuration

Generate Claude Code MCP config during init:

```json
// .claude/settings.json
{
  "mcpServers": {
    "qmd": {
      "command": "qmd",
      "args": ["mcp"]
    }
  }
}
```

This gives agents direct access to:
- `qmd_search` - Keyword search
- `qmd_vsearch` - Semantic search  
- `qmd_query` - Hybrid with reranking
- `qmd_get` - Retrieve full document

### Configuration

Add to `.adw/config.toml`:

```toml
[qmd]
enabled = true
collection = "auto"  # or explicit name
mask = "**/*.md"     # file pattern
max_context_results = 5
context_injection = true  # inject into planner prompts
mcp_server = true  # generate MCP config
```

### CLI Commands

```bash
# Manual control
adw qmd status          # Check if qmd is set up
adw qmd init            # Initialize qmd for current project
adw qmd search "query"  # Quick search
adw qmd update          # Re-index changed files
```

## Implementation Plan

### Phase 1: Core Integration (`integrations/qmd.py`)

```python
"""QMD integration for ADW."""

import json
import shutil
import subprocess
from pathlib import Path

def is_qmd_available() -> bool:
    """Check if qmd CLI is installed."""
    return shutil.which("qmd") is not None

def init_collection(
    project_path: Path,
    collection_name: str | None = None,
    mask: str = "**/*.md",
) -> dict:
    """Initialize qmd collection for project."""
    name = collection_name or project_path.name
    
    result = subprocess.run(
        ["qmd", "collection", "add", str(project_path), "--name", name, "--mask", mask],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        return {"success": False, "error": result.stderr}
    
    # Run embedding
    embed_result = subprocess.run(
        ["qmd", "embed"],
        capture_output=True, text=True
    )
    
    return {
        "success": True,
        "collection": name,
        "output": result.stdout,
        "embed_output": embed_result.stdout
    }

def search(query: str, collection: str | None = None, limit: int = 5) -> list[dict]:
    """Search for relevant documents."""
    cmd = ["qmd", "search", query, "-n", str(limit), "--json"]
    if collection:
        cmd.extend(["-c", collection])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        return []
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

def get_context_for_task(task: str, collection: str | None = None) -> str:
    """Get formatted context for a task."""
    results = search(task, collection, limit=5)
    
    if not results:
        return ""
    
    context_parts = []
    for doc in results:
        path = doc.get("path", "unknown")
        snippet = doc.get("snippet", "")
        score = doc.get("score", 0)
        
        if score >= 0.3:  # Only include reasonably relevant results
            context_parts.append(f"### {path}\n{snippet}")
    
    if not context_parts:
        return ""
    
    return "## Relevant Context (from project docs)\n\n" + "\n\n".join(context_parts)

def setup_mcp_config(project_path: Path) -> bool:
    """Create Claude Code MCP config for qmd."""
    claude_dir = project_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    
    settings_path = claude_dir / "settings.json"
    
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass
    
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}
    
    settings["mcpServers"]["qmd"] = {
        "command": "qmd",
        "args": ["mcp"]
    }
    
    settings_path.write_text(json.dumps(settings, indent=2))
    return True

def get_status(project_path: Path) -> dict:
    """Get qmd status for project."""
    result = subprocess.run(
        ["qmd", "status"],
        capture_output=True, text=True
    )
    
    # Check if project has a collection
    collections = []
    if result.returncode == 0:
        # Parse status output for collections
        for line in result.stdout.split("\n"):
            if project_path.name in line or str(project_path) in line:
                collections.append(line.strip())
    
    return {
        "available": is_qmd_available(),
        "collections": collections,
        "raw_status": result.stdout if result.returncode == 0 else None
    }
```

### Phase 2: Init Integration

Update `init.py` to include qmd setup:

```python
# Add to init_project()
if qmd_enabled and is_qmd_available():
    console.print("[dim]Setting up qmd search...[/dim]")
    qmd_result = init_collection(project_path)
    if qmd_result["success"]:
        result["created"].append(f"qmd collection: {qmd_result['collection']}")
        setup_mcp_config(project_path)
        result["created"].append(".claude/settings.json (MCP config)")
```

### Phase 3: Context Injection

Update planner to inject context:

```python
# In workflow or agent manager
context = get_context_for_task(task.description, project_name)
if context:
    prompt = f"{original_prompt}\n\n{context}"
```

## Testing

```bash
# Create test project
mkdir /tmp/test-adw-qmd && cd /tmp/test-adw-qmd
echo "# API Reference\n\n## Authentication\nUse Bearer tokens." > docs/api.md

# Initialize with qmd
adw init --qmd

# Verify
adw qmd status
qmd search "auth" -c test-adw-qmd

# Test context injection
adw add "implement user authentication"
# Should see relevant context in planner prompt
```

## Dependencies

- qmd must be installed separately (`bun install -g github:tobi/qmd`)
- Graceful degradation if qmd not available

## Timeline

- Phase 1 (integrations/qmd.py): 30 min
- Phase 2 (init integration): 30 min  
- Phase 3 (context injection): 30 min
- Testing: 30 min

Total: ~2 hours
