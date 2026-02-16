import time

from src.dao.governance import ProposalState, VoteType
from src.dao.incident_workflow import Incident, IncidentSeverity
from src.network.batman.node_manager import (
    NodeManager, create_incident_workflow_for_node_manager)


def test_dead_node_incident_deregisters_node():
    nm = NodeManager(mesh_id="mesh-1", local_node_id="node-controller")
    nm.register_node(
        node_id="node-7",
        mac_address="00:00:00:00:00:07",
        ip_address="10.0.0.7",
        spiffe_id="spiffe://x0tta6bl4.mesh/node/node-7",
    )

    workflow = create_incident_workflow_for_node_manager(nm)
    assert workflow is not None

    # Set voting power to match default cast_vote tokens (1.0) so quorum is met
    workflow.governance.voting_power = {workflow.governance.node_id: 1.0}
    workflow.governance.total_supply = 1.0

    incident = Incident(
        incident_id="inc-node-7-down",
        incident_type="node_down",
        severity=IncidentSeverity.CRITICAL,
        description="Node 7 missed heartbeats",
        detected_at=time.time(),
        metadata={"node_id": "node-7"},
    )

    proposal = workflow.create_proposal_from_incident(incident, duration_seconds=0.1)

    voters = {workflow.governance.node_id: VoteType.YES}
    success = workflow.auto_vote_and_execute(proposal.id, voters)

    assert success is True
    assert proposal.state == ProposalState.EXECUTED
    # Узел должен быть дерегистрирован executor'ом
    assert "node-7" not in nm.nodes
