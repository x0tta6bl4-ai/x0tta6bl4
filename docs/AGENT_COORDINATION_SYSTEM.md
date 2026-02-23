# Agent Coordination System

## Обзор

Система автоматической координации действий между несколькими ИИ-агентами, работающими одновременно над проектом MaaS x0tta6bl4.

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT COORDINATION SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   GEMINI     │    │    CODEX     │    │   CLAUDE     │          │
│  │  (Architect) │    │   (Coder)    │    │  (Reviewer)  │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│                    ┌────────▼────────┐                              │
│                    │  EVENT BUS      │                              │
│                    │  (Pub/Sub)      │                              │
│                    └────────┬────────┘                              │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                   │
│  ┌──────▼───────┐    ┌──────▼───────┐    ┌──────▼───────┐          │
│  │ COORDINATOR  │    │  TASK QUEUE  │    │  CONFLICT    │          │
│  │  (Locks)     │    │  (Pipeline)  │    │  DETECTOR    │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                      │
│                    ┌────────────────┐                                │
│                    │  GLM-5         │                                │
│                    │  (Researcher)  │                                │
│                    └────────────────┘                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. AgentCoordinator (`src/coordination/state.py`)

Центральный координатор для управления состоянием агентов и блокировками файлов.

**Основные функции:**
- Регистрация/отмена регистрации агентов
- Блокировка файлов (file-based locking)
- Проверка зон доступа
- Heartbeat мониторинг

**Зоны файлов по ролям:**

| Роль | Разрешённые пути | Запрещённые пути |
|------|------------------|------------------|
| Gemini (Architect) | `plans/`, `docs/adr/` | `src/`, `tests/` |
| Codex (Coder) | `src/`, `tests/`, `alembic/` | `plans/`, `ROADMAP.md` |
| Claude (Reviewer) | `src/`, `tests/`, `docs/` | — |
| GLM-5 (Researcher) | `experiments/`, `tests/load/` | `src/` |
| Human (Coordinator) | Все | — |

### 2. EventBus (`src/coordination/events.py`)

Система publish-subscribe для коммуникации между агентами.

**Типы событий:**
- `AGENT_*` — жизненный цикл агентов
- `TASK_*` — создание, назначение, завершение задач
- `LOCK_*` — блокировка и разблокировка файлов
- `PIPELINE_*` — переходы между стадиями
- `CONFLICT_*` — обнаружение и разрешение конфликтов

### 3. TaskQueue (`src/coordination/tasks.py`)

Очередь задач с приоритетами и отслеживанием зависимостей.

**Типы задач:**
- `DESIGN_*` — архитектура, интерфейсы, декомпозиция
- `CODE_*` — реализация, тесты, миграции
- `REVIEW_*` — код-ревью, безопасность, рефакторинг
- `RESEARCH_*` — альтернативы, оптимизация, нагрузочные тесты
- `INTEGRATE_*` — слияние, деплой, документация

**Приоритеты:**
- `CRITICAL` (P0) — немедленное выполнение
- `HIGH` (P1) — высокая важность
- `MEDIUM` (P2) — нормальный приоритет
- `LOW` (P3) — низкий приоритет
- `BACKGROUND` — фоновые задачи

### 4. ConflictDetector (`src/coordination/conflicts.py`)

Автоматическое обнаружение и разрешение конфликтов.

**Типы конфликтов:**
- `FILE_LOCK` — несколько агентов хотят один файл
- `ZONE_VIOLATION` — агент в запрещённой зоне
- `PRIORITY` — агенты с одинаковым приоритетом
- `PIPELINE` — нарушение порядка стадий

**Стратегии разрешения:**
- `PRIORITY` — выше приоритет выигрывает
- `FIRST_COME` — первый пришёл — первый обслужен
- `ROLE_BASED` — иерархия ролей
- `QUEUE` — постановка в очередь
- `MANUAL` — требуется вмешательство человека

## CLI Использование

### Регистрация агента

```bash
# Регистрация Gemini как архитектора
python -m src.coordination.cli register gemini-1 gemini --description "Design agent"

# Регистрация Codex как кодера
python -m src.coordination.cli register codex-1 codex --description "Implementation agent"

# Регистрация Claude как ревьюера
python -m src.coordination.cli register claude-1 claude --description "Review agent"
```

### Статус координации

```bash
# Показать статус всех агентов
python -m src.coordination.cli status
```

### Блокировка файлов

```bash
# Заблокировать файл для работы
python -m src.coordination.cli lock codex-1 src/api/new_endpoint.py

# Освободить блокировку
python -m src.coordination.cli lock codex-1 src/api/new_endpoint.py --release
```

### Управление задачами

```bash
# Показать очередь задач
python -m src.coordination.cli tasks --list

# Создать задачу
python -m src.coordination.cli tasks --create \
    --title "Implement user authentication" \
    --type code.implement \
    --priority high \
    --role codex

# Создать pipeline (5 связанных задач)
python -m src.coordination.cli tasks --pipeline \
    --title "Swarm Intelligence Phase 2" \
    --description "Distributed decision making" \
    --files "src/swarm/,tests/test_swarm.py" \
    --priority high

# Назначить задачу агенту
python -m src.coordination.cli tasks --assign --task-id abc123 --agent-id codex-1

# Завершить задачу
python -m src.coordination.cli tasks --complete --task-id abc123 --result "Implemented successfully"
```

### Получение следующей задачи

```bash
# Получить следующую задачу для агента
python -m src.coordination.cli next codex-1
```

### Управление конфликтами

```bash
# Обнаружить конфликты
python -m src.coordination.cli conflicts --detect

# Автоматически разрешить конфликты
python -m src.coordination.cli conflicts --resolve
```

