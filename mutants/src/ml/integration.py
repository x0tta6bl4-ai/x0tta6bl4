"""
ML Integration with MAPE-K

Integrates all ML modules (RAG, LoRA, Anomaly, Decision, MLOps) with the MAPE-K autonomic loop.
"""

import asyncio
from typing import Dict, List, Optional, Any
import numpy as np
from datetime import datetime

from src.ml.rag import RAGAnalyzer
from src.ml.lora import LoRAAdapter, LoRAConfig
from src.ml.anomaly import AnomalyDetectionSystem, AnomalyConfig
from src.ml.decision import DecisionEngine, Policy, PolicyPriority
from src.ml.mlops import MLOpsManager


class MLEnhancedMAPEK:
    """MAPE-K autonomic loop enhanced with ML capabilities"""
    
    def __init__(self):
        """Initialize ML-enhanced MAPE-K"""
        # RAG for knowledge augmentation
        self.rag_analyzer = RAGAnalyzer()
        
        # LoRA for adaptive learning
        self.lora_adapter = LoRAAdapter(LoRAConfig(rank=8))
        
        # Anomaly detection
        self.anomaly_system = AnomalyDetectionSystem(AnomalyConfig(threshold=0.7))
        
        # Smart decision making
        self.decision_engine = DecisionEngine()
        
        # MLOps management
        self.mlops_manager = MLOpsManager()
        
        # Integration history
        self.augmentation_history: List[Dict[str, Any]] = []
        self.learning_cycles: List[Dict[str, Any]] = []
    
    # ========== MONITOR PHASE ==========
    
    async def monitor_with_ml(
        self,
        metrics: Dict[str, float],
        component: str = "system"
    ) -> Dict[str, Any]:
        """
        Enhanced monitoring with ML anomaly detection
        
        Args:
            metrics: System metrics
            component: Component being monitored
            
        Returns:
            Monitoring results with anomalies
        """
        # Register component if needed
        if component not in self.anomaly_system.detectors:
            self.anomaly_system.register_component(component, input_dim=32)
        
        # Convert metrics to vector
        metric_vector = np.array(list(metrics.values())[:32]).astype(np.float32)
        
        # Detect anomalies
        anomaly, confidence = await self.anomaly_system.check_component(
            component,
            metric_vector,
            context={"timestamp": datetime.now().isoformat()}
        )
        
        result = {
            "component": component,
            "metrics": metrics,
            "anomaly_detected": anomaly is not None,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        
        if anomaly:
            result["anomaly_details"] = {
                "severity": anomaly.severity,
                "description": anomaly.description,
                "metric": anomaly.metric
            }
        
        return result
    
    # ========== ANALYZE PHASE ==========
    
    async def analyze_with_rag(
        self,
        monitoring_data: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """
        Enhanced analysis with RAG knowledge augmentation
        
        Args:
            monitoring_data: Data from monitoring phase
            query: Analysis query
            
        Returns:
            Analysis results with augmented context
        """
        # Retrieve relevant context from knowledge base
        context = await self.rag_analyzer.retrieve_context(
            query,
            k=3,
            threshold=0.6
        )
        
        analysis = {
            "query": query,
            "monitoring_data": monitoring_data,
            "knowledge_context": context,
            "confidence": len(context) / 3.0 if context else 0.0,  # Confidence based on context
            "timestamp": datetime.now().isoformat()
        }
        
        # Track augmentation
        self.augmentation_history.append({
            "phase": "analyze",
            "query": query,
            "contexts_retrieved": len(context),
            "timestamp": datetime.now().isoformat()
        })
        
        return analysis
    
    # ========== PLAN PHASE ==========
    
    async def plan_with_intelligent_decisions(
        self,
        analysis: Dict[str, Any],
        available_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Enhanced planning with intelligent decision making
        
        Args:
            analysis: Analysis results
            available_actions: Available action policies
            
        Returns:
            Planning decision with reasoning
        """
        # Make intelligent decision
        context = {
            "analysis": analysis.get("query"),
            "component_type": "autonomous_system",
            "confidence": analysis.get("confidence", 0.5)
        }
        
        decision = await self.decision_engine.decide_on_action(
            available_actions,
            context
        )
        
        plan = {
            "decision": decision,
            "selected_action": decision.get("selected_policy"),
            "confidence": decision.get("confidence"),
            "reasoning": decision.get("reasoning"),
            "alternatives": decision.get("ranked_candidates", []),
            "timestamp": datetime.now().isoformat()
        }
        
        return plan
    
    # ========== EXECUTE PHASE ==========
    
    async def execute_with_lora_adaptation(
        self,
        plan: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enhanced execution with LoRA-based adaptation
        
        Args:
            plan: Execution plan
            execution_context: Context for execution
            
        Returns:
            Execution results
        """
        component = plan.get("selected_action", "unknown")
        
        # Prepare input for LoRA adaptation
        context_vector = np.array([
            execution_context.get("metric", 0.5) if execution_context else 0.5
        ] * 64).astype(np.float32)
        
        base_output = np.array([0.5] * 32).astype(np.float32)
        
        # Add LoRA layer if needed
        if component not in self.lora_adapter.lora_layers:
            self.lora_adapter.add_layer(component, input_dim=64, output_dim=32)
        
        # Adapt output using LoRA
        adapted_output = await self.lora_adapter.adapt_output(
            component,
            context_vector,
            base_output
        )
        
        result = {
            "action": component,
            "execution_success": True,
            "base_output": base_output.tolist()[:5],  # Truncate for display
            "adapted_output": adapted_output.tolist()[:5],
            "adaptation_applied": True,
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    
    # ========== KNOWLEDGE UPDATE PHASE ==========
    
    async def update_knowledge_with_outcomes(
        self,
        plan_decision: str,
        execution_result: Dict[str, Any],
        success: bool,
        reward: float
    ) -> Dict[str, Any]:
        """
        Update knowledge with execution outcomes and learn from experience
        
        Args:
            plan_decision: Decision that was made
            execution_result: Execution results
            success: Whether execution succeeded
            reward: Reward signal
            
        Returns:
            Learning update summary
        """
        # Record outcome for decision learning
        await self.decision_engine.evaluate_decision(
            policy_id=plan_decision,
            success=success,
            reward=reward,
            duration_ms=50.0,
            context=execution_result
        )
        
        # Trigger LoRA fine-tuning on success
        if success and reward > 0.7:
            trajectories = [
                {"reward": reward, "data": np.random.randn(128)}
            ]
            finetune_result = await self.lora_adapter.fine_tune_on_trajectory(
                plan_decision,
                trajectories
            )
        else:
            finetune_result = None
        
        # Continuous learning from decision history
        learning_insights = await self.decision_engine.continuous_learning(window_size=50)
        
        update = {
            "decision_evaluated": plan_decision,
            "success": success,
            "reward": reward,
            "finetune_applied": finetune_result is not None,
            "learning_insights": learning_insights.get("insights", []),
            "timestamp": datetime.now().isoformat()
        }
        
        self.learning_cycles.append(update)
        
        return update
    
    # ========== COMPLETE AUTONOMIC LOOP ==========
    
    async def autonomic_loop_iteration(
        self,
        monitoring_data: Dict[str, float],
        available_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Complete ML-enhanced autonomic loop iteration
        
        Args:
            monitoring_data: System metrics
            available_actions: Available action policies
            
        Returns:
            Complete loop iteration results
        """
        # M - Monitor
        monitor_result = await self.monitor_with_ml(monitoring_data)
        
        # A - Analyze
        analyze_result = await self.analyze_with_rag(
            monitor_result,
            "system_health"
        )
        
        # P - Plan
        plan_result = await self.plan_with_intelligent_decisions(
            analyze_result,
            available_actions
        )
        
        # E - Execute
        execute_result = await self.execute_with_lora_adaptation(
            plan_result,
            execution_context=monitoring_data
        )
        
        # K - Update Knowledge
        success = monitor_result.get("anomaly_detected") is False
        reward = 1.0 if success else 0.3
        
        knowledge_result = await self.update_knowledge_with_outcomes(
            plan_result.get("selected_action", "unknown"),
            execute_result,
            success,
            reward
        )
        
        return {
            "monitoring": monitor_result,
            "analysis": analyze_result,
            "planning": plan_result,
            "execution": execute_result,
            "knowledge_update": knowledge_result,
            "overall_success": success,
            "timestamp": datetime.now().isoformat()
        }
    
    # ========== SYSTEM STATISTICS ==========
    
    def get_ml_statistics(self) -> Dict[str, Any]:
        """Get ML system statistics"""
        return {
            "rag": self.rag_analyzer.get_stats(),
            "lora": self.lora_adapter.get_lora_weights("system") is not None,
            "anomaly_system": self.anomaly_system.get_stats(),
            "decision_engine": self.decision_engine.get_decision_stats(),
            "mlops": self.mlops_manager.get_system_stats(),
            "augmentation_cycles": len(self.augmentation_history),
            "learning_cycles": len(self.learning_cycles),
            "timestamp": datetime.now().isoformat()
        }


# Example usage
async def example_ml_enhanced_mapek():
    """Example ML-enhanced MAPE-K loop"""
    system = MLEnhancedMAPEK()
    
    # Simulate 3 autonomic loops
    for i in range(3):
        monitoring_data = {
            "cpu_usage": 0.5 + np.random.random() * 0.1,
            "memory_usage": 0.6 + np.random.random() * 0.05,
            "request_latency_ms": 45 + np.random.random() * 10
        }
        
        available_actions = ["scale_up", "optimize_config", "restart_component"]
        
        result = await system.autonomic_loop_iteration(
            monitoring_data,
            available_actions
        )
        
        print(f"Loop {i+1}: Success={result['overall_success']}")
    
    # Get statistics
    stats = system.get_ml_statistics()
    print(f"ML Stats: {stats}")
    
    return system


if __name__ == "__main__":
    print("ML-Enhanced MAPE-K integration module")
