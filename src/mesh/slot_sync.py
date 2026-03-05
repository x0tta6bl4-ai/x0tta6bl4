"""
Slot-Based Self-Healing Mesh без GPS.

Локальная синхронизация с соседями через beacon-сигналы.
Не требует глобальной временной синхронизации.

Target metrics:
- Beacon Jitter ≤ 5ms
- Collision Resolution ≤ 35 sec
- MTTD (Mean Time To Detect) ≤ 1.9 sec
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SlotState(Enum):
    """Состояние временного слота."""

    IDLE = "idle"  # Ожидание
    LISTENING = "listening"  # Слушаем эфир
    TRANSMITTING = "tx"  # Передаём
    COLLISION = "collision"  # Обнаружена коллизия


@dataclass
class Beacon:
    """Beacon-сигнал для синхронизации."""

    node_id: str
    sequence: int
    timestamp_local: float  # Локальное время отправителя
    timestamp_received: float  # Когда мы получили
    slot_offset: float  # Смещение слота
    neighbors: List[str]  # Известные соседи

    def calculate_drift(self) -> float:
        """Вычислить drift между нами и отправителем."""
        return self.timestamp_received - self.timestamp_local


@dataclass
class SlotConfig:
    """Конфигурация слотов."""

    slot_duration_ms: float = 100.0  # Длительность слота (мс)
    beacon_interval_ms: float = 1000.0  # Интервал beacon (мс)
    jitter_max_ms: float = 5.0  # Максимальный jitter (мс)
    collision_backoff_ms: float = 50.0  # Backoff при коллизии
    sync_window_ms: float = 10.0  # Окно синхронизации


@dataclass
class NeighborInfo:
    """Информация о соседе."""

    node_id: str
    last_seen: float
    drift: float = 0.0  # Drift относительно нас
    beacons_received: int = 0
    quality: float = 1.0  # Качество связи (0-1)


class SlotSynchronizer:
    """
    GPS-independent синхронизатор слотов.

    Каждый узел синхронизируется с соседями локально,
    корректируя время передачи на основе моментов приёма beacon-сигналов.
    """

    def __init__(
        self,
        node_id: str,
        config: SlotConfig = None,
        on_beacon_received: Optional[Callable] = None,
        on_collision: Optional[Callable] = None,
    ):
        self.node_id = node_id
        self.config = config or SlotConfig()
        self.on_beacon_received = on_beacon_received
        self.on_collision = on_collision

        # Состояние
        self.state = SlotState.IDLE
        self.current_slot = 0
        self.sequence = 0

        # Соседи
        self.neighbors: Dict[str, NeighborInfo] = {}

        # Синхронизация
        self._local_offset = 0.0  # Наше смещение
        self._drift_history: List[float] = []
        self._last_beacon_time = 0.0

        # Collision tracking
        self._collision_count = 0
        self._backoff_until = 0.0

        # Running
        self._running = False
        self._tasks: List[asyncio.Task] = []

    def now(self) -> float:
        """Текущее время с коррекцией."""
        return time.time() + self._local_offset

    def _calculate_slot(self) -> int:
        """Вычислить текущий номер слота."""
        slot_duration_sec = self.config.slot_duration_ms / 1000
        return int(self.now() / slot_duration_sec)

    async def start(self):
        """Запустить синхронизатор."""
        self._running = True
        logger.info(f"[{self.node_id}] SlotSync started")

        # Запускаем задачи
        self._tasks = [
            asyncio.create_task(self._beacon_loop()),
            asyncio.create_task(self._listen_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]

    async def stop(self):
        """Остановить синхронизатор."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        logger.info(f"[{self.node_id}] SlotSync stopped")

    async def _beacon_loop(self):
        """Цикл отправки beacon-сигналов."""
        while self._running:
            try:
                # Ждём до следующего beacon с jitter
                jitter = random.uniform(0, self.config.jitter_max_ms) / 1000
                await asyncio.sleep(self.config.beacon_interval_ms / 1000 + jitter)

                # Проверяем backoff
                if time.time() < self._backoff_until:
                    continue

                # Отправляем beacon
                await self._send_beacon()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Beacon loop error: {e}")

    async def _send_beacon(self):
        """Отправить beacon-сигнал."""
        self.state = SlotState.TRANSMITTING
        self.sequence += 1

        beacon = Beacon(
            node_id=self.node_id,
            sequence=self.sequence,
            timestamp_local=self.now(),
            timestamp_received=0,  # Заполнит получатель
            slot_offset=self._local_offset,
            neighbors=list(self.neighbors.keys()),
        )

        self._last_beacon_time = time.time()
        logger.debug(f"[{self.node_id}] Beacon #{self.sequence} sent")

        self.state = SlotState.IDLE
        return beacon

    async def _listen_loop(self):
        """Цикл прослушивания."""
        while self._running:
            try:
                self.state = SlotState.LISTENING
                await asyncio.sleep(self.config.slot_duration_ms / 1000)
            except asyncio.CancelledError:
                break

    async def _cleanup_loop(self):
        """Удаление устаревших соседей."""
        while self._running:
            try:
                await asyncio.sleep(5.0)

                now = time.time()
                timeout = self.config.beacon_interval_ms * 5 / 1000

                stale = [
                    nid
                    for nid, info in self.neighbors.items()
                    if now - info.last_seen > timeout
                ]

                for nid in stale:
                    del self.neighbors[nid]
                    logger.info(f"[{self.node_id}] Neighbor {nid} timed out")

            except asyncio.CancelledError:
                break

    def receive_beacon(self, beacon: Beacon):
        """
        Обработать полученный beacon.

        Это вызывается когда мы получаем beacon от соседа.
        """
        beacon.timestamp_received = self.now()
        drift = beacon.calculate_drift()

        # Обновляем информацию о соседе
        if beacon.node_id not in self.neighbors:
            self.neighbors[beacon.node_id] = NeighborInfo(
                node_id=beacon.node_id, last_seen=time.time()
            )
            logger.info(f"[{self.node_id}] New neighbor: {beacon.node_id}")

        neighbor = self.neighbors[beacon.node_id]
        neighbor.last_seen = time.time()
        neighbor.beacons_received += 1
        neighbor.drift = drift

        # Адаптивная синхронизация
        self._adapt_timing(drift)

        # Callback
        if self.on_beacon_received:
            self.on_beacon_received(beacon)

        logger.debug(
            f"[{self.node_id}] Beacon from {beacon.node_id}, "
            f"drift={drift*1000:.2f}ms"
        )

    def _adapt_timing(self, drift: float):
        """
        Адаптировать локальное время на основе drift.

        Используем экспоненциальное сглаживание для плавной коррекции.
        """
        alpha = 0.3  # Коэффициент сглаживания

        self._drift_history.append(drift)
        if len(self._drift_history) > 10:
            self._drift_history.pop(0)

        # Среднее drift
        avg_drift = sum(self._drift_history) / len(self._drift_history)

        # Корректируем только если drift значительный
        if abs(avg_drift) > self.config.jitter_max_ms / 1000:
            correction = avg_drift * alpha
            self._local_offset -= correction

            logger.debug(
                f"[{self.node_id}] Timing correction: "
                f"{correction*1000:.2f}ms, offset={self._local_offset*1000:.2f}ms"
            )

    def detect_collision(self) -> bool:
        """
        Обнаружить коллизию.

        Коллизия = получили beacon в момент нашей передачи.
        """
        if self.state != SlotState.TRANSMITTING:
            return False

        self.state = SlotState.COLLISION
        self._collision_count += 1

        # Exponential backoff
        backoff = self.config.collision_backoff_ms * (
            2 ** min(self._collision_count, 5)
        )
        backoff += random.uniform(0, backoff / 2)
        self._backoff_until = time.time() + backoff / 1000

        logger.warning(
            f"[{self.node_id}] Collision #{self._collision_count}, "
            f"backoff={backoff:.0f}ms"
        )

        if self.on_collision:
            self.on_collision()

        return True

    def resolve_collision(self):
        """Разрешить коллизию после backoff."""
        if time.time() >= self._backoff_until:
            self.state = SlotState.IDLE
            # Сбрасываем счётчик если долго без коллизий
            if self._collision_count > 0:
                self._collision_count = max(0, self._collision_count - 1)

    def get_sync_status(self) -> Dict:
        """Получить статус синхронизации."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "current_slot": self._calculate_slot(),
            "local_offset_ms": self._local_offset * 1000,
            "neighbors_count": len(self.neighbors),
            "neighbors": {
                nid: {
                    "drift_ms": info.drift * 1000,
                    "beacons": info.beacons_received,
                    "quality": info.quality,
                }
                for nid, info in self.neighbors.items()
            },
            "collision_count": self._collision_count,
            "sequence": self.sequence,
        }

    def calculate_mttd(self) -> float:
        """
        Calculate Mean Time To Detect (обнаружение сбоя).

        MTTD = среднее время между последним beacon и обнаружением проблемы.
        """
        if not self.neighbors:
            return 0.0

        # Среднее время с последнего beacon
        now = time.time()
        times = [now - info.last_seen for info in self.neighbors.values()]
        return sum(times) / len(times)


class MeshSlotNetwork:
    """
    Сеть узлов с slot-based синхронизацией.

    Симуляция для тестирования.
    """

    def __init__(self, num_nodes: int = 5):
        self.nodes: Dict[str, SlotSynchronizer] = {}

        for i in range(num_nodes):
            node_id = f"node-{i:02d}"
            self.nodes[node_id] = SlotSynchronizer(node_id)

    async def start(self):
        """Запустить все узлы."""
        for node in self.nodes.values():
            await node.start()

    async def stop(self):
        """Остановить все узлы."""
        for node in self.nodes.values():
            await node.stop()

    def simulate_beacon(self, from_node: str, to_node: str):
        """Симулировать отправку beacon между узлами."""
        sender = self.nodes.get(from_node)
        receiver = self.nodes.get(to_node)

        if sender and receiver:
            # Создаём beacon
            beacon = Beacon(
                node_id=from_node,
                sequence=sender.sequence,
                timestamp_local=sender.now(),
                timestamp_received=0,
                slot_offset=sender._local_offset,
                neighbors=list(sender.neighbors.keys()),
            )

            # Добавляем задержку сети (симуляция)
            network_delay = random.uniform(0.001, 0.005)  # 1-5ms
            beacon.timestamp_local -= network_delay

            receiver.receive_beacon(beacon)

    def get_network_status(self) -> Dict:
        """Получить статус всей сети."""
        return {
            "nodes": {nid: node.get_sync_status() for nid, node in self.nodes.items()},
            "total_nodes": len(self.nodes),
            "avg_mttd": sum(n.calculate_mttd() for n in self.nodes.values())
            / len(self.nodes),
        }


# === Quick Test ===
def _run_test():
    """Test function - call explicitly, don't run on import"""
    import asyncio

    async def test():
        print("🔄 Testing Slot-Based Sync...")

        # Создаём 3 узла
        network = MeshSlotNetwork(num_nodes=3)

        # Симулируем beacon обмен
        for _ in range(5):
            network.simulate_beacon("node-00", "node-01")
            network.simulate_beacon("node-01", "node-02")
            network.simulate_beacon("node-02", "node-00")

        # Статус
        status = network.get_network_status()
        print(f"✅ Network: {status['total_nodes']} nodes")
        print(f"✅ Avg MTTD: {status['avg_mttd']*1000:.2f}ms")

        for nid, node_status in status["nodes"].items():
            print(
                f"   {nid}: offset={node_status['local_offset_ms']:.2f}ms, "
                f"neighbors={node_status['neighbors_count']}"
            )

    asyncio.run(test())


if __name__ == "__main__":
    _run_test()
