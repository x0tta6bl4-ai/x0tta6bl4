"""
Interactive Demo API для x0tta6bl4
Позволяет пользователям "ломать" узлы и видеть self-healing в действии
"""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import time
import uuid
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="x0tta6bl4 Interactive Demo API",
    description="Interactive demo where users can break nodes and see self-healing",
    version="1.0.0"
)

# CORS для frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class MeshNode:
    """Узел в mesh сети"""
    id: str
    x: float = 0.0
    y: float = 0.0
    status: NodeStatus = NodeStatus.HEALTHY
    last_failure: Optional[float] = None
    recovery_time: Optional[float] = None


@dataclass
class MeshLink:
    """Связь между узлами"""
    source: str
    target: str
    status: str = "healthy"


@dataclass
class DemoSession:
    """Демо-сессия"""
    session_id: str
    nodes: Dict[str, MeshNode] = field(default_factory=dict)
    links: List[MeshLink] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    
    def add_event(self, event_type: str, node_id: str, data: Dict = None):
        """Добавить событие в timeline"""
        self.events.append({
            "timestamp": time.time(),
            "type": event_type,
            "node_id": node_id,
            "data": data or {}
        })


class InteractiveDemo:
    """Управление интерактивными демо-сессиями"""
    
    def __init__(self):
        self.sessions: Dict[str, DemoSession] = {}
        self._cleanup_task = None
    
    def create_session(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=100 + (i // 3) * 200
            )
        
        # Создать связи (mesh topology)
        links = []
        node_ids = list(nodes.keys())
        for i, node_id in enumerate(node_ids):
            # Каждый узел связан с соседними
            if i > 0:
                links.append(MeshLink(source=node_ids[i-1], target=node_id))
            if i < len(node_ids) - 1:
                links.append(MeshLink(source=node_id, target=node_ids[i+1]))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    async def destroy_node(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=400, detail="Node already failed")
        
        start_time = time.time()
        
        # 1. Узел падает
        node.status = NodeStatus.FAILED
        node.last_failure = start_time
        session.add_event("node_failed", node_id, {"timestamp": start_time})
        
        # Обновить связи
        for link in session.links:
            if link.source == node_id or link.target == node_id:
                link.status = "failed"
        
        await asyncio.sleep(0.3)  # Симуляция задержки
        
        # 2. Обнаружение аномалии (20 секунд в реальности, 0.5s в демо)
        detection_time = time.time()
        session.add_event("anomaly_detected", node_id, {
            "detection_time": detection_time - start_time,
            "confidence": 0.98
        })
        
        await asyncio.sleep(0.5)
        
        # 3. Восстановление (<3 минуты в реальности, 1-2s в демо)
        node.status = NodeStatus.RECOVERING
        session.add_event("recovery_initiated", node_id, {
            "timestamp": time.time()
        })
        
        # Симуляция времени восстановления (1-2 секунды)
        recovery_duration = 1.0 + (hash(node_id) % 100) / 100.0  # 1.0-2.0 секунды
        await asyncio.sleep(recovery_duration)
        
        # 4. Узел восстановлен
        recovery_time = time.time()
        node.status = NodeStatus.HEALTHY
        node.recovery_time = recovery_time - start_time
        session.add_event("node_recovered", node_id, {
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time
        })
        
        # Восстановить связи
        for link in session.links:
            if link.source == node_id or link.target == node_id:
                link.status = "healthy"
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    def get_session_status(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "nodes": [
                {
                    "id": node.id,
                    "x": node.x,
                    "y": node.y,
                    "status": node.status.value,
                    "recovery_time": node.recovery_time
                }
                for node in session.nodes.values()
            ],
            "links": [
                {
                    "source": link.source,
                    "target": link.target,
                    "status": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def reset_session(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Сбросить все узлы
        for node in session.nodes.values():
            node.status = NodeStatus.HEALTHY
            node.last_failure = None
            node.recovery_time = None
        
        # Сбросить все связи
        for link in session.links:
            link.status = "healthy"
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}


# Глобальный экземпляр
demo_manager = InteractiveDemo()


@app.post("/api/demo/interactive/create")
async def create_demo(num_nodes: int = 5):
    """Создать новую демо-сессию"""
    if num_nodes < 3 or num_nodes > 10:
        raise HTTPException(status_code=400, detail="num_nodes must be between 3 and 10")
    
    session_id = demo_manager.create_session(num_nodes=num_nodes)
    return {
        "session_id": session_id,
        "num_nodes": num_nodes,
        "message": "Demo session created"
    }


@app.post("/api/demo/interactive/destroy/{session_id}/{node_id}")
async def destroy_node(session_id: str, node_id: str):
    """'Сломать' узел и запустить self-healing"""
    result = await demo_manager.destroy_node(session_id, node_id)
    return result


@app.get("/api/demo/interactive/status/{session_id}")
async def get_status(session_id: str):
    """Получить статус сессии"""
    return demo_manager.get_session_status(session_id)


@app.post("/api/demo/interactive/reset/{session_id}")
async def reset_session(session_id: str):
    """Сбросить сессию"""
    return demo_manager.reset_session(session_id)


@app.get("/api/demo/interactive/metrics/{session_id}")
async def get_metrics(session_id: str):
    """Получить метрики сессии"""
    session = demo_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Подсчитать метрики
    total_failures = sum(1 for e in session.events if e["type"] == "node_failed")
    total_recoveries = sum(1 for e in session.events if e["type"] == "node_recovered")
    
    recovery_times = [
        e["data"].get("recovery_time", 0)
        for e in session.events
        if e["type"] == "node_recovered" and e["data"].get("recovery_time")
    ]
    
    avg_mttr = sum(recovery_times) / len(recovery_times) if recovery_times else 0
    
    return {
        "total_failures": total_failures,
        "total_recoveries": total_recoveries,
        "avg_mttr": round(avg_mttr, 2),
        "uptime_percent": 100.0 if total_failures == 0 else (total_recoveries / total_failures * 100),
        "healthy_nodes": sum(1 for n in session.nodes.values() if n.status == NodeStatus.HEALTHY),
        "total_nodes": len(session.nodes)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)

