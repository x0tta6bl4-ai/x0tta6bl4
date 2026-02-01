# Dependabot Security Fixes

## Обнаруженные уязвимости

GitHub обнаружил **118 уязвимостей** в зависимостях:
- 3 critical
- 35 high
- 44 moderate
- 36 low

## Автоматическое исправление через Dependabot

### Шаг 1: Включить Dependabot alerts

На GitHub перейти:
```
Settings → Security → Dependabot alerts → Enable
```

### Шаг 2: Включить Dependabot security updates

```
Settings → Security → Dependabot security updates → Enable
```

Это автоматически создаст PR для исправления критических уязвимостей.

### Шаг 3: Создать dependabot.yml

Файл [`.github/dependabot.yml`](.github/dependabot.yml) уже существует и настроен.

## Ручное обновление зависимостей

### Python зависимости

```bash
# Проверить устаревшие пакеты
pip list --outdated

# Обновить все пакеты
pip install -r requirements-core.txt --upgrade

# Или обновить конкретный пакет
pip install package-name --upgrade
```

### Node.js зависимости

```bash
# Проверить устаревшие пакеты
npm outdated

# Обновить все пакеты
npm update

# Или обновить конкретный пакет
npm install package-name@latest
```

## Критические уязвимости (требуют немедленного исправления)

### 1. Python пакеты

```bash
# Проверить на известные уязвимости
pip install safety
safety check -r requirements-core.txt
```

### 2. Node.js пакеты

```bash
# Проверить на известные уязвимости
npm audit

# Автоматическое исправление
npm audit fix

# Принудительное исправление (может сломать совместимость)
npm audit fix --force
```

## План действий

1. ✅ Включить Dependabot alerts (в настройках GitHub)
2. ✅ Включить Dependabot security updates
3. ⏳ Дождаться автоматических PR от Dependabot
4. ⏳ Проверить и merge PR для critical/high уязвимостей
5. ⏳ Запустить тесты после обновления
6. ⏳ Создать новый релиз с исправлениями

## Примечание

Dependabot создаст отдельные PR для каждой уязвимости. Рекомендуется:
- Немедленно merge PR для critical уязвимостей
- Проверить PR для high уязвимостей в течение 24 часов
- Протестировать перед merge moderate/low уязвимостей
