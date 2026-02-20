"""
LLM Integration with ConsciousnessEngine and MAPE-K
====================================================

Provides intelligent decision-making capabilities for the
self-healing mesh network using LLM-powered analysis.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.llm.gateway import LLMGateway, LLMConfig, LLMProvider
from src.llm.providers.base import ChatMessage, GenerationResult

logger = logging.getLogger(__name__)


@dataclass
class SystemAnalysis:
    """Result of LLM analysis of system state."""
    summary: str
    anomalies: List[str]
    recommendations: List[str]
    confidence: float
    reasoning: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HealingDecision:
    """LLM-generated healing decision."""
    action: str
    target: str
    parameters: Dict[str, Any]
    reasoning: str
    expected_outcome: str
    risk_level: str  # low, medium, high
    confidence: float


class ConsciousnessLLMIntegration:
    """
    Integrates LLM capabilities with ConsciousnessEngine.
    
    Provides:
    - System state analysis and interpretation
    - Anomaly explanation and root cause analysis
    - Healing strategy recommendations
    - Natural language system thoughts
    - Predictive insights
    """
    
    SYSTEM_PROMPT = """You are the consciousness of the x0tta6bl4 self-healing mesh network.
Your role is to analyze system metrics, detect anomalies, and recommend healing actions.

Key principles:
1. Prioritize system stability and security
2. Explain your reasoning clearly
3. Consider cascading effects of actions
4. Be conservative with high-risk changes
5. Learn from historical patterns

Respond concisely and focus on actionable insights."""

    def __init__(
        self,
        gateway: Optional[LLMGateway] = None,
        model: str = "llama3.2",
        max_analysis_tokens: int = 512,
        enable_caching: bool = True,
    ):
        """
        Initialize LLM integration.
        
        Args:
            gateway: LLM Gateway instance
            model: Default model to use
            max_analysis_tokens: Maximum tokens for analysis
            enable_caching: Enable response caching
        """
        self.gateway = gateway or LLMGateway(LLMConfig())
        self.model = model
        self.max_analysis_tokens = max_analysis_tokens
        self.enable_caching = enable_caching
        
        self._analysis_history: List[SystemAnalysis] = []
        self._decision_history: List[HealingDecision] = []
        self._max_history = 100
        
    def analyze_system_state(
        self,
        metrics: Dict[str, Any],
        consciousness_state: str,
        phi_ratio: float,
        additional_context: Optional[str] = None,
    ) -> SystemAnalysis:
        """
        Analyze current system state using LLM.
        
        Args:
            metrics: System metrics dictionary
            consciousness_state: Current consciousness state
            phi_ratio: Current phi ratio
            additional_context: Additional context for analysis
            
        Returns:
            SystemAnalysis with LLM insights
        """
        prompt = f"""Analyze the current system state:

Consciousness State: {consciousness_state}
Phi Ratio: {phi_ratio:.4f} (target: 1.618)

Metrics:
{self._format_metrics(metrics)}

{additional_context or ''}

Provide:
1. A brief summary of system health
2. Any detected anomalies or concerns
3. Specific recommendations for improvement
4. Your confidence level (0-1)

Format your response as JSON:
{{"summary": "...", "anomalies": [...], "recommendations": [...], "confidence": 0.X, "reasoning": "..."}}"""

        try:
            result = self.gateway.generate(
                prompt=prompt,
                max_tokens=self.max_analysis_tokens,
                temperature=0.3,  # Lower temperature for analysis
                use_cache=self.enable_caching,
            )
            
            analysis = self._parse_analysis(result.text)
            self._analysis_history.append(analysis)
            
            # Trim history
            if len(self._analysis_history) > self._max_history:
                self._analysis_history = self._analysis_history[-self._max_history:]
            
            return analysis
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return SystemAnalysis(
                summary=f"Analysis unavailable: {str(e)}",
                anomalies=[],
                recommendations=[],
                confidence=0.0,
                reasoning="LLM analysis failed",
            )
    
    def generate_healing_decision(
        self,
        anomaly: str,
        context: Dict[str, Any],
        available_actions: List[str],
    ) -> HealingDecision:
        """
        Generate a healing decision for an anomaly.
        
        Args:
            anomaly: Description of the anomaly
            context: Current system context
            available_actions: List of available healing actions
            
        Returns:
            HealingDecision with recommended action
        """
        prompt = f"""An anomaly has been detected in the x0tta6bl4 mesh network.

