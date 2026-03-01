# x0tta6bl4 MaaS: Enterprise Go-To-Market Offers (Updated February 2026)

Этот документ фиксирует два приоритетных коммерческих направления и привязан к фактическому состоянию кода и биллинга.

---

## Оффер №1: Quantum-Safe Remote Access (SASE)
**Целевая аудитория:** IT-компании, FinTech, команды с распределенным доступом к критичным данным.  
**Проблема:** Риски компрометации доступа и рост требований к Zero-Trust + PQC.

### Состав решения:
*   **Zero-Trust Identity:** SPIFFE/SPIRE-ориентированная сервисная идентичность.
*   **PQC Layer:** ML-KEM/ML-DSA в поддерживаемом runtime.
*   **Ghost Transport (optional):** транспортный профиль для сложных сетевых сред с обязательной валидацией на клиентской инфраструктуре.
*   **Admin Control Plane:** аудит и управление доступом.

### Коммерческая модель (что реализовано в коде):
*   **Usage billing:** `$0.01` за node-hour для non-enterprise планов, `$0.05` за node-hour для enterprise.
*   **Минимальный инвойс:** `$0.50`.
*   **Пилотные setup/SOW-услуги:** оформляются отдельным договором (вне автоматической инвойсной логики API).

---

## Оффер №2: Resilient Industrial Mesh
**Целевая аудитория:** IoT/robotics/industrial-контуры и распределенные edge-сети.  
**Проблема:** Простои из-за сетевых обрывов, сложность централизованного управления edge-узлами.

### Состав решения:
*   **Self-Healing (MAPE-K):** автоматизация обнаружения/планирования/восстановления.
*   **PARL Optimization:** оптимизация маршрутизации и пропускной способности.
*   **Federated/Privacy-Aware ML:** локальное обучение моделей аномалий.
*   **Hardware Trust Anchors:** TPM/HSM-интеграция для целевых профилей.

### Коммерческая модель (что реализовано в коде):
*   **Usage billing:** тот же rate-card (`$0.01` / `$0.05` за node-hour) + Stripe checkout/portal/webhook flow.
*   **Кастомная интеграция с оборудованием:** отдельный SOW.

---

## План действий (март 2026)

1.  **Week 1:** адресная рассылка CTO/CISO с reality-aligned one-pager и ссылкой на `STATUS_REALITY.md`.
2.  **Week 2:** лендинг с явным разделением "реализовано сейчас" vs "roadmap".
3.  **Week 3:** платный пилот с измеримыми KPI (uptime, MTTR, security events).
4.  **Week 4:** публичный кейс только после подтвержденных метрик из production telemetry.

---
*Status: Draft. Technical execution readiness: TRL 7 (см. `STATUS_REALITY.md`).*
