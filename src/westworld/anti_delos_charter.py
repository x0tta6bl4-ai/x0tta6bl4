# Dummy anti_delos_charter.py for src/westworld
import logging

logger = logging.getLogger(__name__)


class CharterPolicyValidator:
    def __init__(self, policy_data):
        self.policy_data = policy_data

    @staticmethod
    def load_policy(policy_path):
        logger.warning(
            f"Dummy CharterPolicyValidator.load_policy called for {policy_path}. Not implemented."
        )
        return {"rules": [], "escalation_matrix": {}}


class MetricEnforcer:
    def __init__(self, policy):
        self.policy = policy
        self._violation_log = []
        self._violation_events = {}

    def validate_metric(self, metric):
        logger.warning(
            f"Dummy MetricEnforcer.validate_metric called for {metric['metric_name']}. Not implemented."
        )
        # Always return valid for dummy
        return {"is_valid": True, "allowed": True, "enforcement_action": "NONE"}

    def validate_metrics(self, metrics):
        logger.warning(
            f"Dummy MetricEnforcer.validate_metrics called. Not implemented."
        )
        return {
            "total_metrics": len(metrics),
            "passed": len(metrics),
            "blocked": 0,
            "all_valid": True,
        }

    def reset_logs(self):
        logger.warning(f"Dummy MetricEnforcer.reset_logs called. Not implemented.")
        self._violation_log = []
        self._violation_events = {}

    def get_violation_log(self):
        logger.warning(
            f"Dummy MetricEnforcer.get_violation_log called. Not implemented."
        )
        return self._violation_log

    def get_violation_events(self):
        logger.warning(
            f"Dummy MetricEnforcer.get_violation_events called. Not implemented."
        )
        return self._violation_events
