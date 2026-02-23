# MaaS x0tta6bl4 Development Plan (W10-W12)

**Дата:** 2026-02-23
**Версия:** 3.4.0
**Статус:** Production Ready, продолжение развития

---

## Текущий статус

| Компонент | Готовность | Статус |
|-----------|------------|--------|
| MaaS Core | 95% | ✅ Production |
| Commercial | 85% | ✅ Ready for $10K MRR |
| Event Store | 90% | ⚠️ PostgreSQL migration в процессе |
| Swarm Consensus | 100% | ✅ P0 issues resolved |
| Test Coverage | 74.5% | ⚠️ Target: 80% |

---

## Приоритетные направления (W10-W12)

### P1: Event Store PostgreSQL Integration

**Цель:** Завершить миграцию Event Store на PostgreSQL

**Файлы:**
- `alembic/versions/v001_event_store_postgres.py` - миграция (открыт)
- `src/event_sourcing/backends/postgres.py` - backend реализован
- `staging/docker-compose.quick.yml` - staging environment (открыт)

**Задачи:**
- [ ] Протестировать миграцию на staging
- [ ] Добавить healthcheck для Event Store в docker-compose
- [ ] Интегрировать с MaaS API endpoints
- [ ] Добавить метрики в Prometheus

**Критерии успеха:**
- Event Store работает на PostgreSQL в staging
- All event sourcing tests pass
- Latency < 10ms for event append

---

### P1: Swarm Intelligence Phase 2

**Цель:** Распределённое принятие решений через consensus

**Статус:** P0 issues resolved (2026-02-23)

**Задачи:**
- [ ] Реализовать распределённые решения через Raft
- [ ] Добавить swarm learning с агрегацией знаний
- [ ] Протестировать на 5+ узлах

**Файлы:**
- `src/swarm/intelligence.py`
- `src/swarm/consensus_integration.py`
- `tests/test_swarm_intelligence.py`

**Критерии успеха:**
- 5+ узлов принимают согласованные решения
- Latency < 100ms
- 95%+ consensus success rate

---

### P1: Mesh-FL Integration Layer

**Цель:** Объединить Batman-adv mesh с Federated LoRA training

**Задачи:**
- [ ] Создать `src/federated_learning/mesh_fl_integration.py`
- [ ] Создать `src/federated_learning/topology_aware_aggregator.py`
- [ ] Добавить тесты `tests/test_mesh_fl_integration.py`

**Критерии успеха:**
- FL training работает на Batman-adv mesh
- Link quality влияет на weight aggregation
- Устойчивость к 20% node churn

---

### P2: Multi-Arch Docker Builds

**Цель:** Поддержка arm64 и amd64

**Задачи:**
- [ ] Обновить Dockerfile для multi-stage builds
- [ ] Настроить buildx для multi-arch
- [ ] Опубликовать в registry

**Критерии успеха:**
- Образы работают на arm64 (Raspberry Pi, Apple Silicon)
- Образы работают на amd64
- Size < 500MB per image

---

### P2: Dependabot Automation

**Цель:** Автоматическое обновление зависимостей

**Задачи:**
- [ ] Создать `.github/dependabot.yml`
- [ ] Добавить auto-merge для patch versions
- [ ] Настроить security updates

---

## Technical Debt

| ID | Описание | Priority | Статус |
|----|----------|----------|--------|
| TD-001 | Busy-waiting в Paxos | P1 | Open |
| TD-003 | Missing input validation | P1 | Open |
| TD-005 | Missing Paxos/PBFT unit tests | P1 | Open |
| TD-006 | Self-reported latency in tests | P2 | Open |
| TD-007 | KimiK25Integration placeholder | P3 | Open |
| TD-008 | MAPE-K duplication | P2 | Open |

---

## Timeline

| Неделя | Задачи |
|--------|--------|
| W10 (Feb 23 - Mar 1) | Event Store PostgreSQL + Swarm Intelligence Phase 2 |
| W11 (Mar 2 - Mar 8) | Mesh-FL Integration Layer |
| W12 (Mar 9 - Mar 15) | Multi-Arch Docker + Dependabot |

---

## Следующие шаги

1. **Event Store:** Запустить миграцию на staging
   ```bash
   cd staging && docker-compose -f docker-compose.quick.yml up -d
   alembic upgrade head
   pytest tests/test_event_store_backends.py -v
   ```

2. **Swarm Intelligence:** Протестировать consensus
   ```bash
   pytest tests/unit/swarm/test_consensus_transport_integration_unit.py -v
   ```

3. **Mesh-FL:** Создать integration layer
   ```bash
   # Создать файлы в src/federated_learning/
   ```

---

*Создано: 2026-02-23*
