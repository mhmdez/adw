"""Expert system for ADW.

Provides domain-specific expert agents that specialize in particular areas
and improve over time through knowledge accumulation.

Experts:
- FrontendExpert: React, Vue, CSS, accessibility
- BackendExpert: FastAPI, Supabase, REST APIs
- AIExpert: LLM integration, prompts, agents
"""

from .ai import AIExpert
from .backend import BackendExpert
from .base import Expert, ExpertKnowledge, get_expert, list_experts, register_expert
from .frontend import FrontendExpert
from .selector import ExpertMatch, select_experts

__all__ = [
    # Base
    "Expert",
    "ExpertKnowledge",
    "get_expert",
    "list_experts",
    "register_expert",
    # Experts
    "FrontendExpert",
    "BackendExpert",
    "AIExpert",
    # Selection
    "select_experts",
    "ExpertMatch",
]