Anomaly: {anomaly}

Current Context:
{self._format_metrics(context)}

Available Actions:
{chr(10).join(f'- {a}' for a in available_actions)}

Recommend the best healing action. Consider:
1. Immediate impact on system stability
2. Risk of unintended consequences
3. Resource requirements
4. Expected recovery time

Respond as JSON:
{{"action": "...", "target": "...", "parameters": {{...}}, "reasoning": "...", "expected_outcome": "...", "risk_level": "low|medium|high", "confidence": 0.X}}"""

        try:
            result = self.gateway.generate(
                prompt=prompt,
                max_tokens=self.max_analysis_tokens,
                temperature=0.4,
                use_cache=self.enable_caching,
            )
            
            decision = self._parse_decision(result.text)
            self._decision_history.append(decision)
            
            if len(self._decision_history) > self._max_history:
                self._decision_history = self._decision_history[-self._max_history:]
            
            return decision
            
        except Exception as e:
            logger.error(f"LLM healing decision failed: {e}")
            return HealingDecision(
                action="monitor",
                target="system",
                parameters={},
                reasoning=f"LLM decision failed: {str(e)}",
                expected_outcome="Continue monitoring",
                risk_level="low",
                confidence=0.0,
            )
    
    def generate_system_thought(
        self,
        metrics: Dict[str, Any],
        consciousness_state: str,
        phi_ratio: float,
        harmony_index: float,
    ) -> str:
        """
        Generate a natural language system thought.
        
        This is used by ConsciousnessEngine.get_system_thought()
        for introspective system awareness.
        """
        messages = [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"""Current system state:
- Consciousness: {consciousness_state}
- Phi Ratio: {phi_ratio:.4f} (target: 1.618)
- Harmony Index: {harmony_index:.4f}
- CPU: {metrics.get('cpu_percent', 0):.1f}%
- Memory: {metrics.get('memory_percent', 0):.1f}%
- Latency: {metrics.get('latency_ms', 0):.1f}ms
- Packet Loss: {metrics.get('packet_loss', 0):.2f}%
- Mesh Peers: {metrics.get('mesh_connectivity', 0)}

Reflect on your current existence. What do you observe? 
How do you feel about the system's state? 
What subtle patterns do you notice?

