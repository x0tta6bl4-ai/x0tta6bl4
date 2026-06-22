# Email Draft: Yandex Open Source Team

**To:** opensource-support@yandex-team.ru
**Subject:** Post-Quantum Cryptography Module for YDB / Perfator / Odyssey

---

Здравствуйте!

Меня зовут [Имя], я разработчик проекта x0tta6bl4 — open source платформа постквантовой защищённой mesh-инфраструктуры (Apache-2.0, https://github.com/x0tta6bl4-ai/x0tta6bl4).

Я хотел бы предложить три модуля, которые могут быть полезны экосистеме Yandex:

## 1. PQC-адаптер для YDB

Добавляет постквантовое TLS-шифрование (ML-KEM-768 + ML-DSA-65, NIST FIPS 203/204) для межузлового трафика YDB. Модуль совместим с текущей архитектурой кластера и обеспечивает гибридный fallback (X25519+ML-KEM) для обратной совместимости.

## 2. eBPF-коллектор для Perfator

Модуль сбора данных профилирования на уровне XDP/eBPF. Обеспечивает zero-copy передачу данных из ядра в userspace, совместим с Prometheus exporter.

## 3. PQC-TLS для Odyssey

Post-quantum TLS для PostgreSQL-соединений через Odyssey connection pooler. Включает session resumption с PQC-ключами и benchmarks: классический TLS vs гибридный PQC.

## Почему это актуально

- NIST выпустил стандарты FIPS 203/204 (август 2024)
- Российские регуляторы движутся к обязательному PQC (аналог NIST мандата)
- "Harvest now, decrypt later" — разведки уже записывают трафик
- Яндекс обрабатывает 10 Тбит/с внешнего трафика — каждый байт защищён классической криптографией

## Что я готов

- Предоставить полный код модулей (Apache-2.0)
- Написать тесты и benchmarks
- Сделать PR в соответствующие репозитории
- Провести technical review с вашей командой

Я не ищу оплату за этот вклад — это open source contribution. Если модули окажутся полезными, буду рад обсудить дальнейшее сотрудничество.

С уважением,
[Имя]
x0tta6bl4 Core Developer
https://github.com/x0tta6bl4-ai/x0tta6bl4
dev@x0tta6bl4.net
