"""
Vision Coding Module - Coding with Vision для Kimi K2.5
Реализация визуального программирования, отладки и анализа графов.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import deque
import heapq

import numpy  # type: ignore
from PIL import Image, ImageDraw, ImageFont  # type: ignore

logger = logging.getLogger(__name__)


class AnalysisType(Enum):
    """Типы визуального анализа"""
    UI_LAYOUT = auto()
    CODE_STRUCTURE = auto()
    GRAPH_PATHFINDING = auto()
    ERROR_DETECTION = auto()
    PERFORMANCE_VISUALIZATION = auto()
    DATA_FLOW = auto()


class Severity(Enum):
    """Уровень серьёзности проблемы"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class BoundingBox:
    """Ограничивающий прямоугольник"""
    x: float
    y: float
    width: float
    height: float
    
    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def contains(self, point: Tuple[float, float]) -> bool:
        px, py = point
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)
    
    def intersects(self, other: 'BoundingBox') -> bool:
        return not (self.x + self.width < other.x or
                    other.x + other.width < self.x or
                    self.y + self.height < other.y or
                    other.y + other.height < self.y)


@dataclass
class Style:
    """Стиль визуального элемента"""
    color: str = "#00FF00"
    border_width: float = 2.0
    opacity: float = 0.8
    font_size: int = 12
    fill_color: Optional[str] = None
    dash_pattern: Optional[List[int]] = None


@dataclass
class OverlayElement:
    """Элемент визуального наложения"""
    element_type: str
    location: BoundingBox
    style: Style
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    """Найденная проблема"""
    issue_type: str
    severity: Severity
    location: BoundingBox
    description: str
    suggestion: str = ""
    confidence: float = 0.0


@dataclass
class Suggestion:
    """Предложение по улучшению"""
    suggestion_type: str
    confidence: float
    action: str
    code_snippet: str = ""
    explanation: str = ""


