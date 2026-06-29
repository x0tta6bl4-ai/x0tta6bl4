# Резюме

## x0tta6bl4 — AI Systems Architect & Agent Orchestrator

**Локация:** Крым, РФ  
**Telegram:** @x0tta6bl4_ai  
**Email:** x0tta6bl4.ai@gmail.com  
**GitHub:** github.com/x0tta6bl4-ai  
**Цель:** AI Systems Architect / Agent Orchestrator / TPM (AI)

---

### Профиль

Архитектор распределённых систем с фокусом на AI-оркестрацию. Не пишу код руками — проектирую архитектуру, управляю AI-агентами (Claude, GPT-4, Codex) как командой разработчиков, выстраиваю пайплайны валидации.

Флагманский проект: mesh-платформа с PQC, eBPF/XDP, self-healing — **1 млн строк кода, 0 строк вручную**.

---

### Ключевой кейс: x0tta6bl4 Mesh Platform

| | |
|---|---|
| **Роль** | Архитектор системы, оркестратор AI-агентов |
| **Срок** | 2025–2026 (1.5 года, part-time) |
| **Бюджет** | $0 |
| **AI-инструменты** | Claude, GPT-4, Codex, Dependabot |

**Архитектура:** 11-слойная система — от eBPF/XDP dataplane до DAO (Solidity).

**Моя зона:**
- Проектирование архитектуры и выбор стека
- Системные промпты и контекст для AI-агентов
- LLM-as-a-Judge — автоматическая валидация кода агентами
- Chaos Engineering, системная интеграция, security audit

**Зона AI-агентов:**
- Генерация 1M строк Python + 22K строк Go
- Имплементация алгоритмов (PQC, Ghost Transport, MAPE-K)
- Unit/интеграционные тесты (~340K строк)
- Рефакторинг и устранение уязвимостей

**Результаты:**
- 1,012,493 строк, 7,636 файлов, 1,033 коммита
- PQC handshake <50 ms (ML-KEM-768 + ML-DSA-65, liboqs 0.15)
- eBPF/XDP throughput: 142k PPS TX на Intel i5 + r8169
- Self-healing: MTTD <20 сек, MTTR ~3 мин
- 7 Docker контейнеров, 7 systemd сервисов
- 29/29 ZTCR chaos tests pass, 0 High vulnerabilities
- Dependencies: 342 → 72 (supply chain security)

---

### Технологии

| Категория | Стек |
|---|---|
| **Архитектура** | Distributed systems, Zero Trust, MAPE-K, PBFT |
| **Криптография** | PQC (ML-KEM/ML-DSA), SPIRE/SPIFFE mTLS, ChaCha20 |
| **Сеть** | eBPF/XDP, AF_XDP, WireGuard, Ghost Transport |
| **AI/ML** | PyTorch, GNN, scikit-learn, LLM-as-a-Judge |
| **Инфраструктура** | Docker, systemd, Prometheus, GitHub Actions |
| **Языки (проектные)** | Python 71%, C 20%, Go 1.2%, Shell |

---

### Ключевые компетенции

1. **Prompt Engineering для кода** — системные инструкции для генерации production-grade кода AI-агентами
2. **Agentic CI/CD** — пайплайны, где AI валидирует AI (LLM-as-a-Judge, chaos testing, security audit)
3. **Системная интеграция** — сборка разнородного сгенерированного кода (C, Go, Python) в единый оркестр
4. **Supply Chain Security** — аудит зависимостей, минимизация вектора атак

---

### Почему я

Я не кодер. Я архитектор, управляющий AI-командой. Моя ценность в том, что я могу спроектировать систему любой сложности, декомпозировать её для AI-агентов и доставить working product — без ручного написания кода. Это умножение продуктивности: один архитектор = команда из 5-10 разработчиков.
