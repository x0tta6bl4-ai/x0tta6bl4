"""
API Endpoints for V3.0 Components
==================================

REST API endpoints для управления и мониторинга компонентов v3.0.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.version import __version__

logger = logging.getLogger(__name__)

# Импорты компонентов v3.0
try:
    from src.self_healing.mape_k_v3_integration import MAPEKV3Integration
    from src.storage.immutable_audit_trail import ImmutableAuditTrail
    from src.testing.digital_twins import ChaosScenario

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
V3_STATUS_CLAIM_BOUNDARY = (
    "V3 status reports local component availability for GraphSAGE, Stego-Mesh, "
    "digital twins, and audit helpers only. status=operational does not prove "
    "production readiness, live dataplane delivery, customer traffic, DPI bypass, "
    "trust finality, settlement finality, or production SLOs."
)
V3_GRAPHSAGE_CLAIM_BOUNDARY = (
    "V3 GraphSAGE analysis reports local model inference over caller-supplied "
    "node features and topology only. It does not prove route discovery, route "
    "quality, control-action application, live dataplane delivery, customer "
    "traffic, trust finality, settlement finality, or production readiness."
)
V3_STEGO_CLAIM_BOUNDARY = (
    "V3 Stego-Mesh endpoints return local encode/decode transform results only. "
    "A transformed payload does not prove external DPI bypass, external "
    "reachability, live dataplane delivery, customer traffic, trust finality, "
    "settlement finality, or production readiness."
)
V3_CHAOS_CLAIM_BOUNDARY = (
    "V3 chaos runs report local digital-twin simulation results only. A "
    "simulation result does not prove live failover, production SLOs, restored "
    "dataplane, customer traffic, external DPI bypass, settlement finality, or "
    "production readiness."
)
V3_AUDIT_CLAIM_BOUNDARY = (
    "V3 audit endpoints report local audit-trail records and statistics only. "
    "Local merkle/IPFS-looking metadata does not prove external storage "
    "durability, chain finality, trust finality, settlement finality, or "
    "production readiness."
)
V3_LOCAL_CLAIM_GATE_SCHEMA = "x0tta6bl4.v3.local_operation_claim_gate.v1"


def _unique_claims(claims: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(str(claim) for claim in claims if str(claim).strip()))


def _v3_local_operation_claim_gate(
    *,
    surface: str,
    allowed_claim_id: str,
    blocked_claim_ids: Sequence[str],
    claim_boundary: str,
) -> Dict[str, Any]:
    return {
        "schema": V3_LOCAL_CLAIM_GATE_SCHEMA,
        "decision": "V3_LOCAL_OPERATION_CLAIM_ONLY",
        "surface": surface,
        "allowed_claim_ids": _unique_claims((allowed_claim_id,)),
        "blocked_claim_ids": _unique_claims(blocked_claim_ids),
        "local_operation_claim_allowed": True,
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "trust_finality_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": claim_boundary,
    }

# Глобальный экземпляр интеграции (в production должен быть через dependency injection)
_v3_integration: Optional[MAPEKV3Integration] = None
_audit_trail: Optional[ImmutableAuditTrail] = None


def get_v3_integration() -> MAPEKV3Integration:
    """Dependency для получения V3 интеграции"""
    global _v3_integration
    if _v3_integration is None:
        _v3_integration = MAPEKV3Integration(
            enable_graphsage=True, enable_stego_mesh=True, enable_digital_twins=True
        )
    return _v3_integration


def get_audit_trail() -> ImmutableAuditTrail:
    """Dependency для получения Audit Trail"""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = ImmutableAuditTrail()
    return _audit_trail


def _get_v3_integration() -> MAPEKV3Integration:
    return get_v3_integration()


def _get_audit_trail() -> ImmutableAuditTrail:
    return get_audit_trail()


@router.get("/status")
async def get_v3_status(
    integration: MAPEKV3Integration = Depends(_get_v3_integration),
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
        "version": __version__,
        "local_component_status_claim_allowed": True,
        "dataplane_confirmed": False,
        "customer_traffic_confirmed": False,
        "external_dpi_bypass_confirmed": False,
        "trust_finality_confirmed": False,
        "settlement_finality_confirmed": False,
        "production_readiness_claim_allowed": False,
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="v3_status",
            claims=(
                "production_readiness",
                "dataplane_delivery",
                "traffic_delivery",
                "customer_traffic",
                "dpi_bypass",
                "trust_finality",
                "settlement_finality",
            ),
        ),
        "claim_boundary": V3_STATUS_CLAIM_BOUNDARY,
    }


@router.post("/graphsage/analyze")
async def analyze_with_graphsage(
    request: GraphSAGEAnalysisRequest,
    integration: MAPEKV3Integration = Depends(_get_v3_integration),
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
            node_features=request.node_features, node_topology=request.node_topology
        )

        if analysis is None:
            raise HTTPException(status_code=503, detail="GraphSAGE analysis failed")

        return {
            "failure_type": analysis.failure_type.value,
            "confidence": analysis.confidence,
            "recommended_action": analysis.recommended_action,
            "severity": analysis.severity,
            "affected_nodes": analysis.affected_nodes,
            "local_model_analysis_claim_allowed": True,
            "control_action_applied": False,
            "dataplane_confirmed": False,
            "customer_traffic_confirmed": False,
            "external_dpi_bypass_confirmed": False,
            "trust_finality_confirmed": False,
            "settlement_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "graphsage_claim_gate": _v3_local_operation_claim_gate(
                surface="v3_graphsage_analyze",
                allowed_claim_id="local_model_analysis",
                blocked_claim_ids=(
                    "route_discovery",
                    "route_quality",
                    "control_action_applied",
                    "dataplane_delivery",
                    "customer_traffic",
                    "trust_finality",
                    "settlement_finality",
                    "production_readiness",
                ),
                claim_boundary=V3_GRAPHSAGE_CLAIM_BOUNDARY,
            ),
            "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                surface="v3_graphsage_analyze",
                claims=(
                    "production_readiness",
                    "dataplane_delivery",
                    "traffic_delivery",
                    "customer_traffic",
                    "trust_finality",
                    "settlement_finality",
                ),
            ),
            "claim_boundary": V3_GRAPHSAGE_CLAIM_BOUNDARY,
        }
    except Exception as e:
        logger.error(f"GraphSAGE analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stego/encode")
async def encode_stego_packet(
    request: StegoMeshEncodeRequest,
    integration: MAPEKV3Integration = Depends(_get_v3_integration),
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

        encoded = integration.encode_packet_stego(payload, request.protocol_mimic)

        if encoded is None:
            raise HTTPException(status_code=503, detail="Stego-Mesh encoding failed")

        encoded_b64 = base64.b64encode(encoded).decode("utf-8")

        return {
            "encoded_packet": encoded_b64,
            "original_size": len(payload),
            "encoded_size": len(encoded),
            "overhead": len(encoded) - len(payload),
            "protocol": request.protocol_mimic,
            "local_transform_claim_allowed": True,
            "dataplane_confirmed": False,
            "customer_traffic_confirmed": False,
            "external_dpi_bypass_confirmed": False,
            "trust_finality_confirmed": False,
            "settlement_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "stego_claim_gate": _v3_local_operation_claim_gate(
                surface="v3_stego_encode",
                allowed_claim_id="local_stego_encode_transform",
                blocked_claim_ids=(
                    "external_dpi_bypass",
                    "external_reachability",
                    "dataplane_delivery",
                    "traffic_delivery",
                    "customer_traffic",
                    "trust_finality",
                    "settlement_finality",
                    "production_readiness",
                ),
                claim_boundary=V3_STEGO_CLAIM_BOUNDARY,
            ),
            "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                surface="v3_stego_encode",
                claims=(
                    "production_readiness",
                    "dataplane_delivery",
                    "traffic_delivery",
                    "customer_traffic",
                    "dpi_bypass",
                    "trust_finality",
                    "settlement_finality",
                ),
            ),
            "claim_boundary": V3_STEGO_CLAIM_BOUNDARY,
        }
    except Exception as e:
        logger.error(f"Stego-Mesh encoding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stego/decode")
async def decode_stego_packet(
    encoded_packet: str,  # Base64
    integration: MAPEKV3Integration = Depends(_get_v3_integration),
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

        decoded_b64 = base64.b64encode(decoded).decode("utf-8")

        return {
            "decoded_payload": decoded_b64,
            "size": len(decoded),
            "local_transform_claim_allowed": True,
            "dataplane_confirmed": False,
            "customer_traffic_confirmed": False,
            "external_dpi_bypass_confirmed": False,
            "trust_finality_confirmed": False,
            "settlement_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "stego_claim_gate": _v3_local_operation_claim_gate(
                surface="v3_stego_decode",
                allowed_claim_id="local_stego_decode_transform",
                blocked_claim_ids=(
                    "external_dpi_bypass",
                    "external_reachability",
                    "dataplane_delivery",
                    "traffic_delivery",
                    "customer_traffic",
                    "trust_finality",
                    "settlement_finality",
                    "production_readiness",
                ),
                claim_boundary=V3_STEGO_CLAIM_BOUNDARY,
            ),
            "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                surface="v3_stego_decode",
                claims=(
                    "production_readiness",
                    "dataplane_delivery",
                    "traffic_delivery",
                    "customer_traffic",
                    "dpi_bypass",
                    "trust_finality",
                    "settlement_finality",
                ),
            ),
            "claim_boundary": V3_STEGO_CLAIM_BOUNDARY,
        }
    except Exception as e:
        logger.error(f"Stego-Mesh decoding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chaos/run")
async def run_chaos_test(
    request: ChaosTestRequest,
    integration: MAPEKV3Integration = Depends(_get_v3_integration),
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
            scenario=request.scenario, intensity=request.intensity
        )

        if result is None:
            raise HTTPException(status_code=503, detail="Chaos test failed")

        response = dict(result) if isinstance(result, dict) else {"result": result}
        response.update(
            {
                "local_simulation_claim_allowed": True,
                "control_action_applied": False,
                "dataplane_confirmed": False,
                "customer_traffic_confirmed": False,
                "external_dpi_bypass_confirmed": False,
                "production_slo_confirmed": False,
                "trust_finality_confirmed": False,
                "settlement_finality_confirmed": False,
                "production_readiness_claim_allowed": False,
                "chaos_claim_gate": _v3_local_operation_claim_gate(
                    surface="v3_chaos_run",
                    allowed_claim_id="local_digital_twin_simulation",
                    blocked_claim_ids=(
                        "live_failover",
                        "production_slo",
                        "restored_dataplane",
                        "dataplane_delivery",
                        "customer_traffic",
                        "external_dpi_bypass",
                        "settlement_finality",
                        "production_readiness",
                    ),
                    claim_boundary=V3_CHAOS_CLAIM_BOUNDARY,
                ),
                "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                    surface="v3_chaos_run",
                    claims=(
                        "production_readiness",
                        "dataplane_delivery",
                        "traffic_delivery",
                        "customer_traffic",
                        "dpi_bypass",
                        "settlement_finality",
                    ),
                ),
                "claim_boundary": V3_CHAOS_CLAIM_BOUNDARY,
            }
        )
        return response
    except Exception as e:
        logger.error(f"Chaos test error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/audit/add")
async def add_audit_record(
    request: AuditRecordRequest,
    audit_trail: ImmutableAuditTrail = Depends(_get_audit_trail),
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
            record_type=request.record_type, data=request.data, auditor=request.auditor
        )

        return {
            "record_id": len(audit_trail.records) - 1,
            "ipfs_cid": record.get("ipfs_cid"),
            "merkle_root": record.get("merkle_root"),
            "timestamp": record.get("timestamp"),
            "local_audit_record_claim_allowed": True,
            "external_storage_finality_confirmed": False,
            "trust_finality_confirmed": False,
            "settlement_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "audit_claim_gate": _v3_local_operation_claim_gate(
                surface="v3_audit_add",
                allowed_claim_id="local_audit_record_write",
                blocked_claim_ids=(
                    "external_storage_finality",
                    "chain_finality",
                    "trust_finality",
                    "settlement_finality",
                    "production_readiness",
                ),
                claim_boundary=V3_AUDIT_CLAIM_BOUNDARY,
            ),
            "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                surface="v3_audit_add",
                claims=(
                    "production_readiness",
                    "trust_finality",
                    "settlement_finality",
                ),
            ),
            "claim_boundary": V3_AUDIT_CLAIM_BOUNDARY,
        }
    except Exception as e:
        logger.error(f"Audit record error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/audit/records")
async def get_audit_records(
    record_type: Optional[str] = None,
    limit: int = 100,
    audit_trail: ImmutableAuditTrail = Depends(_get_audit_trail),
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
            "records": records,
            "local_audit_record_claim_allowed": True,
            "external_storage_finality_confirmed": False,
            "trust_finality_confirmed": False,
            "settlement_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "audit_claim_gate": _v3_local_operation_claim_gate(
                surface="v3_audit_records",
                allowed_claim_id="local_audit_record_read",
                blocked_claim_ids=(
                    "external_storage_finality",
                    "chain_finality",
                    "trust_finality",
                    "settlement_finality",
                    "production_readiness",
                ),
                claim_boundary=V3_AUDIT_CLAIM_BOUNDARY,
            ),
            "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                surface="v3_audit_records",
                claims=(
                    "production_readiness",
                    "trust_finality",
                    "settlement_finality",
                ),
            ),
            "claim_boundary": V3_AUDIT_CLAIM_BOUNDARY,
        }
    except Exception as e:
        logger.error(f"Get audit records error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/audit/statistics")
async def get_audit_statistics(
    audit_trail: ImmutableAuditTrail = Depends(_get_audit_trail),
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
        response = dict(stats) if isinstance(stats, dict) else {"statistics": stats}
        response.update(
            {
                "local_audit_record_claim_allowed": True,
                "external_storage_finality_confirmed": False,
                "trust_finality_confirmed": False,
                "settlement_finality_confirmed": False,
                "production_readiness_claim_allowed": False,
                "audit_claim_gate": _v3_local_operation_claim_gate(
                    surface="v3_audit_statistics",
                    allowed_claim_id="local_audit_statistics_read",
                    blocked_claim_ids=(
                        "external_storage_finality",
                        "chain_finality",
                        "trust_finality",
                        "settlement_finality",
                        "production_readiness",
                    ),
                    claim_boundary=V3_AUDIT_CLAIM_BOUNDARY,
                ),
                "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
                    surface="v3_audit_statistics",
                    claims=(
                        "production_readiness",
                        "trust_finality",
                        "settlement_finality",
                    ),
                ),
                "claim_boundary": V3_AUDIT_CLAIM_BOUNDARY,
            }
        )
        return response
    except Exception as e:
        logger.error(f"Get audit statistics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
