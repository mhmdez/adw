"""QMD Plugin - Semantic search and context injection for ADW.

This plugin integrates qmd (Query Markup Documents) to provide:
- Automatic project indexing during init
- Context injection during planning phase
- CLI commands for manual search
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from adw.plugins.base import Plugin
from adw.integrations import qmd as qmd_integration


class QmdPlugin(Plugin):
    """QMD semantic search plugin."""
    
    name = "qmd"
    version = "0.1.0"
    description = "Semantic search and context injection using qmd"
    author = "StudiBudi"
    requires_external = ["qmd"]
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.auto_context = self.config.get("auto_context", True)
        self.max_results = self.config.get("max_results", 5)
        self.collection = self.config.get("collection", None)
    
    def on_init(self, project_path: Path) -> None:
        """Set up qmd collection for project."""
        if not qmd_integration.is_available():
            return
        
        # Get or generate collection name
        collection = self.collection or qmd_integration.get_collection_name(project_path)
        
        # Check if collection already exists
        status = qmd_integration.get_status()
        if collection in status.get("collections", []):
            # Already indexed, just update
            qmd_integration.update_index()
            return
        
        # Initialize new collection
        result = qmd_integration.init_collection(
            project_path,
            collection_name=collection,
            embed=True,
        )
        
        if result["success"]:
            # Add context description
            claude_md = project_path / "CLAUDE.md"
            if claude_md.exists():
                # Extract first meaningful line as context
                content = claude_md.read_text()
                lines = content.split("\n")
                context = ""
                for line in lines[1:10]:
                    if line.strip() and not line.startswith("#"):
                        context = line.strip()[:100]
                        break
                if context:
                    qmd_integration.add_context(collection, context)
            
            # Set up MCP config for Claude Code
            qmd_integration.setup_mcp_config(project_path)
    
    def on_plan(self, task: str, context: str) -> str:
        """Inject relevant context from qmd search."""
        if not self.auto_context:
            return context
        
        if not qmd_integration.is_available():
            return context
        
        # Search for relevant docs
        qmd_context = qmd_integration.get_context_for_task(
            task,
            collection=self.collection,
            limit=self.max_results,
        )
        
        if qmd_context:
            context = f"{context}\n\n{qmd_context}"
        
        return context
    
    def get_commands(self) -> list:
        """Return CLI commands for qmd."""
        return [create_qmd_commands()]
    
    def status(self) -> dict[str, Any]:
        """Return plugin status."""
        base_status = super().status()
        
        qmd_status = qmd_integration.get_status()
        base_status.update({
            "available": qmd_status.get("available", False),
            "collections": qmd_status.get("collections", []),
            "documents": qmd_status.get("documents", 0),
            "auto_context": self.auto_context,
        })
        
        return base_status
    
    @classmethod
    def install(cls, plugin_dir: Path) -> tuple[bool, str | None]:
        """Check qmd is available, offer to install if not."""
        if qmd_integration.is_available():
            return True, None
        
        # Check if bun is available
        import shutil
        if not shutil.which("bun"):
            return False, (
                "qmd requires Bun runtime. Install with:\n"
                "  curl -fsSL https://bun.sh/install | bash\n"
                "Then run: bun install -g github:tobi/qmd"
            )
        
        # Try to install qmd
        import subprocess
        result = subprocess.run(
            ["bun", "install", "-g", "github:tobi/qmd"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            return False, f"Failed to install qmd: {result.stderr}"
        
        return True, None


def create_qmd_commands():
    """Create the qmd command group."""
    
    @click.group()
    def qmd():
        """Semantic search commands."""
        pass
    
    @qmd.command("status")
    def qmd_status():
        """Show qmd installation and index status."""
        from rich.console import Console
        console = Console()
        
        status = qmd_integration.get_status()
        
        if not status.get("available"):
            console.print("[red]✗ qmd not installed[/red]")
            console.print()
            console.print("[dim]Install with:[/dim]")
            console.print("  [cyan]bun install -g github:tobi/qmd[/cyan]")
            return
        
        console.print("[green]✓ qmd installed[/green]")
        console.print()
        
        collections = status.get("collections", [])
        if collections:
            console.print("[bold]Collections:[/bold]")
            for col in collections:
                console.print(f"  • {col}")
        else:
            console.print("[yellow]No collections found[/yellow]")
        
        if status.get("documents"):
            console.print()
            console.print(f"[dim]Total documents: {status['documents']}[/dim]")
    
    @qmd.command("init")
    @click.option("--name", "-n", help="Collection name")
    @click.option("--mask", "-m", default="**/*.md", help="File pattern")
    @click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
    def qmd_init(name: str | None, mask: str, path: Path | None):
        """Initialize qmd for the current project."""
        from rich.console import Console
        console = Console()
        
        project_path = path or Path.cwd()
        
        if not qmd_integration.is_available():
            console.print("[red]✗ qmd not installed[/red]")
            return
        
        console.print(f"[bold cyan]Setting up qmd for {project_path.name}[/bold cyan]")
        
        with console.status("[cyan]Indexing and embedding...[/cyan]"):
            result = qmd_integration.init_collection(
                project_path,
                collection_name=name,
                mask=mask,
                embed=True,
            )
        
        if result["success"]:
            console.print(f"[green]✓ Created collection: {result['collection']}[/green]")
            console.print(f"  Files: {result.get('files', '?')}")
            console.print(f"  Chunks: {result.get('chunks', '?')}")
            
            if qmd_integration.setup_mcp_config(project_path):
                console.print("[green]✓ Created MCP config[/green]")
        else:
            console.print(f"[red]✗ Failed: {result.get('error')}[/red]")
    
    @qmd.command("search")
    @click.argument("query")
    @click.option("-n", "--limit", default=5, help="Number of results")
    @click.option("-c", "--collection", help="Filter to collection")
    @click.option("--semantic", "-s", is_flag=True, help="Use semantic search")
    def qmd_search(query: str, limit: int, collection: str | None, semantic: bool):
        """Search project documents."""
        from rich.console import Console
        console = Console()
        
        if not qmd_integration.is_available():
            console.print("[red]✗ qmd not installed[/red]")
            return
        
        mode = "vsearch" if semantic else "search"
        results = qmd_integration.search(query, collection, limit, mode=mode)
        
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        console.print(f"[bold cyan]Results for: {query}[/bold cyan]")
        console.print()
        
        for i, doc in enumerate(results, 1):
            path = doc.get("path", doc.get("file", "unknown"))
            snippet = doc.get("snippet", doc.get("text", ""))[:200]
            score = doc.get("score", 0)
            
            if path.startswith("qmd://"):
                path = "/".join(path.split("/")[3:])
            
            score_str = f"{score * 100:.0f}%" if isinstance(score, float) else str(score)
            
            console.print(f"[bold]{i}. {path}[/bold] [dim]({score_str})[/dim]")
            console.print(f"   [dim]{snippet}...[/dim]")
            console.print()
    
    @qmd.command("update")
    @click.option("--pull", is_flag=True, help="Git pull before indexing")
    def qmd_update(pull: bool):
        """Re-index all collections."""
        from rich.console import Console
        console = Console()
        
        if not qmd_integration.is_available():
            console.print("[red]✗ qmd not installed[/red]")
            return
        
        with console.status("[cyan]Updating...[/cyan]"):
            result = qmd_integration.update_index(pull=pull)
        
        if result["success"]:
            console.print("[green]✓ Index updated[/green]")
        else:
            console.print(f"[red]✗ Failed: {result.get('error')}[/red]")
    
    return qmd


# Export plugin class
plugin_class = QmdPlugin
