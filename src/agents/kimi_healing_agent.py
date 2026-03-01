import logging
from typing import Any, Dict, List

from src.api.maas_playbooks import PlaybookAction

logger = logging.getLogger(__name__)

class KimiHealingAgent:
    """
    LLM-based autonomous agent for mesh self-healing.
    Uses Kimi K2.5 (or compatible LLM) to analyze complex anomalies 
    and generate executable Playbooks.
    """
    def __init__(self, mode="thinking"):
        self.mode = mode
        self.system_prompt = """
        You are Kimi K2.5, an autonomous self-healing agent for the x0tta6bl4 mesh network.
        Your goal is to analyze node metrics and topology, and output ONLY a valid JSON 
        representing a PlaybookAction array to fix the detected issue.
        Do not explain. Only output JSON.
        """

    def _build_action(self, action: str, params: Dict[str, Any]) -> PlaybookAction:
        """
        Build a validated PlaybookAction.

        Keep this mapping in sync with src.api.maas_playbooks.PlaybookAction.
        """
        allowed_actions = {"restart", "upgrade", "update_config", "exec", "ban_peer"}
        if action not in allowed_actions:
            logger.warning(
                "Unsupported playbook action '%s', falling back to 'restart'",
                action,
            )
            action = "restart"
            params = {"reason": "invalid_action_fallback"}
        return PlaybookAction(action=action, params=params)

    def analyze_and_heal(self, anomaly_data: Dict[str, Any], target_node: str) -> List[PlaybookAction]:
        """
        Analyzes anomaly and generates healing actions.
        In a real scenario, this calls the LLM API. Here it simulates the logic based on context.
        """
        logger.info("Kimi agent analyzing anomaly on %s in %s mode", target_node, self.mode)
        
        # Simulate LLM reasoning
        actions = []
        issue_type = anomaly_data.get("type", "unknown")
        
        if issue_type == "high_latency":
            logger.info("Decision: Rerouting traffic due to high latency.")
            actions.append(
                self._build_action(
                    action="update_config",
                    params={"route_preference": "low_latency", "force_reconnect": True},
                )
            )
        elif issue_type == "ddos_suspected":
            logger.info("Decision: Isolating node due to suspected DDoS.")
            actions.append(
                self._build_action(
                    action="ban_peer",
                    params={"reason": "ddos_suspected", "duration_sec": 3600},
                )
            )
        else:
            logger.info("Decision: Restarting node as fallback.")
            actions.append(
                self._build_action(
                    action="restart",
                    params={"reason": "unknown_anomaly"},
                )
            )
            
        return actions

# Global instance for easy import
kimi_agent = KimiHealingAgent()
