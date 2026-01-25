"""
API Endpoints for V3.0 Components
==================================

REST API endpoints для управления и мониторинга компонентов v3.0.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Импорты компонентов v3.0
try:
    from src.self_healing.mape_k_v3_integration import MAPEKV3Integration
    from src.testing.digital_twins import ChaosScenario
    from src.storage.immutable_audit_trail import ImmutableAuditTrail
    V3_AVAILABLE = True
except ImportError:
    V3_AVAILABLE = False
    logger.warning("V3.0 components not available")


# Pydantic модели для запросов/ответов
class GraphSAGEAnalysisRequest(BaseModel):
    node_features: Dict[str, Dict[str, float]]
    node_topology: Optional[Dict[str, List[str]]] = None


class StegoMeshEncodeRequest(BaseModel):
    payload: str  # Base64 encoded
    protocol_mimic: str = "http"  # http, icmp, dns


class ChaosTestRequest(BaseModel):
    scenario: str  # node_down, link_failure, ddos, byzantine, resource_exhaustion
    intensity: float = 0.3
    duration: float = 60.0


class AuditRecordRequest(BaseModel):
    record_type: str
    data: Dict[str, Any]
    auditor: Optional[str] = None


# Создаём router
router = APIRouter(prefix="/api/v3", tags=["v3.0"])

# Глобальный экземпляр интеграции (в production должен быть через dependency injection)
_v3_integration: Optional[MAPEKV3Integration] = None
_audit_trail: Optional[ImmutableAuditTrail] = None


def get_v3_integration() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=True,
            enable_digital_twins=True
        )
    return _v3_integration


def get_audit_trail() -> ImmutableAuditTrail:
    """Dependency для получения Audit Trail"""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = ImmutableAuditTrail()
    return _audit_trail


@router.get("/status")
async def get_v3_status(
    integration: MAPEKV3Integration = Depends(get_v3_integration)
) -> Dict[str, Any]:
    """
    Получение статуса компонентов v3.0.
    
    Returns:
        Статус всех компонентов v3.0
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="V3.0 components not available")
    
    status = integration.get_status()
    return {
        "status": "operational",
        "components": status,
        "version": "3.0.0"
    }


@router.post("/graphsage/analyze")
async def analyze_with_graphsage(
    request: GraphSAGEAnalysisRequest,
    integration: MAPEKV3Integration = Depends(get_v3_integration)
) -> Dict[str, Any]:
    """
    Анализ сети с помощью GraphSAGE.
    
    Args:
        request: Запрос с признаками узлов и топологией
        
    Returns:
        Результат анализа GraphSAGE
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="GraphSAGE not available")
    
    try:
        analysis = await integration.analyze_with_graphsage(
            node_features=request.node_features,
            node_topology=request.node_topology
        )
        
        if analysis is None:
            raise HTTPException(status_code=503, detail="GraphSAGE analysis failed")
        
        return {
            "failure_type": analysis.failure_type.value,
            "confidence": analysis.confidence,
            "recommended_action": analysis.recommended_action,
            "severity": analysis.severity,
            "affected_nodes": analysis.affected_nodes
        }
    except Exception as e:
        logger.error(f"GraphSAGE analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stego/encode")
async def encode_stego_packet(
    request: StegoMeshEncodeRequest,
    integration: MAPEKV3Integration = Depends(get_v3_integration)
) -> Dict[str, Any]:
    """
    Кодирование пакета через Stego-Mesh.
    
    Args:
        request: Запрос с payload и протоколом маскировки
        
    Returns:
        Закодированный пакет (Base64)
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stego-Mesh not available")
    
    try:
        import base64
        payload = base64.b64decode(request.payload)
        
        encoded = integration.encode_packet_stego(
            payload,
            request.protocol_mimic
        )
        
        if encoded is None:
            raise HTTPException(status_code=503, detail="Stego-Mesh encoding failed")
        
        encoded_b64 = base64.b64encode(encoded).decode('utf-8')
        
        return {
            "encoded_packet": encoded_b64,
            "original_size": len(payload),
            "encoded_size": len(encoded),
            "overhead": len(encoded) - len(payload),
            "protocol": request.protocol_mimic
        }
    except Exception as e:
        logger.error(f"Stego-Mesh encoding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stego/decode")
async def decode_stego_packet(
    encoded_packet: str,  # Base64
    integration: MAPEKV3Integration = Depends(get_v3_integration)
) -> Dict[str, Any]:
    """
    Декодирование стеганографического пакета.
    
    Args:
        encoded_packet: Закодированный пакет (Base64)
        
    Returns:
        Декодированные данные (Base64)
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stego-Mesh not available")
    
    try:
        import base64
        stego_packet = base64.b64decode(encoded_packet)
        
        decoded = integration.decode_packet_stego(stego_packet)
        
        if decoded is None:
            raise HTTPException(status_code=400, detail="Failed to decode packet")
        
        decoded_b64 = base64.b64encode(decoded).decode('utf-8')
        
        return {
            "decoded_payload": decoded_b64,
            "size": len(decoded)
        }
    except Exception as e:
        logger.error(f"Stego-Mesh decoding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chaos/run")
async def run_chaos_test(
    request: ChaosTestRequest,
    integration: MAPEKV3Integration = Depends(get_v3_integration)
) -> Dict[str, Any]:
    """
    Запуск chaos-теста на Digital Twins.
    
    Args:
        request: Параметры chaos-теста
        
    Returns:
        Результат chaos-теста
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Digital Twins not available")
    
    try:
        result = await integration.run_chaos_test(
            scenario=request.scenario,
            intensity=request.intensity
        )
        
        if result is None:
            raise HTTPException(status_code=503, detail="Chaos test failed")
        
        return result
    except Exception as e:
        logger.error(f"Chaos test error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit/add")
async def add_audit_record(
    request: AuditRecordRequest,
    audit_trail: ImmutableAuditTrail = Depends(get_audit_trail)
) -> Dict[str, Any]:
    """
    Добавление записи в аудит-трейл.
    
    Args:
        request: Данные записи
        
    Returns:
        Созданная запись
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Audit Trail not available")
    
    try:
        record = audit_trail.add_record(
            record_type=request.record_type,
            data=request.data,
            auditor=request.auditor
        )
        
        return {
            "record_id": len(audit_trail.records) - 1,
            "ipfs_cid": record.get("ipfs_cid"),
            "merkle_root": record.get("merkle_root"),
            "timestamp": record.get("timestamp")
        }
    except Exception as e:
        logger.error(f"Audit record error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/records")
async def get_audit_records(
    record_type: Optional[str] = None,
    limit: int = 100,
    audit_trail: ImmutableAuditTrail = Depends(get_audit_trail)
) -> Dict[str, Any]:
    """
    Получение записей из аудит-трейла.
    
    Args:
        record_type: Фильтр по типу записи
        limit: Максимальное количество записей
        
    Returns:
        Список записей
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Audit Trail not available")
    
    try:
        records = audit_trail.get_records(record_type=record_type)
        records = records[-limit:]  # Последние N записей
        
        return {
            "total": len(audit_trail.records),
            "returned": len(records),
            "records": records
        }
    except Exception as e:
        logger.error(f"Get audit records error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/statistics")
async def get_audit_statistics(
    audit_trail: ImmutableAuditTrail = Depends(get_audit_trail)
) -> Dict[str, Any]:
    """
    Получение статистики аудит-трейла.
    
    Returns:
        Статистика аудит-трейла
    """
    if not V3_AVAILABLE:
        raise HTTPException(status_code=503, detail="Audit Trail not available")
    
    try:
        stats = audit_trail.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Get audit statistics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

