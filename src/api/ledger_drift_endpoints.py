"""
API Endpoints для Ledger Drift Detection

Обнаружение расхождений в ledger через GraphSAGE и Causal Analysis
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ledger.drift_detector import get_drift_detector, LedgerDriftDetector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ledger/drift", tags=["ledger", "drift"])


class DriftDetectionResponse(BaseModel):
    """Ответ на обнаружение расхождений"""
    timestamp: str
    total_drifts: int
    code_drifts: int
    metrics_drifts: int
    doc_drifts: int
    drifts: list[Dict[str, Any]]
    graph: Dict[str, Any]
    status: str


@router.post("/detect", response_model=DriftDetectionResponse)
async def detect_drift():
    """
    Обнаружение расхождений в ledger.
    
    Использует GraphSAGE и Causal Analysis для обнаружения:
    - Code drift (расхождения между кодом и документацией)
    - Metrics drift (расхождения в метриках)
    - Doc drift (устаревшая документация)
    """
    try:
        detector = get_drift_detector()
        result = await detector.detect_drift()
        
        return DriftDetectionResponse(**result)
        
    except Exception as e:
        logger.error(f"Ошибка при обнаружении расхождений: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обнаружения: {str(e)}")


@router.get("/status")
async def drift_detector_status():
    """
    Статус drift detector.
    """
    try:
        detector = get_drift_detector()
        return {
            "initialized": detector._initialized,
            "anomaly_detector_available": detector.anomaly_detector is not None,
            "causal_engine_available": detector.causal_engine is not None,
            "continuity_file": str(detector.continuity_file),
            "file_exists": detector.continuity_file.exists()
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

