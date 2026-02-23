import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from src.database import MeshNode, NodeBinaryAttestation, AuditLog

logger = logging.getLogger(__name__)

class TrustEvaluator:
    """
    Continuous Trust Evaluation Engine.
    Calculates dynamic trust scores (0.0 - 1.0) for mesh nodes.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def calculate_node_trust(self, node_id: str) -> float:
        """
        Multi-factor trust calculation:
        1. PQC Attestation (40%) - Is code genuine?
        2. Stability/Heartbeat (30%) - Is node reliable?
        3. Audit History (30%) - Any suspicious actions?
        """
        score = 1.0
        
        # 1. PQC Attestation Factor
        attestation = self.db.query(NodeBinaryAttestation).filter(
            NodeBinaryAttestation.node_id == node_id
        ).order_by(NodeBinaryAttestation.verified_at.desc()).first()
        
        if not attestation or attestation.status != "verified":
            score -= 0.4 # Massive penalty for unverified code
        
        # 2. Stability Factor (Heartbeats)
        node = self.db.query(MeshNode).filter(MeshNode.id == node_id).first()
        if node and node.last_seen:
            if (datetime.utcnow() - node.last_seen) > timedelta(minutes=5):
                score -= 0.2
            if node.status == "degraded":
                score -= 0.1
        else:
            score -= 0.3 # Unknown node stability

        # 3. Audit/Behavior Factor
        suspicious_actions = self.db.query(AuditLog).filter(
            AuditLog.user_id == node_id, # If node has its own identity
            AuditLog.status_code >= 400
        ).count()
        
        score -= min(0.3, suspicious_actions * 0.05)

        final_score = max(0.0, score)
        logger.debug(f"🛡️ Trust Score for {node_id}: {final_score:.2f}")
        return final_score

    def get_routing_weight(self, node_id: str) -> float:
        """Translates trust score into routing weight for Stigmergy."""
        trust = self.calculate_node_trust(node_id)
        # Low trust = Exponentially lower weight
        return trust ** 2
