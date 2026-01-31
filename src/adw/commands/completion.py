"""Shell completion support for ADW CLI."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import click


def get_task_ids() -> list[str]:
    """Get list of task IDs for completion."""
    from ..agent.task_parser import get_all_tasks
    
    tasks_file = Path("tasks.md")
    if not tasks_file.exists():
        return []
    
    tasks = get_all_tasks(tasks_file)
    ids = []
    
    for task in tasks:
        # Extract TASK-XXX from description
        match = re.search(r"(TASK-\d+)", task.description)
        if match:
            ids.append(match.group(1))
        # Also add ADW ID if present
        if task.adw_id:
            ids.append(task.adw_id)
    
    return ids


def get_worktree_names() -> list[str]:
    """Get list of worktree names for completion."""
    from ..agent.worktree import list_worktrees
    
    worktrees = list_worktrees()
    return [Path(wt.get("path", "")).name for wt in worktrees if wt.get("path")]


def get_spec_names() -> list[str]:
    """Get list of spec names for completion."""
    specs_dir = Path("specs")
    if not specs_dir.exists():
        return []
    
    return [f.stem for f in specs_dir.glob("*.md")]


class TaskIdType(click.ParamType):
    """Custom parameter type with task ID completion."""
    
    name = "task_id"
    
    def shell_complete(self, ctx: click.Context, incomplete: str) -> list:
        """Return completions for task IDs."""
        task_ids = get_task_ids()
        return [
            click.shell_completion.CompletionItem(tid)
            for tid in task_ids
            if tid.lower().startswith(incomplete.lower())
        ]


class WorktreeNameType(click.ParamType):
    """Custom parameter type with worktree name completion."""
    
    name = "worktree_name"
    
    def shell_complete(self, ctx: click.Context, incomplete: str) -> list:
        """Return completions for worktree names."""
        names = get_worktree_names()
        return [
            click.shell_completion.CompletionItem(name)
            for name in names
            if name.lower().startswith(incomplete.lower())
        ]


class SpecNameType(click.ParamType):
    """Custom parameter type with spec name completion."""
    
    name = "spec_name"
    
    def shell_complete(self, ctx: click.Context, incomplete: str) -> list:
        """Return completions for spec names."""
        names = get_spec_names()
        return [
            click.shell_completion.CompletionItem(name)
            for name in names
            if name.lower().startswith(incomplete.lower())
        ]


TASK_ID = TaskIdType()
WORKTREE_NAME = WorktreeNameType()
SPEC_NAME = SpecNameType()


def setup_completion(shell: str | None = None) -> str:
    """Generate shell completion script.
    
    Args:
        shell: Shell type (bash, zsh, fish). Auto-detected if not provided.
    
    Returns:
        Completion script content.
    """
    if shell is None:
        shell = os.environ.get("SHELL", "").split("/")[-1]
        if shell not in ("bash", "zsh", "fish"):
            shell = "bash"
    
    if shell == "bash":
        return '''
# ADW Bash completion
# Add to ~/.bashrc: eval "$(adw completion bash)"

_adw_completion() {
    local IFS=$'\\n'
    local response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _ADW_COMPLETE=bash_complete adw)
    
    for completion in $response; do
        IFS=',' read type value <<< "$completion"
        if [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
        fi
    done
    return 0
}

complete -o default -F _adw_completion adw
'''
    
    elif shell == "zsh":
        return '''
# ADW Zsh completion
# Add to ~/.zshrc: eval "$(adw completion zsh)"

_adw() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[adw] )) && return 1
    
    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _ADW_COMPLETE=zsh_complete adw)}")
    
    for key descr in ${(kv)response}; do
        if [[ "$descr" == "_" ]]; then
            completions+=("$key")
        else
            completions_with_descriptions+=("$key":"$descr")
        fi
    done
    
    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi
    
    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _adw adw
'''
    
    elif shell == "fish":
        return '''
# ADW Fish completion
# Add to ~/.config/fish/completions/adw.fish

function _adw_completion
    set -l response (env _ADW_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) adw)
    for completion in $response
        echo $completion
    end
end

complete -c adw -a '(_adw_completion)' -f
'''
    
    return f"# Unsupported shell: {shell}"


# Completion for status filter
STATUS_CHOICES = click.Choice(
    ["pending", "running", "done", "failed", "blocked", "all"],
    case_sensitive=False,
)
