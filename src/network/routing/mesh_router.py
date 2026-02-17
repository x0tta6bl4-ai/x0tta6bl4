"""
MeshRouter - AODV-like Routing Protocol для x0tta6bl4.
Multi-hop forwarding с reactive route discovery.
"""

import asyncio
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PacketType(Enum):
    """Типы пакетов маршрутизации."""

    DATA = 0x01  # Данные приложения
    RREQ = 0x02  # Route Request
    RREP = 0x03  # Route Reply
    RERR = 0x04  # Route Error
    HELLO = 0x05  # Hello/keepalive
    CRDT_SYNC = 0x06  # CRDT Synchronization data


@dataclass
class RouteEntry:
    """Запись в routing table."""

    destination: str
    next_hop: str
    hop_count: int
    seq_num: int
    timestamp: float = field(default_factory=time.time)
    valid: bool = True
    path: List[str] = field(default_factory=list)  # Добавляем путь в RouteEntry

    @property
    def age(self) -> float:
        return time.time() - self.timestamp


@dataclass
class RoutingPacket:
    """Пакет маршрутизации."""

    packet_type: PacketType
    source: str
    destination: str
    seq_num: int
    hop_count: int
    ttl: int
    payload: bytes
    packet_id: str = field(default_factory=lambda: secrets.token_hex(8))
    # Новое поле для отслеживания пройденного пути (для Node-Disjointness)
    path_traversed: List[str] = field(default_factory=list)

    def to_bytes(self) -> bytes:
        header = {
            "type": self.packet_type.value,
            "src": self.source,
            "dst": self.destination,
            "seq": self.seq_num,
            "hops": self.hop_count,
            "ttl": self.ttl,
            "id": self.packet_id,
            "path": self.path_traversed,  # Добавляем путь в заголовок
        }
        header_bytes = json.dumps(header).encode()
        return len(header_bytes).to_bytes(2, "big") + header_bytes + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "RoutingPacket":
        header_len = int.from_bytes(data[:2], "big")
        header = json.loads(data[2 : 2 + header_len].decode())
        payload = data[2 + header_len :]

        return cls(
            packet_type=PacketType(header["type"]),
            source=header["src"],
            destination=header["dst"],
            seq_num=header["seq"],
            hop_count=header["hops"],
            ttl=header["ttl"],
            payload=payload,
            packet_id=header["id"],
            path_traversed=header.get(
                "path", []
            ),  # Извлекаем путь, по умолчанию пустой список
        )


