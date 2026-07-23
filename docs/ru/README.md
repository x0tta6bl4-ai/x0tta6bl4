# x0tta6bl4 — Само-восстанавливающаяся mesh-сеть

[![Лицензия](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![Статус](https://img.shields.io/badge/status-v3.5.0--hardening-blue)
[![x0tMQ](https://img.shields.io/badge/x0tMQ-черновик%20IETF-blueviolet)](https://github.com/x0tta6bl4-ai/x0tmq)

**Постквантовая криптография · eBPF/XDP ядро · Автономное самовосстановление**  
Независимый инженерный проект [x0tta6bl4](https://github.com/x0tta6bl4-ai).

---

**[English version](../README.md)**

---

## О проекте

Независимый исследовательский проект, исследующий постквантовые mesh-сети:

- **Постквантовая криптография** — ML-KEM-768/1024 + ML-DSA-65/87 (FIPS 203/204)
- **eBPF/XDP dataplane** — Обработка пакетов на уровне ядра Linux
- **MAPE-K цикл** — Автономное самовосстановление инфраструктуры
- **SPIRE/SPIFFE** — Zero-trust идентификация mesh-узлов
- **x0tMQ** — Стандарт постквантовой аутентификации MAVLink v2

## Архитектура

```
┌──────────────────────────────────────┐
│  Application Layer                   │
│  FastAPI / MaaS API · Биллинг       │
├──────────────────────────────────────┤
│  Control Plane                       │
│  MAPE-K · ZTCR · Шина событий        │
├──────────────────────────────────────┤
│  Mesh Layer                          │
│  DHT · CRDT · Ghost Transport VPN    │
├──────────────────────────────────────┤
│  Transport Security                  │
│  PQC TLS 1.3 · SPIRE/SPIFFE mTLS    │
├──────────────────────────────────────┤
│  Kernel (eBPF/XDP)                   │
│  Фильтрация · Zero-Copy кольца      │
└──────────────────────────────────────┘
```

## Компоненты

| Компонент | Строк | Статус |
|-----------|-------|--------|
| PQC (ML-KEM + ML-DSA) | ~3,500 | ✅ |
| MAPE-K самовосстановление | ~1,900 | ✅ |
| MaaS API | ~5,000 | ✅ |
| eBPF/XDP | ~1,500 | ✅ |
| Anti-Censorship | ~2,000 | ✅ |
| Ghost VPN | ~2,000 | ✅ |
| **x0tMQ** (MAVLink PQC) | ~775 | ✅ [Черновик IETF](https://github.com/x0tta6bl4-ai/x0tmq) |

## Быстрый старт

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
docker compose -f deploy/docker-compose/compose.yaml up -d
```

## Контакты

- [Issues](https://github.com/x0tta6bl4-ai/x0tta6bl4/issues)
- Telegram: @x0tta6bl4_ai
- Email: x0tta6bl4.ai@gmail.com

---

*Независимый инженерный проект.*