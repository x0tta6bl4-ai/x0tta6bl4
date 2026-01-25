# Быстрая справка BazisLite-Web

## Основные компоненты и их задачи

| Компонент | Файл | Задача | Ключевые методы |
|-----------|------|--------|-----------------|
| **CabinetGenerator** | `services/CabinetGenerator.ts` | Генерирует Panel[] из конфигурации | `generate()`, `generateWithConstraints()` |
| **ConstraintSolver** | `services/ConstraintSolver.ts` | Оптимизирует позиции компонентов (Newton-Raphson) | `solve()`, `computeJacobianNumerical()` |
| **geminiService** | `services/geminiService.ts` | AI интеграция (генерация, аудит, советы) | `generateDesignFromDescription()`, `auditConstruction()` |
| **BillOfMaterials** | `services/BillOfMaterials.ts` | Расчет стоимости и массы | `generate()`, `exportCSV()`, `exportExcel()` |
| **DFMValidator** | `services/DFMValidator.ts` | Проверка производимости | `validateAssembly()`, `calculateDFMScore()` |
| **InputValidator** | `services/InputValidator.ts` | Валидация входных данных | `validateCabinetConfig()`, `validatePanel()` |
| **hardwareUtils** | `services/hardwareUtils.ts` | Управление крепежом | `validateHardwarePosition()`, `generateHardwareArray()` |
| **ProjectStore** | `store/projectStore.ts` | State Management (Zustand) | `setPanels()`, `updatePanel()`, `undo()`, `redo()` |

---

## Главный workflow: От идеи к изделию

```
1. User Input (текст или конфиг)
        ↓
2. InputValidator ← проверить корректность
        ↓
3. CabinetGenerator ← создать 3D панели
        ↓
4. [Параллельно] Solver + BOM + DFM + FEA
        ↓
5. geminiService (аудит) ← проверить физическую возможность
        ↓
6. ProjectStore ← сохранить результат
        ↓
7. UI (Scene3D) ← визуализировать
        ↓
8. Export/Production
```

---

## Быстрый старт: Как использовать основные сервисы

### 1️⃣ Генерировать шкаф

```typescript
import { CabinetGenerator } from './services/CabinetGenerator';

const config: CabinetConfig = {
  name: 'Мой шкаф',
  width: 2400, height: 2200, depth: 650,
  doorType: 'sliding', doorCount: 2,
  baseType: 'legs', facadeStyle: 'combined'
};

const sections: Section[] = [
  { id: 1, width: 1200, items: [
    { id: '1', type: 'shelf', y: 800, height: 50, name: 'Полка' }
  ]}
];

const generator = new CabinetGenerator(config, sections, MATERIAL_LIBRARY);
const panels = generator.generate();
```

### 2️⃣ Оптимизировать позиции (ConstraintSolver)

```typescript
const { panels: optimizedPanels, solverResult } = 
  generator.generateWithConstraints();

if (!solverResult.success) {
  console.error('Solver failed:', solverResult.error);
} else {
  console.log(`✅ Solved in ${solverResult.iterations} iterations`);
}
```

### 3️⃣ AI аудит конструкции

```typescript
import { auditConstruction } from './services/geminiService';

const audit = await auditConstruction(panels, config);

if (audit.hardCheck.errors.length > 0) {
  console.log('❌ Critical issues found!');
  audit.hardCheck.errors.forEach(e => console.log(e.suggestion));
}
```

### 4️⃣ Рассчитать стоимость и массу

```typescript
import { BillOfMaterials } from './services/BillOfMaterials';

const bom = new BillOfMaterials(assembly, materialPrices);
const bomData = bom.generate();

console.log(`Total cost: ${bomData.stats.totalCost}₽`);
console.log(`Total mass: ${bomData.stats.totalMass}kg`);
```

### 5️⃣ Проверить производимость (DFM)

```typescript
import { DFMValidator } from './services/DFMValidator';

const dfm = new DFMValidator(DFM_CONFIG);
const report = dfm.validateAssembly(assembly);

console.log(`DFM Score: ${report.score}/100`);
report.checks.forEach(c => {
  if (c.severity === 'ERROR') console.log('⚠️', c.message);
});
```

### 6️⃣ Сохранить в store

```typescript
import { useProjectStore } from './store/projectStore';

const { setPanels, setBOMData, setDFMReport } = useProjectStore();

setPanels(panels);
setBOMData(bomData);
setDFMReport(dfmReport);
```

---

## Важные типы данных

### Panel (основной тип)

```typescript
interface Panel {
  id: string;                    // Уникальный ID
  name: string;                  // Название: "Боковая стенка левая"
  width: number;                 // мм
  height: number;                // мм
  depth: number;                 // мм (толщина материала)
  x: number; y: number; z: number;  // Позиция в 3D
  materialId: string;            // Ссылка на материал
  color: string;                 // Цвет в 3D (#FFFFFF)
  texture: TextureType;          // wood_oak, concrete, etc.
  hardware: Hardware[];          // Крепежи на этой панели
  edging: Edging;                // Кромка: top/bottom/left/right
  groove: Groove;                // Паз для задней стенки
  layer: string;                 // Слой: body, facade, back, shelves
  visible: boolean;              // Видна в 3D?
  openingType: OpeningType;      // none, left, right, drawer, etc.
  productionStatus?: ProductionStatus;  // pending, in_progress, completed
  currentStage?: ProductionStage;       // design -> cutting -> drilling -> ...
}
```