class MeshRouter:
    """
    AODV-like Mesh Router.

    Features:
    - Reactive route discovery (RREQ/RREP)
    - Multi-hop forwarding
    - Route maintenance
    - Loop prevention via TTL and sequence numbers
    """

    DEFAULT_TTL = 16
    ROUTE_TIMEOUT = 60.0  # секунды
    RREQ_TIMEOUT = 5.0  # таймаут ожидания RREP

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.seq_num = 0

        # Routing table: destination -> List[RouteEntry]
        self._routes: Dict[str, List[RouteEntry]] = {}

        # Pending route requests
        self._pending_rreq: Dict[str, asyncio.Future] = {}

        # Seen packet IDs (for deduplication)
        self._seen_packets: Set[str] = set()
        self._seen_cleanup_task: Optional[asyncio.Task] = None

        # Callbacks
        self._send_callback: Optional[Callable] = (
            None  # (packet_bytes, next_hop) -> bool
        )
        self._receive_callback: Optional[Callable[[str, bytes], None]] = None
        self._crdt_sync_callback: Optional[Callable[[Dict[str, Any]], None]] = (
            None  # (crdt_data) -> None
        )

        # Statistics
        self._stats = {
            "packets_sent": 0,
            "packets_received": 0,
            "packets_forwarded": 0,
            "packets_dropped": 0,
            "rreq_sent": 0,
            "rreq_received": 0,
            "rrep_sent": 0,
            "rrep_received": 0,
            "routes_discovered": 0,
        }
        self._stats_lock = asyncio.Lock()

    async def start(self):
        """Запустить router."""
        self._seen_cleanup_task = asyncio.create_task(self._cleanup_seen_packets())
        logger.info(f"MeshRouter started for {self.node_id}")

    async def stop(self):
        """Остановить router."""
        if self._seen_cleanup_task:
            self._seen_cleanup_task.cancel()
            try:
                await self._seen_cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info(f"MeshRouter stopped for {self.node_id}")

    async def _cleanup_seen_packets(self):
        """Периодически очищать кэш обработанных packet_id."""
        while True:
            await asyncio.sleep(self.ROUTE_TIMEOUT)
            self._seen_packets.clear()

    def set_send_callback(self, callback: Callable):
        """Установить callback для отправки пакетов."""
        self._send_callback = callback

    def set_receive_callback(self, callback: Callable):
        """Установить callback для отправки пакетов."""
        self._receive_callback = callback

    def set_crdt_sync_callback(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ):  # Changed callback signature
        """Установить callback для полученных CRDT-данных."""
        self._crdt_sync_callback = callback

    def add_neighbor(self, neighbor_id: str):
        """Добавить прямого соседа (1 hop)."""
        new_entry = RouteEntry(
            destination=neighbor_id,
            next_hop=neighbor_id,
            hop_count=1,
            seq_num=0,
            path=[self.node_id, neighbor_id],  # Direct path
        )

        if neighbor_id not in self._routes:
            self._routes[neighbor_id] = []

        # Check if a direct route already exists and update it
        found = False
        for i, entry in enumerate(self._routes[neighbor_id]):
            if entry.next_hop == neighbor_id and entry.hop_count == 1:
                self._routes[neighbor_id][i] = new_entry
                found = True
                break

        if not found:
            self._routes[neighbor_id].append(new_entry)

        logger.debug(f"Added/Updated neighbor route: {neighbor_id}")

    def remove_neighbor(self, neighbor_id: str):
        """Удалить соседа и связанные маршруты."""
        # Remove direct routes to the neighbor
        if neighbor_id in self._routes:
            del self._routes[neighbor_id]
            logger.debug(f"Removed direct routes to neighbor: {neighbor_id}")

        # Invalidate/remove routes that use this neighbor as a next_hop
        destinations_to_clean = list(self._routes.keys())  # Operate on a copy
        for dest in destinations_to_clean:
            if dest == neighbor_id:  # Already handled direct routes above
                continue

            initial_route_count = len(self._routes[dest])
            self._routes[dest] = [
                route for route in self._routes[dest] if route.next_hop != neighbor_id
            ]

            if len(self._routes[dest]) < initial_route_count:
                logger.debug(
                    f"Invalidated/Removed routes to {dest} through {neighbor_id}. Remaining routes: {len(self._routes[dest])}"
                )

            if not self._routes[dest]:
                del self._routes[dest]
                logger.debug(f"No routes left for {dest}, removing from routing table.")

        logger.debug(f"Finished processing neighbor removal: {neighbor_id}")

    def get_route(self, destination: str) -> List[RouteEntry]:
        """Получить все активные маршруты к destination, отсортированные по качеству."""
        routes_for_dest = self._routes.get(destination, [])

        valid_routes = [
            route
            for route in routes_for_dest
            if route.valid and route.age < self.ROUTE_TIMEOUT
        ]

        # Sort by:
        # 1. Lower hop_count (primary)
        # 2. Higher seq_num (secondary, for same hop_count)
        valid_routes.sort(key=lambda route: (route.hop_count, -route.seq_num))

        return valid_routes

    def get_routes(self) -> Dict[str, List[RouteEntry]]:
        """Получить все активные маршруты."""
        active_routes: Dict[str, List[RouteEntry]] = {}
        for dest, routes_list in self._routes.items():
            valid_routes = [
                route
                for route in routes_list
                if route.valid and route.age < self.ROUTE_TIMEOUT
            ]
            if valid_routes:
                active_routes[dest] = valid_routes
        return active_routes

    async def send(self, destination: str, payload: bytes) -> bool:
        """
        Отправить данные к destination.
        Автоматически выполняет route discovery если нужно, и пытается использовать
        альтернативные маршруты при неудаче.
        """
        # Проверяем локальную доставку
        if destination == self.node_id:
            if self._receive_callback:
                await self._receive_callback(self.node_id, payload)
            return True

        routes_to_try = self.get_route(destination)

        if not routes_to_try:
            # Route discovery
            logger.info(f"No existing routes to {destination}, starting discovery...")
            discovered_route = await self._discover_route(destination)
            if discovered_route:
                # After discovery, re-fetch routes as _update_route would have added the new one
                routes_to_try = self.get_route(destination)

            if not routes_to_try:
                logger.warning(
                    f"Route discovery failed for {destination} and no routes found."
                )
                async with self._stats_lock:
                    self._stats["packets_dropped"] += 1
                return False

        # Try sending through available routes
        for route in routes_to_try:
            # Создаём DATA пакет
            self.seq_num += 1
            packet = RoutingPacket(
                packet_type=PacketType.DATA,
                source=self.node_id,
                destination=destination,
                seq_num=self.seq_num,
                hop_count=0,
                ttl=self.DEFAULT_TTL,
                payload=payload,
            )

            logger.debug(
                f"Attempting to send packet to {destination} via next_hop {route.next_hop} (hops: {route.hop_count})"
            )
            send_successful = await self._send_packet(packet, route.next_hop)

            if send_successful:
                logger.debug(
                    f"Packet sent successfully to {destination} via {route.next_hop}"
                )
                return True
            else:
                logger.warning(
                    f"Failed to send packet to {destination} via {route.next_hop}. Initiating route failure handling."
                )
                await self._handle_route_failure(destination, route.next_hop)
                # Continue loop to try next route if available

        logger.error(f"All available routes to {destination} failed to send packet.")
        async with self._stats_lock:
            self._stats["packets_dropped"] += 1
        return False

    async def handle_packet(self, data: bytes, from_neighbor: str):
        """Обработать входящий пакет."""
        try:
            packet = RoutingPacket.from_bytes(data)
        except Exception as e:
            logger.error(f"Failed to parse packet: {e}")
            return

        # Дедупликация
        if packet.packet_id in self._seen_packets:
            return
        self._seen_packets.add(packet.packet_id)

        async with self._stats_lock:
            self._stats["packets_received"] += 1

        # Обновляем обратный маршрут к source
        self._update_route(
            packet.source, from_neighbor, packet.hop_count + 1, packet.seq_num
        )

        # Обрабатываем по типу
        if packet.packet_type == PacketType.DATA:
            await self._handle_data(packet, from_neighbor)
        elif packet.packet_type == PacketType.RREQ:
            await self._handle_rreq(packet, from_neighbor)
        elif packet.packet_type == PacketType.RREP:
            await self._handle_rrep(packet, from_neighbor)
        elif packet.packet_type == PacketType.RERR:
            await self._handle_rerr(packet, from_neighbor)
        elif packet.packet_type == PacketType.CRDT_SYNC:
            await self._handle_crdt_sync(packet, from_neighbor)

    async def _handle_data(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать DATA пакет."""
        if packet.destination == self.node_id:
            # Для нас - доставляем приложению
            logger.debug(f"Received data from {packet.source}")
            if self._receive_callback:
                await self._receive_callback(packet.source, packet.payload)
        else:
            # Forwarding
            await self._forward_packet(packet)

    async def _handle_rreq(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать Route Request."""
        async with self._stats_lock:
            self._stats["rreq_received"] += 1
        target = packet.payload.decode()

        # Если наш ID уже в пути, дропаем RREQ (loop prevention / node-disjointness)
        if self.node_id in packet.path_traversed:
            logger.debug(
                f"RREQ for {target} dropped: Node {self.node_id} already in path_traversed."
            )
            async with self._stats_lock:
                self._stats["packets_dropped"] += 1
            return

        # Добавляем текущий узел в path_traversed для дальнейшей обработки
        current_path_traversed = packet.path_traversed + [self.node_id]

        logger.debug(
            f"RREQ from {packet.source} for {target} via {from_neighbor}, path: {current_path_traversed}"
        )

        # Обновляем обратный маршрут к source, используя расширенный path_traversed
        self._update_route(
            packet.source,
            from_neighbor,
            packet.hop_count + 1,
            packet.seq_num,
            current_path_traversed,
        )

        if target == self.node_id:
            # Мы - цель, отправляем RREP
            # Передаем path_traversed из RREQ, чтобы RREP знал полный путь
            await self._send_rrep(packet.source, from_neighbor, current_path_traversed)
        else:
            # Проверяем есть ли у нас маршрут к цели
            routes = self.get_route(target)
            if routes:
                # Отвечаем за цель (proxy reply)
                # Передаем path_traversed из RREQ, чтобы RREP знал полный путь
                await self._send_rrep(
                    packet.source,
                    from_neighbor,
                    current_path_traversed,
                    target,
                    routes[0].hop_count,
                )
            else:
                # Пересылаем RREQ, добавляя себя в path_traversed
                # Создаем новый пакет, чтобы не менять оригинальный, который мог быть нужен для _update_route
                forward_packet = RoutingPacket(
                    packet_type=packet.packet_type,
                    source=packet.source,
                    destination=packet.destination,
                    seq_num=packet.seq_num,
                    hop_count=packet.hop_count,
                    ttl=packet.ttl,
                    payload=packet.payload,
                    packet_id=packet.packet_id,
                    path_traversed=current_path_traversed,  # Используем расширенный path_traversed
                )
                await self._forward_packet(forward_packet)

    async def _handle_rrep(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать Route Reply."""
        async with self._stats_lock:
            self._stats["rrep_received"] += 1

        # Парсим payload: теперь это JSON
        rrep_data = json.loads(packet.payload.decode())
        target = rrep_data["target"]
        hop_count = rrep_data["hop_count"]
        path_to_target = rrep_data["path"]

        logger.debug(
            f"RREP: route to {target} via {from_neighbor}, hops={hop_count}, path: {path_to_target}"
        )

        # The rrep_data["hop_count"] is hop_count from RREP_RESPONDER to TARGET_NODE.
        # So, the hop count from self.node_id to target: (hop_count_from_RREP_RESPONDER_to_TARGET_NODE) + 1 (for from_neighbor).
        final_hop_count = rrep_data["hop_count"] + 1

        self._update_route(
            target, from_neighbor, final_hop_count, packet.seq_num, path_to_target
        )

        if packet.destination == self.node_id:
            # RREP для нас - завершаем route discovery
            if target in self._pending_rreq:
                future = self._pending_rreq.pop(target)
                if not future.done():
                    # get_route(target) now returns a list of routes. We need to set the result to the best one.
                    best_routes = self.get_route(target)
                    if best_routes:
                        future.set_result(
                            best_routes[0]
                        )  # Return the single best route
                    else:
                        future.set_result(None)  # No route found after all
        else:
            # Пересылаем RREP к источнику
            await self._forward_packet(packet)

    async def _handle_rerr(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать Route Error."""
        broken_dest = packet.payload.decode()

        # Инвалидируем маршрут
        if broken_dest in self._routes:
            for route in self._routes[broken_dest]:
                route.valid = False

        # Пересылаем RERR
        await self._forward_packet(packet)

    async def _handle_crdt_sync(self, packet: RoutingPacket, from_neighbor: str):
        """Обработать CRDT_SYNC пакет."""
        if packet.destination == self.node_id:
            # Для нас - передаем CRDTSync менеджеру
            logger.debug(f"Received CRDT_SYNC from {packet.source}")
            if self._crdt_sync_callback:
                try:
                    crdt_data = json.loads(packet.payload.decode("utf-8"))
                    # В CRDTSync менеджер нужно передать peer_id и crdt_data
                    await self._crdt_sync_callback(packet.source, crdt_data)
                except Exception as e:
                    logger.error(f"Failed to parse or process CRDT_SYNC payload: {e}")
            else:
                logger.warning(
                    "No CRDT sync callback configured to handle received CRDT_SYNC packet."
                )
        else:
            # Forwarding
            await self._forward_packet(packet)

    async def _forward_packet(self, packet: RoutingPacket):
        """Переслать пакет к следующему hop."""
        # Проверяем TTL
        if packet.ttl <= 1:
            logger.debug(f"Packet dropped: TTL expired")
            async with self._stats_lock:
                self._stats["packets_dropped"] += 1
            return

        # Ищем маршрут
        route = self.get_route(packet.destination)

        if not route:
            # Для RREQ - broadcast
            if packet.packet_type == PacketType.RREQ:
                await self._broadcast_packet(packet)
                return
            else:
                logger.warning(f"No route to forward packet to {packet.destination}")
                async with self._stats_lock:
                    self._stats["packets_dropped"] += 1
                return
        # Декрементируем TTL и увеличиваем hop_count
        packet.ttl -= 1
        packet.hop_count += 1

        sent = await self._send_packet(packet, route[0].next_hop)
        async with self._stats_lock:
            if sent:
                self._stats["packets_forwarded"] += 1
            else:
                self._stats["packets_dropped"] += 1

    async def _broadcast_packet(self, packet: RoutingPacket):
        """Broadcast пакет всем соседям."""
        packet.ttl -= 1
        packet.hop_count += 1

        direct_neighbors = []
        for dest, routes in self._routes.items():
            if any(
                route.hop_count == 1
                and route.valid
                and route.age < self.ROUTE_TIMEOUT
                for route in routes
            ):
                direct_neighbors.append(dest)

        for dest in direct_neighbors:
            await self._send_packet(packet, dest)

    async def _send_packet(self, packet: RoutingPacket, next_hop: str) -> bool:
        """Отправить пакет через transport."""
        if not self._send_callback:
            logger.error("No send callback configured")
            return False

        try:
            result = await self._send_callback(packet.to_bytes(), next_hop)
            if result:
                async with self._stats_lock:
                    self._stats["packets_sent"] += 1
            return result
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
            return False

    async def _discover_route(self, destination: str) -> Optional[RouteEntry]:
        """Выполнить route discovery."""
        # Создаём future для ожидания RREP
        future = asyncio.get_event_loop().create_future()
        self._pending_rreq[destination] = future

        # Отправляем RREQ
        self.seq_num += 1
        rreq = RoutingPacket(
            packet_type=PacketType.RREQ,
            source=self.node_id,
            destination=destination,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=destination.encode(),
            path_traversed=[self.node_id],  # Инициализируем с текущим узлом
        )

        await self._broadcast_packet(rreq)
        async with self._stats_lock:
            self._stats["rreq_sent"] += 1

        # Ждём RREP
        try:
            route = await asyncio.wait_for(future, timeout=self.RREQ_TIMEOUT)
            async with self._stats_lock:
                self._stats["routes_discovered"] += 1
            return route
        except asyncio.TimeoutError:
            logger.warning(f"Route discovery timeout for {destination}")
            self._pending_rreq.pop(destination, None)
            return None

    async def _send_rrep(
        self,
        requester: str,
        next_hop: str,
        path_to_target: List[str],
        target: str = None,
        hop_count: int = 0,
    ):
        """Отправить Route Reply."""
        target = target or self.node_id

        self.seq_num += 1
        # RREP payload теперь включает path_to_target
        rrep_payload = json.dumps(
            {"target": target, "hop_count": hop_count, "path": path_to_target}
        ).encode()

        rrep = RoutingPacket(
            packet_type=PacketType.RREP,
            source=self.node_id,
            destination=requester,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=rrep_payload,
        )

        await self._send_packet(rrep, next_hop)
        async with self._stats_lock:
            self._stats["rrep_sent"] += 1

    def _update_route(
        self,
        destination: str,
        next_hop: str,
        hop_count: int,
        seq_num: int,
        path: Optional[List[str]] = None,
    ):
        """Обновить или добавить маршрут."""
        if path is None:
            if next_hop == destination:
                path = [self.node_id, destination]
            else:
                path = [self.node_id, next_hop, destination]

        new_entry = RouteEntry(
            destination=destination,
            next_hop=next_hop,
            hop_count=hop_count,
            seq_num=seq_num,
            path=path,
        )

        if destination not in self._routes:

            self._routes[destination] = [new_entry]

            logger.debug(f"New route added for {destination}: {new_entry}")

            return

        existing_routes = self._routes[destination]

        updated = False

        for i, entry in enumerate(existing_routes):

            # Check if this new entry is an update to an existing path (same next_hop and path)

            # Or if it's an update to an existing next_hop with a better metric

            if (
                entry.next_hop == new_entry.next_hop
            ):  # This identifies the "same" path from our node's perspective

                # Apply AODV-like update rules

                if new_entry.seq_num > entry.seq_num:

                    existing_routes[i] = new_entry

                    updated = True

                    logger.debug(
                        f"Route updated (better seq_num) for {destination}: {new_entry}"
                    )

                    break

                elif (
                    new_entry.seq_num == entry.seq_num
                    and new_entry.hop_count < entry.hop_count
                ):

                    existing_routes[i] = new_entry

                    updated = True

                    logger.debug(
                        f"Route updated (same seq_num, better hop_count) for {destination}: {new_entry}"
                    )

                    break

                elif (
                    new_entry.seq_num == entry.seq_num
                    and new_entry.hop_count == entry.hop_count
                    and new_entry.path != entry.path
                ):

                    # If it's the same next_hop and destination but a different path, this means a different path to the same next_hop

                    # We might want to replace it or add it depending on specific criteria for 'k-disjointness' and path quality.

                    # For now, let's prioritize the first seen route for the same next_hop unless a better metric route is found.

                    # If we need to support multiple paths through the *same* next_hop but with different subsequent hops,

                    # the identifying key would need to be the full path, not just next_hop.

                    # Given 'k-disjoint' refers to multiple paths to the destination, distinct next_hops are more relevant.

                    # Keeping existing for now if metrics are not better.

                    pass

        if not updated:

            # If no existing route was updated, it means it's either a truly new next_hop

            # or not a better metric for an existing next_hop path.

            # Add it as a new distinct path.

            existing_routes.append(new_entry)

            logger.debug(f"New distinct route added for {destination}: {new_entry}")

    async def _handle_route_failure(
        self, broken_destination: str, failed_next_hop: str
    ):
        """

        Handles a route failure by invalidating/removing the problematic route(s)

        and broadcasting an RERR to inform neighbors about the broken link.

        """

        logger.info(
            f"Handling route failure: broken_destination={broken_destination}, failed_next_hop={failed_next_hop}"
        )

        # Invalidate/remove routes that use failed_next_hop for broken_destination

        if broken_destination in self._routes:

            initial_count = len(self._routes[broken_destination])

            self._routes[broken_destination] = [
                route
                for route in self._routes[broken_destination]
                if not (
                    route.next_hop == failed_next_hop
                )  # Remove routes that use the failed next_hop
            ]

            if len(self._routes[broken_destination]) < initial_count:

                logger.debug(
                    f"Removed {initial_count - len(self._routes[broken_destination])} routes to {broken_destination} via {failed_next_hop}."
                )

            if not self._routes[broken_destination]:

                del self._routes[broken_destination]

                logger.debug(
                    f"No routes left for {broken_destination}, removing from routing table."
                )

        # Generate and broadcast an RERR packet for the failed link

        # The RERR should indicate that the link from self.node_id to failed_next_hop is broken.

        # The broken_dest in RERR refers to the destination that is now unreachable via this node.

        rerr_payload = (
            failed_next_hop.encode()
        )  # The broken link's next_hop is the broken destination for other nodes.

        # Need to increment sequence number for RERR

        self.seq_num += 1

        rerr_packet = RoutingPacket(
            packet_type=PacketType.RERR,
            source=self.node_id,
            destination="",  # RERR is broadcast, so destination is not a single node
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=rerr_payload,
        )

        # Broadcast RERR to all neighbors

        await self._broadcast_packet(rerr_packet)

        logger.debug(f"Broadcasted RERR for broken link to {failed_next_hop}.")

    async def send_crdt_update(
        self, destination: str, crdt_data: Dict[str, Any]
    ) -> bool:
        """
        Отправить CRDT-данные к destination.
        """
        if destination == self.node_id:
            # Локальная доставка, если это возможно, или игнорируем
            logger.debug(
                f"CRDT_SYNC: Local delivery to {self.node_id} is not supported directly, expecting peer-to-peer merge."
            )
            return True

        routes_to_try = self.get_route(destination)
        if not routes_to_try:
            logger.warning(
                f"No existing routes to {destination} for CRDT_SYNC, attempting discovery..."
            )
            discovered_route = await self._discover_route(destination)
            if discovered_route:
                routes_to_try = self.get_route(destination)  # Re-fetch routes
            if not routes_to_try:
                logger.warning(f"CRDT_SYNC: Route discovery failed for {destination}.")
                return False

        # Сериализуем CRDT-данные в JSON и затем в байты
        try:
            payload_bytes = json.dumps(crdt_data).encode("utf-8")
        except Exception as e:
            logger.error(f"Failed to serialize CRDT data for {destination}: {e}")
            return False

        # Создаём CRDT_SYNC пакет
        self.seq_num += 1
        packet = RoutingPacket(
            packet_type=PacketType.CRDT_SYNC,
            source=self.node_id,
            destination=destination,
            seq_num=self.seq_num,
            hop_count=0,
            ttl=self.DEFAULT_TTL,
            payload=payload_bytes,
        )

        for route in routes_to_try:
            send_successful = await self._send_packet(packet, route.next_hop)
            if send_successful:
                logger.debug(
                    f"CRDT_SYNC packet sent successfully to {destination} via {route.next_hop}"
                )
                return True
            else:
                logger.warning(
                    f"Failed to send CRDT_SYNC packet to {destination} via {route.next_hop}. Initiating route failure handling."
                )
                await self._handle_route_failure(destination, route.next_hop)

        logger.error(
            f"All available routes to {destination} failed to send CRDT_SYNC packet."
        )
        return False

    async def get_stats(self) -> dict:
        """Получить статистику."""
        async with self._stats_lock:
            stats_copy = {
                "node_id": self.node_id,
                "routes_count": len(self.get_routes()),
                **self._stats,
            }
        return {
            "node_id": self.node_id,
            "routes_count": len(self.get_routes()),
            **stats_copy,
        }

    async def get_mape_k_metrics(self) -> Dict[str, float]:
        """
        Calculates and returns key MAPE-K metrics based on current router statistics.
        """
        async with self._stats_lock:
            # Copy stats to avoid holding lock during calculations
            current_stats = self._stats.copy()

        metrics = {}

        # 1. Packet Drop Rate
        # Considering all packets that this node directly handles (sends, receives, forwards RREQ/RREP)
        total_packets_involved = (
            current_stats["packets_sent"]
            + current_stats[
                "packets_received"
            ]  # Total packets received by this node (including those for forwarding)
            + current_stats["packets_forwarded"]
            + current_stats["rreq_sent"]
            + current_stats["rreq_received"]
            + current_stats["rrep_sent"]
            + current_stats["rrep_received"]
            # Not including RERR or HELLO as they are typically minimal and for control, not data flow.
        )
        if total_packets_involved > 0:
            metrics["packet_drop_rate"] = (
                current_stats["packets_dropped"] / total_packets_involved
            )
        else:
            metrics["packet_drop_rate"] = 0.0

        # 2. Route Discovery Success Rate
        if current_stats["rreq_sent"] > 0:
            metrics["route_discovery_success_rate"] = (
                current_stats["routes_discovered"] / current_stats["rreq_sent"]
            )
        else:
            metrics["route_discovery_success_rate"] = 0.0

        # 3. Total Routes Known
        # Note: get_routes() already filters valid and fresh routes.
        active_routes_dict = self.get_routes()
        metrics["total_routes_known"] = len(active_routes_dict)

        # 4. Average Route Hop Count for active routes
        total_hops = 0
        num_routes_for_avg = 0
        for dest_routes in active_routes_dict.values():
            for route_entry in dest_routes:
                total_hops += route_entry.hop_count
                num_routes_for_avg += 1

        if num_routes_for_avg > 0:
            metrics["avg_route_hop_count"] = total_hops / num_routes_for_avg
        else:
            metrics["avg_route_hop_count"] = 0.0

        # 5. Routing Overhead Ratio (Simplified: Control packets vs Data packets)
        total_routing_control_packets = (
            current_stats["rreq_sent"]
            + current_stats["rreq_received"]
            + current_stats["rrep_sent"]
            + current_stats["rrep_received"]
        )
        # Data packets are those originated by this node and forwarded by this node
        total_data_packets = (
            current_stats["packets_sent"] + current_stats["packets_forwarded"]
        )

        if total_data_packets > 0:
            metrics["routing_overhead_ratio"] = (
                total_routing_control_packets / total_data_packets
            )
        else:
            metrics["routing_overhead_ratio"] = (
                0.0  # If no data packets, no routing overhead from this perspective
            )

        return metrics
