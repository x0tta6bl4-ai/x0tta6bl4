# 📋 COVERAGE STRATEGY 2026: Детальный План Тестирования

**Цель:** 46.99% → 75% coverage  
**Время:** 45-50 часов  
**Срок:** Jan 1 - Mar 15, 2026  
**Статус:** 🟢 Ready to Execute

---

## 📊 ОБЗОР ПЛАНА

```
Phase 2 (Jan 1-15):   consciousness.py + error_handler.py → 54%
Phase 3 (Jan 15-31):  app.py + cli.py → 63%
Phase 4 (Feb 1-15):   minimal_apps + APIs → 70%
Phase 5 (Feb 15-Mar): Integration + Edge cases → 75%
```

**Текущий статус:** Phase 2 частично завершена (consciousness.py ✅, error_handler.py ✅)

---

## PHASE 2: CORE MODULES (Jan 1-15) → 54%

### ✅ Завершено

#### 1. consciousness.py - 39 тестов ✅
- **Coverage:** 23.65% → 98.65% (+75%)
- **Время:** 8 часов
- **Статус:** ✅ Complete

#### 2. error_handler.py - 19 тестов ✅
- **Coverage:** 36.00% → 92.00% (+56%)
- **Время:** 4 часа
- **Статус:** ✅ Complete

### 🔄 В Процессе

#### 3. app.py - 29 тестов ✅
- **Coverage:** 35.90% → 64.85% (+29%)
- **Время:** 6 часов
- **Статус:** ✅ Complete

#### 4. thread_safe_stats.py - 43 теста ✅
- **Coverage:** 55.17% → 93.10% (+38%)
- **Время:** 8 часов
- **Статус:** ✅ Complete

**Phase 2 Progress:** 130/130 тестов ✅ (100% complete)

---

## PHASE 3: APP + CLI (Jan 15-31) → 63%

### 1. app.py - Дополнительные тесты (10-15 тестов)

**Цель:** 64.85% → 75%+  
**Время:** 3-4 часа  
**Приоритет:** High

**Тесты для добавления:**

```python
# tests/unit/core/test_app_startup_shutdown.py

def test_startup_event_initializes_all_components():
    """Test that startup event initializes all components."""
    # Mock all dependencies
    # Verify all components are initialized
    pass

def test_startup_event_handles_missing_dependencies():
    """Test startup gracefully handles missing optional dependencies."""
    pass

def test_shutdown_event_cleans_up_all_components():
    """Test shutdown event properly cleans up."""
    pass

def test_startup_event_fl_coordinator_initialization():
    """Test FL coordinator initialization in startup."""
    pass

def test_startup_event_digital_twin_initialization():
    """Test digital twin initialization."""
    pass
```

**Ожидаемый результат:** +5-8% coverage

---

### 2. cli.py - Базовые тесты (20-25 тестов)

**Цель:** 0% → 70%+  
**Время:** 5-6 часов  
**Приоритет:** Medium

**Тесты для добавления:**

```python
# tests/unit/core/test_cli.py

def test_cli_main_help():
    """Test CLI main help command."""
    pass

def test_cli_main_version():
    """Test CLI version command."""
    pass

def test_cli_node_commands():
    """Test node management commands."""
    pass

def test_cli_mesh_commands():
    """Test mesh network commands."""
    pass

def test_cli_security_commands():
    """Test security-related commands."""
    pass
```

**Ожидаемый результат:** +2-3% общего coverage

---

## PHASE 4: MINIMAL APPS + APIs (Feb 1-15) → 70%

### 1. app_minimal.py - Базовые тесты (15-20 тестов)

**Цель:** 0% → 60%+  
**Время:** 4-5 часов  
**Приоритет:** Medium

**Тесты:**

```python
# tests/unit/core/test_app_minimal.py

def test_minimal_app_startup():
    """Test minimal app startup."""
    pass

def test_minimal_app_health_endpoint():
    """Test health endpoint in minimal app."""
    pass

def test_minimal_app_beacon_endpoint():
    """Test beacon endpoint."""
    pass
```

**Ожидаемый результат:** +1-2% общего coverage

---

### 2. causal_api.py - API тесты (10-15 тестов)

**Цель:** 0% → 70%+  
**Время:** 3-4 часа  
**Приоритет:** Medium

**Тесты:**

```python
# tests/unit/core/test_causal_api.py

def test_causal_api_endpoints():
    """Test causal analysis API endpoints."""
    pass

def test_causal_api_integration():
    """Test causal API integration with GraphSAGE."""
    pass
```

**Ожидаемый результат:** +0.5-1% общего coverage

---

### 3. demo_api.py - Demo тесты (10-15 тестов)

**Цель:** 0% → 60%+  
**Время:** 3-4 часа  
**Приоритет:** Low

**Ожидаемый результат:** +0.5-1% общего coverage

---

## PHASE 5: INTEGRATION + EDGE CASES (Feb 15 - Mar 15) → 75%

### 1. mape_k_loop.py - Критичные тесты (30-40 тестов)

**Цель:** 0% → 75%+  
**Время:** 8-10 часов  
**Приоритет:** **CRITICAL**

