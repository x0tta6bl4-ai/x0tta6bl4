"""
Integration Tests for Scenario 2: Telegram Bot → Node Launch → Status
=====================================================================

Тесты для проверки user journey:
1. Пользователь запускает узел через /launch
2. Пользователь получает статус сети через /status
3. Пользователь закрывает соединение через /close
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.services.node_manager_service import NodeManagerService, UserNode
from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig


@pytest_asyncio.fixture
async def node_manager():
    """Создать экземпляр NodeManagerService."""
    manager = NodeManagerService(base_port=6000)
    await manager.initialize()
    try:
        yield manager
    finally:
        # Cleanup
        for user_node in list(manager.user_nodes.values()):
            try:
                await user_node.mesh_node.stop()
            except:
                pass


@pytest.mark.asyncio
async def test_launch_node_success(node_manager):
    """Тест успешного запуска узла."""
    user_id = 12345
    
    result = await node_manager.launch_node(user_id)
    
    assert result["success"] is True
    assert "node_id" in result
    assert result["node_id"].startswith(f"user-{user_id}-")
    assert "port" in result
    assert result["port"] >= 6000
    assert user_id in node_manager.user_nodes
    
    # Проверяем, что узел запущен
    user_node = node_manager.user_nodes[user_id]
    assert user_node.is_active is True
    assert user_node.user_id == user_id


@pytest.mark.asyncio
async def test_launch_node_already_running(node_manager):
    """Тест запуска узла, когда он уже запущен."""
    user_id = 12345
    
    # Первый запуск
    result1 = await node_manager.launch_node(user_id)
    assert result1["success"] is True
    
    # Второй запуск (должен вернуть ошибку)
    result2 = await node_manager.launch_node(user_id)
    assert result2["success"] is False
    assert "уже запущен" in result2["error"].lower() or "already" in result2["error"].lower()


@pytest.mark.asyncio
async def test_get_network_status_success(node_manager):
    """Тест получения статуса сети."""
    user_id = 12345
    
    # Запускаем узел
    launch_result = await node_manager.launch_node(user_id)
    assert launch_result["success"] is True
    
    # Получаем статус
    status = await node_manager.get_network_status(user_id)
    
    assert status["success"] is True
    assert status["node_id"] == launch_result["node_id"]
    assert status["port"] == launch_result["port"]
    assert "peers" in status
    assert "routes" in status
    assert "connections" in status


@pytest.mark.asyncio
async def test_get_network_status_node_not_launched(node_manager):
    """Тест получения статуса, когда узел не запущен."""
    user_id = 99999
    
    status = await node_manager.get_network_status(user_id)
    
    assert status["success"] is False
    assert "не запущен" in status["error"].lower() or "not launched" in status["error"].lower()


@pytest.mark.asyncio
async def test_close_connection_all(node_manager):
    """Тест закрытия всех соединений."""
    user_id = 12345
    
    # Запускаем узел
    await node_manager.launch_node(user_id)
    
    # Создаём тестовые соединения
    node_manager.connections["conn-1"] = {"user_id": user_id, "type": "test"}
    node_manager.connections["conn-2"] = {"user_id": user_id, "type": "test"}
    node_manager.connections["conn-3"] = {"user_id": 99999, "type": "test"}  # Другой пользователь
    
    # Закрываем все соединения пользователя
    result = await node_manager.close_connection(user_id)
    
    assert result["success"] is True
    assert result["count"] == 2
    assert "conn-1" in result["closed"]
    assert "conn-2" in result["closed"]
    assert "conn-3" not in result["closed"]  # Другой пользователь
    assert "conn-1" not in node_manager.connections
    assert "conn-2" not in node_manager.connections
    assert "conn-3" in node_manager.connections  # Должно остаться


@pytest.mark.asyncio
async def test_close_connection_specific(node_manager):
    """Тест закрытия конкретного соединения."""
    user_id = 12345
    
    # Запускаем узел
    await node_manager.launch_node(user_id)
    
    # Создаём тестовые соединения
    node_manager.connections["conn-1"] = {"user_id": user_id, "type": "test"}
    node_manager.connections["conn-2"] = {"user_id": user_id, "type": "test"}
    
    # Закрываем конкретное соединение
    result = await node_manager.close_connection(user_id, "conn-1")
    
    assert result["success"] is True
    assert result["count"] == 1
    assert "conn-1" in result["closed"]
    assert "conn-1" not in node_manager.connections
    assert "conn-2" in node_manager.connections  # Должно остаться


@pytest.mark.asyncio
async def test_close_connection_no_connections(node_manager):
    """Тест закрытия соединений, когда их нет."""
    user_id = 12345
    
    # Запускаем узел
    await node_manager.launch_node(user_id)
    
    # Пытаемся закрыть соединения (их нет)
    result = await node_manager.close_connection(user_id)
    
    assert result["success"] is False
    assert "нет активных" in result["error"].lower() or "no active" in result["error"].lower()


@pytest.mark.asyncio
async def test_stop_node(node_manager):
    """Тест остановки узла."""
    user_id = 12345
    
    # Запускаем узел
    await node_manager.launch_node(user_id)
    assert user_id in node_manager.user_nodes
    
    # Создаём соединения
    node_manager.connections["conn-1"] = {"user_id": user_id, "type": "test"}
    
    # Останавливаем узел
    result = await node_manager.stop_node(user_id)
    
    assert result["success"] is True
    assert user_id not in node_manager.user_nodes
    assert "conn-1" not in node_manager.connections  # Соединения должны быть закрыты


@pytest.mark.asyncio
async def test_get_global_status(node_manager):
    """Тест получения глобального статуса."""
    # Запускаем несколько узлов
    await node_manager.launch_node(111)
    await node_manager.launch_node(222)
    await node_manager.launch_node(333)
    
    # Создаём соединения
    node_manager.connections["conn-1"] = {"user_id": 111, "type": "test"}
    node_manager.connections["conn-2"] = {"user_id": 222, "type": "test"}
    
    # Получаем глобальный статус
    status = await node_manager.get_global_status()
    
    assert status["total_nodes"] == 3
    assert status["active_nodes"] == 3
    assert status["total_connections"] == 2
    assert len(status["nodes"]) == 3


@pytest.mark.asyncio
async def test_multiple_users_independent(node_manager):
    """Тест независимости узлов разных пользователей."""
    user1_id = 111
    user2_id = 222
    
    # Запускаем узлы для двух пользователей
    result1 = await node_manager.launch_node(user1_id)
    result2 = await node_manager.launch_node(user2_id)
    
    assert result1["success"] is True
    assert result2["success"] is True
    assert result1["node_id"] != result2["node_id"]
    assert result1["port"] != result2["port"]
    
    # Проверяем статус каждого
    status1 = await node_manager.get_network_status(user1_id)
    status2 = await node_manager.get_network_status(user2_id)
    
    assert status1["success"] is True
    assert status2["success"] is True
    assert status1["node_id"] != status2["node_id"]


@pytest.mark.asyncio
async def test_bootstrap_nodes(node_manager):
    """Тест запуска узла с bootstrap nodes."""
    user_id = 12345
    bootstrap = [("127.0.0.1", 5000), ("127.0.0.1", 5001)]
    
    result = await node_manager.launch_node(user_id, bootstrap_nodes=bootstrap)
    
    assert result["success"] is True
    user_node = node_manager.user_nodes[user_id]
    assert user_node.mesh_node.config.bootstrap_nodes == bootstrap


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

