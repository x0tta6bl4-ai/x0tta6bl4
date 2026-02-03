# Contributing to x0tta6bl4

Спасибо за интерес к проекту x0tta6bl4! Этот документ поможет вам внести вклад.

## Как внести вклад

### Сообщить об ошибке

1. Проверьте, не создан ли уже issue для этой ошибки
2. Создайте новый issue используя шаблон [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md)
3. Предоставьте максимум информации для воспроизведения

### Предложить функциональность

1. Создайте issue с описанием предлагаемой функции
2. Обсудите подход с maintainers
3. После одобрения создайте PR

### Pull Request процесс

1. Форкните репозиторий
2. Создайте ветку для ваших изменений: `git checkout -b feature/my-feature`
3. Сделайте изменения с понятными commit messages
4. Убедитесь, что тесты проходят: `pytest`
5. Запустите линтеры: `ruff check src/ tests/`
6. Создайте Pull Request используя шаблон

## Стандарты кода

### Python
- Следуйте PEP 8
- Используйте type hints
- Документируйте функции (docstrings)
- Максимальная длина строки: 100 символов

### Коммиты
- Используйте понятные сообщения
- Формат: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Примеры:
```
feat(pqc): add ML-KEM-768 key encapsulation
fix(mesh): resolve Yggdrasil connection timeout
docs(api): update authentication endpoints
```

### Тестирование
- Все новые функции должны иметь тесты
- Поддерживайте coverage > 80%
- Используйте pytest
- Установите dev-зависимости перед запуском тестов локально: `pip install -r requirements-dev.txt`

## Структура проекта

```
x0tta6bl4/
├── src/           # Исходный код
├── tests/         # Тесты
├── docs/          # Документация
├── scripts/       # Вспомогательные скрипты
└── config/        # Конфигурации
```

## Лицензия

Внося вклад, вы соглашаетесь с тем, что ваш код будет лицензирован под Apache License 2.0.

## Вопросы?

- Email: contact@x0tta6bl4.net
- Issues: GitHub Issues
