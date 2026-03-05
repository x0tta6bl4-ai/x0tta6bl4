import logging
from typing import Any, Dict, Optional
from src.vision.processor import VisionProcessor
from src.vision.topology_analyzer import MeshTopologyAnalyzer

logger = logging.getLogger(__name__)

class SelfCorrectionEngine:
    """
    Closes the loop between Vision Analysis and MAPE-K execution.
    Takes visual anomalies and converts them into actionable recovery plans.
    Phase 3: Week 11 Deliverable.
    """

    def __init__(self, processor: Optional[VisionProcessor] = None, analyzer: Optional[MeshTopologyAnalyzer] = None):
        self.processor = processor or VisionProcessor()
        self.analyzer = analyzer or MeshTopologyAnalyzer(self.processor)

    async def debug_bytes(self, image_data: bytes, context_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Visual debugging from image bytes.
        """
        logger.info(f"Starting visual debugging session for image bytes (size: {len(image_data)})")
        
        # Extract topology issues
        topo_result = await self.analyzer.analyze_bytes(image_data)
        
        # Check for other text/UI errors
        raw_vision = await self.processor.process_image(image_data)
        
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

    async def debug_visually(self, image_path: str, context_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main entry point for visual debugging from a file.
        """
        import os
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")
            
        with open(image_path, "rb") as f:
            return await self.debug_bytes(f.read(), context_metrics)

