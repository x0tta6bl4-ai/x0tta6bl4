"""
MAPE-K V3.0 Integration
=======================

Интеграция компонентов v3.0 (GraphSAGE, Stego-Mesh, Digital Twins) в production MAPE-K цикл.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Импорты компонентов v3.0
try:
    from src.ml.anomaly_models import AnomalyAnalysis, FailureType
    from src.ml.graphsage_anomaly_detector import GraphSAGEAnalyzer

    GRAPHSAGE_AVAILABLE = True
except (ImportError, NameError) as e:
    GRAPHSAGE_AVAILABLE = False
    AnomalyAnalysis = None  # Fallback для типизации
    logger.warning(f"GraphSAGE Analyzer not available: {e}")

try:
    from src.anti_censorship.stego_mesh import StegoMeshProtocol

    STEGO_MESH_AVAILABLE = True
except ImportError:
    STEGO_MESH_AVAILABLE = False
    logger.warning("Stego-Mesh not available")

try:
    from src.testing.digital_twins import ChaosScenario, DigitalTwinsSimulator

    DIGITAL_TWINS_AVAILABLE = True
except ImportError:
    DIGITAL_TWINS_AVAILABLE = False
    logger.warning("Digital Twins not available")


class MAPEKV3Integration:
    """
    Интеграция компонентов v3.0 в MAPE-K цикл.

    Добавляет:
    - GraphSAGE для Analyze-фазы
    - Stego-Mesh для Execute-фазы (при необходимости)
    - Digital Twins для тестирования
    """

    def __init__(
        self,
        enable_graphsage: bool = True,
        enable_stego_mesh: bool = False,
        enable_digital_twins: bool = False,
    ):
        """
        Инициализация интеграции v3.0.

        Args:
            enable_graphsage: Включить GraphSAGE в Analyze-фазе
            enable_stego_mesh: Включить Stego-Mesh для трафика
            enable_digital_twins: Включить Digital Twins для тестирования
        """
        self.graphsage_analyzer = None
        self.stego_mesh = None
        self.digital_twins = None

        # Инициализация GraphSAGE
        if enable_graphsage and GRAPHSAGE_AVAILABLE:
            try:
                self.graphsage_analyzer = GraphSAGEAnalyzer(
                    in_channels=10, hidden_channels=64, num_layers=3, device="cpu"
                )
                logger.info("✅ GraphSAGE Analyzer integrated into MAPE-K")
            except Exception as e:
                logger.error(f"Failed to initialize GraphSAGE: {e}")

        # Инициализация Stego-Mesh (требует master key)
        if enable_stego_mesh and STEGO_MESH_AVAILABLE:
            try:
                # В production master key должен быть из secure storage
                import secrets

                master_key = secrets.token_bytes(32)
                self.stego_mesh = StegoMeshProtocol(master_key)
                logger.info("✅ Stego-Mesh integrated into MAPE-K")
            except Exception as e:
                logger.error(f"Failed to initialize Stego-Mesh: {e}")

        # Инициализация Digital Twins (для тестирования)
        if enable_digital_twins and DIGITAL_TWINS_AVAILABLE:
            try:
                self.digital_twins = DigitalTwinsSimulator(node_count=100)
                logger.info("✅ Digital Twins integrated into MAPE-K")
            except Exception as e:
                logger.error(f"Failed to initialize Digital Twins: {e}")

    async def analyze_with_graphsage(
        self,
        node_features: Dict[str, Dict[str, float]],
        node_topology: Optional[Dict[str, List[str]]] = None,
    ) -> Optional[AnomalyAnalysis]:
        """
        Анализ аномалий с помощью GraphSAGE.

        Args:
            node_features: Признаки узлов сети
            node_topology: Топология сети (соседи)

        Returns:
            AnomalyAnalysis или None если GraphSAGE недоступен
        """
        if not self.graphsage_analyzer:
            return None

        try:
            analysis = await self.graphsage_analyzer.analyze_anomaly(
                node_features=node_features, node_topology=node_topology
            )

            logger.info(
                f"GraphSAGE Analysis: {analysis.failure_type.value} "
                f"(confidence={analysis.confidence:.2f}, severity={analysis.severity})"
            )

            return analysis
        except Exception as e:
            logger.error(f"GraphSAGE analysis failed: {e}", exc_info=True)
            return None

    def encode_packet_stego(
        self, payload: bytes, protocol_mimic: str = "http"
    ) -> Optional[bytes]:
        """
        Кодирование пакета через Stego-Mesh.

        Args:
            payload: Данные для передачи
            protocol_mimic: Протокол для маскировки

        Returns:
            Стеганографический пакет или None
        """
        if not self.stego_mesh:
            return None

        try:
            return self.stego_mesh.encode_packet(payload, protocol_mimic)
        except Exception as e:
            logger.error(f"Stego-Mesh encoding failed: {e}")
            return None

    def decode_packet_stego(self, stego_packet: bytes) -> Optional[bytes]:
        """
        Декодирование стеганографического пакета.

        Args:
            stego_packet: Стеганографический пакет

        Returns:
            Расшифрованные данные или None
        """
        if not self.stego_mesh:
            return None

        try:
            return self.stego_mesh.decode_packet(stego_packet)
        except Exception as e:
            logger.error(f"Stego-Mesh decoding failed: {e}")
            return None

    async def run_chaos_test(
        self, scenario: str, intensity: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        """
        Запуск chaos-теста на Digital Twins.

        Args:
            scenario: Тип сценария (node_down, link_failure, ddos, etc.)
            intensity: Интенсивность (0.0 - 1.0)

        Returns:
            Результат теста или None
        """
        if not self.digital_twins:
            return None

        try:
            # Преобразуем строку в ChaosScenario
            scenario_map = {
                "node_down": ChaosScenario.NODE_DOWN,
                "link_failure": ChaosScenario.LINK_FAILURE,
                "ddos": ChaosScenario.DDOS,
                "byzantine": ChaosScenario.BYZANTINE,
                "resource_exhaustion": ChaosScenario.RESOURCE_EXHAUSTION,
            }

            chaos_scenario = scenario_map.get(scenario.lower())
            if not chaos_scenario:
                logger.error(f"Unknown chaos scenario: {scenario}")
                return None

            result = await self.digital_twins.run_chaos_test(
                scenario=chaos_scenario, intensity=intensity, duration=60.0
            )

            return {
                "scenario": result.scenario.value,
                "intensity": result.intensity,
                "recovery_time": result.recovery_time,
                "success": result.success,
                "affected_nodes": result.affected_nodes,
                "timestamp": result.timestamp.isoformat(),
            }
        except Exception as e:
            logger.error(f"Chaos test failed: {e}", exc_info=True)
            return None

    def get_status(self) -> Dict[str, Any]:
        """Получение статуса интеграции v3.0"""
        return {
            "graphsage_available": self.graphsage_analyzer is not None,
            "stego_mesh_available": self.stego_mesh is not None,
            "digital_twins_available": self.digital_twins is not None,
            "components_loaded": {
                "graphsage": GRAPHSAGE_AVAILABLE,
                "stego_mesh": STEGO_MESH_AVAILABLE,
                "digital_twins": DIGITAL_TWINS_AVAILABLE,
            },
        }


def integrate_v3_into_mapek(mapek_cycle, enable_graphsage=True, enable_stego=False):
    """
    Интеграция компонентов v3.0 в существующий MAPE-K цикл.

    Args:
        mapek_cycle: Экземпляр MAPE-K цикла
        enable_graphsage: Включить GraphSAGE
        enable_stego: Включить Stego-Mesh
    """
    v3_integration = MAPEKV3Integration(
        enable_graphsage=enable_graphsage, enable_stego_mesh=enable_stego
    )

    # Интегрируем GraphSAGE в Analyze-фазу
    if v3_integration.graphsage_analyzer and hasattr(mapek_cycle, "analyzer"):
        original_analyze = mapek_cycle.analyzer.analyze

        async def enhanced_analyze(metrics, context=None):
            # Вызываем оригинальный анализ
            result = await original_analyze(metrics, context)

            # Добавляем GraphSAGE анализ если доступны node_features
            if isinstance(metrics, dict) and "node_features" in metrics:
                graphsage_result = await v3_integration.analyze_with_graphsage(
                    node_features=metrics["node_features"],
                    node_topology=metrics.get("node_topology"),
                )

                if graphsage_result:
                    # Обогащаем результат GraphSAGE данными
                    result["graphsage_analysis"] = {
                        "failure_type": graphsage_result.failure_type.value,
                        "confidence": graphsage_result.confidence,
                        "recommended_action": graphsage_result.recommended_action,
                        "severity": graphsage_result.severity,
                        "affected_nodes": graphsage_result.affected_nodes,
                    }

            return result

        mapek_cycle.analyzer.analyze = enhanced_analyze
        logger.info("✅ GraphSAGE integrated into MAPE-K Analyze phase")

    return v3_integration