@dataclass
class VisualOverlay:
    """Визуальное наложение на изображение"""
    elements: List[OverlayElement] = field(default_factory=list)
    original_size: Tuple[int, int] = (0, 0)
    
    def add_element(self, element: OverlayElement) -> None:
        self.elements.append(element)
    
    def render(self, base_image: Image.Image) -> Image.Image:  # noqa: ANN001
        """Накладывает элементы на изображение"""
        from PIL import Image as PILImage
        
        result = base_image.copy().convert("RGBA")
        overlay = PILImage.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        for element in self.elements:
            self._render_element(draw, element)
        
        # Композитим наложение
        result = PILImage.alpha_composite(result, overlay)
        return result.convert("RGB")
    
    def _render_element(self, draw: ImageDraw.Draw, element: OverlayElement) -> None:  # noqa: ANN001
        """Отрисовывает один элемент"""
        loc = element.location
        style = element.style
        
        # Преобразуем цвет с учётом прозрачности
        color = self._hex_to_rgba(style.color, int(255 * style.opacity))
        
        if style.fill_color:
            fill = self._hex_to_rgba(style.fill_color, int(128 * style.opacity))
            draw.rectangle(
                [loc.x, loc.y, loc.x + loc.width, loc.y + loc.height],
                fill=fill,
                outline=color,
                width=int(style.border_width)
            )
        else:
            draw.rectangle(
                [loc.x, loc.y, loc.x + loc.width, loc.y + loc.height],
                outline=color,
                width=int(style.border_width)
            )
        
        # Добавляем текст
        if element.content:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                         style.font_size)
            except Exception:
                font = ImageFont.load_default()
            
            text_x = loc.x + 5
            text_y = loc.y - style.font_size - 2
            
            # Фон для текста
            bbox = draw.textbbox((0, 0), element.content, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            draw.rectangle(
                [text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2],
                fill=(0, 0, 0, 180)
            )
            
            draw.text((text_x, text_y), element.content, fill=color[:3], font=font)
    
    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
        """Конвертирует hex в RGBA"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b, alpha)


@dataclass
class GraphNode:
    """Узел графа"""
    id: str
    x: float
    y: float
    neighbors: List[str] = field(default_factory=list)
    cost: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def distance_to(self, other: 'GraphNode') -> float:
        """Евклидово расстояние до другого узла"""
        return numpy.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


@dataclass
class Graph:
    """Представление графа"""
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    nodes_visited: int = 0
    analysis_time_ms: float = 0.0
    
    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = []
    
    def add_edge(self, from_id: str, to_id: str, bidirectional: bool = True) -> None:
        if from_id in self.edges:
            if to_id not in self.edges[from_id]:
                self.edges[from_id].append(to_id)
        
        if bidirectional and to_id in self.edges:
            if from_id not in self.edges[to_id]:
                self.edges[to_id].append(from_id)
    
    def get_neighbors(self, node_id: str) -> List[str]:
        return self.edges.get(node_id, [])


@dataclass
class PathMetrics:
    """Метрики найденного пути"""
    length: int
    total_cost: float
    nodes_visited: int
    time_ms: float
    path_nodes: List[str] = field(default_factory=list)


class BFSAlgorithm:
    """Алгоритм поиска в ширину"""
    
    def __init__(self, max_depth: int = 10000, parallel_workers: int = 4):
        self.max_depth = max_depth
        self.parallel_workers = parallel_workers
    
    def find_path(self, graph: Graph, start_id: str, end_id: str) -> PathMetrics:
        """Находит кратчайший путь с помощью BFS"""
        start_time = time.time()
        
        if start_id not in graph.nodes:
            raise ValueError(f"Start node not found: {start_id}")
        if end_id not in graph.nodes:
            raise ValueError(f"End node not found: {end_id}")
        
        visited: set[str] = {start_id}
        queue: deque[Tuple[str, List[str]]] = deque([(start_id, [start_id])])
        nodes_visited = 0
        
        while queue:
            node_id, path = queue.popleft()
            nodes_visited += 1
            
            if node_id == end_id:
                elapsed = (time.time() - start_time) * 1000
                return PathMetrics(
                    length=len(path),
                    total_cost=sum(graph.nodes[n].cost for n in path),
                    nodes_visited=nodes_visited,
                    time_ms=elapsed,
                    path_nodes=path
                )
            
            if len(path) > self.max_depth:
                continue
            
            for neighbor in graph.get_neighbors(node_id):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    queue.append((neighbor, new_path))
        
        raise ValueError("No path found")


class AStarAlgorithm:
    """Алгоритм A* для поиска пути"""
    
    def __init__(self, heuristic_weight: float = 1.0):
        self.heuristic_weight = heuristic_weight
    
    def manhattan_distance(self, node1: GraphNode, node2: GraphNode) -> float:
        """Манхэттенское расстояние"""
        return abs(node1.x - node2.x) + abs(node1.y - node2.y)
    
    def find_path(
        self, 
        graph: Graph, 
        start_id: str, 
        end_id: str,
        heuristic: Optional[Callable[[GraphNode, GraphNode], float]] = None
    ) -> PathMetrics:
        """Находит оптимальный путь с помощью A*"""
        start_time = time.time()
        
        if start_id not in graph.nodes:
            raise ValueError(f"Start node not found: {start_id}")
        if end_id not in graph.nodes:
            raise ValueError(f"End node not found: {end_id}")
        
        if heuristic is None:
            heuristic = lambda a, b: a.distance_to(b)
        
        start_node = graph.nodes[start_id]
        end_node = graph.nodes[end_id]
        
        # Priority queue: (f_score, counter, node_id)
        counter = 0
        open_set: List[Tuple[float, int, str]] = [
            (heuristic(start_node, end_node) * self.heuristic_weight, counter, start_id)
        ]
        open_set_ids: set[str] = {start_id}
        
        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {start_id: 0.0}
        
        nodes_visited = 0
        
        while open_set:
            _, _, current_id = heapq.heappop(open_set)
            open_set_ids.discard(current_id)
            nodes_visited += 1
            
            if current_id == end_id:
                # Восстанавливаем путь
                path: List[str] = []
                node_id = end_id
                while node_id in came_from:
                    path.append(node_id)
                    node_id = came_from[node_id]
                path.append(start_id)
                path.reverse()
                
                elapsed = (time.time() - start_time) * 1000
                return PathMetrics(
                    length=len(path),
                    total_cost=g_score[end_id],
                    nodes_visited=nodes_visited,
                    time_ms=elapsed,
                    path_nodes=path
                )
            
            current_node = graph.nodes[current_id]
            
            for neighbor_id in graph.get_neighbors(current_id):
                neighbor = graph.nodes[neighbor_id]
                tentative_g = g_score[current_id] + current_node.cost
                
                if neighbor_id not in g_score or tentative_g < g_score[neighbor_id]:
                    came_from[neighbor_id] = current_id
                    g_score[neighbor_id] = tentative_g
                    f = tentative_g + heuristic(neighbor, end_node) * self.heuristic_weight
                    
                    if neighbor_id not in open_set_ids:
                        counter += 1
                        heapq.heappush(open_set, (f, counter, neighbor_id))
                        open_set_ids.add(neighbor_id)
        
        raise ValueError("No path found")


class VisionCache:
    """Кэш для операций Vision"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600.0):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: deque[str] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
    
    def _generate_key(self, data: bytes, operation: str) -> str:
        """Генерирует ключ кэша"""
        hash_input = data + operation.encode()
        return hashlib.sha256(hash_input).hexdigest()[:32]
    
    async def get(self, data: bytes, operation: str) -> Optional[Any]:
        """Получает данные из кэша"""
        async with self._lock:
            key = self._generate_key(data, operation)
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry['timestamp'] < self.ttl:
                    entry['hits'] += 1
                    self._access_order.remove(key)
                    self._access_order.append(key)
                    return entry['data']
                
                del self._cache[key]
            return None
    
    async def set(self, data: bytes, operation: str, result: Any) -> None:
        """Сохраняет данные в кэш"""
        async with self._lock:
            key = self._generate_key(data, operation)
            
            if len(self._cache) >= self.max_size:
                # LRU eviction
                oldest = self._access_order.popleft()
                if oldest in self._cache:
                    del self._cache[oldest]
            
            self._cache[key] = {
                'data': result,
                'timestamp': time.time(),
                'hits': 0
            }
            self._access_order.append(key)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэша"""
        async with self._lock:
            total_hits = sum(e['hits'] for e in self._cache.values())
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'total_hits': total_hits,
                'hit_rate': total_hits / max(1, len(self._cache))
            }


class VisionCodingEngine:
    """Движок Coding with Vision"""
    
    def __init__(self):
        self.bfs = BFSAlgorithm()
        self.a_star = AStarAlgorithm()
        self.cache = VisionCache()
        self.logger = logging.getLogger(__name__)
        
        # OCR конфигурация
        self.ocr_enabled = False
        self.ocr_languages = ['eng', 'rus']
    
    async def analyze_maze(
        self,
        image_data: bytes,
        start_pos: Tuple[int, int],
        end_pos: Tuple[int, int]
    ) -> Dict[str, Any]:
        """Анализирует лабиринт и находит путь"""
        import io
        
        # Проверяем кэш
        cached = await self.cache.get(image_data, f"maze_{start_pos}_{end_pos}")
        if cached:
            return cached
        
        start_time = time.time()
        
        # 1. Извлекаем граф из изображения
        graph = await self._extract_graph_from_image(image_data)
        
        # 2. Находим ближайшие узлы к стартовой и конечной позициям
        start_node = self._find_nearest_node(graph, start_pos)
        end_node = self._find_nearest_node(graph, end_pos)
        
        # 3. Находим путь с помощью A*
        try:
            path_metrics = self.a_star.find_path(graph, start_node.id, end_node.id)
        except ValueError:
            # Fallback на BFS
            path_metrics = self.bfs.find_path(graph, start_node.id, end_node.id)
        
        # 4. Создаём визуальное наложение
        overlay = self._create_path_overlay(image_data, path_metrics, graph)
        
        result = {
            'path': path_metrics.path_nodes,
            'metrics': {
                'length': path_metrics.length,
                'total_cost': path_metrics.total_cost,
                'nodes_visited': path_metrics.nodes_visited,
                'time_ms': path_metrics.time_ms,
                'total_time_ms': (time.time() - start_time) * 1000
            },
            'overlay': overlay,
            'graph_stats': {
                'total_nodes': len(graph.nodes),
                'total_edges': sum(len(e) for e in graph.edges.values())
            }
        }
        
        await self.cache.set(image_data, f"maze_{start_pos}_{end_pos}", result)
        return result
    
    async def _extract_graph_from_image(self, image_data: bytes) -> Graph:
        """Извлекает граф из изображения лабиринта"""
        import io
        
        image = Image.open(io.BytesIO(image_data))
        img_array = numpy.array(image.convert('L'))
        
        # Бинаризация
        threshold = 128
        binary = (img_array < threshold).astype(numpy.uint8)
        
        graph = Graph()
        
        # Находим проходимые клетки (белые/светлые)
        height, width = binary.shape
        cell_size = 10  # Размер ячейки сетки
        
        node_id = 0
        node_positions: Dict[Tuple[int, int], str] = {}
        
        for y in range(0, height, cell_size):
            for x in range(0, width, cell_size):
                # Проверяем, является ли область проходимой
                region = binary[y:min(y+cell_size, height), x:min(x+cell_size, width)]
                if numpy.mean(region) < 0.5:  # Более 50% тёмных пикселей = стена
                    continue
                
                # Создаём узел
                node = GraphNode(
                    id=f"node_{node_id}",
                    x=x + cell_size / 2,
                    y=y + cell_size / 2,
                    cost=1.0
                )
                graph.add_node(node)
                node_positions[(x // cell_size, y // cell_size)] = node.id
                node_id += 1
        
        # Создаём рёбра между соседними узлами
        for (gx, gy), node_id_str in node_positions.items():
            neighbors = [
                (gx + 1, gy), (gx - 1, gy),
                (gx, gy + 1), (gx, gy - 1)
            ]
            for nx, ny in neighbors:
                if (nx, ny) in node_positions:
                    graph.add_edge(node_id_str, node_positions[(nx, ny)])
        
        return graph
    
    def _find_nearest_node(self, graph: Graph, pos: Tuple[int, int]) -> GraphNode:
        """Находит ближайший узел к заданной позиции"""
        x, y = pos
        nearest: Optional[GraphNode] = None
        min_dist = float('inf')
        
        for node in graph.nodes.values():
            dist = (node.x - x)**2 + (node.y - y)**2
            if dist < min_dist:
                min_dist = dist
                nearest = node
        
        if nearest is None:
            raise ValueError("No nodes found in graph")
        
        return nearest
    
    def _create_path_overlay(
        self, 
        image_data: bytes, 
        path_metrics: PathMetrics, 
        graph: Graph
    ) -> VisualOverlay:
        """Создаёт визуальное наложение пути"""
        import io
        
        image = Image.open(io.BytesIO(image_data))
        overlay = VisualOverlay(original_size=image.size)
        
        # Создаём цветной градиент для пути
        path_length = len(path_metrics.path_nodes)
        
        for i, node_id in enumerate(path_metrics.path_nodes):
            node = graph.nodes[node_id]
            
            # Интерполируем цвет от зелёного к красному
            ratio = i / max(1, path_length - 1)
            r = int(255 * ratio)
            g = int(255 * (1 - ratio))
            color = f"#{r:02x}{g:02x}00"
            
            element = OverlayElement(
                element_type="path_node",
                location=BoundingBox(
                    x=node.x - 5,
                    y=node.y - 5,
                    width=10,
                    height=10
                ),
                style=Style(
                    color=color,
                    border_width=3,
                    opacity=0.9,
                    fill_color=color
                ),
                content=str(i + 1),
                metadata={'node_id': node_id, 'step': i}
            )
            overlay.add_element(element)
        
        return overlay

    async def analyze_mesh_topology(
        self,
        image_data: bytes,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Анализирует изображение топологии mesh-сети.

        Выявляет:
        - Узлы и связи
        - Bottlenecks (узлы с высокой связностью)
        - Изолированные узлы
        - Рекомендации по оптимизации
        """
        import io
        start_time = time.time()

        # Проверяем кэш
        cached = await self.cache.get(image_data, "mesh_topology")
        if cached:
            return cached

        # Извлекаем граф из изображения
        graph = await self._extract_graph_from_image(image_data)

        # Анализируем топологию
        analysis = self._analyze_topology(graph)

        # Создаём визуальное наложение
        image = Image.open(io.BytesIO(image_data))
        overlay = VisualOverlay(original_size=image.size)

        # Отмечаем bottlenecks
        for bottleneck in analysis['bottlenecks']:
            node = graph.nodes.get(bottleneck['node_id'])
            if node:
                overlay.add_element(OverlayElement(
                    element_type="bottleneck",
                    location=BoundingBox(
                        x=node.x - 15,
                        y=node.y - 15,
                        width=30,
                        height=30
                    ),
                    style=Style(
                        color="#FF0000",
                        border_width=3,
                        opacity=0.8
                    ),
                    content=f"Bottleneck: {bottleneck['connections']} connections",
                    metadata=bottleneck
                ))

        # Отмечаем изолированные узлы
        for isolated_id in analysis['isolated_nodes']:
            node = graph.nodes.get(isolated_id)
            if node:
                overlay.add_element(OverlayElement(
                    element_type="isolated",
                    location=BoundingBox(
                        x=node.x - 10,
                        y=node.y - 10,
                        width=20,
                        height=20
                    ),
                    style=Style(
                        color="#FFA500",
                        border_width=2,
                        opacity=0.8
                    ),
                    content="Isolated node",
                    metadata={'node_id': isolated_id}
                ))

        result = {
            'nodes_detected': len(graph.nodes),
            'links_detected': sum(len(e) for e in graph.edges.values()) // 2,
            'bottlenecks': analysis['bottlenecks'],
            'isolated_nodes': analysis['isolated_nodes'],
            'connectivity_score': analysis['connectivity_score'],
            'recommendations': analysis['recommendations'],
            'processing_time_ms': (time.time() - start_time) * 1000,
            'overlay': overlay.to_dict()
        }

        await self.cache.set(image_data, "mesh_topology", result)
        return result

    def _analyze_topology(self, graph: Graph) -> Dict[str, Any]:
        """Анализирует топологию графа."""
        bottlenecks = []
        isolated_nodes = []
        recommendations = []

        # Находим узлы с высокой связностью (bottlenecks)
        avg_connections = 0
        if graph.nodes:
            connection_counts = {
                node_id: len(graph.edges.get(node_id, []))
                for node_id in graph.nodes
            }
            avg_connections = sum(connection_counts.values()) / len(connection_counts)

            # Bottleneck = узел с > 2x среднего числа связей
            threshold = max(4, avg_connections * 2)
            for node_id, count in connection_counts.items():
                if count >= threshold:
                    node = graph.nodes[node_id]
                    bottlenecks.append({
                        'node_id': node_id,
                        'connections': count,
                        'location': {'x': node.x, 'y': node.y},
                        'severity': 'high' if count > threshold * 1.5 else 'medium'
                    })
                    recommendations.append({
                        'action': 'add_redundant_link',
                        'target': node_id,
                        'reason': f'Node has {count} connections (high centrality)'
                    })
                elif count == 0:
                    isolated_nodes.append(node_id)
                    recommendations.append({
                        'action': 'connect_isolated_node',
                        'target': node_id,
                        'reason': 'Node is completely isolated'
                    })
                elif count == 1:
                    # Узел с одним соединением - потенциальная точка отказа
                    recommendations.append({
                        'action': 'add_backup_link',
                        'target': node_id,
                        'reason': 'Single point of failure (only 1 connection)'
                    })

        # Вычисляем connectivity score (0-1)
        if graph.nodes:
            max_edges = len(graph.nodes) * (len(graph.nodes) - 1) / 2
            actual_edges = sum(len(e) for e in graph.edges.values()) / 2
            connectivity_score = min(1.0, actual_edges / max(1, max_edges) * 10)
        else:
            connectivity_score = 0.0

        return {
            'bottlenecks': bottlenecks,
            'isolated_nodes': isolated_nodes,
            'connectivity_score': round(connectivity_score, 2),
            'recommendations': recommendations[:10]  # Top 10 recommendations
        }

    async def detect_anomalies(
        self,
        image_data: bytes,
        baseline_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Обнаруживает визуальные аномалии на изображении.

        Если предоставлен baseline, сравнивает с ним.
        """
        import io
        start_time = time.time()

        image = Image.open(io.BytesIO(image_data))
        img_array = numpy.array(image.convert('RGB'))

        anomalies = []

        if baseline_data:
            # Сравнение с baseline
            baseline_img = Image.open(io.BytesIO(baseline_data))
            baseline_array = numpy.array(baseline_img.convert('RGB'))

            # Resize if different sizes
            if baseline_array.shape != img_array.shape:
                baseline_img = baseline_img.resize(image.size)
                baseline_array = numpy.array(baseline_img.convert('RGB'))

            # Находим различия
            diff = numpy.abs(img_array.astype(float) - baseline_array.astype(float))
            diff_gray = numpy.mean(diff, axis=2)

            # Порог для детекции изменений
            threshold = 30
            changed_mask = diff_gray > threshold

            # Находим регионы с изменениями
            if numpy.any(changed_mask):
                # Простой поиск bounding box
                rows = numpy.any(changed_mask, axis=1)
                cols = numpy.any(changed_mask, axis=0)
                if numpy.any(rows) and numpy.any(cols):
                    y_min, y_max = numpy.where(rows)[0][[0, -1]]
                    x_min, x_max = numpy.where(cols)[0][[0, -1]]

                    change_intensity = numpy.mean(diff_gray[changed_mask])

                    anomalies.append({
                        'type': 'visual_change',
                        'location': {
                            'x': int(x_min),
                            'y': int(y_min),
                            'width': int(x_max - x_min),
                            'height': int(y_max - y_min)
                        },
                        'severity': 'high' if change_intensity > 100 else 'medium',
                        'confidence': min(1.0, change_intensity / 100)
                    })
        else:
            # Детекция аномалий без baseline (яркие/тёмные пятна)
            gray = numpy.mean(img_array, axis=2)
            mean_brightness = numpy.mean(gray)
            std_brightness = numpy.std(gray)

            # Очень яркие области
            bright_mask = gray > mean_brightness + 2 * std_brightness
            if numpy.any(bright_mask):
                rows = numpy.any(bright_mask, axis=1)
                cols = numpy.any(bright_mask, axis=0)
                if numpy.any(rows) and numpy.any(cols):
                    y_min, y_max = numpy.where(rows)[0][[0, -1]]
                    x_min, x_max = numpy.where(cols)[0][[0, -1]]

                    anomalies.append({
                        'type': 'bright_spot',
                        'location': {
                            'x': int(x_min),
                            'y': int(y_min),
                            'width': int(x_max - x_min),
                            'height': int(y_max - y_min)
                        },
                        'severity': 'low',
                        'confidence': 0.7
                    })

        return {
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies,
            'processing_time_ms': (time.time() - start_time) * 1000
        }


# Глобальный экземпляр движка
_vision_engine: Optional[VisionCodingEngine] = None


def get_vision_engine() -> VisionCodingEngine:
    """Возвращает глобальный экземпляр движка"""
    global _vision_engine
    if _vision_engine is None:
        _vision_engine = VisionCodingEngine()
    return _vision_engine


async def analyze_maze(
    image_data: bytes,
    start_pos: Tuple[int, int],
    end_pos: Tuple[int, int]
) -> Dict[str, Any]:
    """Утилита для анализа лабиринта"""
    engine = get_vision_engine()
    return await engine.analyze_maze(image_data, start_pos, end_pos)


async def analyze_mesh_topology(
    image_data: bytes,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Утилита для анализа топологии mesh-сети"""
    engine = get_vision_engine()
    return await engine.analyze_mesh_topology(image_data, context)


async def detect_anomalies(
    image_data: bytes,
    baseline_data: Optional[bytes] = None
) -> Dict[str, Any]:
    """Утилита для обнаружения визуальных аномалий"""
    engine = get_vision_engine()
    return await engine.detect_anomalies(image_data, baseline_data)
