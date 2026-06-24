"""Vision Coding Engine."""
from __future__ import annotations
import base64
import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from .models import AnalysisType, BoundingBox, Issue, Severity, Style, Suggestion, VisualOverlay
from .graph import GraphNode, BFSAlgorithm, AStarAlgorithm
from .cache import VisionCache
logger = logging.getLogger(__name__)

class VisionCodingEngine:
    """Движок Coding with Vision"""

    def __init__(self):
        self.bfs = BFSAlgorithm()
        self.a_star = AStarAlgorithm()
        self.cache = VisionCache()
        self.logger = logging.getLogger(__name__)

        # OCR конфигурация
        self.ocr_enabled = False
        self.ocr_languages = ["eng", "rus"]

    async def analyze_maze(
        self, image_data: bytes, start_pos: Tuple[int, int], end_pos: Tuple[int, int]
    ) -> Dict[str, Any]:
        """Анализирует лабиринт и находит путь"""

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
            "path": path_metrics.path_nodes,
            "metrics": {
                "length": path_metrics.length,
                "total_cost": path_metrics.total_cost,
                "nodes_visited": path_metrics.nodes_visited,
                "time_ms": path_metrics.time_ms,
                "total_time_ms": (time.time() - start_time) * 1000,
            },
            "overlay": overlay,
            "graph_stats": {
                "total_nodes": len(graph.nodes),
                "total_edges": sum(len(e) for e in graph.edges.values()),
            },
        }

        await self.cache.set(image_data, f"maze_{start_pos}_{end_pos}", result)
        return result

    async def _extract_graph_from_image(self, image_data: bytes) -> Graph:
        """Извлекает граф из изображения лабиринта"""
        import io

        image = Image.open(io.BytesIO(image_data))
        img_array = numpy.array(image.convert("L"))

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
                region = binary[
                    y : min(y + cell_size, height), x : min(x + cell_size, width)
                ]
                if numpy.mean(region) < 0.5:  # Более 50% тёмных пикселей = стена
                    continue

                # Создаём узел
                node = GraphNode(
                    id=f"node_{node_id}",
                    x=x + cell_size / 2,
                    y=y + cell_size / 2,
                    cost=1.0,
                )
                graph.add_node(node)
                node_positions[(x // cell_size, y // cell_size)] = node.id
                node_id += 1

        # Создаём рёбра между соседними узлами
        for (gx, gy), node_id_str in node_positions.items():
            neighbors = [(gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)]
            for nx, ny in neighbors:
                if (nx, ny) in node_positions:
                    graph.add_edge(node_id_str, node_positions[(nx, ny)])

        return graph

    def _find_nearest_node(self, graph: Graph, pos: Tuple[int, int]) -> GraphNode:
        """Находит ближайший узел к заданной позиции"""
        x, y = pos
        nearest: Optional[GraphNode] = None
        min_dist = float("inf")

        for node in graph.nodes.values():
            dist = (node.x - x) ** 2 + (node.y - y) ** 2
            if dist < min_dist:
                min_dist = dist
                nearest = node

        if nearest is None:
            raise ValueError("No nodes found in graph")

        return nearest

    def _create_path_overlay(
        self, image_data: bytes, path_metrics: PathMetrics, graph: Graph
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
                location=BoundingBox(x=node.x - 5, y=node.y - 5, width=10, height=10),
                style=Style(color=color, border_width=3, opacity=0.9, fill_color=color),
                content=str(i + 1),
                metadata={"node_id": node_id, "step": i},
            )
            overlay.add_element(element)

        return overlay

    async def analyze_mesh_topology(
        self, image_data: bytes, context: Optional[Dict[str, Any]] = None
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
        for bottleneck in analysis["bottlenecks"]:
            node = graph.nodes.get(bottleneck["node_id"])
            if node:
                overlay.add_element(
                    OverlayElement(
                        element_type="bottleneck",
                        location=BoundingBox(
                            x=node.x - 15, y=node.y - 15, width=30, height=30
                        ),
                        style=Style(color="#FF0000", border_width=3, opacity=0.8),
                        content=f"Bottleneck: {bottleneck['connections']} connections",
                        metadata=bottleneck,
                    )
                )

        # Отмечаем изолированные узлы
        for isolated_id in analysis["isolated_nodes"]:
            node = graph.nodes.get(isolated_id)
            if node:
                overlay.add_element(
                    OverlayElement(
                        element_type="isolated",
                        location=BoundingBox(
                            x=node.x - 10, y=node.y - 10, width=20, height=20
                        ),
                        style=Style(color="#FFA500", border_width=2, opacity=0.8),
                        content="Isolated node",
                        metadata={"node_id": isolated_id},
                    )
                )

        result = {
            "nodes_detected": len(graph.nodes),
            "links_detected": sum(len(e) for e in graph.edges.values()) // 2,
            "bottlenecks": analysis["bottlenecks"],
            "isolated_nodes": analysis["isolated_nodes"],
            "connectivity_score": analysis["connectivity_score"],
            "recommendations": analysis["recommendations"],
            "processing_time_ms": (time.time() - start_time) * 1000,
            "overlay": overlay.to_dict(),
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
                node_id: len(graph.edges.get(node_id, [])) for node_id in graph.nodes
            }
            avg_connections = sum(connection_counts.values()) / len(connection_counts)

            # Bottleneck = узел с > 2x среднего числа связей
            threshold = max(4, avg_connections * 2)
            for node_id, count in connection_counts.items():
                if count >= threshold:
                    node = graph.nodes[node_id]
                    bottlenecks.append(
                        {
                            "node_id": node_id,
                            "connections": count,
                            "location": {"x": node.x, "y": node.y},
                            "severity": "high" if count > threshold * 1.5 else "medium",
                        }
                    )
                    recommendations.append(
                        {
                            "action": "add_redundant_link",
                            "target": node_id,
                            "reason": f"Node has {count} connections (high centrality)",
                        }
                    )
                elif count == 0:
                    isolated_nodes.append(node_id)
                    recommendations.append(
                        {
                            "action": "connect_isolated_node",
                            "target": node_id,
                            "reason": "Node is completely isolated",
                        }
                    )
                elif count == 1:
                    # Узел с одним соединением - потенциальная точка отказа
                    recommendations.append(
                        {
                            "action": "add_backup_link",
                            "target": node_id,
                            "reason": "Single point of failure (only 1 connection)",
                        }
                    )

        # Вычисляем connectivity score (0-1)
        if graph.nodes:
            max_edges = len(graph.nodes) * (len(graph.nodes) - 1) / 2
            actual_edges = sum(len(e) for e in graph.edges.values()) / 2
            connectivity_score = min(1.0, actual_edges / max(1, max_edges) * 10)
        else:
            connectivity_score = 0.0

        return {
            "bottlenecks": bottlenecks,
            "isolated_nodes": isolated_nodes,
            "connectivity_score": round(connectivity_score, 2),
            "recommendations": recommendations[:10],  # Top 10 recommendations
        }

    async def detect_anomalies(
        self, image_data: bytes, baseline_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Обнаруживает визуальные аномалии на изображении.

        Если предоставлен baseline, сравнивает с ним.
        """
        import io

        start_time = time.time()

        image = Image.open(io.BytesIO(image_data))
        img_array = numpy.array(image.convert("RGB"))

        anomalies = []

        if baseline_data:
            # Сравнение с baseline
            baseline_img = Image.open(io.BytesIO(baseline_data))
            baseline_array = numpy.array(baseline_img.convert("RGB"))

            # Resize if different sizes
            if baseline_array.shape != img_array.shape:
                baseline_img = baseline_img.resize(image.size)
                baseline_array = numpy.array(baseline_img.convert("RGB"))

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

                    anomalies.append(
                        {
                            "type": "visual_change",
                            "location": {
                                "x": int(x_min),
                                "y": int(y_min),
                                "width": int(x_max - x_min),
                                "height": int(y_max - y_min),
                            },
                            "severity": "high" if change_intensity > 100 else "medium",
                            "confidence": min(1.0, change_intensity / 100),
                        }
                    )
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

                    anomalies.append(
                        {
                            "type": "bright_spot",
                            "location": {
                                "x": int(x_min),
                                "y": int(y_min),
                                "width": int(x_max - x_min),
                                "height": int(y_max - y_min),
                            },
                            "severity": "low",
                            "confidence": 0.7,
                        }
                    )

        return {
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies,
            "processing_time_ms": (time.time() - start_time) * 1000,
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
    image_data: bytes, start_pos: Tuple[int, int], end_pos: Tuple[int, int]
) -> Dict[str, Any]:
    """Утилита для анализа лабиринта"""
    engine = get_vision_engine()
    return await engine.analyze_maze(image_data, start_pos, end_pos)


async def analyze_mesh_topology(
    image_data: bytes, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Утилита для анализа топологии mesh-сети"""
    engine = get_vision_engine()
    return await engine.analyze_mesh_topology(image_data, context)


async def detect_anomalies(
    image_data: bytes, baseline_data: Optional[bytes] = None
) -> Dict[str, Any]:
    """Утилита для обнаружения визуальных аномалий"""
    engine = get_vision_engine()
    return await engine.detect_anomalies(image_data, baseline_data)
