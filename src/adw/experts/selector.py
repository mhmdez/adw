"""Expert auto-selection based on task context.

Automatically selects the appropriate expert(s) based on:
- Task keywords and description
- File patterns involved
- Project type detection
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Expert

logger = logging.getLogger(__name__)


@dataclass
class ExpertMatch:
    """Result of expert matching.

    Attributes:
        expert: The matched expert instance.
        score: Confidence score (0.0 to 1.0).
        reasons: List of reasons for the match.
    """

    expert: Expert
    score: float
    reasons: list[str]

    def __post_init__(self) -> None:
        # Clamp score to valid range
        self.score = max(0.0, min(1.0, self.score))


# Keyword patterns for each domain
DOMAIN_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "frontend": [
        (r"\breact\b", 0.9),
        (r"\bvue\b", 0.9),
        (r"\bcomponent\b", 0.7),
        (r"\bcss\b", 0.8),
        (r"\bstyle\b", 0.6),
        (r"\btailwind\b", 0.9),
        (r"\bui\b", 0.7),
        (r"\bfrontend\b", 1.0),
        (r"\bclient[- ]side\b", 0.8),
        (r"\bbutton\b", 0.5),
        (r"\bform\b", 0.5),
        (r"\bmodal\b", 0.6),
        (r"\blayout\b", 0.6),
        (r"\bresponsive\b", 0.7),
        (r"\baccessibility\b", 0.8),
        (r"\ba11y\b", 0.8),
        (r"\baria\b", 0.9),
        (r"\bhook\b", 0.6),
        (r"\bstate\s*management\b", 0.7),
        (r"\bzustand\b", 0.9),
        (r"\bredux\b", 0.9),
        (r"\bpinia\b", 0.9),
    ],
    "backend": [
        (r"\bfastapi\b", 0.9),
        (r"\bdjango\b", 0.9),
        (r"\bflask\b", 0.9),
        (r"\bapi\b", 0.7),
        (r"\bendpoint\b", 0.8),
        (r"\brest\b", 0.7),
        (r"\bdatabase\b", 0.8),
        (r"\bpostgres(ql)?\b", 0.9),
        (r"\bsupabase\b", 0.9),
        (r"\bsql\b", 0.7),
        (r"\bquery\b", 0.6),
        (r"\bauth(entication)?\b", 0.7),
        (r"\bbackend\b", 1.0),
        (r"\bserver[- ]side\b", 0.8),
        (r"\brouter\b", 0.6),
        (r"\bmiddleware\b", 0.7),
        (r"\bpydantic\b", 0.9),
        (r"\borm\b", 0.8),
        (r"\bmigration\b", 0.7),
        (r"\brls\b", 0.9),  # Row Level Security
        (r"\bjwt\b", 0.8),
        (r"\boauth\b", 0.8),
    ],
    "ai": [
        (r"\bllm\b", 0.9),
        (r"\bgpt\b", 0.9),
        (r"\bclaude\b", 0.9),
        (r"\banthropic\b", 0.9),
        (r"\bopenai\b", 0.9),
        (r"\bprompt\b", 0.8),
        (r"\bagent\b", 0.7),
        (r"\bchat(bot)?\b", 0.7),
        (r"\bembedding\b", 0.9),
        (r"\brag\b", 0.9),
        (r"\bretrieval\b", 0.7),
        (r"\btoken\b", 0.6),
        (r"\bai\b", 0.8),
        (r"\bmodel\b", 0.5),  # Lower score, too generic
        (r"\bgenerat(e|ion)\b", 0.5),
        (r"\bcompletion\b", 0.8),
        (r"\bfine[- ]tun(e|ing)\b", 0.9),
        (r"\bvector\b", 0.7),
        (r"\bsemantic\b", 0.7),
        (r"\btool\s*use\b", 0.9),
        (r"\bfunction\s*call(ing)?\b", 0.9),
    ],
}

# File patterns for each domain
FILE_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "frontend": [
        (r"\.tsx$", 0.9),
        (r"\.jsx$", 0.9),
        (r"\.vue$", 0.95),
        (r"\.css$", 0.7),
        (r"\.scss$", 0.7),
        (r"\.less$", 0.7),
        (r"components/", 0.8),
        (r"pages/", 0.6),
        (r"hooks/", 0.8),
        (r"styles/", 0.7),
        (r"ui/", 0.7),
        (r"layouts/", 0.6),
    ],
    "backend": [
        (r"routes?/", 0.8),
        (r"api/", 0.7),
        (r"models?\.py$", 0.8),
        (r"schemas?\.py$", 0.8),
        (r"services?/", 0.7),
        (r"repositories?/", 0.8),
        (r"migrations?/", 0.8),
        (r"endpoints?/", 0.8),
        (r"routers?/", 0.8),
        (r"main\.py$", 0.5),  # Could be either
        (r"db\.py$", 0.8),
        (r"database\.py$", 0.8),
    ],
    "ai": [
        (r"prompts?/", 0.9),
        (r"agents?/", 0.7),  # Could be ADW agents
        (r"llm/", 0.95),
        (r"chat/", 0.7),
        (r"embeddings?/", 0.9),
        (r"rag/", 0.95),
        (r"retrieval/", 0.8),
        (r"ai/", 0.8),
    ],
}


def select_experts(
    task: str,
    files: list[str | Path] | None = None,
    threshold: float = 0.3,
    max_experts: int = 2,
) -> list[ExpertMatch]:
    """Select appropriate experts based on task and files.

    Args:
        task: Task description.
        files: Optional list of files involved.
        threshold: Minimum score to include expert.
        max_experts: Maximum number of experts to return.

    Returns:
        List of ExpertMatch objects, sorted by score descending.
    """
    from .base import get_expert

    scores: dict[str, tuple[float, list[str]]] = {}
    task_lower = task.lower()

    # Score based on keywords
    for domain, patterns in DOMAIN_KEYWORDS.items():
        domain_score = 0.0
        reasons: list[str] = []

        for pattern, weight in patterns:
            if re.search(pattern, task_lower, re.IGNORECASE):
                domain_score += weight
                match = re.search(pattern, task_lower, re.IGNORECASE)
                if match:
                    reasons.append(f"keyword: '{match.group()}'")

        if domain_score > 0:
            scores[domain] = (domain_score, reasons)

    # Score based on file patterns
    if files:
        for domain, patterns in FILE_PATTERNS.items():
            current_score, current_reasons = scores.get(domain, (0.0, []))

            for file in files:
                file_str = str(file)
                for pattern, weight in patterns:
                    if re.search(pattern, file_str, re.IGNORECASE):
                        current_score += weight
                        current_reasons.append(f"file: '{file_str}'")
                        break  # Only count each file once per domain

            if current_score > 0:
                scores[domain] = (current_score, current_reasons)

    # Normalize scores
    if scores:
        max_score = max(s[0] for s in scores.values())
        if max_score > 0:
            scores = {
                domain: (score / max_score, reasons) for domain, (score, reasons) in scores.items()
            }

    # Build results
    results: list[ExpertMatch] = []
    for domain, (score, reasons) in scores.items():
        if score >= threshold:
            expert = get_expert(domain)
            if expert:
                results.append(
                    ExpertMatch(
                        expert=expert,
                        score=score,
                        reasons=reasons[:5],  # Limit reasons
                    )
                )

    # Sort by score and limit
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:max_experts]


def detect_domain_from_path(path: str | Path) -> str | None:
    """Detect domain from a file path.

    Args:
        path: File path to analyze.

    Returns:
        Domain name or None if not detected.
    """
    path_str = str(path)

    for domain, patterns in FILE_PATTERNS.items():
        for pattern, _ in patterns:
            if re.search(pattern, path_str, re.IGNORECASE):
                return domain

    return None


def get_relevant_experts_for_files(
    files: list[str | Path],
    threshold: float = 0.3,
) -> list[ExpertMatch]:
    """Get experts relevant to a list of files.

    Args:
        files: List of file paths.
        threshold: Minimum score threshold.

    Returns:
        List of relevant ExpertMatch objects.
    """
    # Build a synthetic task from file paths
    task_parts = []
    for f in files[:10]:  # Limit files analyzed
        domain = detect_domain_from_path(f)
        if domain:
            task_parts.append(domain)

    task = " ".join(set(task_parts)) if task_parts else "general"
    return select_experts(task, files=files, threshold=threshold)
