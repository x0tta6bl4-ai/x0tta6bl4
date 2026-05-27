import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageStat, UnidentifiedImageError

logger = logging.getLogger(__name__)

class VisionProcessor:
    """
    Core Vision Processor for analyzing UI screenshots and system state visualizations.
    Phase 3: Week 9 Deliverable.
    """

    def __init__(self, api_key: Optional[str] = None, *, require_external_provider: bool = False):
        self.api_key = api_key or os.getenv("VISION_API_KEY")
        self.require_external_provider = require_external_provider
        if self.require_external_provider and not self.api_key:
            logger.warning("VisionProcessor initialized without external provider credentials.")

    async def process_image(self, image_data: bytes, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process image bytes to extract structure, text, and visual anomalies.
        """
        if self.require_external_provider and not self.api_key:
            raise RuntimeError("Vision external provider credentials are required for this processor.")
        context = context or {}
        try:
            import io
            with Image.open(io.BytesIO(image_data)) as image:
                image.load()
                logger.info("Processing image locally: %s %s", image.format, image.size)
                return self._build_local_analysis(image, context)
        except UnidentifiedImageError as e:
            logger.error("Vision processing failed: invalid image bytes")
            raise ValueError("Invalid image bytes; PIL could not identify the image.") from e
        except Exception as e:
            logger.error(f"Vision processing failed: {e}")
            raise

    async def _call_vision_api(self, image_data: bytes, context: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibility wrapper for older callers expecting this private hook."""
        return await self.process_image(image_data, context)

    def _build_local_analysis(self, image: Image.Image, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return deterministic local image facts without claiming AI object detection."""
        width, height = image.size
        grayscale = image.convert("L")
        stats = ImageStat.Stat(grayscale)
        mean_luma = float(stats.mean[0]) if stats.mean else 0.0
        contrast = float(stats.stddev[0]) if stats.stddev else 0.0

        objects = self._context_objects(context)
        links = list(context.get("links", []))
        anomalies = self._detect_basic_anomalies(width, height, mean_luma, contrast)

        image_metadata = {
            "format": image.format,
            "mode": image.mode,
            "width": width,
            "height": height,
            "mean_luma": round(mean_luma, 3),
            "contrast": round(contrast, 3),
        }

        findings = {
            "analysis_mode": "local_pillow",
            "external_provider_configured": bool(self.api_key),
            "image_metadata": image_metadata,
            "topology_source": "context" if objects or links else "not_detected",
        }
        if context.get("findings"):
            findings["context"] = context["findings"]

        return {
            "status": "success",
            "provider": "local_pillow",
            "image": image_metadata,
            "objects_detected": objects,
            "links": links,
            "findings": findings,
            "anomalies": anomalies,
            "text_extracted": list(context.get("text_extracted", [])),
            "proposed_plan": list(context.get("proposed_plan", [])),
        }

    def _context_objects(self, context: Dict[str, Any]) -> list[Dict[str, Any]]:
        objects = context.get("objects_detected")
        if isinstance(objects, list):
            return list(objects)

        nodes = context.get("nodes")
        if isinstance(nodes, list):
            normalized = []
            for index, node in enumerate(nodes):
                if isinstance(node, dict):
                    normalized.append({"id": node.get("id", f"node-{index + 1}"), **node})
                else:
                    normalized.append({"id": str(node)})
            return normalized

        return []

    def _detect_basic_anomalies(
        self,
        width: int,
        height: int,
        mean_luma: float,
        contrast: float,
    ) -> list[Dict[str, Any]]:
        anomalies = []
        if width <= 0 or height <= 0:
            anomalies.append({"type": "invalid_dimensions", "severity": "error"})
            return anomalies

        aspect_ratio = max(width / height, height / width)
        if aspect_ratio >= 4.0:
            anomalies.append({
                "type": "extreme_aspect_ratio",
                "severity": "warning",
                "value": round(aspect_ratio, 3),
            })

        if contrast < 2.0:
            anomalies.append({
                "type": "low_contrast_or_blank",
                "severity": "warning",
                "contrast": round(contrast, 3),
            })

        if mean_luma < 5.0:
            anomalies.append({"type": "mostly_dark", "severity": "info"})
        elif mean_luma > 250.0:
            anomalies.append({"type": "mostly_bright", "severity": "info"})

        return anomalies


    async def extract_text(self, image_path: str) -> str:
        """
        OCR processing (Fallback to tesseract if local).
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found at {image_path}")

        try:
            import pytesseract
        except ImportError:
            logger.info("pytesseract is not installed; returning empty OCR text.")
            return ""

        with Image.open(path) as image:
            return pytesseract.image_to_string(image).strip()
