from __future__ import annotations
# src/core/mape_orchestrator.py
import asyncio
import hashlib
import logging
import time
from typing import Any, Dict

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _metrics_summary(metrics: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted(str(key) for key in (metrics or {}).keys())
    return {
        "key_count": len(keys),
        "keys_hash": _safe_hash("|".join(keys)),
        "has_latency": "latency_p95_value" in metrics,
        "has_packet_loss": "packet_loss_value" in metrics,
        "has_pqc": "pqc_handshake_success_value" in metrics,
    }


class MAPEOrchestrator:
    def __init__(self, prometheus_client, mesh_client, dao_client, ipfs_client):
        self.prometheus = prometheus_client
        self.mesh = mesh_client
        self.dao = dao_client
        self.ipfs = ipfs_client
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"libx0t-mape-orchestrator:{_safe_hash(id(self))}",
            role="healing",
            capabilities=("mape_k", "monitoring", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "libx0t_mape_orchestrator_init",
                "goal": "Initialize MAPE-K orchestrator clients",
                "signals": {
                    "prometheus_configured": prometheus_client is not None,
                    "mesh_configured": mesh_client is not None,
                    "dao_configured": dao_client is not None,
                    "ipfs_configured": ipfs_client is not None,
                },
                "safety_boundary": (
                    "Do not expose raw metrics, routing plans, DAO event payloads, "
                    "or snapshot names in orchestrator thinking context."
                ),
            }
        )
        logger.info("MAPEOrchestrator initialized.")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_metrics": True,
                    "redact_routing_details": True,
                    "redact_dao_payloads": True,
                    "preserve_mapek_contract": True,
                },
                "safety_boundary": (
                    "Use metric summaries, action names, hashes, and boolean flags."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def monitor_cycle(self):
        """
        Slot-based sync каждые 3.14 сек. Собирает метрики из Prometheus.
        """
        logger.debug("Начало цикла мониторинга...")
        # Предполагаем, что self.prometheus.query возвращает текущие метрики
        # в виде словаря. В реальной реализации это будет Prometheus-клиент.
        metrics = await self.prometheus.query(
            {
                "latency_p95": "<87ms",  # Пример запроса, в реальности будет PromQL
                "packet_loss": "<1.6%",
                "pqc_handshake_success": ">99%",
            }
        )
        logger.debug(f"Метрики получены: {metrics}")
        self._record_thinking(
            "libx0t_mape_monitor_cycle",
            "Collect metrics for MAPE-K analysis",
            {"metrics": _metrics_summary(metrics)},
        )
        return metrics

    async def analyze_cycle(self, metrics):
        """
        GNN GraphSAGE для topology optimization.
        Анализирует метрики и определяет план действий.
        """
        logger.debug("Начало цикла анализа...")
        plan = {}
        # Простая эвристика для примера. В реальности будет GNN GraphSAGE.
        if (
            metrics.get("latency_p95_value", 0) > 87
        ):  # Пример, что Prometheus вернет значение
            plan = {
                "action": "re-route",
                "algorithm": "k-disjoint-spf",
                "reason": "High latency",
            }
            logger.warn(f"Высокая задержка обнаружена, планируется {plan['action']}")
        elif metrics.get("packet_loss_value", 0) > 1.6:
            plan = {
                "action": "re-route",
                "algorithm": "fast-failover",
                "reason": "High packet loss",
            }
            logger.warn(f"Высокая потеря пакетов, планируется {plan['action']}")
        else:
            plan = {"action": "none", "reason": "System stable"}

        logger.debug(f"План анализа: {plan}")
        self._record_thinking(
            "libx0t_mape_analyze_cycle",
            "Select routing plan from redacted metric summary",
            {
                "metrics": _metrics_summary(metrics),
                "action": plan.get("action"),
                "algorithm": plan.get("algorithm"),
                "reason_hash": _safe_hash(plan.get("reason")),
            },
        )
        return plan

    async def execute_cycle(self, plan):
        """
        Zero-downtime rerouting + DAO audit.
        Выполняет план действий и логирует в DAO.
        """
        logger.debug(f"Начало цикла выполнения: {plan['action']}")
        self._record_thinking(
            "libx0t_mape_execute_cycle_started",
            "Execute selected MAPE-K plan",
            {
                "action": plan.get("action"),
                "algorithm": plan.get("algorithm"),
                "plan_key_count": len(plan),
                "plan_keys_hash": _safe_hash("|".join(sorted(str(k) for k in plan))),
            },
        )
        if plan["action"] == "re-route":
            # Предполагаем, что self.mesh.apply_routing() применяет изменения маршрутизации
            logger.info(f"Применяется маршрутизация: {plan['algorithm']}")
            await self.mesh.apply_routing(plan)

        # Логирование события в DAO
        event_data = {
            "type": "topology_change",
            "action": plan["action"],
            "timestamp": time.time(),
            "details": plan,
        }
        logger.info(f"Логирование события в DAO: {event_data['type']}")
        await self.dao.log_event(event_data["type"], event_data)

        # IPFS snapshot
        timestamp_str = time.strftime("%Y%m%d%H%M%S")
        snapshot_name = f"mesh-state-{timestamp_str}"
        logger.info(f"Создание IPFS snapshot: {snapshot_name}")
        await self.ipfs.snapshot(snapshot_name)
        logger.debug("Цикл выполнения завершен.")
        self._record_thinking(
            "libx0t_mape_execute_cycle_completed",
            "Record MAPE-K execution audit and snapshot completion",
            {
                "action": plan.get("action"),
                "dao_event_type": event_data["type"],
                "snapshot_created": True,
                "snapshot_hash": _safe_hash(snapshot_name),
            },
        )

    async def mape_k_loop(self, interval_seconds: float = 3.14):
        """
        Основной цикл MAPE-K.
        """
        logger.info(
            f"Запуск основного цикла MAPE-K с интервалом {interval_seconds} секунд..."
        )
        self._record_thinking(
            "libx0t_mape_loop_started",
            "Start continuous MAPE-K loop",
            {"interval_seconds": interval_seconds},
        )
        while True:
            try:
                metrics = await self.monitor_cycle()
                plan = await self.analyze_cycle(metrics)
                if plan["action"] != "none":
                    await self.execute_cycle(plan)
            except Exception as e:
                logger.error(f"Ошибка в цикле MAPE-K: {e}")
                self._record_thinking(
                    "libx0t_mape_loop_error",
                    "Handle MAPE-K loop error",
                    {"error_type": type(e).__name__},
                )
            await asyncio.sleep(interval_seconds)


# Пример использования (для тестирования или демонстрации)
async def main():
    # Mock-клиенты для демонстрации
    class MockPrometheus:
        async def query(self, query_params):
            await asyncio.sleep(0.1)  # Имитация задержки запроса
            # Имитация получения метрик
            return {
                "latency_p95_value": (
                    90 if time.time() % 20 < 10 else 50
                ),  # Меняется каждые 10 секунд
                "packet_loss_value": 0.5,
                "pqc_handshake_success_value": 99.5,
            }

    class MockMesh:
        async def apply_routing(self, plan):
            await asyncio.sleep(0.1)
            logger.info(f"MockMesh: Применение маршрутизации: {plan['algorithm']}")

    class MockDAO:
        async def log_event(self, event_type, event_data):
            await asyncio.sleep(0.05)
            logger.info(f"MockDAO: Логирование события: {event_type}")

    class MockIPFS:
        async def snapshot(self, name):
            await asyncio.sleep(0.05)
            logger.info(f"MockIPFS: Создание snapshot: {name}")

    logging.basicConfig(level=logging.INFO)  # Установите INFO для более чистого вывода
    orchestrator = MAPEOrchestrator(MockPrometheus(), MockMesh(), MockDAO(), MockIPFS())
    await orchestrator.mape_k_loop(interval_seconds=3.14)


if __name__ == "__main__":
    # Для корректного запуска asyncio main() функции
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MAPE-K цикл остановлен пользователем.")

