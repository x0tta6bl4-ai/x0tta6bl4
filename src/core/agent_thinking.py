"""Shared thinking-technique support for x0tta6bl4 agents.

The goal of this module is deliberately practical: every agent can ask for the
same compact thinking context before it makes a decision, while agents keep
their existing public behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from src.core.enhanced_thinking_techniques import (
    FirstPrinciplesThinking,
    LateralThinking,
    MindMapGenerator,
    ReversePlanner,
    SelfReflection,
    SixThinkingHats,
    ThinkAloudLogger,
)


@dataclass(frozen=True)
class ThinkingTechniqueSpec:
    """A technique agents are expected to know how to use."""

    technique_id: str
    name: str
    category: str
    purpose: str
    useful_for: tuple[str, ...]
    implemented: bool = False


@dataclass(frozen=True)
class AgentThinkingProfile:
    """Role-specific technique selection for an agent."""

    agent_id: str
    role: str
    techniques: tuple[str, ...]
    capabilities: tuple[str, ...] = field(default_factory=tuple)


ALL_THINKING_TECHNIQUES: tuple[ThinkingTechniqueSpec, ...] = (
    ThinkingTechniqueSpec(
        "meta_cognitive_cycle",
        "Four-step meta-cognitive cycle",
        "metacognitive",
        "Plan, monitor, evaluate, and self-correct reasoning.",
        ("all",),
    ),
    ThinkingTechniqueSpec(
        "think_aloud",
        "Think aloud",
        "metacognitive",
        "Record the current reasoning step so gaps are visible.",
        ("all",),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "three_questions_reflection",
        "Three questions reflection",
        "metacognitive",
        "After work, capture what worked, what to improve, and what was learned.",
        ("all",),
    ),
    ThinkingTechniqueSpec(
        "framing",
        "Framing",
        "metacognitive",
        "State the problem, success condition, constraints, and safety boundary.",
        ("all",),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "self_reflection",
        "Self-reflection",
        "metacognitive",
        "Check assumptions, confidence, bias, and alternatives before action.",
        ("all",),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "six_thinking_hats",
        "Six Thinking Hats",
        "creative",
        "Balance facts, risks, benefits, emotions, ideas, and process control.",
        ("architect", "security", "monitoring", "healing", "pricing", "gtm", "marketing"),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "first_principles",
        "First Principles Thinking",
        "creative",
        "Break a problem into fundamentals before rebuilding the solution.",
        ("architect", "development", "healing", "pricing", "maas-dev"),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "lateral_thinking",
        "Lateral Thinking",
        "creative",
        "Generate non-obvious alternatives, reversals, analogies, and provocations.",
        ("architect", "development", "healing", "marketing", "gtm"),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "mind_maps",
        "Mind Maps",
        "creative",
        "Organize related signals, branches, causes, and actions around a center.",
        ("architect", "monitoring", "logging", "researcher", "documentation"),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "reverse_planning",
        "Reverse Planning",
        "planning",
        "Start from the desired end state and work backward to the next action.",
        ("architect", "healing", "development", "ops", "coordinator"),
        implemented=True,
    ),
    ThinkingTechniqueSpec(
        "scamper",
        "SCAMPER",
        "brainstorming",
        "Substitute, combine, adapt, modify, put to another use, eliminate, reverse.",
        ("marketing", "gtm", "development", "product", "pricing"),
    ),
    ThinkingTechniqueSpec(
        "lotus_blossom",
        "Lotus Blossom",
        "brainstorming",
        "Expand a central idea into surrounding themes and concrete options.",
        ("marketing", "gtm", "development", "product", "documentation"),
    ),
    ThinkingTechniqueSpec(
        "mape_k",
        "MAPE-K",
        "systems",
        "Monitor, analyze, plan, execute, and store knowledge from the outcome.",
        ("monitoring", "healing", "ops", "coordinator", "architect"),
    ),
    ThinkingTechniqueSpec(
        "rag",
        "RAG",
        "systems",
        "Retrieve relevant knowledge before generating or deciding.",
        ("documentation", "development", "researcher", "support"),
    ),
    ThinkingTechniqueSpec(
        "graphsage",
        "GraphSAGE reasoning",
        "systems",
        "Use graph-neighborhood signals when topology or anomaly context matters.",
        ("monitoring", "healing", "architect", "fl"),
    ),
    ThinkingTechniqueSpec(
        "causal_analysis",
        "Causal Analysis",
        "systems",
        "Prefer cause chains and evidence over symptom-only fixes.",
        ("monitoring", "logging", "healing", "security"),
    ),
    ThinkingTechniqueSpec(
        "causal_loops_system_dynamics",
        "Causal loops and system dynamics",
        "systems",
        "Look for feedback loops, delayed effects, and reinforcing failure modes.",
        ("architect", "healing", "ops", "coordinator"),
    ),
    ThinkingTechniqueSpec(
        "delphi_consensus",
        "Delphi consensus",
        "governance",
        "Use independent estimates and convergence when decisions need agreement.",
        ("coordinator", "reviewer", "governance", "quality"),
    ),
    ThinkingTechniqueSpec(
        "weighted_decision_matrix",
        "Weighted decision matrix",
        "governance",
        "Score options against explicit weighted criteria before choosing.",
        ("coordinator", "reviewer", "security", "pricing", "maas-dev"),
    ),
    ThinkingTechniqueSpec(
        "quadratic_voting",
        "Quadratic voting",
        "governance",
        "Represent preference intensity when agent decisions go through governance.",
        ("governance", "coordinator", "marketplace"),
    ),
    ThinkingTechniqueSpec(
        "stride_threat_modeling",
        "STRIDE threat modeling",
        "security",
        "Check spoofing, tampering, repudiation, disclosure, denial, and elevation.",
        ("security", "zero-trust", "architect", "maas-dev"),
    ),
    ThinkingTechniqueSpec(
        "zero_trust_review",
        "Zero Trust review",
        "security",
        "Default deny, least privilege, explicit identity, and small blast radius.",
        ("security", "zero-trust", "ops", "maas-dev"),
    ),
    ThinkingTechniqueSpec(
        "chaos_driven_design",
        "Chaos-driven design",
        "resilience",
        "Use failure scenarios to improve recovery behavior before production.",
        ("healing", "ops", "architect", "quality"),
    ),
    ThinkingTechniqueSpec(
        "community_co_design",
        "Community co-design",
        "product",
        "Include operator and user feedback in product or workflow decisions.",
        ("gtm", "marketing", "product", "documentation"),
    ),
)

TECHNIQUE_BY_ID: dict[str, ThinkingTechniqueSpec] = {
    spec.technique_id: spec for spec in ALL_THINKING_TECHNIQUES
}

BASE_TECHNIQUES: tuple[str, ...] = (
    "meta_cognitive_cycle",
    "think_aloud",
    "framing",
    "self_reflection",
    "three_questions_reflection",
)

ROLE_TECHNIQUE_OVERRIDES: dict[str, tuple[str, ...]] = {
    "architect": (
        "six_thinking_hats",
        "first_principles",
        "lateral_thinking",
        "mind_maps",
        "reverse_planning",
        "causal_loops_system_dynamics",
    ),
    "monitor": ("mape_k", "mind_maps", "causal_analysis", "graphsage"),
    "monitoring": ("mape_k", "mind_maps", "causal_analysis", "graphsage"),
    "logging": ("mind_maps", "causal_analysis"),
    "healing": (
        "mape_k",
        "six_thinking_hats",
        "first_principles",
        "lateral_thinking",
        "reverse_planning",
        "causal_analysis",
        "chaos_driven_design",
    ),
    "pricing_optimizer": (
        "six_thinking_hats",
        "first_principles",
        "weighted_decision_matrix",
        "scamper",
    ),
    "pricing": (
        "six_thinking_hats",
        "first_principles",
        "weighted_decision_matrix",
        "scamper",
    ),
    "security": (
        "six_thinking_hats",
        "stride_threat_modeling",
        "zero_trust_review",
        "causal_analysis",
        "weighted_decision_matrix",
    ),
    "zero-trust": (
        "stride_threat_modeling",
        "zero_trust_review",
        "causal_analysis",
        "weighted_decision_matrix",
    ),
    "development": ("first_principles", "lateral_thinking", "reverse_planning", "rag"),
    "maas-dev": (
        "first_principles",
        "weighted_decision_matrix",
        "stride_threat_modeling",
        "zero_trust_review",
    ),
    "documentation": ("mind_maps", "rag", "lotus_blossom", "community_co_design"),
    "marketing": ("six_thinking_hats", "scamper", "lotus_blossom", "framing"),
    "gtm": (
        "six_thinking_hats",
        "scamper",
        "lotus_blossom",
        "community_co_design",
    ),
    "coordinator": (
        "reverse_planning",
        "delphi_consensus",
        "weighted_decision_matrix",
        "causal_loops_system_dynamics",
    ),
    "quality": (
        "weighted_decision_matrix",
        "delphi_consensus",
        "chaos_driven_design",
    ),
    "fl": ("graphsage", "causal_analysis", "weighted_decision_matrix"),
    "marketplace": (
        "quadratic_voting",
        "weighted_decision_matrix",
        "six_thinking_hats",
    ),
}


def _plain(value: Any) -> Any:
    """Convert technique outputs into JSON-like data."""

    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    return value


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def build_agent_thinking_profile(
    agent_id: str,
    role: str,
    capabilities: Iterable[str] = (),
    extra_techniques: Iterable[str] = (),
) -> AgentThinkingProfile:
    """Build the technique profile an agent should keep available."""

    role_key = (role or "generic").strip().lower()
    cap_keys = tuple(str(cap).strip().lower() for cap in capabilities if str(cap).strip())
    selected: list[str] = list(BASE_TECHNIQUES)
    selected.extend(ROLE_TECHNIQUE_OVERRIDES.get(role_key, ()))
    for cap in cap_keys:
        selected.extend(ROLE_TECHNIQUE_OVERRIDES.get(cap, ()))
    selected.extend(extra_techniques)

    known = [tech for tech in _dedupe(selected) if tech in TECHNIQUE_BY_ID]
    return AgentThinkingProfile(
        agent_id=agent_id,
        role=role_key,
        capabilities=cap_keys,
        techniques=tuple(known),
    )


class AgentThinkingCoach:
    """Small facade that applies the shared technique pack for agents."""

    def __init__(
        self,
        agent_id: str,
        role: str,
        capabilities: Iterable[str] = (),
        extra_techniques: Iterable[str] = (),
    ):
        self.profile = build_agent_thinking_profile(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities,
            extra_techniques=extra_techniques,
        )
        self.think_aloud = ThinkAloudLogger()
        self.six_hats = SixThinkingHats()
        self.first_principles = FirstPrinciplesThinking()
        self.lateral = LateralThinking()
        self.reverse_planner = ReversePlanner()
        self.mind_maps = MindMapGenerator()
        self.self_reflection = SelfReflection()

    def list_techniques(self) -> list[dict[str, Any]]:
        """Return the agent's training catalog in stable order."""

        return [
            _plain(TECHNIQUE_BY_ID[technique_id])
            for technique_id in self.profile.techniques
            if technique_id in TECHNIQUE_BY_ID
        ]

    def prompt_guidance(self) -> str:
        """Compact instruction block for prompt-based agents."""

        lines = [
            "Thinking contract:",
            "1. Frame the task, success condition, constraints, and safety boundary.",
            "2. Use the role-specific techniques listed below when they improve the decision.",
            "3. Prefer evidence-backed action over speculative action.",
            "4. After the result, record what worked, what to improve, and what was learned.",
            "Role techniques:",
        ]
        for spec in self.list_techniques():
            lines.append(f"- {spec['name']}: {spec['purpose']}")
        return "\n".join(lines)

    def prepare_task(self, task: Mapping[str, Any] | None) -> dict[str, Any]:
        """Apply useful implemented techniques and return a serializable context."""

        task_data = dict(task or {})
        task_type = str(
            task_data.get("task_type")
            or task_data.get("type")
            or task_data.get("code_type")
            or self.profile.role
            or "task"
        )
        goal = str(
            task_data.get("goal")
            or task_data.get("description")
            or task_data.get("issue")
            or task_data.get("name")
            or task_type
        )

        applied: dict[str, Any] = {}
        techniques = set(self.profile.techniques)

        if "think_aloud" in techniques:
            self.think_aloud.log(
                f"Agent {self.profile.agent_id} is framing {task_type}",
                {"task_type": task_type, "goal": goal},
            )
            applied["think_aloud"] = {
                "latest": self.think_aloud.get_thoughts()[-1],
                "logic_gaps": self.think_aloud.detect_logic_gaps(),
            }

        if "framing" in techniques:
            applied["framing"] = {
                "problem": task_type,
                "goal": goal,
                "constraints": task_data.get("constraints", task_data.get("limits", {})),
                "safety_boundary": task_data.get(
                    "safety_boundary",
                    "Do not expand permissions, execute untrusted code, or hide uncertainty.",
                ),
            }

        if "self_reflection" in techniques:
            applied["self_reflection"] = _plain(self.self_reflection.reflect(task_data))

        if "six_thinking_hats" in techniques:
            applied["six_thinking_hats"] = _plain(self.six_hats.analyze(task_data))

        if "first_principles" in techniques:
            decomposition = self.first_principles.decompose(task_data)
            applied["first_principles"] = {
                "decomposition": _plain(decomposition),
                "rebuilt_solution": _plain(
                    self.first_principles.build_from_scratch(decomposition)
                ),
            }

        if "lateral_thinking" in techniques:
            applied["lateral_thinking"] = _plain(self.lateral.generate(task_data))

        if "reverse_planning" in techniques:
            applied["reverse_planning"] = self.reverse_planner.plan(goal)

        if "mind_maps" in techniques:
            applied["mind_maps"] = self.mind_maps.create(
                {
                    "center": goal,
                    "task": task_type,
                    "inputs": task_data,
                    "techniques": list(self.profile.techniques),
                }
            )

        documented = [
            TECHNIQUE_BY_ID[technique_id]
            for technique_id in self.profile.techniques
            if technique_id in TECHNIQUE_BY_ID
            and not TECHNIQUE_BY_ID[technique_id].implemented
        ]

        return {
            "agent_id": self.profile.agent_id,
            "role": self.profile.role,
            "techniques": list(self.profile.techniques),
            "applied": applied,
            "documented_guidance": [_plain(spec) for spec in documented],
        }

    def status(self) -> dict[str, Any]:
        """Expose the loaded thinking profile without leaking task data."""

        return {
            "profile": _plain(self.profile),
            "technique_count": len(self.profile.techniques),
            "techniques": list(self.profile.techniques),
        }
