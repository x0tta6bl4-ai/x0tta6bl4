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
    
    def xǁInteractiveDemoǁ__init____mutmut_orig(self):
        self.sessions: Dict[str, DemoSession] = {}
        self._cleanup_task = None
    
    def xǁInteractiveDemoǁ__init____mutmut_1(self):
        self.sessions: Dict[str, DemoSession] = None
        self._cleanup_task = None
    
    def xǁInteractiveDemoǁ__init____mutmut_2(self):
        self.sessions: Dict[str, DemoSession] = {}
        self._cleanup_task = ""
    
    xǁInteractiveDemoǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁInteractiveDemoǁ__init____mutmut_1': xǁInteractiveDemoǁ__init____mutmut_1, 
        'xǁInteractiveDemoǁ__init____mutmut_2': xǁInteractiveDemoǁ__init____mutmut_2
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁInteractiveDemoǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁInteractiveDemoǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁInteractiveDemoǁ__init____mutmut_orig)
    xǁInteractiveDemoǁ__init____mutmut_orig.__name__ = 'xǁInteractiveDemoǁ__init__'
    
    def xǁInteractiveDemoǁcreate_session__mutmut_orig(self, num_nodes: int = 5) -> str:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_1(self, num_nodes: int = 6) -> str:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_2(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = None
        
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_3(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(None)}_{uuid.uuid4().hex[:8]}"
        
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_4(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:9]}"
        
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_5(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = None
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_6(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(None):
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_7(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = None
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_8(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i - 1}"
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_9(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+2}"
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_10(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = None
        
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_11(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=None,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_12(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=None,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_13(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=None
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_14(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_15(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_16(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_17(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 - (i % 3) * 200,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_18(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=101 + (i % 3) * 200,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_19(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) / 200,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_20(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i / 3) * 200,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_21(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 4) * 200,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_22(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 201,
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_23(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=100 - (i // 3) * 200
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_24(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=101 + (i // 3) * 200
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_25(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=100 + (i // 3) / 200
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_26(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=100 + (i / 3) * 200
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_27(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=100 + (i // 4) * 200
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_28(self, num_nodes: int = 5) -> str:
        """Создать новую демо-сессию"""
        session_id = f"demo_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Создать узлы
        nodes = {}
        for i in range(num_nodes):
            node_id = f"node-{i+1}"
            nodes[node_id] = MeshNode(
                id=node_id,
                x=100 + (i % 3) * 200,
                y=100 + (i // 3) * 201
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_29(self, num_nodes: int = 5) -> str:
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
        links = None
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_30(self, num_nodes: int = 5) -> str:
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
        node_ids = None
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_31(self, num_nodes: int = 5) -> str:
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
        node_ids = list(None)
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_32(self, num_nodes: int = 5) -> str:
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
        for i, node_id in enumerate(None):
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_33(self, num_nodes: int = 5) -> str:
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
            if i >= 0:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_34(self, num_nodes: int = 5) -> str:
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
            if i > 1:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_35(self, num_nodes: int = 5) -> str:
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
                links.append(None)
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_36(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=None, target=node_id))
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_37(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_ids[i-1], target=None))
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_38(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(target=node_id))
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_39(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_ids[i-1], ))
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_40(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_ids[i + 1], target=node_id))
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_41(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_ids[i-2], target=node_id))
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_42(self, num_nodes: int = 5) -> str:
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
            if i <= len(node_ids) - 1:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_43(self, num_nodes: int = 5) -> str:
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
            if i < len(node_ids) + 1:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_44(self, num_nodes: int = 5) -> str:
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
            if i < len(node_ids) - 2:
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
    
    def xǁInteractiveDemoǁcreate_session__mutmut_45(self, num_nodes: int = 5) -> str:
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
                links.append(None)
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_46(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=None, target=node_ids[i+1]))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_47(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_id, target=None))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_48(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(target=node_ids[i+1]))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_49(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_id, ))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_50(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_id, target=node_ids[i - 1]))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_51(self, num_nodes: int = 5) -> str:
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
                links.append(MeshLink(source=node_id, target=node_ids[i+2]))
        
        # Создать сессию
        session = DemoSession(
            session_id=session_id,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_52(self, num_nodes: int = 5) -> str:
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
        session = None
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_53(self, num_nodes: int = 5) -> str:
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
            session_id=None,
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_54(self, num_nodes: int = 5) -> str:
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
            nodes=None,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_55(self, num_nodes: int = 5) -> str:
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
            links=None
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_56(self, num_nodes: int = 5) -> str:
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
            nodes=nodes,
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_57(self, num_nodes: int = 5) -> str:
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
            links=links
        )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_58(self, num_nodes: int = 5) -> str:
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
            )
        self.sessions[session_id] = session
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_59(self, num_nodes: int = 5) -> str:
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
        self.sessions[session_id] = None
        
        logger.info(f"Created demo session: {session_id} with {num_nodes} nodes")
        return session_id
    
    def xǁInteractiveDemoǁcreate_session__mutmut_60(self, num_nodes: int = 5) -> str:
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
        
        logger.info(None)
        return session_id
    
    xǁInteractiveDemoǁcreate_session__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁInteractiveDemoǁcreate_session__mutmut_1': xǁInteractiveDemoǁcreate_session__mutmut_1, 
        'xǁInteractiveDemoǁcreate_session__mutmut_2': xǁInteractiveDemoǁcreate_session__mutmut_2, 
        'xǁInteractiveDemoǁcreate_session__mutmut_3': xǁInteractiveDemoǁcreate_session__mutmut_3, 
        'xǁInteractiveDemoǁcreate_session__mutmut_4': xǁInteractiveDemoǁcreate_session__mutmut_4, 
        'xǁInteractiveDemoǁcreate_session__mutmut_5': xǁInteractiveDemoǁcreate_session__mutmut_5, 
        'xǁInteractiveDemoǁcreate_session__mutmut_6': xǁInteractiveDemoǁcreate_session__mutmut_6, 
        'xǁInteractiveDemoǁcreate_session__mutmut_7': xǁInteractiveDemoǁcreate_session__mutmut_7, 
        'xǁInteractiveDemoǁcreate_session__mutmut_8': xǁInteractiveDemoǁcreate_session__mutmut_8, 
        'xǁInteractiveDemoǁcreate_session__mutmut_9': xǁInteractiveDemoǁcreate_session__mutmut_9, 
        'xǁInteractiveDemoǁcreate_session__mutmut_10': xǁInteractiveDemoǁcreate_session__mutmut_10, 
        'xǁInteractiveDemoǁcreate_session__mutmut_11': xǁInteractiveDemoǁcreate_session__mutmut_11, 
        'xǁInteractiveDemoǁcreate_session__mutmut_12': xǁInteractiveDemoǁcreate_session__mutmut_12, 
        'xǁInteractiveDemoǁcreate_session__mutmut_13': xǁInteractiveDemoǁcreate_session__mutmut_13, 
        'xǁInteractiveDemoǁcreate_session__mutmut_14': xǁInteractiveDemoǁcreate_session__mutmut_14, 
        'xǁInteractiveDemoǁcreate_session__mutmut_15': xǁInteractiveDemoǁcreate_session__mutmut_15, 
        'xǁInteractiveDemoǁcreate_session__mutmut_16': xǁInteractiveDemoǁcreate_session__mutmut_16, 
        'xǁInteractiveDemoǁcreate_session__mutmut_17': xǁInteractiveDemoǁcreate_session__mutmut_17, 
        'xǁInteractiveDemoǁcreate_session__mutmut_18': xǁInteractiveDemoǁcreate_session__mutmut_18, 
        'xǁInteractiveDemoǁcreate_session__mutmut_19': xǁInteractiveDemoǁcreate_session__mutmut_19, 
        'xǁInteractiveDemoǁcreate_session__mutmut_20': xǁInteractiveDemoǁcreate_session__mutmut_20, 
        'xǁInteractiveDemoǁcreate_session__mutmut_21': xǁInteractiveDemoǁcreate_session__mutmut_21, 
        'xǁInteractiveDemoǁcreate_session__mutmut_22': xǁInteractiveDemoǁcreate_session__mutmut_22, 
        'xǁInteractiveDemoǁcreate_session__mutmut_23': xǁInteractiveDemoǁcreate_session__mutmut_23, 
        'xǁInteractiveDemoǁcreate_session__mutmut_24': xǁInteractiveDemoǁcreate_session__mutmut_24, 
        'xǁInteractiveDemoǁcreate_session__mutmut_25': xǁInteractiveDemoǁcreate_session__mutmut_25, 
        'xǁInteractiveDemoǁcreate_session__mutmut_26': xǁInteractiveDemoǁcreate_session__mutmut_26, 
        'xǁInteractiveDemoǁcreate_session__mutmut_27': xǁInteractiveDemoǁcreate_session__mutmut_27, 
        'xǁInteractiveDemoǁcreate_session__mutmut_28': xǁInteractiveDemoǁcreate_session__mutmut_28, 
        'xǁInteractiveDemoǁcreate_session__mutmut_29': xǁInteractiveDemoǁcreate_session__mutmut_29, 
        'xǁInteractiveDemoǁcreate_session__mutmut_30': xǁInteractiveDemoǁcreate_session__mutmut_30, 
        'xǁInteractiveDemoǁcreate_session__mutmut_31': xǁInteractiveDemoǁcreate_session__mutmut_31, 
        'xǁInteractiveDemoǁcreate_session__mutmut_32': xǁInteractiveDemoǁcreate_session__mutmut_32, 
        'xǁInteractiveDemoǁcreate_session__mutmut_33': xǁInteractiveDemoǁcreate_session__mutmut_33, 
        'xǁInteractiveDemoǁcreate_session__mutmut_34': xǁInteractiveDemoǁcreate_session__mutmut_34, 
        'xǁInteractiveDemoǁcreate_session__mutmut_35': xǁInteractiveDemoǁcreate_session__mutmut_35, 
        'xǁInteractiveDemoǁcreate_session__mutmut_36': xǁInteractiveDemoǁcreate_session__mutmut_36, 
        'xǁInteractiveDemoǁcreate_session__mutmut_37': xǁInteractiveDemoǁcreate_session__mutmut_37, 
        'xǁInteractiveDemoǁcreate_session__mutmut_38': xǁInteractiveDemoǁcreate_session__mutmut_38, 
        'xǁInteractiveDemoǁcreate_session__mutmut_39': xǁInteractiveDemoǁcreate_session__mutmut_39, 
        'xǁInteractiveDemoǁcreate_session__mutmut_40': xǁInteractiveDemoǁcreate_session__mutmut_40, 
        'xǁInteractiveDemoǁcreate_session__mutmut_41': xǁInteractiveDemoǁcreate_session__mutmut_41, 
        'xǁInteractiveDemoǁcreate_session__mutmut_42': xǁInteractiveDemoǁcreate_session__mutmut_42, 
        'xǁInteractiveDemoǁcreate_session__mutmut_43': xǁInteractiveDemoǁcreate_session__mutmut_43, 
        'xǁInteractiveDemoǁcreate_session__mutmut_44': xǁInteractiveDemoǁcreate_session__mutmut_44, 
        'xǁInteractiveDemoǁcreate_session__mutmut_45': xǁInteractiveDemoǁcreate_session__mutmut_45, 
        'xǁInteractiveDemoǁcreate_session__mutmut_46': xǁInteractiveDemoǁcreate_session__mutmut_46, 
        'xǁInteractiveDemoǁcreate_session__mutmut_47': xǁInteractiveDemoǁcreate_session__mutmut_47, 
        'xǁInteractiveDemoǁcreate_session__mutmut_48': xǁInteractiveDemoǁcreate_session__mutmut_48, 
        'xǁInteractiveDemoǁcreate_session__mutmut_49': xǁInteractiveDemoǁcreate_session__mutmut_49, 
        'xǁInteractiveDemoǁcreate_session__mutmut_50': xǁInteractiveDemoǁcreate_session__mutmut_50, 
        'xǁInteractiveDemoǁcreate_session__mutmut_51': xǁInteractiveDemoǁcreate_session__mutmut_51, 
        'xǁInteractiveDemoǁcreate_session__mutmut_52': xǁInteractiveDemoǁcreate_session__mutmut_52, 
        'xǁInteractiveDemoǁcreate_session__mutmut_53': xǁInteractiveDemoǁcreate_session__mutmut_53, 
        'xǁInteractiveDemoǁcreate_session__mutmut_54': xǁInteractiveDemoǁcreate_session__mutmut_54, 
        'xǁInteractiveDemoǁcreate_session__mutmut_55': xǁInteractiveDemoǁcreate_session__mutmut_55, 
        'xǁInteractiveDemoǁcreate_session__mutmut_56': xǁInteractiveDemoǁcreate_session__mutmut_56, 
        'xǁInteractiveDemoǁcreate_session__mutmut_57': xǁInteractiveDemoǁcreate_session__mutmut_57, 
        'xǁInteractiveDemoǁcreate_session__mutmut_58': xǁInteractiveDemoǁcreate_session__mutmut_58, 
        'xǁInteractiveDemoǁcreate_session__mutmut_59': xǁInteractiveDemoǁcreate_session__mutmut_59, 
        'xǁInteractiveDemoǁcreate_session__mutmut_60': xǁInteractiveDemoǁcreate_session__mutmut_60
    }
    
    def create_session(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁInteractiveDemoǁcreate_session__mutmut_orig"), object.__getattribute__(self, "xǁInteractiveDemoǁcreate_session__mutmut_mutants"), args, kwargs, self)
        return result 
    
    create_session.__signature__ = _mutmut_signature(xǁInteractiveDemoǁcreate_session__mutmut_orig)
    xǁInteractiveDemoǁcreate_session__mutmut_orig.__name__ = 'xǁInteractiveDemoǁcreate_session'
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_orig(self, session_id: str, node_id: str) -> Dict:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_1(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_2(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(None)
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_3(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if session:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_4(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=None, detail="Session not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_5(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_6(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(detail="Session not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_7(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_8(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=405, detail="Session not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_9(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="XXSession not foundXX")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_10(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_11(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="SESSION NOT FOUND")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_12(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id in session.nodes:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_13(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=None, detail="Node not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_14(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail=None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_15(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(detail="Node not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_16(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_17(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=405, detail="Node not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_18(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="XXNode not foundXX")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_19(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="node not found")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_20(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="NODE NOT FOUND")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_21(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = None
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_22(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status != NodeStatus.FAILED:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_23(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=None, detail="Node already failed")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_24(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=400, detail=None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_25(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(detail="Node already failed")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_26(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=400, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_27(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=401, detail="Node already failed")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_28(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=400, detail="XXNode already failedXX")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_29(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=400, detail="node already failed")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_30(self, session_id: str, node_id: str) -> Dict:
        """'Сломать' узел и запустить self-healing"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if node_id not in session.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = session.nodes[node_id]
        
        # Проверить, что узел не уже сломан
        if node.status == NodeStatus.FAILED:
            raise HTTPException(status_code=400, detail="NODE ALREADY FAILED")
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_31(self, session_id: str, node_id: str) -> Dict:
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
        
        start_time = None
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_32(self, session_id: str, node_id: str) -> Dict:
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
        node.status = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_33(self, session_id: str, node_id: str) -> Dict:
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
        node.last_failure = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_34(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(None, node_id, {"timestamp": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_35(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_failed", None, {"timestamp": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_36(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_failed", node_id, None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_37(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(node_id, {"timestamp": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_38(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_failed", {"timestamp": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_39(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_failed", node_id, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_40(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("XXnode_failedXX", node_id, {"timestamp": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_41(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("NODE_FAILED", node_id, {"timestamp": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_42(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_failed", node_id, {"XXtimestampXX": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_43(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_failed", node_id, {"TIMESTAMP": start_time})
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_44(self, session_id: str, node_id: str) -> Dict:
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
            if link.source == node_id and link.target == node_id:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_45(self, session_id: str, node_id: str) -> Dict:
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
            if link.source != node_id or link.target == node_id:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_46(self, session_id: str, node_id: str) -> Dict:
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
            if link.source == node_id or link.target != node_id:
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_47(self, session_id: str, node_id: str) -> Dict:
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
                link.status = None
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_48(self, session_id: str, node_id: str) -> Dict:
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
                link.status = "XXfailedXX"
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_49(self, session_id: str, node_id: str) -> Dict:
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
                link.status = "FAILED"
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_50(self, session_id: str, node_id: str) -> Dict:
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
        
        await asyncio.sleep(None)  # Симуляция задержки
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_51(self, session_id: str, node_id: str) -> Dict:
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
        
        await asyncio.sleep(1.3)  # Симуляция задержки
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_52(self, session_id: str, node_id: str) -> Dict:
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
        detection_time = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_53(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(None, node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_54(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("anomaly_detected", None, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_55(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("anomaly_detected", node_id, None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_56(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_57(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("anomaly_detected", {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_58(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("anomaly_detected", node_id, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_59(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("XXanomaly_detectedXX", node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_60(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("ANOMALY_DETECTED", node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_61(self, session_id: str, node_id: str) -> Dict:
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
            "XXdetection_timeXX": detection_time - start_time,
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_62(self, session_id: str, node_id: str) -> Dict:
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
            "DETECTION_TIME": detection_time - start_time,
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_63(self, session_id: str, node_id: str) -> Dict:
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
            "detection_time": detection_time + start_time,
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_64(self, session_id: str, node_id: str) -> Dict:
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
            "XXconfidenceXX": 0.98
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_65(self, session_id: str, node_id: str) -> Dict:
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
            "CONFIDENCE": 0.98
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_66(self, session_id: str, node_id: str) -> Dict:
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
            "confidence": 1.98
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_67(self, session_id: str, node_id: str) -> Dict:
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
        
        await asyncio.sleep(None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_68(self, session_id: str, node_id: str) -> Dict:
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
        
        await asyncio.sleep(1.5)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_69(self, session_id: str, node_id: str) -> Dict:
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
        node.status = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_70(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(None, node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_71(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("recovery_initiated", None, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_72(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("recovery_initiated", node_id, None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_73(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_74(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("recovery_initiated", {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_75(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("recovery_initiated", node_id, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_76(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("XXrecovery_initiatedXX", node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_77(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("RECOVERY_INITIATED", node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_78(self, session_id: str, node_id: str) -> Dict:
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
            "XXtimestampXX": time.time()
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_79(self, session_id: str, node_id: str) -> Dict:
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
            "TIMESTAMP": time.time()
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_80(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = None  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_81(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 1.0 - (hash(node_id) % 100) / 100.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_82(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 2.0 + (hash(node_id) % 100) / 100.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_83(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 1.0 + (hash(node_id) % 100) * 100.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_84(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 1.0 + (hash(node_id) / 100) / 100.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_85(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 1.0 + (hash(None) % 100) / 100.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_86(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 1.0 + (hash(node_id) % 101) / 100.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_87(self, session_id: str, node_id: str) -> Dict:
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
        recovery_duration = 1.0 + (hash(node_id) % 100) / 101.0  # 1.0-2.0 секунды
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_88(self, session_id: str, node_id: str) -> Dict:
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
        await asyncio.sleep(None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_89(self, session_id: str, node_id: str) -> Dict:
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
        recovery_time = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_90(self, session_id: str, node_id: str) -> Dict:
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
        node.status = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_91(self, session_id: str, node_id: str) -> Dict:
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
        node.recovery_time = None
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_92(self, session_id: str, node_id: str) -> Dict:
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
        node.recovery_time = recovery_time + start_time
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_93(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(None, node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_94(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_recovered", None, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_95(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_recovered", node_id, None)
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_96(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event(node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_97(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_recovered", {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_98(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("node_recovered", node_id, )
        
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_99(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("XXnode_recoveredXX", node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_100(self, session_id: str, node_id: str) -> Dict:
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
        session.add_event("NODE_RECOVERED", node_id, {
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_101(self, session_id: str, node_id: str) -> Dict:
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
            "XXrecovery_timeXX": node.recovery_time,
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_102(self, session_id: str, node_id: str) -> Dict:
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
            "RECOVERY_TIME": node.recovery_time,
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_103(self, session_id: str, node_id: str) -> Dict:
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
            "XXmttrXX": node.recovery_time
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_104(self, session_id: str, node_id: str) -> Dict:
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
            "MTTR": node.recovery_time
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
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_105(self, session_id: str, node_id: str) -> Dict:
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
            if link.source == node_id and link.target == node_id:
                link.status = "healthy"
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_106(self, session_id: str, node_id: str) -> Dict:
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
            if link.source != node_id or link.target == node_id:
                link.status = "healthy"
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_107(self, session_id: str, node_id: str) -> Dict:
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
            if link.source == node_id or link.target != node_id:
                link.status = "healthy"
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_108(self, session_id: str, node_id: str) -> Dict:
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
                link.status = None
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_109(self, session_id: str, node_id: str) -> Dict:
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
                link.status = "XXhealthyXX"
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_110(self, session_id: str, node_id: str) -> Dict:
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
                link.status = "HEALTHY"
        
        return {
            "node_id": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_111(self, session_id: str, node_id: str) -> Dict:
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
            "XXnode_idXX": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_112(self, session_id: str, node_id: str) -> Dict:
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
            "NODE_ID": node_id,
            "detection_time": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_113(self, session_id: str, node_id: str) -> Dict:
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
            "XXdetection_timeXX": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_114(self, session_id: str, node_id: str) -> Dict:
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
            "DETECTION_TIME": detection_time - start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_115(self, session_id: str, node_id: str) -> Dict:
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
            "detection_time": detection_time + start_time,
            "recovery_time": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_116(self, session_id: str, node_id: str) -> Dict:
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
            "XXrecovery_timeXX": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_117(self, session_id: str, node_id: str) -> Dict:
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
            "RECOVERY_TIME": node.recovery_time,
            "mttr": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_118(self, session_id: str, node_id: str) -> Dict:
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
            "XXmttrXX": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_119(self, session_id: str, node_id: str) -> Dict:
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
            "MTTR": node.recovery_time,
            "status": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_120(self, session_id: str, node_id: str) -> Dict:
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
            "XXstatusXX": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_121(self, session_id: str, node_id: str) -> Dict:
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
            "STATUS": "recovered",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_122(self, session_id: str, node_id: str) -> Dict:
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
            "status": "XXrecoveredXX",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_123(self, session_id: str, node_id: str) -> Dict:
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
            "status": "RECOVERED",
            "events": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_124(self, session_id: str, node_id: str) -> Dict:
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
            "XXeventsXX": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_125(self, session_id: str, node_id: str) -> Dict:
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
            "EVENTS": session.events[-4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_126(self, session_id: str, node_id: str) -> Dict:
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
            "events": session.events[+4:]  # Последние 4 события
        }
    
    async def xǁInteractiveDemoǁdestroy_node__mutmut_127(self, session_id: str, node_id: str) -> Dict:
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
            "events": session.events[-5:]  # Последние 4 события
        }
    
    xǁInteractiveDemoǁdestroy_node__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁInteractiveDemoǁdestroy_node__mutmut_1': xǁInteractiveDemoǁdestroy_node__mutmut_1, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_2': xǁInteractiveDemoǁdestroy_node__mutmut_2, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_3': xǁInteractiveDemoǁdestroy_node__mutmut_3, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_4': xǁInteractiveDemoǁdestroy_node__mutmut_4, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_5': xǁInteractiveDemoǁdestroy_node__mutmut_5, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_6': xǁInteractiveDemoǁdestroy_node__mutmut_6, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_7': xǁInteractiveDemoǁdestroy_node__mutmut_7, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_8': xǁInteractiveDemoǁdestroy_node__mutmut_8, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_9': xǁInteractiveDemoǁdestroy_node__mutmut_9, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_10': xǁInteractiveDemoǁdestroy_node__mutmut_10, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_11': xǁInteractiveDemoǁdestroy_node__mutmut_11, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_12': xǁInteractiveDemoǁdestroy_node__mutmut_12, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_13': xǁInteractiveDemoǁdestroy_node__mutmut_13, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_14': xǁInteractiveDemoǁdestroy_node__mutmut_14, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_15': xǁInteractiveDemoǁdestroy_node__mutmut_15, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_16': xǁInteractiveDemoǁdestroy_node__mutmut_16, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_17': xǁInteractiveDemoǁdestroy_node__mutmut_17, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_18': xǁInteractiveDemoǁdestroy_node__mutmut_18, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_19': xǁInteractiveDemoǁdestroy_node__mutmut_19, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_20': xǁInteractiveDemoǁdestroy_node__mutmut_20, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_21': xǁInteractiveDemoǁdestroy_node__mutmut_21, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_22': xǁInteractiveDemoǁdestroy_node__mutmut_22, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_23': xǁInteractiveDemoǁdestroy_node__mutmut_23, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_24': xǁInteractiveDemoǁdestroy_node__mutmut_24, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_25': xǁInteractiveDemoǁdestroy_node__mutmut_25, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_26': xǁInteractiveDemoǁdestroy_node__mutmut_26, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_27': xǁInteractiveDemoǁdestroy_node__mutmut_27, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_28': xǁInteractiveDemoǁdestroy_node__mutmut_28, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_29': xǁInteractiveDemoǁdestroy_node__mutmut_29, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_30': xǁInteractiveDemoǁdestroy_node__mutmut_30, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_31': xǁInteractiveDemoǁdestroy_node__mutmut_31, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_32': xǁInteractiveDemoǁdestroy_node__mutmut_32, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_33': xǁInteractiveDemoǁdestroy_node__mutmut_33, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_34': xǁInteractiveDemoǁdestroy_node__mutmut_34, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_35': xǁInteractiveDemoǁdestroy_node__mutmut_35, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_36': xǁInteractiveDemoǁdestroy_node__mutmut_36, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_37': xǁInteractiveDemoǁdestroy_node__mutmut_37, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_38': xǁInteractiveDemoǁdestroy_node__mutmut_38, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_39': xǁInteractiveDemoǁdestroy_node__mutmut_39, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_40': xǁInteractiveDemoǁdestroy_node__mutmut_40, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_41': xǁInteractiveDemoǁdestroy_node__mutmut_41, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_42': xǁInteractiveDemoǁdestroy_node__mutmut_42, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_43': xǁInteractiveDemoǁdestroy_node__mutmut_43, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_44': xǁInteractiveDemoǁdestroy_node__mutmut_44, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_45': xǁInteractiveDemoǁdestroy_node__mutmut_45, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_46': xǁInteractiveDemoǁdestroy_node__mutmut_46, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_47': xǁInteractiveDemoǁdestroy_node__mutmut_47, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_48': xǁInteractiveDemoǁdestroy_node__mutmut_48, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_49': xǁInteractiveDemoǁdestroy_node__mutmut_49, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_50': xǁInteractiveDemoǁdestroy_node__mutmut_50, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_51': xǁInteractiveDemoǁdestroy_node__mutmut_51, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_52': xǁInteractiveDemoǁdestroy_node__mutmut_52, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_53': xǁInteractiveDemoǁdestroy_node__mutmut_53, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_54': xǁInteractiveDemoǁdestroy_node__mutmut_54, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_55': xǁInteractiveDemoǁdestroy_node__mutmut_55, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_56': xǁInteractiveDemoǁdestroy_node__mutmut_56, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_57': xǁInteractiveDemoǁdestroy_node__mutmut_57, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_58': xǁInteractiveDemoǁdestroy_node__mutmut_58, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_59': xǁInteractiveDemoǁdestroy_node__mutmut_59, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_60': xǁInteractiveDemoǁdestroy_node__mutmut_60, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_61': xǁInteractiveDemoǁdestroy_node__mutmut_61, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_62': xǁInteractiveDemoǁdestroy_node__mutmut_62, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_63': xǁInteractiveDemoǁdestroy_node__mutmut_63, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_64': xǁInteractiveDemoǁdestroy_node__mutmut_64, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_65': xǁInteractiveDemoǁdestroy_node__mutmut_65, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_66': xǁInteractiveDemoǁdestroy_node__mutmut_66, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_67': xǁInteractiveDemoǁdestroy_node__mutmut_67, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_68': xǁInteractiveDemoǁdestroy_node__mutmut_68, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_69': xǁInteractiveDemoǁdestroy_node__mutmut_69, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_70': xǁInteractiveDemoǁdestroy_node__mutmut_70, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_71': xǁInteractiveDemoǁdestroy_node__mutmut_71, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_72': xǁInteractiveDemoǁdestroy_node__mutmut_72, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_73': xǁInteractiveDemoǁdestroy_node__mutmut_73, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_74': xǁInteractiveDemoǁdestroy_node__mutmut_74, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_75': xǁInteractiveDemoǁdestroy_node__mutmut_75, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_76': xǁInteractiveDemoǁdestroy_node__mutmut_76, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_77': xǁInteractiveDemoǁdestroy_node__mutmut_77, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_78': xǁInteractiveDemoǁdestroy_node__mutmut_78, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_79': xǁInteractiveDemoǁdestroy_node__mutmut_79, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_80': xǁInteractiveDemoǁdestroy_node__mutmut_80, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_81': xǁInteractiveDemoǁdestroy_node__mutmut_81, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_82': xǁInteractiveDemoǁdestroy_node__mutmut_82, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_83': xǁInteractiveDemoǁdestroy_node__mutmut_83, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_84': xǁInteractiveDemoǁdestroy_node__mutmut_84, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_85': xǁInteractiveDemoǁdestroy_node__mutmut_85, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_86': xǁInteractiveDemoǁdestroy_node__mutmut_86, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_87': xǁInteractiveDemoǁdestroy_node__mutmut_87, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_88': xǁInteractiveDemoǁdestroy_node__mutmut_88, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_89': xǁInteractiveDemoǁdestroy_node__mutmut_89, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_90': xǁInteractiveDemoǁdestroy_node__mutmut_90, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_91': xǁInteractiveDemoǁdestroy_node__mutmut_91, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_92': xǁInteractiveDemoǁdestroy_node__mutmut_92, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_93': xǁInteractiveDemoǁdestroy_node__mutmut_93, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_94': xǁInteractiveDemoǁdestroy_node__mutmut_94, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_95': xǁInteractiveDemoǁdestroy_node__mutmut_95, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_96': xǁInteractiveDemoǁdestroy_node__mutmut_96, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_97': xǁInteractiveDemoǁdestroy_node__mutmut_97, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_98': xǁInteractiveDemoǁdestroy_node__mutmut_98, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_99': xǁInteractiveDemoǁdestroy_node__mutmut_99, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_100': xǁInteractiveDemoǁdestroy_node__mutmut_100, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_101': xǁInteractiveDemoǁdestroy_node__mutmut_101, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_102': xǁInteractiveDemoǁdestroy_node__mutmut_102, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_103': xǁInteractiveDemoǁdestroy_node__mutmut_103, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_104': xǁInteractiveDemoǁdestroy_node__mutmut_104, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_105': xǁInteractiveDemoǁdestroy_node__mutmut_105, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_106': xǁInteractiveDemoǁdestroy_node__mutmut_106, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_107': xǁInteractiveDemoǁdestroy_node__mutmut_107, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_108': xǁInteractiveDemoǁdestroy_node__mutmut_108, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_109': xǁInteractiveDemoǁdestroy_node__mutmut_109, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_110': xǁInteractiveDemoǁdestroy_node__mutmut_110, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_111': xǁInteractiveDemoǁdestroy_node__mutmut_111, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_112': xǁInteractiveDemoǁdestroy_node__mutmut_112, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_113': xǁInteractiveDemoǁdestroy_node__mutmut_113, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_114': xǁInteractiveDemoǁdestroy_node__mutmut_114, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_115': xǁInteractiveDemoǁdestroy_node__mutmut_115, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_116': xǁInteractiveDemoǁdestroy_node__mutmut_116, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_117': xǁInteractiveDemoǁdestroy_node__mutmut_117, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_118': xǁInteractiveDemoǁdestroy_node__mutmut_118, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_119': xǁInteractiveDemoǁdestroy_node__mutmut_119, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_120': xǁInteractiveDemoǁdestroy_node__mutmut_120, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_121': xǁInteractiveDemoǁdestroy_node__mutmut_121, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_122': xǁInteractiveDemoǁdestroy_node__mutmut_122, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_123': xǁInteractiveDemoǁdestroy_node__mutmut_123, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_124': xǁInteractiveDemoǁdestroy_node__mutmut_124, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_125': xǁInteractiveDemoǁdestroy_node__mutmut_125, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_126': xǁInteractiveDemoǁdestroy_node__mutmut_126, 
        'xǁInteractiveDemoǁdestroy_node__mutmut_127': xǁInteractiveDemoǁdestroy_node__mutmut_127
    }
    
    def destroy_node(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁInteractiveDemoǁdestroy_node__mutmut_orig"), object.__getattribute__(self, "xǁInteractiveDemoǁdestroy_node__mutmut_mutants"), args, kwargs, self)
        return result 
    
    destroy_node.__signature__ = _mutmut_signature(xǁInteractiveDemoǁdestroy_node__mutmut_orig)
    xǁInteractiveDemoǁdestroy_node__mutmut_orig.__name__ = 'xǁInteractiveDemoǁdestroy_node'
    
    def xǁInteractiveDemoǁget_session_status__mutmut_orig(self, session_id: str) -> Dict:
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_1(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = None
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_2(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(None)
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_3(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if session:
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_4(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=None, detail="Session not found")
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_5(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=None)
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_6(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(detail="Session not found")
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_7(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, )
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_8(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=405, detail="Session not found")
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_9(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="XXSession not foundXX")
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_10(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_11(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="SESSION NOT FOUND")
        
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_12(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "XXsession_idXX": session_id,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_13(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "SESSION_ID": session_id,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_14(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "XXnodesXX": [
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_15(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "NODES": [
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_16(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "nodes": [
                {
                    "XXidXX": node.id,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_17(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "nodes": [
                {
                    "ID": node.id,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_18(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "nodes": [
                {
                    "id": node.id,
                    "XXxXX": node.x,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_19(self, session_id: str) -> Dict:
        """Получить статус сессии"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "session_id": session_id,
            "nodes": [
                {
                    "id": node.id,
                    "X": node.x,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_20(self, session_id: str) -> Dict:
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
                    "XXyXX": node.y,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_21(self, session_id: str) -> Dict:
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
                    "Y": node.y,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_22(self, session_id: str) -> Dict:
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
                    "XXstatusXX": node.status.value,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_23(self, session_id: str) -> Dict:
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
                    "STATUS": node.status.value,
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_24(self, session_id: str) -> Dict:
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
                    "XXrecovery_timeXX": node.recovery_time
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_25(self, session_id: str) -> Dict:
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
                    "RECOVERY_TIME": node.recovery_time
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_26(self, session_id: str) -> Dict:
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
            "XXlinksXX": [
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_27(self, session_id: str) -> Dict:
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
            "LINKS": [
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
    
    def xǁInteractiveDemoǁget_session_status__mutmut_28(self, session_id: str) -> Dict:
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
                    "XXsourceXX": link.source,
                    "target": link.target,
                    "status": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_29(self, session_id: str) -> Dict:
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
                    "SOURCE": link.source,
                    "target": link.target,
                    "status": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_30(self, session_id: str) -> Dict:
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
                    "XXtargetXX": link.target,
                    "status": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_31(self, session_id: str) -> Dict:
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
                    "TARGET": link.target,
                    "status": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_32(self, session_id: str) -> Dict:
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
                    "XXstatusXX": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_33(self, session_id: str) -> Dict:
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
                    "STATUS": link.status
                }
                for link in session.links
            ],
            "events": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_34(self, session_id: str) -> Dict:
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
            "XXeventsXX": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_35(self, session_id: str) -> Dict:
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
            "EVENTS": session.events[-10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_36(self, session_id: str) -> Dict:
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
            "events": session.events[+10:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_37(self, session_id: str) -> Dict:
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
            "events": session.events[-11:],  # Последние 10 событий
            "created_at": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_38(self, session_id: str) -> Dict:
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
            "XXcreated_atXX": session.created_at
        }
    
    def xǁInteractiveDemoǁget_session_status__mutmut_39(self, session_id: str) -> Dict:
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
            "CREATED_AT": session.created_at
        }
    
    xǁInteractiveDemoǁget_session_status__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁInteractiveDemoǁget_session_status__mutmut_1': xǁInteractiveDemoǁget_session_status__mutmut_1, 
        'xǁInteractiveDemoǁget_session_status__mutmut_2': xǁInteractiveDemoǁget_session_status__mutmut_2, 
        'xǁInteractiveDemoǁget_session_status__mutmut_3': xǁInteractiveDemoǁget_session_status__mutmut_3, 
        'xǁInteractiveDemoǁget_session_status__mutmut_4': xǁInteractiveDemoǁget_session_status__mutmut_4, 
        'xǁInteractiveDemoǁget_session_status__mutmut_5': xǁInteractiveDemoǁget_session_status__mutmut_5, 
        'xǁInteractiveDemoǁget_session_status__mutmut_6': xǁInteractiveDemoǁget_session_status__mutmut_6, 
        'xǁInteractiveDemoǁget_session_status__mutmut_7': xǁInteractiveDemoǁget_session_status__mutmut_7, 
        'xǁInteractiveDemoǁget_session_status__mutmut_8': xǁInteractiveDemoǁget_session_status__mutmut_8, 
        'xǁInteractiveDemoǁget_session_status__mutmut_9': xǁInteractiveDemoǁget_session_status__mutmut_9, 
        'xǁInteractiveDemoǁget_session_status__mutmut_10': xǁInteractiveDemoǁget_session_status__mutmut_10, 
        'xǁInteractiveDemoǁget_session_status__mutmut_11': xǁInteractiveDemoǁget_session_status__mutmut_11, 
        'xǁInteractiveDemoǁget_session_status__mutmut_12': xǁInteractiveDemoǁget_session_status__mutmut_12, 
        'xǁInteractiveDemoǁget_session_status__mutmut_13': xǁInteractiveDemoǁget_session_status__mutmut_13, 
        'xǁInteractiveDemoǁget_session_status__mutmut_14': xǁInteractiveDemoǁget_session_status__mutmut_14, 
        'xǁInteractiveDemoǁget_session_status__mutmut_15': xǁInteractiveDemoǁget_session_status__mutmut_15, 
        'xǁInteractiveDemoǁget_session_status__mutmut_16': xǁInteractiveDemoǁget_session_status__mutmut_16, 
        'xǁInteractiveDemoǁget_session_status__mutmut_17': xǁInteractiveDemoǁget_session_status__mutmut_17, 
        'xǁInteractiveDemoǁget_session_status__mutmut_18': xǁInteractiveDemoǁget_session_status__mutmut_18, 
        'xǁInteractiveDemoǁget_session_status__mutmut_19': xǁInteractiveDemoǁget_session_status__mutmut_19, 
        'xǁInteractiveDemoǁget_session_status__mutmut_20': xǁInteractiveDemoǁget_session_status__mutmut_20, 
        'xǁInteractiveDemoǁget_session_status__mutmut_21': xǁInteractiveDemoǁget_session_status__mutmut_21, 
        'xǁInteractiveDemoǁget_session_status__mutmut_22': xǁInteractiveDemoǁget_session_status__mutmut_22, 
        'xǁInteractiveDemoǁget_session_status__mutmut_23': xǁInteractiveDemoǁget_session_status__mutmut_23, 
        'xǁInteractiveDemoǁget_session_status__mutmut_24': xǁInteractiveDemoǁget_session_status__mutmut_24, 
        'xǁInteractiveDemoǁget_session_status__mutmut_25': xǁInteractiveDemoǁget_session_status__mutmut_25, 
        'xǁInteractiveDemoǁget_session_status__mutmut_26': xǁInteractiveDemoǁget_session_status__mutmut_26, 
        'xǁInteractiveDemoǁget_session_status__mutmut_27': xǁInteractiveDemoǁget_session_status__mutmut_27, 
        'xǁInteractiveDemoǁget_session_status__mutmut_28': xǁInteractiveDemoǁget_session_status__mutmut_28, 
        'xǁInteractiveDemoǁget_session_status__mutmut_29': xǁInteractiveDemoǁget_session_status__mutmut_29, 
        'xǁInteractiveDemoǁget_session_status__mutmut_30': xǁInteractiveDemoǁget_session_status__mutmut_30, 
        'xǁInteractiveDemoǁget_session_status__mutmut_31': xǁInteractiveDemoǁget_session_status__mutmut_31, 
        'xǁInteractiveDemoǁget_session_status__mutmut_32': xǁInteractiveDemoǁget_session_status__mutmut_32, 
        'xǁInteractiveDemoǁget_session_status__mutmut_33': xǁInteractiveDemoǁget_session_status__mutmut_33, 
        'xǁInteractiveDemoǁget_session_status__mutmut_34': xǁInteractiveDemoǁget_session_status__mutmut_34, 
        'xǁInteractiveDemoǁget_session_status__mutmut_35': xǁInteractiveDemoǁget_session_status__mutmut_35, 
        'xǁInteractiveDemoǁget_session_status__mutmut_36': xǁInteractiveDemoǁget_session_status__mutmut_36, 
        'xǁInteractiveDemoǁget_session_status__mutmut_37': xǁInteractiveDemoǁget_session_status__mutmut_37, 
        'xǁInteractiveDemoǁget_session_status__mutmut_38': xǁInteractiveDemoǁget_session_status__mutmut_38, 
        'xǁInteractiveDemoǁget_session_status__mutmut_39': xǁInteractiveDemoǁget_session_status__mutmut_39
    }
    
    def get_session_status(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁInteractiveDemoǁget_session_status__mutmut_orig"), object.__getattribute__(self, "xǁInteractiveDemoǁget_session_status__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_session_status.__signature__ = _mutmut_signature(xǁInteractiveDemoǁget_session_status__mutmut_orig)
    xǁInteractiveDemoǁget_session_status__mutmut_orig.__name__ = 'xǁInteractiveDemoǁget_session_status'
    
    def xǁInteractiveDemoǁreset_session__mutmut_orig(self, session_id: str) -> Dict:
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_1(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = None
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_2(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(None)
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_3(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if session:
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_4(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=None, detail="Session not found")
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_5(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=None)
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_6(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(detail="Session not found")
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_7(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, )
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_8(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=405, detail="Session not found")
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_9(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="XXSession not foundXX")
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_10(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_11(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="SESSION NOT FOUND")
        
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
    
    def xǁInteractiveDemoǁreset_session__mutmut_12(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Сбросить все узлы
        for node in session.nodes.values():
            node.status = None
            node.last_failure = None
            node.recovery_time = None
        
        # Сбросить все связи
        for link in session.links:
            link.status = "healthy"
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_13(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Сбросить все узлы
        for node in session.nodes.values():
            node.status = NodeStatus.HEALTHY
            node.last_failure = ""
            node.recovery_time = None
        
        # Сбросить все связи
        for link in session.links:
            link.status = "healthy"
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_14(self, session_id: str) -> Dict:
        """Сбросить сессию (все узлы здоровы)"""
        session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Сбросить все узлы
        for node in session.nodes.values():
            node.status = NodeStatus.HEALTHY
            node.last_failure = None
            node.recovery_time = ""
        
        # Сбросить все связи
        for link in session.links:
            link.status = "healthy"
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_15(self, session_id: str) -> Dict:
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
            link.status = None
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_16(self, session_id: str) -> Dict:
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
            link.status = "XXhealthyXX"
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_17(self, session_id: str) -> Dict:
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
            link.status = "HEALTHY"
        
        # Очистить события
        session.events = []
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_18(self, session_id: str) -> Dict:
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
        session.events = None
        
        return {"status": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_19(self, session_id: str) -> Dict:
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
        
        return {"XXstatusXX": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_20(self, session_id: str) -> Dict:
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
        
        return {"STATUS": "reset", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_21(self, session_id: str) -> Dict:
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
        
        return {"status": "XXresetXX", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_22(self, session_id: str) -> Dict:
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
        
        return {"status": "RESET", "session_id": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_23(self, session_id: str) -> Dict:
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
        
        return {"status": "reset", "XXsession_idXX": session_id}
    
    def xǁInteractiveDemoǁreset_session__mutmut_24(self, session_id: str) -> Dict:
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
        
        return {"status": "reset", "SESSION_ID": session_id}
    
    xǁInteractiveDemoǁreset_session__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁInteractiveDemoǁreset_session__mutmut_1': xǁInteractiveDemoǁreset_session__mutmut_1, 
        'xǁInteractiveDemoǁreset_session__mutmut_2': xǁInteractiveDemoǁreset_session__mutmut_2, 
        'xǁInteractiveDemoǁreset_session__mutmut_3': xǁInteractiveDemoǁreset_session__mutmut_3, 
        'xǁInteractiveDemoǁreset_session__mutmut_4': xǁInteractiveDemoǁreset_session__mutmut_4, 
        'xǁInteractiveDemoǁreset_session__mutmut_5': xǁInteractiveDemoǁreset_session__mutmut_5, 
        'xǁInteractiveDemoǁreset_session__mutmut_6': xǁInteractiveDemoǁreset_session__mutmut_6, 
        'xǁInteractiveDemoǁreset_session__mutmut_7': xǁInteractiveDemoǁreset_session__mutmut_7, 
        'xǁInteractiveDemoǁreset_session__mutmut_8': xǁInteractiveDemoǁreset_session__mutmut_8, 
        'xǁInteractiveDemoǁreset_session__mutmut_9': xǁInteractiveDemoǁreset_session__mutmut_9, 
        'xǁInteractiveDemoǁreset_session__mutmut_10': xǁInteractiveDemoǁreset_session__mutmut_10, 
        'xǁInteractiveDemoǁreset_session__mutmut_11': xǁInteractiveDemoǁreset_session__mutmut_11, 
        'xǁInteractiveDemoǁreset_session__mutmut_12': xǁInteractiveDemoǁreset_session__mutmut_12, 
        'xǁInteractiveDemoǁreset_session__mutmut_13': xǁInteractiveDemoǁreset_session__mutmut_13, 
        'xǁInteractiveDemoǁreset_session__mutmut_14': xǁInteractiveDemoǁreset_session__mutmut_14, 
        'xǁInteractiveDemoǁreset_session__mutmut_15': xǁInteractiveDemoǁreset_session__mutmut_15, 
        'xǁInteractiveDemoǁreset_session__mutmut_16': xǁInteractiveDemoǁreset_session__mutmut_16, 
        'xǁInteractiveDemoǁreset_session__mutmut_17': xǁInteractiveDemoǁreset_session__mutmut_17, 
        'xǁInteractiveDemoǁreset_session__mutmut_18': xǁInteractiveDemoǁreset_session__mutmut_18, 
        'xǁInteractiveDemoǁreset_session__mutmut_19': xǁInteractiveDemoǁreset_session__mutmut_19, 
        'xǁInteractiveDemoǁreset_session__mutmut_20': xǁInteractiveDemoǁreset_session__mutmut_20, 
        'xǁInteractiveDemoǁreset_session__mutmut_21': xǁInteractiveDemoǁreset_session__mutmut_21, 
        'xǁInteractiveDemoǁreset_session__mutmut_22': xǁInteractiveDemoǁreset_session__mutmut_22, 
        'xǁInteractiveDemoǁreset_session__mutmut_23': xǁInteractiveDemoǁreset_session__mutmut_23, 
        'xǁInteractiveDemoǁreset_session__mutmut_24': xǁInteractiveDemoǁreset_session__mutmut_24
    }
    
    def reset_session(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁInteractiveDemoǁreset_session__mutmut_orig"), object.__getattribute__(self, "xǁInteractiveDemoǁreset_session__mutmut_mutants"), args, kwargs, self)
        return result 
    
    reset_session.__signature__ = _mutmut_signature(xǁInteractiveDemoǁreset_session__mutmut_orig)
    xǁInteractiveDemoǁreset_session__mutmut_orig.__name__ = 'xǁInteractiveDemoǁreset_session'


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

