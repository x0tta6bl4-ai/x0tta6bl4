import asyncio
import logging
from typing import Any, Dict, List
from src.vision.processor import VisionProcessor
from src.vision.topology_analyzer import MeshTopologyAnalyzer

logger = logging.getLogger(__name__)

class SelfCorrectionEngine:
    """
    Closes the loop between Vision Analysis and MAPE-K execution.
    Takes visual anomalies and converts them into actionable recovery plans.
    Phase 3: Week 11 Deliverable.
    """

    def __init__(self, processor: VisionProcessor = None, analyzer: MeshTopologyAnalyzer = None):
        self.processor = processor or VisionProcessor()
        self.analyzer = analyzer or MeshTopologyAnalyzer(self.processor)

    async def debug_visually(self, image_path: str, context_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main entry point for visual debugging.
        1. Analyzes image.
        2. Correlates with metrics (if provided).
        3. Proposes an action plan.
        """
        logger.info(f"Starting visual debugging session for {image_path}")
        
        # Extract topology issues
        topo_result = await self.analyzer.analyze(image_path)
        
        # Check for other text/UI errors
        raw_vision = await self.processor.process_image(image_path)
        
        plan = []
        
        # Strategy mapping based on visual cues
        if topo_result.get("isolated_nodes"):
            plan.append({
                "action": "re_enroll_node",
                "targets": topo_result["isolated_nodes"],
                "reason": "Node appeared visually disconnected in dashboard"
            })
            
        for text in raw_vision.get("text_extracted", []):
            if "Connection Refused" in text:
                plan.append({
                    "action": "restart_proxy",
                    "reason": "Detected 'Connection Refused' error modal in UI"
                })
                
        return {
            "status": "analysis_complete",
            "findings": {
                "topology_bottlenecks": topo_result.get("bottlenecks", []),
                "visual_anomalies": raw_vision.get("anomalies", [])
            },
            "proposed_plan": plan
        }