### Material (материал)

```typescript
interface Material {
  id: string;                         // eg-w980
  article: string;                    // Артикул производителя
  brand: 'Egger' | 'Kronospan' | 'Lamarty' | 'MDF_RAL';
  name: string;                       // "Egger White Oak"
  thickness: 4 | 8 | 10 | 16 | 18 | 22 | 25;  // мм
  pricePerM2: number;                 // Стоимость за м²
  texture: TextureType;               // wood_oak, uniform, etc.
  color: string;                      // #FFFFFF
  isTextureStrict: boolean;           // Важна ли точность текстуры?
}
```

### CabinetConfig (конфигурация)

```typescript
interface CabinetConfig {
  name: string;                           // "Шкаф-купе"
  type: 'straight' | 'corner_l';          // Форма
  width: number;                          // мм (200-5000)
  height: number;                         // мм (400-3000)
  depth: number;                          // мм (350-700)
  doorType: 'none' | 'hinged' | 'sliding' | 'folding';
  doorCount: number;                      // Количество дверей
  baseType: 'plinth' | 'legs';            // Цоколь или ножки?
  facadeStyle: 'solid' | 'combined';      // Стиль фасада
  materialId?: string;                    // Основной материал
  hardwareType?: 'confirmat' | 'minifix' | 'none';  // Тип крепежа
}
```

---

## Константы и стандарты

### STD (стандартные размеры)

```typescript
TH_BODY: 16          // Толщина корпуса в мм (LDSP)
TH_BACK: 4           // Толщина задней стенки
SYSTEM_32: 32        // Расстояние между отверстиями (мм)
SYSTEM_32_OFFSET: 37 // Отступ от края до первого отверстия
RAIL_GAP: 13         // Зазор для направляющих
COUPE_DEPTH: 80      // Глубина механизма купе (раздвижные двери)
COUPE_OVERLAP: 26    // Перехлест дверей купе
```

### Нормы производства

| Операция | Время | Примечание |
|----------|-------|-----------|
| Распил (за каждое отверстие) | 0.5-1мин | Зависит от материала |
| Сверление отверстия | 0.5мин | Стандартный диаметр |
| Кромление (за метр) | 1-2мин | Зависит от толщины кромки |
| Сборка узла | 5-10мин | Простой узел (2-3 элемента) |
| Сборка каркаса | 30-60мин | Типовый шкаф |

---

## Частые ошибки и решения

### ❌ Ошибка: "Cannot read property 'id' of undefined"

**Причина**: materialId не найден в библиотеке  
**Решение**:
```typescript
const material = materialLibrary.find(m => m.id === config.materialId);
if (!material) {
  throw new Error(`Material ${config.materialId} not found`);
}
```

### ❌ Ошибка: "Solver did not converge"

**Причина**: Ограничения конфликтуют друг с другом  
**Решение**:
```typescript
// Проверить результаты
console.log(solverResult.constraintErrors);  // Какое ограничение нарушено?

// Смягчить tolerance
const result = solver.solve(assembly, positions, {
  tolerance: 0.01  // Вместо 0.001
});
```

### ❌ Ошибка: "Gemini API key is invalid"

**Причина**: VITE_GEMINI_API_KEY не установлен или неверный  
**Решение**:
```bash
# Создать .env.local
echo "VITE_GEMINI_API_KEY=your_key_here" > .env.local

# Проверить что ключ загружается
console.log(import.meta.env.VITE_GEMINI_API_KEY);
```

### ❌ Ошибка: "NaN in panel dimensions"

**Причина**: Некорректные входные параметры или деление на 0  
**Решение**:
```typescript
// Добавить валидацию
if (!Number.isFinite(panel.width) || panel.width <= 0) {
  throw new ValidationError(`Invalid width: ${panel.width}`);
}
```

---

## Команды для разработки

```bash
# Установка зависимостей
npm install

# Dev сервер (http://localhost:3000)
npm run dev

# Build для production
npm run build

# Preview production build
npm run preview

# Запустить тесты
npm test

# Тесты с coverage
npm run test:coverage

# Tестирование в watch режиме
npm run test:watch

# Type checking
npm run typecheck
```

---

## Debug режим

### Логирование в ConstraintSolver

```typescript
const result = solver.solve(assembly, positions, {
  verbose: true  // Выведет все итерации
});

// Output:
// [Solver] Iteration 0: residual = 2.451238
// [Solver] Iteration 1: residual = 0.824510
// [Solver] Iteration 2: residual = 0.052341
// [Solver] Iteration 3: residual = 0.001223
// ✅ Converged in 3 iterations
```

### Проверить параметры генератора

