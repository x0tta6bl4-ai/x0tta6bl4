# GitLab/GitHub CI/CD Setup — 1–2 дня

- Цена: $700–1200 фикс (USD). Срок: 1–2 дня. Формат: remote.
- Предпосылки: доступ к репозиторию, Docker registry/секретам.

## Скоуп работ
- Стандартизованный pipeline: build/test/cache, docker buildx, артефакты релиза.
- Интеграционные тесты‑хук, базовый deploy step/скрипт.
- База линтинга и pre-commit (опционально).

## Deliverables
- Workflows (GitHub/GitLab) с кешами и матрицами.
- Makefile/скрипты (при необходимости), артефакт релиза.
- README по запуску и handover.

## Acceptance criteria
- Pipeline проходит на clean репо, артефакты собираются.
- Конфиги параметризованы под окружения.

## Апсейлы
- Self‑hosted runners и cost‑optimization.
- Release orchestration и multi‑env promotion.