### Просмотр событий

```bash
# Показать последние события
python -m src.coordination.cli events --limit 50
```

## Программный API

### Инициализация

```python
from src.coordination import (
    AgentCoordinator,
    EventBus,
    TaskQueue,
    ConflictDetector,
    AgentRole,
)

# Инициализация компонентов
coordinator = AgentCoordinator(".")
event_bus = EventBus(".")
task_queue = TaskQueue(".")
conflict_detector = ConflictDetector(coordinator, ".")
```

### Регистрация агента

```python
# Регистрация
state = coordinator.register_agent(
    agent_id="codex-1",
    role=AgentRole.CODER,
    metadata={"description": "Main implementation agent"}
)

# Heartbeat
coordinator.heartbeat("codex-1")

# Обновление статуса
coordinator.update_agent_status(
    "codex-1",
    status="working",
    current_task="src/api/new_endpoint.py"
)
```

### Работа с блокировками

```python
# Проверка доступа
if coordinator.can_access("codex-1", "src/api/new_endpoint.py"):
    # Блокировка файла
    if coordinator.acquire_lock("codex-1", "src/api/new_endpoint.py"):
        # Работа с файлом
        ...
        # Освобождение
        coordinator.release_lock("codex-1", "src/api/new_endpoint.py")
```

### Создание pipeline

```python
# Создание полного pipeline для фичи
tasks = task_queue.create_pipeline(
    title="User Authentication",
    description="Implement OAuth2 authentication",
    files={"src/auth/", "tests/test_auth.py"},
    priority=TaskPriority.HIGH,
)

# tasks[0] -> Design (Gemini)
# tasks[1] -> Code (Codex)
# tasks[2] -> Research (GLM-5)
# tasks[3] -> Review (Claude)
# tasks[4] -> Integrate (Human)
```

### Публикация событий

```python
from src.coordination.events import emit_pipeline_handoff

# Передача работы между агентами
emit_pipeline_handoff(
    event_bus,
    source_agent="codex-1",
    target_agent="claude-1",
    stage="code",
    artifacts=["src/api/new_endpoint.py", "tests/test_new_endpoint.py"]
)
```

### Обработка конфликтов

```python
# Обнаружение конфликтов
conflicts = conflict_detector.detect_conflicts()

# Автоматическое разрешение
resolutions = conflict_detector.auto_resolve()

for resolution in resolutions:
    print(f"Conflict {resolution.conflict_id}: {resolution.message}")
    if resolution.winner:
        print(f"  Winner: {resolution.winner}")
```

## Хранение данных

Все данные координации хранятся в директории `.agent_coordination/`:

```
.agent_coordination/
├── state.json          # Состояние агентов и блокировок
├── tasks.json          # Очередь задач
├── events.log          # Лог событий (по строкам JSON)
├── conflicts.json      # История конфликтов
└── locks/              # Файловые блокировки
    ├── a1b2c3d4.lock   # Блокировка файла (MD5 хеш пути)
    └── ...
```

## Интеграция с агентами

### Gemini (Architect)

```python
# После завершения дизайна
emit_pipeline_handoff(
    event_bus,
    source_agent="gemini-1",
    target_agent="codex-1",
    stage="design",
    artifacts=["plans/feature_x.md"]
)

task_queue.complete_task(
    design_task.task_id,
    result="Design complete",
    artifacts={"design_doc": "plans/feature_x.md"}
)
```

### Codex (Coder)

```python
# Получение следующей задачи
tasks = task_queue.get_tasks_for_agent("codex-1", "codex")
if tasks:
    task = tasks[0]
    
    # Блокировка файлов
    for file in task.target_files:
        coordinator.acquire_lock("codex-1", file)
    
    # Обновление статуса
    coordinator.update_agent_status("codex-1", "working", task.title)
    
    # ... реализация ...
    
    # Завершение
    task_queue.complete_task(
        task.task_id,
        result="Implemented",
        created_files={"src/api/new_endpoint.py"}
    )
```

### Claude (Reviewer)

```python
# Подписка на события завершения кода
event_bus.subscribe(
    EventType.TASK_COMPLETED,
    lambda event: handle_code_completion(event) if event.data.get("task_type") == "code.implement" else None
)

def handle_code_completion(event):
    # Создание задачи ревью
    task_queue.add_task(
        task_type=TaskType.REVIEW_CODE,
        title=f"Review: {event.data['task_id']}",
        depends_on={event.data["task_id"]},
        assigned_role="claude",
    )
```

## Мониторинг

### Метрики

```python
# Статистика очереди
stats = task_queue.get_stats()
print(f"Total tasks: {stats['total']}")
print(f"Overdue: {stats['overdue']}")
print(f"Blocked: {stats['blocked']}")

# Активные агенты
active = coordinator.get_active_agents()
print(f"Active agents: {len(active)}")

# Конфликты
conflicts = conflict_detector.get_active_conflicts()
print(f"Active conflicts: {len(conflicts)}")
```

### Алерты

Система автоматически генерирует алерты при:
- Истечении срока блокировки (TTL)
- Просроченных задачах
- Критических конфликтах
- Неактивных агентах (нет heartbeat > 5 минут)

## Best Practices

1. **Всегда регистрируйте агента** перед началом работы
2. **Используйте heartbeat** каждые 30-60 секунд
3. **Блокируйте файлы** перед изменением
4. **Освобождайте блокировки** после завершения
5. **Публикуйте события** при переходе между стадиями
6. **Создавайте pipeline** для сложных фич
7. **Проверяйте конфликты** регулярно

---

*Последнее обновление: 2026-02-21*