```typescript
// Получить cache stats
const stats = generator.getParameterCacheStats();
console.log(`Cache hits: ${stats.hits}, misses: ${stats.misses}`);
console.log(`Hit rate: ${stats.hitRate}%`);
```

### Визуализировать DFM проблемы

```typescript
// На UI добавить цветное выделение проблемных компонентов
dfmReport.checks.forEach(check => {
  if (check.severity === 'ERROR') {
    const component = assembly.components.find(c => c.id === check.componentId);
    // Выделить красным на сцене
    highlightComponent(component.id, '#FF0000');
  }
});
```

---

## Производительность: Ожидаемые значения

| Операция | Ожидаемое время |
|----------|-----------------|
| `generator.generate()` | 50-200 мс |
| `solver.solve()` (50 компонентов) | 1-3 сек |
| `bom.generate()` | 50-100 мс |
| `dfmValidator.validate()` | 100-300 мс |
| `geminiService.generateDesign()` | 3-10 сек (API) |
| `geminiService.auditConstruction()` | 2-5 сек (API) |

**Если медленнее**: 
- Добавить кеширование для geminiService
- Использовать Web Worker для Solver
- Оптимизировать вычисления в CabinetGenerator

---

## Тестирование: Основные сценарии

```typescript
// Тест 1: Базовая генерация
test('should generate valid cabinet', () => {
  const gen = new CabinetGenerator(defaultConfig, sections, materials);
  const panels = gen.generate();
  
  expect(panels.length).toBeGreaterThan(0);
  panels.forEach(p => {
    expect(p.width).toBeGreaterThan(0);
    expect(p.height).toBeGreaterThan(0);
    expect(p.depth).toBeGreaterThan(0);
  });
});

// Тест 2: Валидация входов
test('should reject invalid config', () => {
  const invalidConfig = { ...defaultConfig, width: -100 };
  const gen = new CabinetGenerator(invalidConfig, sections, materials);
  
  expect(() => gen.validate()).toThrow(ValidationError);
});

// Тест 3: Solver сходимость
test('should converge to solution', () => {
  const result = solver.solve(assembly, initialPositions);
  
  expect(result.success).toBe(true);
  expect(result.converged).toBe(true);
  expect(result.error).toBeLessThan(0.001);
});

// Тест 4: BOM расчеты
test('should calculate correct total cost', () => {
  const bom = new BillOfMaterials(assembly, materialPrices);
  const stats = bom.getStats();
  
  expect(stats.totalCost).toBeGreaterThan(0);
  expect(stats.totalMass).toBeGreaterThan(0);
});
```

---

## Инструменты для анализа

### Performance Profiling

```typescript
import { PerformanceMonitor } from './services/PerformanceMonitor';

const monitor = new PerformanceMonitor();

monitor.start('full-generation');
const panels = generator.generate();
monitor.mark('generation-done');
const { panels: opt, solverResult } = generator.generateWithConstraints();
monitor.mark('optimization-done');
const metrics = monitor.end('full-generation');

console.log(metrics);
// { name: 'full-generation', duration: 1234, marks: [...] }
```

### Memory Usage Tracking

```typescript
// Chrome DevTools
// 1. Открыть DevTools (F12)
// 2. Перейти в Memory tab
// 3. Take heap snapshot
// 4. Выполнить операцию
// 5. Take another snapshot
// 6. Compare и найти утечки
```

---

## Полезные ссылки в коде

| Что найти | Где | Строка |
|-----------|-----|--------|
| Стандартные размеры | CabinetGenerator.ts | 7-16 |
| Параметерный кеш | CabinetGenerator.ts | 52-86 |
| Newton-Raphson алгоритм | ConstraintSolver.ts | 77-177 |
| Типы ограничений | ConstraintSolver.ts | 50-70 |
| Gemini конфигурация | geminiService.ts | 9-70 |
| Обработка ошибок Gemini | geminiService.ts | 147-200 |
| MaterialProperties | CabinetGenerator.ts | 22-30 |
| BOM структура | BillOfMaterials.ts | 15-70 |
| DFM конфиг | DFMValidator.ts | 19-31 |
| ProjectStore actions | projectStore.ts | 31-59 |

---

## Контрольный список для code review

- [ ] Все входные параметры валидируются?
- [ ] Обработаны NaN/Infinity случаи?
- [ ] Есть error handling с meaningful сообщениями?
- [ ] Код логируется адекватно (не слишком много)?
- [ ] Есть тесты для новых функций?
- [ ] Нет hardcoded значений (использованы константы)?
- [ ] Нет memory leaks (cleanup в useEffect)?
- [ ] TypeScript типы четкие (не `any`)?
- [ ] Performance приемлемая (< 500ms для типовых операций)?
- [ ] Документация актуальна?

---

## Контакты и справка

**Основной документ архитектуры**: `ARCHITECTURE_ANALYSIS_RU.md`  
**Примеры кода**: `CODE_EXAMPLES_RU.md`  
**Issues и Improvements**: `ISSUES_AND_IMPROVEMENTS_RU.md`  

