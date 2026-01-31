"""Workflow manager for task phase tracking."""

import json
from pathlib import Path
from datetime import datetime
from .phases import TaskPhase, TaskWorkflow, PhaseTransition


class WorkflowManager:
    """Manages task workflows and phase transitions."""
    
    def __init__(self, workflows_dir: Path | None = None):
        self.workflows_dir = workflows_dir or Path(".adw/workflows")
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self._workflows: dict[str, TaskWorkflow] = {}
    
    def get_workflow(self, task_id: str) -> TaskWorkflow:
        """Get or create workflow for task."""
        if task_id not in self._workflows:
            workflow = self._load_workflow(task_id)
            if not workflow:
                workflow = TaskWorkflow(task_id=task_id)
            self._workflows[task_id] = workflow
        return self._workflows[task_id]
    
    def transition(
        self,
        task_id: str,
        phase: TaskPhase,
        reason: str | None = None,
        actor: str = "system"
    ) -> bool:
        """Transition a task to a new phase."""
        workflow = self.get_workflow(task_id)
        if workflow.transition_to(phase, reason, actor):
            self._save_workflow(workflow)
            return True
        return False
    
    def _load_workflow(self, task_id: str) -> TaskWorkflow | None:
        """Load workflow from disk."""
        file = self.workflows_dir / f"{task_id}.json"
        if not file.exists():
            return None
        
        try:
            data = json.loads(file.read_text())
            workflow = TaskWorkflow(
                task_id=data["task_id"],
                current_phase=TaskPhase(data["current_phase"]),
                spec_id=data.get("spec_id"),
                spec_file=data.get("spec_file"),
                discussion_file=data.get("discussion_file"),
                implementation_branch=data.get("implementation_branch"),
                depends_on=data.get("depends_on", []),
                blocks=data.get("blocks", []),
            )
            
            for h in data.get("history", []):
                workflow.history.append(PhaseTransition(
                    from_phase=TaskPhase(h["from_phase"]) if h.get("from_phase") else None,
                    to_phase=TaskPhase(h["to_phase"]),
                    timestamp=datetime.fromisoformat(h["timestamp"]),
                    reason=h.get("reason"),
                    actor=h.get("actor", "system"),
                ))
            
            return workflow
        except Exception:
            return None
    
    def _save_workflow(self, workflow: TaskWorkflow) -> None:
        """Save workflow to disk."""
        file = self.workflows_dir / f"{workflow.task_id}.json"
        
        data = {
            "task_id": workflow.task_id,
            "current_phase": workflow.current_phase.value,
            "spec_id": workflow.spec_id,
            "spec_file": workflow.spec_file,
            "discussion_file": workflow.discussion_file,
            "implementation_branch": workflow.implementation_branch,
            "depends_on": workflow.depends_on,
            "blocks": workflow.blocks,
            "history": [
                {
                    "from_phase": h.from_phase.value if h.from_phase else None,
                    "to_phase": h.to_phase.value,
                    "timestamp": h.timestamp.isoformat(),
                    "reason": h.reason,
                    "actor": h.actor,
                }
                for h in workflow.history
            ],
        }
        
        file.write_text(json.dumps(data, indent=2))
    
    def get_tasks_in_phase(self, phase: TaskPhase) -> list[TaskWorkflow]:
        """Get all tasks in a specific phase."""
        workflows = []
        for file in self.workflows_dir.glob("*.json"):
            task_id = file.stem
            workflow = self.get_workflow(task_id)
            if workflow.current_phase == phase:
                workflows.append(workflow)
        return workflows
    
    def get_tasks_needing_human(self) -> list[TaskWorkflow]:
        """Get all tasks that need human input."""
        workflows = []
        for file in self.workflows_dir.glob("*.json"):
            task_id = file.stem
            workflow = self.get_workflow(task_id)
            if workflow.current_phase.needs_human:
                workflows.append(workflow)
        return workflows
