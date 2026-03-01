# Swarm Usage Guide

В этом руководстве описано, как разработчикам взаимодействовать с роем агентов x0tta6bl4.

## Инициализация
В коде бэкенда оркестратор инициализируется глобально:
```python
from src.swarm.orchestrator import SwarmOrchestrator
orchestrator = SwarmOrchestrator()
await orchestrator.start()
```

## Выполнение задач через PARL
Для выполнения тяжелых оптимизационных задач (например, пересчет маршрутов mesh-сети), используйте PARL контроллер:

```python
from src.swarm.parl.controller import PARLController, TaskContext

controller = PARLController(max_workers=10)
await controller.initialize()

tasks = [
    {"task_id": "1", "task_type": "analysis", "payload": {}},
    {"task_id": "2", "task_type": "analysis", "payload": {}}
]

results = await controller.execute_parallel(tasks)
print(results)
```
