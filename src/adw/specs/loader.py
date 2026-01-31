"""Spec loader and manager."""

import re
from pathlib import Path
from datetime import datetime
from .models import Spec, SpecStatus


class SpecLoader:
    """Load and parse spec files from a directory."""

    SPEC_PATTERN = re.compile(r'^(P\d+-\d+)\.md$')
    STATUS_PATTERN = re.compile(r'^Status:\s*(\w+)', re.MULTILINE | re.IGNORECASE)
    TITLE_PATTERN = re.compile(r'^#\s+(?:Task\s+)?(?:P\d+-\d+:?\s*)?(.+)$', re.MULTILINE)

    def __init__(self, specs_dir: Path | None = None):
        self.specs_dir = specs_dir or Path("specs")

    def load_all(self) -> list[Spec]:
        """Load all specs from the directory."""
        specs = []
        if not self.specs_dir.exists():
            return specs

        for file in self.specs_dir.glob("*.md"):
            match = self.SPEC_PATTERN.match(file.name)
            if match:
                spec = self._load_spec(file, match.group(1))
                if spec:
                    specs.append(spec)

        return sorted(specs, key=lambda s: (s.phase or "", s.priority, s.id))

    def _load_spec(self, path: Path, spec_id: str) -> Spec | None:
        """Load a single spec file."""
        try:
            content = path.read_text()
            stat = path.stat()

            title_match = self.TITLE_PATTERN.search(content)
            title = title_match.group(1).strip() if title_match else spec_id

            status = SpecStatus.DRAFT
            status_match = self.STATUS_PATTERN.search(content)
            if status_match:
                try:
                    status = SpecStatus(status_match.group(1).lower())
                except ValueError:
                    pass

            phase = None
            if spec_id.startswith("P"):
                phase_num = spec_id.split("-")[0][1:]
                phase = f"Phase {phase_num}"

            return Spec(
                id=spec_id,
                title=title,
                status=status,
                file_path=path,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                updated_at=datetime.fromtimestamp(stat.st_mtime),
                description=self._extract_description(content),
                phase=phase,
            )
        except Exception:
            return None

    def _extract_description(self, content: str) -> str | None:
        """Extract first paragraph after objective heading."""
        obj_match = re.search(r'##\s*Objective\s*\n+(.+?)(?=\n\n|\n##|$)', content, re.DOTALL)
        if obj_match:
            return obj_match.group(1).strip()[:200]
        return None

    def get_spec(self, spec_id: str) -> Spec | None:
        """Get a specific spec by ID."""
        file = self.specs_dir / f"{spec_id}.md"
        if file.exists():
            return self._load_spec(file, spec_id)
        return None

    def update_status(self, spec_id: str, status: SpecStatus, reason: str | None = None) -> bool:
        """Update a spec's status in its file."""
        file = self.specs_dir / f"{spec_id}.md"
        if not file.exists():
            return False

        content = file.read_text()

        if self.STATUS_PATTERN.search(content):
            content = self.STATUS_PATTERN.sub(f"Status: {status.value}", content)
        else:
            content = re.sub(r'^(#.+\n)', f'\\1\nStatus: {status.value}\n', content)

        if status == SpecStatus.REJECTED and reason:
            content = re.sub(r'(Status: rejected)', f'\\1\nRejection Reason: {reason}', content)

        file.write_text(content)
        return True
