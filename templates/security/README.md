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

## Поддержка
- Расширение: SBOM, PR‑комментарии, авто‑Issue, policy‑as‑code.