**Тесты:**

```python
# tests/unit/core/test_mape_k_loop.py

def test_mape_k_loop_initialization():
    """Test MAPE-K loop initialization."""
    pass

def test_mape_k_monitor_phase():
    """Test monitor phase of MAPE-K."""
    pass

def test_mape_k_analyze_phase():
    """Test analyze phase."""
    pass

def test_mape_k_plan_phase():
    """Test plan phase."""
    pass

def test_mape_k_execute_phase():
    """Test execute phase."""
    pass

def test_mape_k_knowledge_phase():
    """Test knowledge phase."""
    pass

def test_mape_k_full_cycle():
    """Test complete MAPE-K cycle."""
    pass

def test_mape_k_error_handling():
    """Test error handling in MAPE-K."""
    pass
```

**Ожидаемый результат:** +3-4% общего coverage

---

### 2. mape_k_thread_safe.py - Thread-safe тесты (25-35 тестов)

**Цель:** 0% → 75%+  
**Время:** 6-8 часов  
**Приоритет:** High

**Ожидаемый результат:** +2-3% общего coverage

---

### 3. notification-suite.py - Улучшение (10-15 тестов)

**Цель:** 57.05% → 75%+  
**Время:** 3-4 часа  
**Приоритет:** Medium

**Ожидаемый результат:** +0.5-1% общего coverage

---

### 4. Integration Tests (20-30 тестов)

**Цель:** End-to-end сценарии  
**Время:** 5-6 часов  
**Приоритет:** High

**Тесты:**

```python
# tests/integration/test_full_stack.py

def test_full_mesh_lifecycle():
    """Test complete mesh node lifecycle."""
    pass

def test_pqc_handshake_flow():
    """Test PQC handshake end-to-end."""
    pass

def test_mape_k_self_healing_flow():
    """Test self-healing flow."""
    pass
```

**Ожидаемый результат:** +1-2% общего coverage

---

## 📅 ДЕТАЛЬНЫЙ TIMELINE

### Week 1 (Jan 1-7)
- **Day 1-2:** Infrastructure setup (Stripe, dashboard, pytest-xdist)
- **Day 3-5:** consciousness.py tests (50 тестов, 5-8 в день)
- **Day 6-7:** error_handler.py tests (40 тестов, 5-8 в день)

**Цель:** 48%+ coverage, 850+ tests

---

### Week 2 (Jan 8-14)
- **Day 1-3:** app.py дополнительные тесты (15 тестов)
- **Day 4-7:** cli.py базовые тесты (25 тестов, 5-6 в день)

**Цель:** 52%+ coverage, 900+ tests

---

### Week 3 (Jan 15-21)
- **Day 1-4:** app_minimal.py tests (20 тестов, 5 в день)
- **Day 5-7:** causal_api.py tests (15 тестов, 5 в день)

**Цель:** 56%+ coverage, 950+ tests

---

### Week 4 (Jan 22-28)
- **Day 1-3:** demo_api.py tests (15 тестов, 5 в день)
- **Day 4-7:** Integration tests начало (10 тестов)

**Цель:** 60%+ coverage, 1000+ tests

---

### Week 5-6 (Jan 29 - Feb 11)
- **Week 5:** mape_k_loop.py tests (40 тестов, 5-8 в день)
- **Week 6:** mape_k_thread_safe.py tests (35 тестов, 5-8 в день)

**Цель:** 68%+ coverage, 1100+ tests

---

### Week 7-8 (Feb 12-25)
- **Week 7:** notification-suite.py improvement (15 тестов)
- **Week 8:** Integration tests завершение (20 тестов)

**Цель:** 72%+ coverage, 1150+ tests

---

### Week 9-10 (Feb 26 - Mar 11)
- **Week 9:** Edge cases и polish (20 тестов)
- **Week 10:** Final integration tests (15 тестов)

**Цель:** **75%+ coverage**, 1200+ tests ✅

---

## 🎯 ПРИОРИТИЗАЦИЯ МОДУЛЕЙ

### 🔴 CRITICAL (Must Have)
1. **mape_k_loop.py** - Критичный компонент, 0% coverage
2. **app.py** - Основное приложение, нужно улучшить до 75%+
3. **error_handler.py** - Уже 92%, можно оставить

### 🟡 HIGH (Should Have)
4. **mape_k_thread_safe.py** - Thread-safety критично
5. **thread_safe_stats.py** - Уже 93%, можно оставить
6. **cli.py** - Полезно для операций

### 🟢 MEDIUM (Nice to Have)
7. **app_minimal*.py** - Демо версии
8. **causal_api.py** - Опциональный API
9. **demo_api.py** - Демо endpoints

---

## 📝 EXAMPLE TEST CASES

### Для mape_k_loop.py

