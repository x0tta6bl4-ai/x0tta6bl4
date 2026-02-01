# Руководство по очистке репозитория

## ⚠️ ВАЖНО: Перед публикацией выполнить

### 1. Удалить чувствительные файлы

```bash
# Файлы с учётными данными
rm -f credentials.json
credentials.json
rm -f token.json
token.json

# Backup файлы с данными
rm -f backup_*.sql

# Логи
rm -rf agent_logs/
rm -rf .logs/

# Outreach tracking с email данными
rm -f crm_outreach_tracking.csv
```

### 2. Проверить на утечки секретов

```bash
# Установить trufflehog
pip install truffleHog

# Проверить историю
trufflehog git file://.

# Или использовать GitHub Secret Scanning
```

### 3. Очистить историю git (если были коммиты с секретами)

```bash
# Использовать BFG Repo-Cleaner
java -jar bfg.jar --delete-files credentials.json
java -jar bfg.jar --delete-files token.json

# Или filter-branch
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch credentials.json token.json' \
  --prune-empty --tag-name-filter cat -- --all
```

### 4. Список файлов для архивации/удаления

#### Устаревшие отчёты (заархивировать)
```
FINAL_*.txt (кроме FINAL_REPORT.txt)
AUDIT_*_2026_01_*.txt
FAILURE_INJECTION_RESULTS_*.md
P0_VALIDATION_RESULTS_*.md
SPRINT3_*_2026_01_*.txt
```

#### Дублирующиеся README
```
README_START_HERE.md → объединить с START_HERE.md
README_EXECUTE_NOW.md → удалить
README_IMPLEMENTATION.md → перенести в docs/
README_INSTALLATION.md → перенести в docs/
```

#### Временные файлы
```
*.log
*.tmp
*.bak
*.swp
```

### 5. Финальная проверка

```bash
# Проверить размер репозитория
du -sh .git

# Проверить на большие файлы
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print $3, $4}' | sort -rn | head -20

# Проверить на секреты
git log --all --full-history -- . | grep -i "password\|secret\|key\|token"
```

## Чеклист перед публикацией

- [ ] Удалены credentials.json и token.json
- [ ] Удалены backup файлы SQL
- [ ] Удалены логи
- [ ] Проверка на утечки секретов
- [ ] .gitignore обновлён
- [ ] LICENSE файл добавлен
- [ ] README.md обновлён
- [ ] CHANGELOG.md создан
- [ ] CONTRIBUTING.md создан
- [ ] SECURITY.md создан
- [ ] .github/ шаблоны созданы
- [ ] CI/CD workflow настроен
- [ ] Документация организована в docs/
- [ ] Скрипты перенесены в scripts/

## После публикации

1. Включить GitHub Secret Scanning
2. Настроить branch protection rules
3. Включить Dependabot alerts
4. Настроить CodeQL analysis
