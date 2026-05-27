import pytest

from src.network.parl_mesh_integration import PARLMeshOptimizer
from src.network.routing.mesh_router import RouteEntry


class FakePARLController:
    def __init__(self, results):
        self.results = results
        self.tasks = []

    async def execute_parallel(self, tasks):
        self.tasks = tasks
        return self.results(tasks)


@pytest.mark.asyncio
async def test_optimize_routes_uses_worker_best_route_and_fallback_ranking():
    def results(tasks):
        return [
            {
                "success": True,
                "task_id": tasks[0]["task_id"],
                "result": {
                    "destination": "node-a",
                    "best_route": {
                        "destination": "node-a",
                        "next_hop": "fast-hop",
                        "hop_count": 3,
                        "seq_num": 1,
                    },
                },
            },
            {
                "success": False,
                "task_id": tasks[1]["task_id"],
                "error": "worker unavailable",
            },
        ]

    controller = FakePARLController(results)
    optimizer = PARLMeshOptimizer(parl_controller=controller)
    routes = {
        "node-a": [
            RouteEntry("node-a", "local-best", hop_count=1, seq_num=10),
            RouteEntry("node-a", "fast-hop", hop_count=3, seq_num=1),
        ],
        "node-b": [
            RouteEntry("node-b", "stale", hop_count=1, seq_num=99, valid=False),
            RouteEntry("node-b", "usable", hop_count=2, seq_num=1, valid=True),
        ],
    }

    optimized = await optimizer.optimize_routes_parallel(routes)

    assert optimized["node-a"][0].next_hop == "fast-hop"
    assert optimized["node-a"][1].next_hop == "local-best"
    assert optimized["node-b"][0].next_hop == "usable"
    assert optimized["node-b"][1].next_hop == "stale"

    assert all(isinstance(task, dict) for task in controller.tasks)
    assert controller.tasks[0]["task_type"] == "route_optimization"
    assert controller.tasks[0]["payload"]["routes"][0]["next_hop"] == "local-best"


@pytest.mark.asyncio
async def test_optimize_routes_accepts_worker_ordered_route_list():
    def results(tasks):
        return [
            {
                "success": True,
                "task_id": tasks[0]["task_id"],
                "result": {
                    "destination": "node-a",
                    "routes": [
                        {
                            "destination": "node-a",
                            "next_hop": "third",
                            "hop_count": 3,
                            "seq_num": 1,
                        },
                        {
                            "destination": "node-a",
                            "next_hop": "first",
                            "hop_count": 1,
                            "seq_num": 9,
                        },
                    ],
                },
            }
        ]

    optimizer = PARLMeshOptimizer(parl_controller=FakePARLController(results))
    routes = {
        "node-a": [
            RouteEntry("node-a", "first", hop_count=1, seq_num=9),
            RouteEntry("node-a", "second", hop_count=2, seq_num=5),
            RouteEntry("node-a", "third", hop_count=3, seq_num=1),
        ],
    }

    optimized = await optimizer.optimize_routes_parallel(routes)

    assert [route.next_hop for route in optimized["node-a"]] == [
        "third",
        "first",
        "second",
    ]


@pytest.mark.asyncio
async def test_detect_anomalies_uses_dict_tasks_and_result_payloads():
    def results(tasks):
        return [
            {
                "success": True,
                "task_id": tasks[0]["task_id"],
                "result": {"node_id": "node-a", "is_anomaly": True},
            },
            {
                "success": True,
                "task_id": tasks[1]["task_id"],
                "result": {"node_id": "node-b", "is_anomaly": False},
            },
        ]

    controller = FakePARLController(results)
    optimizer = PARLMeshOptimizer(parl_controller=controller)

    anomalies = await optimizer.detect_anomalies_parallel(
        {"node-a": {"cpu": 99}, "node-b": {"cpu": 20}}
    )

    assert anomalies == ["node-a"]
    assert all(isinstance(task, dict) for task in controller.tasks)
    assert controller.tasks[0]["task_type"] == "anomaly_detection"
