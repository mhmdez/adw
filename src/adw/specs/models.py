"""Spec data models."""

from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path


class SpecStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class Spec(BaseModel):
    """A task specification."""
    id: str
    title: str
    status: SpecStatus = SpecStatus.DRAFT
    task_id: str | None = None
    file_path: Path
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    description: str | None = None
    phase: str | None = None
    priority: int = 0
    dependencies: list[str] = []

    class Config:
        arbitrary_types_allowed = True

    @property
    def is_actionable(self) -> bool:
        return self.status == SpecStatus.APPROVED

    @property
    def display_status(self) -> str:
        icons = {
            SpecStatus.DRAFT: "📝",
            SpecStatus.PENDING: "⏳",
            SpecStatus.APPROVED: "✅",
            SpecStatus.REJECTED: "❌",
            SpecStatus.IMPLEMENTED: "🎉",
        }
        return f"{icons.get(self.status, '?')} {self.status.value}"
