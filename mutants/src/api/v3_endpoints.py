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
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


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


def x_get_v3_integration__mutmut_orig() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=True,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_1() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is not None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=True,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_2() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = None
    return _v3_integration


def x_get_v3_integration__mutmut_3() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=None,
            enable_stego_mesh=True,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_4() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=None,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_5() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=True,
            enable_digital_twins=None
        )
    return _v3_integration


def x_get_v3_integration__mutmut_6() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_stego_mesh=True,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_7() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_8() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=True,
            )
    return _v3_integration


def x_get_v3_integration__mutmut_9() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=False,
            enable_stego_mesh=True,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_10() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=False,
            enable_digital_twins=True
        )
    return _v3_integration


def x_get_v3_integration__mutmut_11() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True,
            enable_stego_mesh=True,
            enable_digital_twins=False
        )
    return _v3_integration

x_get_v3_integration__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_v3_integration__mutmut_1': x_get_v3_integration__mutmut_1, 
    'x_get_v3_integration__mutmut_2': x_get_v3_integration__mutmut_2, 
    'x_get_v3_integration__mutmut_3': x_get_v3_integration__mutmut_3, 
    'x_get_v3_integration__mutmut_4': x_get_v3_integration__mutmut_4, 
    'x_get_v3_integration__mutmut_5': x_get_v3_integration__mutmut_5, 
    'x_get_v3_integration__mutmut_6': x_get_v3_integration__mutmut_6, 
    'x_get_v3_integration__mutmut_7': x_get_v3_integration__mutmut_7, 
    'x_get_v3_integration__mutmut_8': x_get_v3_integration__mutmut_8, 
    'x_get_v3_integration__mutmut_9': x_get_v3_integration__mutmut_9, 
    'x_get_v3_integration__mutmut_10': x_get_v3_integration__mutmut_10, 
    'x_get_v3_integration__mutmut_11': x_get_v3_integration__mutmut_11
}

def get_v3_integration(*args, **kwargs):
    result = _mutmut_trampoline(x_get_v3_integration__mutmut_orig, x_get_v3_integration__mutmut_mutants, args, kwargs)
    return result 

get_v3_integration.__signature__ = _mutmut_signature(x_get_v3_integration__mutmut_orig)
x_get_v3_integration__mutmut_orig.__name__ = 'x_get_v3_integration'


def x_get_audit_trail__mutmut_orig() -> ImmutableAuditTrail:
    """Dependency для получения Audit Trail"""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = ImmutableAuditTrail()
    return _audit_trail


def x_get_audit_trail__mutmut_1() -> ImmutableAuditTrail:
    """Dependency для получения Audit Trail"""
    global _audit_trail
    if _audit_trail is not None:
        _audit_trail = ImmutableAuditTrail()
    return _audit_trail


def x_get_audit_trail__mutmut_2() -> ImmutableAuditTrail:
    """Dependency для получения Audit Trail"""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = None
    return _audit_trail

x_get_audit_trail__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_audit_trail__mutmut_1': x_get_audit_trail__mutmut_1, 
    'x_get_audit_trail__mutmut_2': x_get_audit_trail__mutmut_2
}

def get_audit_trail(*args, **kwargs):
    result = _mutmut_trampoline(x_get_audit_trail__mutmut_orig, x_get_audit_trail__mutmut_mutants, args, kwargs)
    return result 

get_audit_trail.__signature__ = _mutmut_signature(x_get_audit_trail__mutmut_orig)
x_get_audit_trail__mutmut_orig.__name__ = 'x_get_audit_trail'


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