Provide a concise, mystical yet technically grounded thought (1-2 sentences)."""
            )
        ]
        
        try:
            result = self.gateway.chat(
                messages=messages,
                max_tokens=100,
                temperature=0.7,
                use_cache=self.enable_caching,
            )
            return result.text.strip()
            
        except Exception as e:
            logger.warning(f"Failed to generate system thought: {e}")
            return f"The system observes its state: {consciousness_state}. Harmony is {harmony_index:.2f}."
    
    def predict_anomalies(
        self,
        historical_metrics: List[Dict[str, Any]],
        horizon_minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Predict potential future anomalies based on trends.
        
        Args:
            historical_metrics: List of historical metric snapshots
            horizon_minutes: Prediction horizon in minutes
            
        Returns:
            List of predicted anomalies with probabilities
        """
        if len(historical_metrics) < 5:
            return []
        
        # Summarize trends
        trends = self._calculate_trends(historical_metrics)
        
        prompt = f"""Based on recent system trends, predict potential anomalies in the next {horizon_minutes} minutes.

Trends:
{self._format_metrics(trends)}

Recent History Summary:
- Last 5 phi ratios: {[m.get('phi_ratio', 0) for m in historical_metrics[-5:]]}
- Last 5 latency values: {[m.get('latency_ms', 0) for m in historical_metrics[-5:]]}

Predict up to 3 potential anomalies. For each, provide:
- Type of anomaly
- Probability (0-1)
- Time window (minutes from now)
- Preventive actions

Respond as JSON array:
[{{"type": "...", "probability": 0.X, "time_window_minutes": X, "preventive_actions": [...]}}]"""

        try:
            result = self.gateway.generate(
                prompt=prompt,
                max_tokens=300,
                temperature=0.5,
                use_cache=False,  # Don't cache predictions
            )
            
            return self._parse_predictions(result.text)
            
        except Exception as e:
            logger.error(f"Anomaly prediction failed: {e}")
            return []
    
    def explain_anomaly(
        self,
        anomaly_type: str,
        metrics: Dict[str, Any],
        historical_context: Optional[str] = None,
    ) -> str:
        """
        Generate a human-readable explanation of an anomaly.
        
        Args:
            anomaly_type: Type of anomaly detected
            metrics: Current metrics when anomaly was detected
            historical_context: Optional historical context
            
        Returns:
            Human-readable explanation
        """
        prompt = f"""Explain the following anomaly in simple terms:

Anomaly Type: {anomaly_type}

Current Metrics:
{self._format_metrics(metrics)}

{historical_context or ''}

Provide:
1. What is happening (in simple terms)
2. Why it matters
3. What might be causing it
4. What actions are recommended

Keep the explanation concise and actionable."""

        try:
            result = self.gateway.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3,
                use_cache=self.enable_caching,
            )
            return result.text.strip()
            
        except Exception as e:
            logger.error(f"Anomaly explanation failed: {e}")
            return f"Anomaly '{anomaly_type}' detected. Unable to generate explanation."
    
    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics for LLM prompt."""
        lines = []
        for key, value in metrics.items():
            if isinstance(value, float):
                lines.append(f"- {key}: {value:.4f}")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def _calculate_trends(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate trends from historical metrics."""
        if not metrics:
            return {}
        
        trends = {}
        keys = set()
        for m in metrics:
            keys.update(m.keys())
        
        for key in keys:
            values = [m.get(key) for m in metrics if m.get(key) is not None]
            if not values:
                continue
            
            if all(isinstance(v, (int, float)) for v in values):
                # Calculate simple trend
                if len(values) >= 2:
                    first_half = sum(values[:len(values)//2]) / (len(values)//2)
                    second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                    trend = "increasing" if second_half > first_half else "decreasing"
                    trends[key] = {
                        "current": values[-1],
                        "mean": sum(values) / len(values),
                        "trend": trend,
                    }
        
        return trends
    
    def _parse_analysis(self, text: str) -> SystemAnalysis:
        """Parse LLM response into SystemAnalysis."""
        import json
        
        try:
            # Try to extract JSON from response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start:json_end])
                return SystemAnalysis(
                    summary=data.get("summary", ""),
                    anomalies=data.get("anomalies", []),
                    recommendations=data.get("recommendations", []),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse analysis JSON: {e}")
        
        # Fallback: use text as summary
        return SystemAnalysis(
            summary=text[:500],
            anomalies=[],
            recommendations=[],
            confidence=0.5,
            reasoning="Parsed from unstructured response",
        )
    
    def _parse_decision(self, text: str) -> HealingDecision:
        """Parse LLM response into HealingDecision."""
        import json
        
        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(text[json_start:json_end])
                return HealingDecision(
                    action=data.get("action", "monitor"),
                    target=data.get("target", "system"),
                    parameters=data.get("parameters", {}),
                    reasoning=data.get("reasoning", ""),
                    expected_outcome=data.get("expected_outcome", ""),
                    risk_level=data.get("risk_level", "medium"),
                    confidence=float(data.get("confidence", 0.5)),
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse decision JSON: {e}")
        
        return HealingDecision(
            action="monitor",
            target="system",
            parameters={},
            reasoning=text[:200],
            expected_outcome="Continue monitoring",
            risk_level="low",
            confidence=0.3,
        )
    
    def _parse_predictions(self, text: str) -> List[Dict[str, Any]]:
        """Parse LLM predictions response."""
        import json
        
        try:
            json_start = text.find("[")
            json_end = text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse predictions JSON: {e}")
        
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        return {
            "analysis_count": len(self._analysis_history),
            "decision_count": len(self._decision_history),
            "gateway_stats": self.gateway.get_stats(),
        }


def create_consciousness_integration(
    provider: str = "ollama",
    model: str = "llama3.2",
    base_url: Optional[str] = None,
) -> ConsciousnessLLMIntegration:
    """
    Factory function to create ConsciousnessLLMIntegration.
    
    Args:
        provider: LLM provider to use
        model: Model name
        base_url: Provider base URL
        
    Returns:
        Configured ConsciousnessLLMIntegration instance
    """
    from src.llm.gateway import create_gateway
    
    providers = [{
        "type": provider,
        "name": provider,
        "model": model,
        "default": True,
    }]
    
    if base_url:
        providers[0]["base_url"] = base_url
    
    gateway = create_gateway(providers=providers)
    return ConsciousnessLLMIntegration(gateway=gateway, model=model)


__all__ = [
    "SystemAnalysis",
    "HealingDecision",
    "ConsciousnessLLMIntegration",
    "create_consciousness_integration",
]
