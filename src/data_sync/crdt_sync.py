"""
CRDT Synchronization (P1)
------------------------
Implements several CRDT types and a lightweight sync manager abstraction.
Designed for integration with mesh networking layer in later phases.
"""

from __future__ import annotations

import asyncio  # Add this import
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Set

# Import CRDT implementations from crdt.py
from .crdt import GCounter, GSet, LWWMap, LWWRegister, ORSet, PNCounter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Interface
# ---------------------------------------------------------------------------
class CRDT(ABC):
    @abstractmethod
    def merge(self, other: "CRDT"):
        pass

    @abstractmethod
    def value(self) -> Any:
        pass


# ---------------------------------------------------------------------------
# Sync Manager
# ---------------------------------------------------------------------------
class CRDTSync:
    def __init__(
        self, node_id: str, mesh_router: Optional[Any] = None
    ):  # Optional[Any] to avoid circular dependency for type hint
        self.node_id = node_id
        self.crdts: Dict[str, CRDT] = {}
        self.sync_callbacks: Set[Callable[[Dict[str, Any]], None]] = set()
        self.mesh_router = mesh_router  # Store the mesh router instance

        if self.mesh_router:
            self.mesh_router.set_crdt_sync_callback(self._receive_updates_from_peer)
            logger.info(f"[{self.node_id}] CRDTSync registered with MeshRouter.")

    def register_crdt(self, key: str, crdt: CRDT):
        self.crdts[key] = crdt
        logger.info(
            f"[{self.node_id}] Registered CRDT key={key} type={crdt.__class__.__name__}"
        )

    def merge_from_peer(self, peer_id: str, updates: Dict[str, CRDT]):
        logger.info(
            f"[{self.node_id}] Merge from peer={peer_id} keys={list(updates.keys())}"
        )
        for key, peer_crdt in updates.items():
            if key in self.crdts:
                self.crdts[key].merge(peer_crdt)

    def get_crdt_state(self) -> Dict[str, Any]:
        return {key: crdt.value() for key, crdt in self.crdts.items()}

    def broadcast(self):
        state = self.get_crdt_state()
        logger.debug(f"[{self.node_id}] Broadcast state={state}")
        for cb in list(self.sync_callbacks):
            try:
                cb(state)
            except Exception as e:  # pragma: no cover
                logger.error(f"Sync callback error: {e}")

    def register_sync_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self.sync_callbacks.add(cb)

    async def start_sync(self, interval_sec: int = 5):
        """Запустить периодическую синхронизацию CRDT с другими узлами."""
        if not self.mesh_router:
            logger.warning(
                f"[{self.node_id}] MeshRouter not provided, CRDT sync will not start."
            )
            return

        self._sync_task = asyncio.create_task(self._periodic_sync_loop(interval_sec))
        logger.info(
            f"[{self.node_id}] CRDT sync started with interval {interval_sec} seconds."
        )

    async def stop_sync(self):
        """Остановить периодическую синхронизацию CRDT."""
        if hasattr(self, "_sync_task") and self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info(f"[{self.node_id}] CRDT sync stopped.")

    async def _periodic_sync_loop(self, interval_sec: int):
        """Периодический цикл для отправки CRDT-обновлений."""
        while True:
            await asyncio.sleep(interval_sec)
            await self._send_updates_to_peers()

    async def _send_updates_to_peers(self):
        """Отправить текущее состояние CRDT всем известным пирам."""
        if not self.mesh_router:
            return

        current_state_data = {key: crdt.to_dict() for key, crdt in self.crdts.items()}
        if not current_state_data:
            logger.debug(f"[{self.node_id}] No CRDTs to send updates for.")
            return

        # Получаем список всех известных пиров из MeshRouter
        known_peers = [
            route.destination
            for routes in self.mesh_router.get_routes().values()
            for route in routes
        ]
        known_peers = list(set(known_peers) - {self.node_id})  # Исключаем самого себя

        if not known_peers:
            logger.debug(f"[{self.node_id}] No known peers to send CRDT updates to.")
            return

        logger.debug(
            f"[{self.node_id}] Sending CRDT updates to {len(known_peers)} peers: {known_peers}"
        )
        for peer_id in known_peers:
            await self.mesh_router.send_crdt_update(peer_id, current_state_data)

    async def _receive_updates_from_peer(
        self, peer_id: str, updates_data: Dict[str, Any]
    ):
        """
        Обработать полученные CRDT-обновления от пира.
        Этот метод вызывается MeshRouter через _crdt_sync_callback.
        """
        logger.debug(
            f"[{self.node_id}] Received CRDT updates from {peer_id} with keys: {updates_data.keys()}"
        )

        # Для каждого CRDT в полученных обновлениях
        for key, crdt_dict in updates_data.items():
            if key in self.crdts:
                # Десериализуем CRDT из словаря (нужен метод from_dict для каждого CRDT)
                # Предполагаем, что crdt_dict содержит тип CRDT
                crdt_type = self.crdts[key].__class__
                try:
                    # Создаем временный объект CRDT из полученных данных, используя from_dict
                    received_crdt = crdt_type.from_dict(crdt_dict)
                    self.crdts[key].merge(received_crdt)
                    logger.debug(
                        f"[{self.node_id}] Merged CRDT '{key}' from {peer_id}. New value: {self.crdts[key].value()}"
                    )
                except Exception as e:
                    logger.error(
                        f"[{self.node_id}] Failed to merge CRDT '{key}' from {peer_id}: {e}"
                    )
            else:
                logger.debug(
                    f"[{self.node_id}] Received update for unknown CRDT '{key}' from {peer_id}. Ignoring."
                )

        # После слияния, возможно, потребуется вызвать callback для локальных потребителей
        # Но пока не делаем broadcast, чтобы избежать шторма
        # self.broadcast()
