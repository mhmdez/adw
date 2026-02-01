"""QMD integration for ADW.

Provides semantic search capabilities for agents via qmd (Query Markup Documents).
https://github.com/tobi/qmd
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _get_qmd_path() -> str | None:
    """Get path to qmd executable."""
    # Check standard PATH
    qmd_path = shutil.which("qmd")
    if qmd_path:
        return qmd_path
    
    # Check common bun install location
    bun_path = Path.home() / ".bun" / "bin" / "qmd"
    if bun_path.exists():
        return str(bun_path)
    
    return None


def is_available() -> bool:
    """Check if qmd CLI is installed."""
    return _get_qmd_path() is not None


def _run_qmd(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run qmd with proper path resolution."""
    qmd_path = _get_qmd_path()
    if not qmd_path:
        raise FileNotFoundError("qmd not found")
    
    cmd = [qmd_path] + args
    return subprocess.run(cmd, **kwargs)


def get_collection_name(project_path: Path) -> str:
    """Generate collection name from project path."""
    # Use project directory name, sanitized
    name = project_path.name.lower()
    # Replace spaces and special chars
    name = "".join(c if c.isalnum() or c == "-" else "-" for c in name)
    return name


def init_collection(
    project_path: Path,
    collection_name: str | None = None,
    mask: str = "**/*.md",
    embed: bool = True,
) -> dict:
    """Initialize qmd collection for project.
    
    Args:
        project_path: Project root path
        collection_name: Optional explicit name (defaults to project dir name)
        mask: Glob pattern for files to index
        embed: Whether to run embedding after indexing
        
    Returns:
        Dict with success status, collection name, and output
    """
    if not is_available():
        return {"success": False, "error": "qmd not installed"}
    
    name = collection_name or get_collection_name(project_path)
    
    # Create collection
    result = _run_qmd(
        ["collection", "add", str(project_path), "--name", name, "--mask", mask],
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        # Check if collection already exists
        if "already exists" in result.stderr.lower():
            # Update instead
            result = _run_qmd(
                ["update"],
                capture_output=True,
                text=True,
            )
        else:
            return {"success": False, "error": result.stderr}
    
    # Parse file count from output
    file_count = 0
    for line in result.stdout.split("\n"):
        if "Indexed:" in line or "Files:" in line:
            # Try to extract number
            parts = line.split()
            for part in parts:
                if part.isdigit():
                    file_count = int(part)
                    break
    
    embed_output = ""
    chunk_count = 0
    
    if embed:
        # Run embedding
        embed_result = _run_qmd(
            ["embed"],
            capture_output=True,
            text=True,
        )
        embed_output = embed_result.stdout
        
        # Parse chunk count
        for line in embed_output.split("\n"):
            if "chunks" in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit():
                        chunk_count = int(part)
                        break
    
    return {
        "success": True,
        "collection": name,
        "files": file_count,
        "chunks": chunk_count,
        "output": result.stdout,
        "embed_output": embed_output,
    }


def add_context(
    collection: str,
    context: str,
    path: str = "/",
) -> bool:
    """Add context description to a collection.
    
    Args:
        collection: Collection name
        context: Context description text
        path: Path within collection (default: root)
        
    Returns:
        True if successful
    """
    if not is_available():
        return False
    
    target = f"qmd://{collection}{path}"
    result = _run_qmd(
        ["context", "add", target, context],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def search(
    query: str,
    collection: str | None = None,
    limit: int = 5,
    min_score: float = 0.3,
    mode: str = "search",  # search, vsearch, or query
) -> list[dict]:
    """Search for relevant documents.
    
    Args:
        query: Search query
        collection: Optional collection filter
        limit: Maximum results
        min_score: Minimum relevance score
        mode: Search mode (search=keyword, vsearch=semantic, query=hybrid)
        
    Returns:
        List of result dicts with path, snippet, score
    """
    if not is_available():
        return []
    
    args = [mode, query, "-n", str(limit), "--json"]
    if collection:
        args.extend(["-c", collection])
    if min_score > 0:
        args.extend(["--min-score", str(min_score)])
    
    result = _run_qmd(args, capture_output=True, text=True)
    
    if result.returncode != 0:
        return []
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def get_document(path: str, full: bool = False) -> str | None:
    """Get a document by path or docid.
    
    Args:
        path: File path or #docid
        full: Return full document (not just snippet)
        
    Returns:
        Document content or None
    """
    if not is_available():
        return None
    
    args = ["get", path]
    if full:
        args.append("--full")
    
    result = _run_qmd(args, capture_output=True, text=True)
    
    if result.returncode != 0:
        return None
    
    return result.stdout


def format_context_for_prompt(results: list[dict], max_chars: int = 4000) -> str:
    """Format search results as context for an LLM prompt.
    
    Args:
        results: Search results from search()
        max_chars: Maximum total characters
        
    Returns:
        Formatted context string
    """
    if not results:
        return ""
    
    context_parts = []
    total_chars = 0
    
    for doc in results:
        path = doc.get("path", doc.get("file", "unknown"))
        snippet = doc.get("snippet", doc.get("text", ""))
        score = doc.get("score", 0)
        
        # Skip low-relevance results
        if isinstance(score, (int, float)) and score < 0.3:
            continue
        
        # Clean up path (remove qmd:// prefix if present)
        if path.startswith("qmd://"):
            path = path.split("/", 3)[-1] if "/" in path[6:] else path[6:]
        
        entry = f"### {path}\n{snippet}"
        
        if total_chars + len(entry) > max_chars:
            break
        
        context_parts.append(entry)
        total_chars += len(entry) + 2  # +2 for newlines
    
    if not context_parts:
        return ""
    
    return "## Relevant Context (from project docs)\n\n" + "\n\n".join(context_parts)


def get_context_for_task(
    task: str,
    collection: str | None = None,
    limit: int = 5,
) -> str:
    """Get formatted context for a task description.
    
    This is the main entry point for context injection.
    
    Args:
        task: Task description to find context for
        collection: Optional collection to search
        limit: Maximum results
        
    Returns:
        Formatted context string for prompt injection
    """
    # Try semantic search first for best results
    results = search(task, collection, limit, mode="vsearch")
    
    # Fall back to keyword search if no results
    if not results:
        results = search(task, collection, limit, mode="search")
    
    return format_context_for_prompt(results)


def setup_mcp_config(project_path: Path) -> bool:
    """Create Claude Code MCP config for qmd.
    
    Args:
        project_path: Project root path
        
    Returns:
        True if config was created/updated
    """
    claude_dir = project_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    
    settings_path = claude_dir / "settings.json"
    
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass
    
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}
    
    # Don't overwrite if already configured
    if "qmd" in settings.get("mcpServers", {}):
        return False
    
    settings["mcpServers"]["qmd"] = {
        "command": "qmd",
        "args": ["mcp"],
    }
    
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    return True


def get_status() -> dict:
    """Get qmd installation and index status.
    
    Returns:
        Dict with availability, collections, and status info
    """
    if not is_available():
        return {
            "available": False,
            "error": "qmd not installed. Install with: bun install -g github:tobi/qmd",
        }
    
    result = _run_qmd(
        ["status"],
        capture_output=True,
        text=True,
    )
    
    collections = []
    doc_count = 0
    
    if result.returncode == 0:
        lines = result.stdout.split("\n")
        in_collections = False
        
        for line in lines:
            # Parse document count
            if "Total:" in line and "files" in line:
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        doc_count = int(part)
                        break
            
            # Parse collection names (they appear after "Collections" header)
            if line.strip() == "Collections":
                in_collections = True
                continue
            
            if line.strip() == "Examples":
                in_collections = False
                continue
            
            if in_collections:
                # Collection lines start with 2 spaces and have (qmd://)
                # Format: "  studibudi-docs (qmd://studibudi-docs/)"
                if line.startswith("  ") and not line.startswith("    ") and "(qmd://" in line:
                    # Extract name before the (qmd://
                    name = line.strip().split("(")[0].strip()
                    if name:
                        collections.append(name)
    
    return {
        "available": True,
        "collections": collections,
        "documents": doc_count,
        "raw_status": result.stdout,
    }


def update_index(pull: bool = False) -> dict:
    """Re-index all collections.
    
    Args:
        pull: Run git pull before indexing
        
    Returns:
        Dict with success status and output
    """
    if not is_available():
        return {"success": False, "error": "qmd not installed"}
    
    args = ["update"]
    if pull:
        args.append("--pull")
    
    result = _run_qmd(args, capture_output=True, text=True)
    
    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None,
    }
