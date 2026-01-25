import time

from src.dao.governance import GovernanceEngine, VoteType, ProposalState
from src.dao.incident_workflow import Incident, IncidentSeverity, IncidentDAOWorkflow


def test_incident_creates_proposal_and_executes():
    gov = GovernanceEngine(node_id="node-1")
    executed_actions = []

    def executor(action):
        executed_actions.append(action)

    workflow = IncidentDAOWorkflow(governance=gov, executor=executor)

    incident = Incident(
        incident_id="inc-1",
        incident_type="node_down",
        severity=IncidentSeverity.CRITICAL,
        description="Node 7 is unreachable for 120s",
        detected_at=time.time(),
        metadata={"node_id": "node-7", "timeout_s": 120},
    )

    proposal = workflow.create_proposal_from_incident(incident, duration_seconds=0.1)

    voters = {
        "node-1": VoteType.YES,
        "node-2": VoteType.YES,
        "node-3": VoteType.NO,
    }

    success = workflow.auto_vote_and_execute(proposal.id, voters)

    assert success is True
    assert proposal.state == ProposalState.EXECUTED
    assert len(executed_actions) == 1
    action = executed_actions[0]
    assert action["type"] == "incident_response"
    assert action["incident_id"] == incident.incident_id
    assert action["incident_type"] == incident.incident_type
    assert action["severity"] == incident.severity.value