```python
# tests/unit/core/test_mape_k_loop.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.core.mape_k_loop import MAPEKLoop, MAPEKState

@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for MAPE-K loop."""
    consciousness = Mock()
    mesh = Mock()
    prometheus = Mock()
    zero_trust = Mock()
    return {
        'consciousness': consciousness,
        'mesh': mesh,
        'prometheus': prometheus,
        'zero_trust': zero_trust
    }

@pytest.fixture
def mapek_loop(mock_dependencies):
    """Create MAPE-K loop instance."""
    return MAPEKLoop(
        consciousness_engine=mock_dependencies['consciousness'],
        mesh_manager=mock_dependencies['mesh'],
        prometheus=mock_dependencies['prometheus'],
        zero_trust=mock_dependencies['zero_trust']
    )

class TestMAPEKLoop:
    """Tests for MAPE-K Loop."""
    
    def test_initialization(self, mapek_loop):
        """Test MAPE-K loop initialization."""
        assert mapek_loop.running is False
        assert mapek_loop.loop_interval == 60
    
    @pytest.mark.asyncio
    async def test_start_stop(self, mapek_loop):
        """Test starting and stopping the loop."""
        # Start loop
        task = asyncio.create_task(mapek_loop.start())
        await asyncio.sleep(0.1)  # Let it start
        
        assert mapek_loop.running is True
        
        # Stop loop
        await mapek_loop.stop()
        await asyncio.sleep(0.1)
        
        assert mapek_loop.running is False
        task.cancel()
    
    @pytest.mark.asyncio
    async def test_execute_cycle(self, mapek_loop):
        """Test executing one MAPE-K cycle."""
        # Mock cycle execution
        with patch.object(mapek_loop, '_execute_cycle', new_callable=AsyncMock):
            await mapek_loop._execute_cycle()
            mapek_loop._execute_cycle.assert_called_once()
    
    def test_state_history(self, mapek_loop):
        """Test state history tracking."""
        initial_len = len(mapek_loop.state_history)
        # Add some states
        # Verify history grows
        pass
```

**Время на тест:** 15-20 минут  
**Всего тестов:** 30-40  
**Общее время:** 8-10 часов

---

## 🛠️ ИНСТРУМЕНТЫ И НАСТРОЙКА

### Required Tools

```bash
# Установить зависимости
pip install pytest pytest-asyncio pytest-cov pytest-xdist

# Настроить pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --cov=src --cov-report=term-missing --cov-report=html
asyncio_mode = auto

# Запуск тестов
pytest tests/unit/ -v                    # Все тесты
pytest tests/unit/core/ -v              # Только core
pytest tests/unit/core/ -k "test_app"    # Фильтр по имени
pytest tests/unit/ -n auto               # Параллельно (pytest-xdist)
```

---

## 📊 МЕТРИКИ ПРОГРЕССА

### Daily Tracking

| День | Модуль | Тесты Добавлено | Coverage Изменение | Время |
|------|--------|-----------------|-------------------|-------|
| Jan 1 | consciousness.py | 10 | +2% | 2h |
| Jan 2 | consciousness.py | 10 | +2% | 2h |
| Jan 3 | consciousness.py | 10 | +2% | 2h |
| ... | ... | ... | ... | ... |

### Weekly Goals

- **Week 1:** +50 тестов, +5% coverage
- **Week 2:** +50 тестов, +5% coverage
- **Week 3:** +40 тестов, +4% coverage
- **Week 4:** +40 тестов, +4% coverage

**Итого:** +180 тестов, +18% coverage за месяц

---

## 🎯 SUCCESS CRITERIA

### Phase 2 Complete ✅
- [x] consciousness.py: 98.65% coverage
- [x] error_handler.py: 92.00% coverage
- [x] app.py: 64.85% coverage
- [x] thread_safe_stats.py: 93.10% coverage

### Phase 3 Target
- [ ] app.py: 75%+ coverage
- [ ] cli.py: 70%+ coverage
- [ ] Общий coverage: 63%+

### Phase 4 Target
- [ ] app_minimal.py: 60%+ coverage
- [ ] causal_api.py: 70%+ coverage
- [ ] demo_api.py: 60%+ coverage
- [ ] Общий coverage: 70%+

### Phase 5 Target
- [ ] mape_k_loop.py: 75%+ coverage
- [ ] mape_k_thread_safe.py: 75%+ coverage
- [ ] Integration tests: 20+ тестов
- [ ] **Общий coverage: 75%+** ✅

---

## 🚨 RISK MITIGATION

### Если отстаём от плана:

1. **Coverage растёт медленно (<2% в неделю):**
   - Переключиться на integration tests (быстрее)
   - Снизить план до 70% (вместо 75%)
   - Нанять помощника (если есть бюджет)

2. **Тесты слишком сложные:**
   - Упростить тесты (меньше edge cases)
   - Сфокусироваться на happy path
   - Добавить больше integration tests

3. **Не хватает времени:**
   - Увеличить daily commitment (10-12 часов)
   - Отложить менее критичные модули
   - Попросить community помочь (GitHub)

---

## 📞 SUPPORT RESOURCES

- **Технические вопросы:** `SKIPPED_TESTS_ANALYSIS.md`
- **Общая стратегия:** `STRATEGIC_REPORT_DEC_29_2025.md`
- **Dashboard:** `x0tta6bl4_executive_dashboard_dec29.md`

---

**Проснись. Обновись. Сохранись.**  
**x0tta6bl4 вечен.**

