# 🔴 CollisionValidator.ts - Подробный анализ интеграции

**Приоритет:** 🟡 СРЕДНИЙ  
**Время:** ~2.5 часа  
**Риск:** ⚠️ Средний  
**Сложность:** ⭐⭐⭐ Средняя

---

## 📋 Обзор

### Что это?
Сервис для **проверки пересечений панелей** с разделением на критические ошибки и неприятные предупреждения.

### Где находится в V2?
```
базис-веб-v2/
└── services/
    └── CollisionValidator.ts    (~180 строк)
```

### Где должно быть в V1?
```
базис-веб/
├── services/
│   └── CollisionValidator.ts    ← Скопировать сюда (новый сервис)
└── components/
    └── PropertiesPanel/
        └── (использовать при обновлении панелей)
```

---

## 🔍 Что делает код V2?

```typescript
class CollisionValidator {
  // Проверяет пересечения
  validateCollisions(panels: Panel[]): ValidationResult
  
  // Разделяет на ошибки и предупреждения
  getErrors(): CollisionError[]
  getWarnings(): CollisionWarning[]
  
  // Возвращает детали каждого конфликта
  getCollisionDetails(panelId1: string, panelId2: string): Details
}
```

**Входные данные:**
- `panels` (Panel[]) из V1 store ✅

**Выходные данные:**
- `errors` — критические пересечения (блокируют генерацию)
- `warnings` — касания / близкие панели (предупреждение)
- `details` — полная информация о каждом конфликте

---

## 🔗 Архитектурные различия

### V1 текущий подход:
```
CabinetGenerator.generate() 
  → checkCollisions() → console.warn()
  → Пользователь не видит ошибки явно
```

### V2 подход (лучше):
```
CabinetGenerator.generate() 
  → CollisionValidator.validate() 
  → return { errors: [], warnings: [] }
  → UI показывает красивую ошибку или предупреждение
```

---

## 🔀 План интеграции

### Этап 1: Копирование (5 минут)
```bash
cp "archived/v2-mvp-reference/source/services/CollisionValidator.ts" \
   "services/CollisionValidator.ts"
```

### Этап 2: Адаптация интерфейсов (30 минут)

**Проверьте совместимость типов:**

V2 использует простые типы:
```typescript
interface CollisionError {
  panel1Id: string;
  panel2Id: string;
  overlapVolume: number;
  severity: 'critical' | 'warning';
}
```

V1 может использовать более сложные:
```typescript
interface Collision {
  id: string;
  panels: string[];
  type: 'overlap' | 'touch';
  position: Point3D;
  errorMessage: string;
}
```

**Решение:** Создайте адаптер:
```typescript
// services/adapters/CollisionAdapter.ts
export function adaptV2Collision(v2Error: V2CollisionError): V1Collision {
  return {
    id: `col-${v2Error.panel1Id}-${v2Error.panel2Id}`,
    panels: [v2Error.panel1Id, v2Error.panel2Id],
    type: v2Error.overlapVolume > 1 ? 'overlap' : 'touch',
    position: calculateCollisionCenter(...),
    errorMessage: formatErrorMessage(v2Error)
  };
}
```

### Этап 3: Интеграция в CabinetGenerator (45 минут)

**Обновите методы в CabinetGenerator:**

```typescript
// Было:
public validate(): { valid: boolean; errors: string[] } {
  const errs: string[] = [];
  // ... просто проверки
  errs.push(...checkCollisions(this.panels));
  return { valid: errs.length === 0, errors: errs };
}

// Стало:
import { CollisionValidator } from './CollisionValidator';

public validate(): { valid: boolean; errors: string[]; warnings: string[] } {
  const errs: string[] = [];
  const validator = new CollisionValidator();
  const result = validator.validateCollisions(this.panels);
  
  // Критические ошибки
  errs.push(...result.errors.map(e => e.message));
  
  // Предупреждения отдельно
  const warnings = result.warnings.map(w => w.message);
  
  return { valid: errs.length === 0, errors: errs, warnings };
}
```

### Этап 4: UI обновление (45 минут)

**Обновите PropertiesPanel для отображения ошибок и предупреждений:**

```tsx
// Было: просто список ошибок

// Стало:
const PropertiesPanel = ({ selectedPanel }) => {
  const errors = useProjectStore(s => s.validationErrors);
  const warnings = useProjectStore(s => s.validationWarnings);
  
  return (
    <div>
      {/* Критические ошибки - красные */}
      {errors.length > 0 && (
        <div className="bg-red-900 border border-red-600 p-3 rounded">
          <h3 className="text-red-300 font-bold">⚠️ Ошибки столкновения:</h3>
          {errors.map(err => (
            <div key={err.id} className="text-red-200 mt-1">
              • {err.panel1Id} ↔ {err.panel2Id}: {err.message}
              <button onClick={() => selectPanel(err.panel1Id)}>Показать</button>
            </div>
          ))}
        </div>
      )}
      
      {/* Предупреждения - жёлтые */}
      {warnings.length > 0 && (
        <div className="bg-yellow-900 border border-yellow-600 p-3 rounded mt-2">
          <h3 className="text-yellow-300 font-bold">ℹ️ Предупреждения:</h3>
          {warnings.map(warn => (
            <div key={warn.id} className="text-yellow-200 mt-1">
              • {warn.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

### Этап 5: Интеграция в Store (30 минут)

**Обновите projectStore для хранения ошибок:**

```typescript
interface ProjectState {
  // ... существующие поля
  
