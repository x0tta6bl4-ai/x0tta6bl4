## Summary

Кратко: что изменено и зачем.

## Single Purpose (Required)

- [ ] PR покрывает только одну цель
- Scope (внутри PR):
- Out of scope (явно НЕ входит в PR):
- Связанный issue/тикет:

## Change Type

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring
- [ ] Operations / CI-CD / staging

## Risk And Rollback (Required)

- Риск: `low` / `medium` / `high`
- Что может сломаться:
- План отката (команда или шаги):

## Verification (Required)

Приведите точные команды и итог (pass/fail):

```bash
make cleanup-gate
make test
make agent-cycle-dry
```

Если команда не применима, укажите причину.

## Checklist

- [ ] Код соответствует стандартам проекта
- [ ] Добавлены/обновлены тесты (или описано why not)
- [ ] Документация обновлена (если нужно)
- [ ] Секреты не утекли
- [ ] Линтеры/проверки CI проходят
