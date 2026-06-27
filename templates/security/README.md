# Security Gates Templates (Snyk + Trivy)

## Быстрый старт (GitLab CI)
1. Скопируйте `templates/security/` в репозиторий.
2. Вставьте job из `gitlab-ci-security.yml` в `.gitlab-ci.yml`.
3. Добавьте секрет `SNYK_TOKEN` в GitLab CI/CD Settings.
4. Запустите pipeline — артефакты появятся в `scan-results/`.

## Быстрый старт (GitHub Actions)
1. Скопируйте `templates/security/` в репозиторий.
2. Добавьте workflow `github-actions-security.yml` в `.github/workflows/security.yml`.
3. Добавьте секрет `SNYK_TOKEN` в GitHub Secrets.
4. Запустите workflow — артефакты появятся в `scan-results/`.

## Пороговые политики
- CRITICAL: threshold=0 → fail
- HIGH: threshold=5 → warn
Измените значения в `templates/security/trivy.yaml` и параметрах jobа.

## Требования
- Доступ к интернету для скачивания CLI.
- Docker для сканирования образов (или переключитесь на `trivy fs .`).

## Локальная самопроверка

```bash
bash templates/security/security-scan.sh --trivy --severity HIGH --image demo-image:latest
```

Результат должен появиться в `scan-results/security-report.html`. Если
`trivy-html-report` не установлен, скрипт создаёт минимальный HTML-отчёт из
JSON Trivy через встроенную функцию `render_json_summary_html`.

## Поддержка
- Расширение: SBOM, PR‑комментарии, авто‑Issue, policy‑as‑code.