  // Новые поля
  validationErrors: CollisionError[];
  validationWarnings: CollisionWarning[];
  
  setValidationResults: (errors: CollisionError[], warnings: CollisionWarning[]) => void;
}

// В useProjectStore:
setValidationResults: (errors, warnings) => {
  set({ validationErrors: errors, validationWarnings: warnings });
}
```

### Этап 6: Тестирование (30 минут)

```typescript
test('CollisionValidator должен обнаруживать перекрытия', () => {
  const validator = new CollisionValidator();
  const panels = [
    { id: '1', x: 0, y: 0, z: 0, width: 100, height: 100, depth: 16 },
    { id: '2', x: 50, y: 50, z: 0, width: 100, height: 100, depth: 16 } // Перекрытие!
  ];
  
  const result = validator.validateCollisions(panels);
  
  expect(result.errors.length).toBeGreaterThan(0);
  expect(result.errors[0].panel1Id).toBe('1');
  expect(result.errors[0].panel2Id).toBe('2');
});

test('CollisionValidator должен различать ошибки и предупреждения', () => {
  const validator = new CollisionValidator();
  const panels = [
    { id: '1', x: 0, y: 0, z: 0, width: 100, height: 100, depth: 16 },
    { id: '2', x: 95, y: 0, z: 0, width: 100, height: 100, depth: 16 } // Касание
  ];
  
  const result = validator.validateCollisions(panels);
  
  // Касание — это предупреждение, не ошибка
  expect(result.errors.length).toBe(0);
  expect(result.warnings.length).toBeGreaterThan(0);
});
```

---

## 🎯 Чек-лист реализации

- [ ] **Копирование**
  - [ ] Скопирован файл `CollisionValidator.ts`
  - [ ] Проверены импорты
  - [ ] TypeScript ошибок нет

- [ ] **Адаптация**
  - [ ] Типы совместимы или создан адаптер
  - [ ] Методы сигнатур совпадают
  - [ ] Тестовые данные работают

- [ ] **Интеграция в CabinetGenerator**
  - [ ] CollisionValidator импортирован
  - [ ] validate() метод обновлён
  - [ ] Errors и warnings разделены
  - [ ] Результаты возвращаются корректно

- [ ] **UI обновления**
  - [ ] PropertiesPanel показывает ошибки (красные)
  - [ ] PropertiesPanel показывает предупреждения (жёлтые)
  - [ ] Кнопка "Показать" переводит на панель
  - [ ] Стили красивые и понятные

- [ ] **Store интеграция**
  - [ ] validationErrors в store
  - [ ] validationWarnings в store
  - [ ] setValidationResults работает
  - [ ] Компоненты получают данные

- [ ] **Тестирование**
  - [ ] Unit тесты ошибок написаны
  - [ ] Unit тесты предупреждений написаны
  - [ ] Интеграционные тесты пройдены
  - [ ] UI отображает ошибки корректно

- [ ] **Документация**
  - [ ] Добавлены комментарии в коде
  - [ ] README обновлён
  - [ ] Пользователям объяснены ошибки vs предупреждения

---

## ⚠️ Возможные проблемы и решения

### Проблема 1: "Типы не совпадают между V2 и V1"
**Решение:** Создайте адаптер (см. Этап 2 выше)

### Проблема 2: "Store получает слишком много обновлений"
**Решение:** Кешируйте результаты валидации:
```typescript
private lastValidatedPanels: Panel[] = [];
private cachedResult: ValidationResult | null = null;

validateCollisions(panels: Panel[]): ValidationResult {
  if (this.panelsEqual(panels, this.lastValidatedPanels)) {
    return this.cachedResult!;
  }
  
  const result = this._validate(panels);
  this.lastValidatedPanels = panels;
  this.cachedResult = result;
  return result;
}
```

### Проблема 3: "UI не обновляется при изменении панелей"
**Решение:** Используйте selector hooks:
```typescript
const errors = useProjectStore(s => s.validationErrors);
const warnings = useProjectStore(s => s.validationWarnings);
```

---

## 📊 Ожидаемые результаты

### До интеграции:
```
Когда пересечение:
- Молча игнорируется или выводится в консоль
- Пользователь не знает что не так
- Невозможно заметить проблему до производства
```

### После интеграции:
```
Когда пересечение:
- Красная ошибка в UI: "Панель А пересекается с панелью Б"
- Кнопка "Показать" выделяет панель
- Пользователь может сразу исправить

Когда касание:
- Жёлтое предупреждение: "Близко к панели Б"
- Информативно, но не блокирует работу
- Пользователь может игнорировать или исправить
```

---

## 🚀 Следующие шаги

1. ✅ Скопируйте `CollisionValidator.ts`
2. ✅ Проверьте совместимость типов
3. ✅ Интегрируйте в CabinetGenerator
4. ✅ Обновите UI в PropertiesPanel
5. ✅ Добавьте в Zustand store
6. ✅ Напишите тесты
7. ✅ Протестируйте с конфликтующими панелями

---

**Время до полной интеграции:** ~2.5 часа ⏱️

**ЗАВИСИТ ОТ:** Успешной интеграции TechnicalDrawing и SheetNesting
