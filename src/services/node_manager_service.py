"""
Node Manager Service
====================
Управление узлами пользователей через Telegram Bot.

Функции:
- Запуск узла для пользователя
- Получение статуса сети
- Закрытие соединения (Tor-like circuit)
"""
import asyncio
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import secrets

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig
from src.network.batman.topology import MeshTopology

logger = logging.getLogger(__name__)


@dataclass
class UserNode:
    """Узел пользователя."""
    user_id: int
    node_id: str
    mesh_node: CompleteMeshNode
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    connection_id: Optional[str] = None  # Для Tor-like circuits


class NodeManagerService:
    """
    Сервис для управления узлами пользователей.
    
    Usage:
        service = NodeManagerService()
        await service.launch_node(user_id=12345)
        status = await service.get_network_status(user_id=12345)
        await service.close_connection(user_id=12345, connection_id="conn-123")
    """
    
    def __init__(self, base_port: int = 5000):
        self.base_port = base_port
        self.user_nodes: Dict[int, UserNode] = {}
        self.connections: Dict[str, Dict] = {}  # connection_id -> connection info
        self._port_counter = base_port
        self._topology: Optional[MeshTopology] = None
        
    async def initialize(self):
        """Инициализация сервиса."""
        # Создаём локальную топологию для отслеживания
        self._topology = MeshTopology(
            mesh_id="x0tta6bl4-mesh",
            local_node_id="coordinator"
        )
        logger.info("NodeManagerService initialized")
    
    async def launch_node(self, user_id: int, bootstrap_nodes: List[tuple] = None) -> Dict:
        """
        Запустить узел для пользователя.
        
        Args:
            user_id: Telegram user ID
            bootstrap_nodes: Список bootstrap узлов [(host, port), ...]
        
        Returns:
            Dict с информацией о запущенном узле
        """
        # Проверяем, есть ли уже узел
        if user_id in self.user_nodes:
            existing = self.user_nodes[user_id]
            if existing.is_active:
                return {
                    "success": False,
                    "error": "Узел уже запущен",
                    "node_id": existing.node_id,
                    "port": existing.mesh_node.config.port
                }
            else:
                # Перезапускаем существующий
                await existing.mesh_node.stop()
                del self.user_nodes[user_id]
        
        # Генерируем уникальный node_id
        node_id = f"user-{user_id}-{secrets.token_hex(4)}"
        
        # Выбираем свободный порт
        port = self._get_next_port()
        
        # Создаём конфигурацию
        config = MeshConfig(
            node_id=node_id,
            port=port,
            enable_discovery=True,
            enable_multicast=True,
            bootstrap_nodes=bootstrap_nodes or [],
            obfuscation="xor",
            traffic_profile="default"
        )
        
        # Создаём и запускаем узел
        try:
            mesh_node = CompleteMeshNode(config)
            await mesh_node.start()
            
            # Сохраняем узел
            user_node = UserNode(
                user_id=user_id,
                node_id=node_id,
                mesh_node=mesh_node
            )
            self.user_nodes[user_id] = user_node
            
            logger.info(f"✅ Node launched for user {user_id}: {node_id} on port {port}")
            
            return {
                "success": True,
                "node_id": node_id,
                "port": port,
                "peers_count": len(mesh_node.get_peers()),
                "status": "running"
            }
        except Exception as e:
            logger.error(f"❌ Failed to launch node for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_network_status(self, user_id: int) -> Dict:
        """
        Получить статус сети для пользователя.
        
        Returns:
            Dict с информацией о сети
        """
        if user_id not in self.user_nodes:
            return {
                "success": False,
                "error": "Узел не запущен. Используйте /launch"
            }
        
        user_node = self.user_nodes[user_id]
        mesh_node = user_node.mesh_node
        
        # Получаем статистику узла
        stats = mesh_node.get_stats()
        peers = mesh_node.get_peers()
        routes = mesh_node.get_routes()
        
        # Формируем ответ
        status = {
            "success": True,
            "node_id": user_node.node_id,
            "port": mesh_node.config.port,
            "running": stats.get("running", False),
            "peers": {
                "count": len(peers),
                "list": peers[:10]  # Первые 10
            },
            "routes": {
                "count": len(routes),
                "destinations": list(routes.keys())[:10]
            },
            "connections": {
                "active": len([c for c in self.connections.values() if c.get("user_id") == user_id]),
                "total": len([c for c in self.connections.values() if c.get("user_id") == user_id])
            }
        }
        
        # Добавляем детали маршрутизации
        if stats.get("routing"):
            status["routing"] = {
                "peers_count": stats["routing"].get("peers_count", 0),
                "routes_cached": stats["routing"].get("routes_cached", 0)
            }
        
        return status
    
    async def close_connection(self, user_id: int, connection_id: Optional[str] = None) -> Dict:
        """
        Закрыть соединение (Tor-like circuit).
        
        Args:
            user_id: Telegram user ID
            connection_id: ID соединения (если None, закрывает все)
        
        Returns:
            Dict с результатом
        """
        if user_id not in self.user_nodes:
            return {
                "success": False,
                "error": "Узел не запущен"
            }
        
        user_node = self.user_nodes[user_id]
        
        # Находим соединения пользователя
        user_connections = [
            (cid, conn) for cid, conn in self.connections.items()
            if conn.get("user_id") == user_id
        ]
        
        if not user_connections:
            return {
                "success": False,
                "error": "Нет активных соединений"
            }
        
        # Закрываем указанное соединение или все
        closed = []
        if connection_id:
            if connection_id in self.connections:
                conn = self.connections[connection_id]
                if conn.get("user_id") == user_id:
                    # Закрываем соединение (здесь можно добавить логику разрыва circuit)
                    del self.connections[connection_id]
                    closed.append(connection_id)
        else:
            # Закрываем все соединения пользователя
            for cid, conn in user_connections:
                del self.connections[cid]
                closed.append(cid)
        
        logger.info(f"✅ Closed {len(closed)} connection(s) for user {user_id}")
        
        return {
            "success": True,
            "closed": closed,
            "count": len(closed)
        }
    
    async def stop_node(self, user_id: int) -> Dict:
        """Остановить узел пользователя."""
        if user_id not in self.user_nodes:
            return {
                "success": False,
                "error": "Узел не запущен"
            }
        
        user_node = self.user_nodes[user_id]
        
        try:
            await user_node.mesh_node.stop()
            user_node.is_active = False
            del self.user_nodes[user_id]
            
            # Закрываем все соединения пользователя
            user_connections = [
                cid for cid, conn in self.connections.items()
                if conn.get("user_id") == user_id
            ]
            for cid in user_connections:
                del self.connections[cid]
            
            logger.info(f"✅ Stopped node for user {user_id}")
            
            return {
                "success": True,
                "message": "Узел остановлен"
            }
        except Exception as e:
            logger.error(f"❌ Failed to stop node for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_next_port(self) -> int:
        """Получить следующий свободный порт."""
        port = self._port_counter
        self._port_counter += 1
        # Если порт занят, пропускаем (в production нужна проверка)
        return port
    
    async def get_global_status(self) -> Dict:
        """Получить глобальный статус сети (для админов)."""
        total_nodes = len(self.user_nodes)
        active_nodes = sum(1 for n in self.user_nodes.values() if n.is_active)
        total_connections = len(self.connections)
        
        return {
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "total_connections": total_connections,
            "nodes": [
                {
                    "user_id": node.user_id,
                    "node_id": node.node_id,
                    "port": node.mesh_node.config.port,
                    "peers": len(node.mesh_node.get_peers())
                }
                for node in self.user_nodes.values() if node.is_active
            ]
        }


# Global instance
_node_manager: Optional[NodeManagerService] = None


async def get_node_manager() -> NodeManagerService:
    """Получить глобальный экземпляр NodeManagerService."""
    global _node_manager
    if _node_manager is None:
        _node_manager = NodeManagerService()
        await _node_manager.initialize()
    return _node_manager

