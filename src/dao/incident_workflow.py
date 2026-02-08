import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Callable, Optional

from src.dao.governance import GovernanceEngine, VoteType, Proposal


class IncidentSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Incident:
    incident_id: str
    incident_type: str
    severity: IncidentSeverity
    description: str
    detected_at: float
    metadata: Dict


class IncidentDAOWorkflow:
    """Maps incidents to DAO proposals and executes approved actions."""

    def __init__(self, governance: GovernanceEngine, executor: Optional[Callable[[Dict], None]] = None):
        self.governance = governance
        self.executor = executor or (lambda action: None)

    def create_proposal_from_incident(self, incident: Incident, duration_seconds: float = 60.0) -> Proposal:
        title = f"Incident: {incident.incident_type} ({incident.severity.value})"
        description = f"Auto-generated from incident {incident.incident_id}: {incident.description}"
        action = {
            "type": "incident_response",
            "incident_id": incident.incident_id,
            "incident_type": incident.incident_type,
            "severity": incident.severity.value,
            "metadata": incident.metadata,
        }
        proposal = self.governance.create_proposal(
            title=title,
            description=description,
            duration_seconds=duration_seconds,
            actions=[action],
        )
        return proposal

    def auto_vote_and_execute(self, proposal_id: str, voters: Dict[str, VoteType]) -> bool:
        for node_id, vote in voters.items():
            tokens = self.governance.voting_power.get(node_id, 100.0)
            self.governance.cast_vote(proposal_id, node_id, vote, tokens=tokens)

        # Для тестового/симуляционного режима не полагаемся на реальные таймеры.
        # Сначала запускаем обычную проверку, затем при необходимости явно подводим итоги.
        self.governance.check_proposals()

        proposal = self.governance.proposals[proposal_id]
        if proposal.state.name.lower() == "active":
            # Время могло ещё не истечь — форсируем подсчёт голосов.
            from src.dao.governance import Proposal  # type: ignore
            if isinstance(proposal, Proposal):
                # Используем внутренний метод tally для текущего объекта.
                self.governance._tally_votes(proposal)  # noqa: SLF001 (осознанный вызов приватного метода в тестовом воркфлоу)

        if proposal.state.name.lower() != "passed":
            return False

        for action in proposal.actions:
            self.executor(action)

        self.governance.execute_proposal(proposal_id)
        return True
