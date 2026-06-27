# Security Gates: Snyk + Trivy за 3 дня

- Цена: $600–1000 фикс (USD). Срок: 3 дня. Формат: remote.
- Предпосылки: доступ к репозиторию, CI-секретам (SNYK_TOKEN, REGISTRY, etc.), контейнерный образ или код.

## Скоуп работ
- Интеграция Snyk (SCA/Code/Container/IaC) и Trivy (CVE/Misconfig/Secrets) в CI (GitLab/GitHub).
- Генерация JSON и единый HTML-отчёт (артефакт пайплайна).
- Пороговые политики: fail/warn по CRITICAL/HIGH.
- Быстрые фиксы: 3 приоритетных рекомендации.

## Deliverables
- Скрипт `templates/security/security-scan.sh`.
- CI job: `templates/security/gitlab-ci-security.yml` и `templates/security/github-actions-security.yml`.
- Конфиг `templates/security/trivy.yaml` (облегчённый).
- Инструкция `templates/security/README.md`.

## Таймлайн
- День 1: аудит CI и секретов, установка инструментов.
- День 2: сборка отчётов, fail-gates, публикация артефактов.
- День 3: документация, обучение, быстрый фикс-трек.

## Acceptance criteria
- Пайплайн формирует HTML-отчёт и артефакты JSON.
- Политики fail на CRITICAL (порог = 0), warn на HIGH (порог = 5) — настраиваемо.
- Отчёт и README доступны в репозитории клиента.

## Assumptions
- Доступ к репо и правам на секреты есть.
- Время CI не ограничивается < 15 минут.

## Апсейлы (опционально)
- SBOM (CycloneDX/SPDX), PR‑комментарии, авто‑создание Issue.
- Полный DevSecOps аудит (+$600–1500).
