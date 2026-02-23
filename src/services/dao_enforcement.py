import logging
import json
from sqlalchemy.orm import Session
from src.database import GovernanceProposal
from src.mesh.yggdrasil_optimizer import get_optimizer, OptimizationConfig

logger = logging.getLogger(__name__)

class DAOEnforcer:
    """
    Applies executed DAO proposals to the live system configuration.
    """
    
    @staticmethod
    def sync_config_with_dao(db: Session):
        """
        Fetches latest executed proposals and updates Optimizer configuration.
        """
        executed_proposals = db.query(GovernanceProposal).filter(
            GovernanceProposal.state == "executed"
        ).order_by(GovernanceProposal.executed_at.desc()).limit(10).all()

        optimizer = get_optimizer()
        current_config = optimizer.config

        for prop in executed_proposals:
            actions = json.loads(prop.actions_json) if prop.actions_json else []
            for action in actions:
                if action.get("type") == "update_config":
                    params = action.get("params", {})
                    key = params.get("key")
                    val = params.get("value")
                    
                    if hasattr(current_config, str(key)):
                        logger.info(f"⚖️ DAO Enforcement: Updating {key} to {val} from proposal {prop.id}")
                        setattr(current_config, str(key), val)

        # Update optimizer with new config
        optimizer.config = current_config
        return True

dao_enforcer = DAOEnforcer()
