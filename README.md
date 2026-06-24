# x0tta6bl4 — mesh networking platform

[![REAL_READINESS_READY](https://img.shields.io/badge/REAL_READINESS_READY-70%2F70-brightgreen)](docs/05-operations/REAL_READINESS_GATE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![GitHub commits](https://img.shields.io/badge/commits-987-blue)
![Status](https://img.shields.io/badge/status-alpha-yellow)

**Само-восстанавливающаяся mesh-сеть с постквантовой криптографией и eBPF dataplane.**

> Код открыт, всё честно. Это соло-проект одного человека, а не корпоративный продукт.

---

## Про проект

**x0tta6bl4** — это не «ещё один VPN». Это **mesh networking platform**:

- **PQC транспорт** — ML-KEM-768 + ML-DSA-65 (NIST FIPS 203/204)
- **eBPF/XDP dataplane** — обработка пакетов на уровне ядра, DPI-bypass
- **MAPE-K self-healing** — автономное восстановление узлов
- **SPIFFE/SPIRE mTLS** — zero-trust аттестация

Всё это можно использовать как VPN, mesh для IoT, приватный overlay, research-полигон — что хочешь.

---

## Об авторе

Привет. Я разработчик из Крыма, под санкциями, без команды и бюджета.

- 1.5+ лет пишу x0tta6bl4 в свободное время
- Домашний сервер в шкафу, сетевая r8169, Linux
- Сделал mesh для себя → друзья попросили доступ → решил поделиться с миром
- Не корпорация, не стартап, не инвесторы. Только я и линукс.

**Почему этот проект?** Постквантовая криптография должна быть доступна обычным людям, а не только enterprise. Инструменты связи, которые нельзя заблокировать.

---

## Что реально работает (RC1 baseline)

| Компонент | Статус |
|-----------|--------|
| **PQC стек** | ✅ ML-KEM-768/1024 + ML-DSA-65/87, liboqs |
| **XDP dataplane** | ✅ 142k PPS TX / 49k PPS RX на r8169 |
| **Self-healing** | ✅ MAPE-K loop, <20s detection |
| **SPIRE mTLS** | ✅ Интегрирован, тесты проходят |
| **x402 Payment** | ✅ USDC на Base mainnet |
| **CI/CD** | ✅ Green Baseline, CodeQL, Dependency Review |

**Доказательства:**
- PQC: `docs/verification/HYBRID_TLS_VALIDATION_LATEST.md`
- XDP: `docs/verification/xdp-live-attach-20260615T133855Z/`
- Readiness gate: `python3 scripts/ops/check_real_readiness.py --json`

### VPS
- `89.125.1.107:8000/api/status` — Ghost-Core node, uptime 46h+, status NORMAL
- x402 API: `89.125.1.107:8120` — paid endpoint tools

---

## Чего НЕТ (не жди)

| Утверждение | Реальность |
|-------------|-----------|
| Production VPN для 1M пользователей | ❌ Тестовый VPS, 0 платящих клиентов |
| 99.97% uptime | ❌ Нет доказательств |
| 1M PPS | ❌ 142k на r8169 — честные цифры |
| Сертифицированная криптография | ❌ PQC через liboqs, без аудита |
| DAO / управление сообществом | ❌ Я один. Возможно в будущем |
| Официальная интеграция с Yandex | ❌ Адаптеры написал сам, Яндекс не при делах |

---

## Benchmarks (честно, с методологией)

| Метрика | Значение | Условия |
|---------|----------|---------|
| TX PPS | 142,000 | XDP_DROP → XDP_TX, r8169, Intel i5, pktgen |
| RX PPS | 49,000 | XDP_DROP без обработки, та же машина |
| PQC handshake | <50ms | ML-KEM-768 + ML-DSA-65, localhost |
| MTTD | <20s | MAPE-K monitor loop |
| MTTR | ~3min | Автономное восстановление |

**Методология:** `docs/benchmarks/`

---

## Quick start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync  # pip install -r requirements.txt (72 deps)
python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q
```

---

## Для российских пользователей

Адаптеры для YDB, Perfator, Odyssey — **community-разработка, неофициальная**. Я написал их для удобства, но они не одобрены Яндексом.

- `src/integration/ydb_pqc_adapter.py` — PQC для YDB
- `src/integration/perforator_ebpf_collector.py` — eBPF для Perfator
- `src/integration/odyssey_pqc_tls.py` — PQC-TLS для Odyssey

---

## Документация

- **CODEX.md** — рабочая инструкция для AI-агентов (факты, процедуры, traps)
- **AGENTS.md** — правила работы AI с монорепо
- **SECURITY.md** — security policy
- **STATUS_REALITY.md** — что доказано, что нет

---

## Контакты

- GitHub Issues: открывай баги и предложения
- Email: dev@x0tta6bl4.net
- GitHub Sponsors: [поддержать разработку](https://github.com/sponsors/x0tta6bl4-ai)

---

*Сделано одним человеком. Проверено машинами, а не маркетингом.*
