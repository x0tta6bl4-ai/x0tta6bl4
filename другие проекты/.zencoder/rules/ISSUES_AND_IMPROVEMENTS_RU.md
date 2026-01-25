# Анализ проблем и рекомендации по улучшениям

## 1. Критические проблемы (Must Fix)

### ⚠️ Проблема 1.1: Отсутствие валидации входных данных

**Файл**: `services/CabinetGenerator.ts`

**Описание**: 
Конструктор CabinetGenerator не проверяет валидность входных параметров конфигурации.

```typescript
// Текущий код (опасно)
constructor(config: CabinetConfig, sections: Section[], materialLibrary: Material[]) {
    this.config = config;  // ❌ Нет проверки config
    this.sections = sections;  // ❌ Может быть пустой
    this.materialLibrary = materialLibrary;  // ❌ Может быть пустой
}
```

**Потенциальные проблемы**:
- Неверные параметры (width=0, height=-100) приводят к NaN в расчетах
- Пустой materialLibrary вызывает исключение при доступе
- Конфликтные параметры (doorCount > doorType возможности) не обнаруживаются

**Решение**:
```typescript
constructor(config: CabinetConfig, sections: Section[], materialLibrary: Material[]) {
    // Валидировать config
    const validationResult = InputValidator.validateCabinetConfig(config);
    if (!validationResult.isValid) {
        throw new ValidationError(
            `Invalid config: ${validationResult.errors.map(e => e.message).join(', ')}`
        );
    }
    
    // Валидировать sections
    if (!sections || sections.length === 0) {
        throw new ValidationError('Sections array cannot be empty');
    }
    
    // Валидировать materialLibrary
    if (!materialLibrary || materialLibrary.length === 0) {
        throw new ValidationError('Material library cannot be empty');
    }
    
    // Валидировать наличие материала
    const material = materialLibrary.find(m => m.id === config.materialId);
    if (!material) {
        throw new ValidationError(`Material ${config.materialId} not found in library`);
    }
    
    this.config = config;
    this.sections = sections;
    this.materialLibrary = materialLibrary;
}
```

**Приоритет**: 🔴 КРИТИЧЕСКИЙ  
**Сложность**: 30 мин  
**Тесты**: Добавить в CabinetGenerator.test.ts

---

### ⚠️ Проблема 1.2: NaN/Infinity в ConstraintSolver не полностью обработаны

**Файл**: `services/ConstraintSolver.ts`, строки 138-175

**Описание**:
Якобиева матрица может содержать NaN значения, что приводит к неправильному решению или divergence.

```typescript
// Текущий код (неполная защита)
if (!isFinite(residual)) {
    residual = Infinity;
    break;  // ❌ Просто выход без исправления
}
```

**Потенциальные проблемы**:
- Если jacobian содержит NaN, solveLU() вернет NaN/Infinity
- Это распространяется на deltaX и новые позиции
- Solver может дать неправильный результат вместо ошибки

**Решение**:
```typescript
private computeJacobianNumerical(
    assembly: Assembly,
    positions: Map<string, Point3D>,
    constraints: Constraint[]
): number[][] {
    const jacobian = this.initializeJacobian(assembly, constraints);
    
    for (let i = 0; i < jacobian.length; i++) {
        for (let j = 0; j < jacobian[i].length; j++) {
            // Проверить на NaN/Infinity
            if (!isFinite(jacobian[i][j])) {
                throw new Error(
                    `Jacobian[${i}][${j}] = ${jacobian[i][j]}, ` +
                    `обычно указывает на вырождение матрицы или масштабирование проблемы`
                );
            }
        }
    }
    
    // Проверить детерминант
    const det = this.computeDeterminant(jacobian);
    if (Math.abs(det) < 1e-10) {
        // Добавить регуляризацию (Tikhonov)
        for (let i = 0; i < jacobian.length; i++) {
            jacobian[i][i] += 1e-6;
        }
    }
    
    return jacobian;
}
```

**Приоритет**: 🔴 КРИТИЧЕСКИЙ  
**Сложность**: 1 час  
**Тесты**: Добавить в ConstraintSolver.test.ts - тесты с вырожденными матрицами

---

### ⚠️ Проблема 1.3: Отсутствует timeout для Gemini API

**Файл**: `services/geminiService.ts`, строка 200+

**Описание**:
Запросы к Gemini API могут зависнуть на неопределенное время.

```typescript
// Текущий код (опасно)
const response = await this.client.generateContent({
    contents: [{ role: 'user', parts: [{ text: prompt }] }],
    systemInstruction: systemPrompt
});  // ❌ Нет timeout, может зависнуть навсегда
```

**Потенциальные проблемы**:
- Запрос зависает → браузер зависает
- Пользователь не может отменить операцию
- Нет feedback после 30+ секунд

**Решение**:
```typescript
async generateContentWithTimeout(
    prompt: string,
    systemPrompt: string,
    timeout: number = 30000
): Promise<GenerateContentResponse> {
    return Promise.race([
        // Основной запрос
        this.client.generateContent({
            contents: [{ role: 'user', parts: [{ text: prompt }] }],
            systemInstruction: systemPrompt
        }),
        
        // Timeout обработчик
        new Promise<GenerateContentResponse>((_, reject) =>
            setTimeout(
                () => reject(new GeminiError(
                    'REQUEST_TIMEOUT',
                    `Запрос к Gemini занял более ${timeout}мс`,
                    { timeout, retryable: true }
                )),
                timeout
            )
        )
    ]);
}
```

**Приоритет**: 🔴 КРИТИЧЕСКИЙ  
**Сложность**: 20 мин  
**Тесты**: Добавить в geminiService.test.ts

---

## 2. Высокие приоритеты (Should Fix)

### 🟠 Проблема 2.1: ParameterCache не инвалидируется при изменении config

**Файл**: `services/CabinetGenerator.ts`, строки 47-86

**Описание**:
Кеш создается один раз в конструкторе и никогда не очищается, даже если config меняется.

```typescript
// Текущий код
class CabinetGenerator {
    private paramCache = new ParameterCache();
    
    constructor(config: CabinetConfig, ...) {
        this.config = config;
        // ❌ Кеш создан для конкретного config
    }
    
    public setConfig(newConfig: CabinetConfig) {
        this.config = newConfig;
        // ❌ Кеш НЕ инвалидирован! Будут возвращены старые значения
    }
}
```

**Потенциальные проблемы**:
- Если изменить config.depth, getInternalParams() вернет параметры для старого depth
- Результирующие панели будут неправильными
- Баг сложно отследить (silent failure)

**Решение**:
```typescript
class CabinetGenerator {
    private paramCache = new ParameterCache();
    private lastConfigHash: string = '';
    
    constructor(config: CabinetConfig, ...) {
        this.config = config;
        this.lastConfigHash = this.hashConfig(config);
    }
    
    public setConfig(newConfig: CabinetConfig) {
        const newHash = this.hashConfig(newConfig);
        if (newHash !== this.lastConfigHash) {
            this.paramCache.invalidate();
            this.lastConfigHash = newHash;
        }
        this.config = newConfig;
    }
    
    private getInternalParams() {
        // Кеш будет чистым если config изменился
        const cacheKey = `internal_${this.config.doorType}_${this.config.backType}_${this.config.depth}`;
        let params = this.paramCache.get(cacheKey);
        // ... остальной код
    }
    
    private hashConfig(config: CabinetConfig): string {
        return JSON.stringify({
            width: config.width,
            height: config.height,
            depth: config.depth,
            doorType: config.doorType,
            doorCount: config.doorCount,
            baseType: config.baseType
        });
    }
}
```

**Приоритет**: 🟠 ВЫСОКИЙ  
**Сложность**: 30 мин  
**Тесты**: Добавить в CabinetGenerator.test.ts

---

### 🟠 Проблема 2.2: Отсутствует Dependency Injection для ConstraintSolver

**Файл**: `services/CabinetGenerator.ts`, строка 123

**Описание**:
ConstraintSolver создается прямо внутри метода, невозможно использовать mock для тестирования.

```typescript
// Текущий код (жесткая связь)
public generateWithConstraints() {
    const solver = new ConstraintSolver();  // ❌ Всегда реальный экземпляр
    // ...
}
```

**Проблемы**:
- Невозможно тестировать CabinetGenerator без запуска реального Solver
- Невозможно подменить Solver на более быструю реализацию
- Сложно отлаживать какой компонент вызвал ошибку

**Решение**:
```typescript
export interface ISolver {
    solve(assembly: Assembly, initialPositions: Map<string, Point3D>, options?: SolverOptions): SolverResult;
}

class CabinetGenerator {
    private solver: ISolver;
    
    constructor(
        config: CabinetConfig,
        sections: Section[],
        materialLibrary: Material[],
        solver?: ISolver  // Optional DI
    ) {
        this.config = config;
        this.solver = solver || new ConstraintSolver();
    }
    
    public generateWithConstraints() {
        const solverResult = this.solver.solve(assembly, initialPositions);
        // ...
    }
}

// Тестирование с mock
class MockSolver implements ISolver {
    solve() {
        return {
            success: true,
            positions: new Map(),
            iterations: 1,
            error: 0,
            converged: true,
            constraintErrors: new Map(),
            solverTime: 0.1
        };
    }
}

const gen = new CabinetGenerator(config, sections, materials, new MockSolver());
```

**Приоритет**: 🟠 ВЫСОКИЙ  
**Сложность**: 45 мин  
**Тесты**: Добавить в CabinetGenerator.test.ts

---

### 🟠 Проблема 2.3: Нет кеширования Gemini запросов

**Файл**: `services/geminiService.ts`

**Описание**:
Одинаковые запросы отправляются в Gemini каждый раз, тратятся токены квоты.

```typescript
// Текущий код (без кеша)
async generateDesignFromDescription(userInput: string) {
    const response = await this.generateContent(...);  // ❌ Всегда API call
    return response;
}
```

**Проблемы**:
- Быстро исчерпывается квота Gemini
- Медленный ответ (100-1000мс) даже для известных запросов
- Нет экономии на повторяющихся запросах

**Решение**:
```typescript
import LRU from 'lru-cache';

class GeminiService {
    private responseCache: LRU<string, any>;
    
    constructor() {
        this.responseCache = new LRU({
            max: 100,              // Макс 100 кешированных ответов
            maxAge: 3600000        // TTL: 1 час
        });
    }
    
    private getCacheKey(systemPrompt: string, userInput: string): string {
        // Использовать SHA-256 хеш для быстрого поиска
        const input = systemPrompt + userInput;
        return require('crypto')
            .createHash('sha256')
            .update(input)
            .digest('hex');
    }
    
    async generateDesignFromDescription(userInput: string) {
        const cacheKey = this.getCacheKey(SYSTEM_PROMPTS.GENERATOR, userInput);
        
        // Проверить кеш
        const cached = this.responseCache.get(cacheKey);
        if (cached) {
            console.log('📦 Cache hit для запроса дизайна');
            return cached;
        }
        
        // API call
        const response = await this.generateContent(
            SYSTEM_PROMPTS.GENERATOR,
            userInput
        );
        
        // Кешировать результат
        this.responseCache.set(cacheKey, response);
        return response;
    }
    
    clearCache(): void {
        this.responseCache.clear();
    }
}
```

**Приоритет**: 🟠 ВЫСОКИЙ  
**Сложность**: 40 мин  
**Тесты**: Добавить в geminiService.test.ts

---

## 3. Средние приоритеты (Nice to Have)

### 🟡 Проблема 3.1: History в Store может быть очень большой

**Файл**: `store/projectStore.ts`, строки 16-17

**Описание**:
История хранит весь массив panels после каждого изменения.

```typescript
// Текущий код (неэффективно)
interface ProjectState {
    history: Panel[][];        // ❌ Сохраняет весь state целиком
    historyIndex: number;
}

pushHistory(panels: Panel[]) {
    // Удалить все redo история
    this.history = this.history.slice(0, this.historyIndex + 1);
    // Добавить новый state целиком
    this.history.push(JSON.parse(JSON.stringify(panels)));  // ❌ Дорого
}
```

**Проблемы**:
- Для 100 операций с 50 панелями: 100 * 50 * Panel_size = много МБ
- Медленный JSON.stringify/parse на больших данных
- Быстро заполняется память браузера

**Решение** (Delta compression):
```typescript
interface HistoryEntry {
    timestamp: number;
    delta: {
        updated: { [panelId: string]: Partial<Panel> };
        added: Panel[];
        removed: string[];
    };
}

pushHistory(newPanels: Panel[], oldPanels: Panel[]) {
    const delta = this.computeDelta(oldPanels, newPanels);
    
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push({
        timestamp: Date.now(),
        delta
    });
    
    this.historyIndex++;
    
    // Ограничить размер истории
    if (this.history.length > 100) {
        this.history = this.history.slice(-100);
    }
}

private computeDelta(
    oldPanels: Panel[],
    newPanels: Panel[]
): HistoryEntry['delta'] {
    const oldMap = new Map(oldPanels.map(p => [p.id, p]));
    const newMap = new Map(newPanels.map(p => [p.id, p]));
    
    const delta: HistoryEntry['delta'] = {
        updated: {},
        added: [],
        removed: []
    };
    
    // Найти измененные
    for (const [id, newPanel] of newMap) {
        const oldPanel = oldMap.get(id);
        if (oldPanel) {
            const changes = this.getDifferences(oldPanel, newPanel);
            if (Object.keys(changes).length > 0) {
                delta.updated[id] = changes;
            }
        } else {
            delta.added.push(newPanel);
        }
    }
    
    // Найти удаленные
    for (const id of oldMap.keys()) {
        if (!newMap.has(id)) {
            delta.removed.push(id);
        }
    }
    
    return delta;
}
```

**Приоритет**: 🟡 СРЕДНИЙ  
**Сложность**: 2 часа  
**Тесты**: Добавить в projectStore.test.ts

---

### 🟡 Проблема 3.2: Отсутствует auto-save в localStorage

**Файл**: `App.tsx`

**Описание**:
При обновлении страницы все данные теряются.

```typescript
// Текущий код (нет сохранения)
const App = () => {
    const [panels, setPanels] = useState<Panel[]>([]);  // ❌ Теряется при refresh
}
```

**Проблемы**:
- Пользователь может потерять работу при случайном обновлении
- Нет recovery при крахе браузера

**Решение**:
```typescript
const App = () => {
    const { panels } = useProjectStore();
    
    // Auto-save каждые 30 секунд
    useEffect(() => {
        const saveTimer = setInterval(() => {
            try {
                localStorage.setItem(
                    'bazis_projects_autosave',
                    JSON.stringify({
                        timestamp: Date.now(),
                        panels: panels,
                        version: 1
                    })
                );
                console.log('✅ Auto-saved to localStorage');
            } catch (e) {
                console.warn('⚠️ Failed to save to localStorage:', e);
            }
        }, 30000);
        
        return () => clearInterval(saveTimer);
    }, [panels]);
    
    // Загрузить при инициализации
    useEffect(() => {
        const saved = localStorage.getItem('bazis_projects_autosave');
        if (saved) {
            try {
                const data = JSON.parse(saved);
                const { setPanels } = useProjectStore.getState();
                setPanels(data.panels);
                addToast('Восстановлено из автосохранения', 'info');
            } catch (e) {
                console.warn('Failed to restore from localStorage:', e);
            }
        }
    }, []);
}
```

**Приоритет**: 🟡 СРЕДНИЙ  
**Сложность**: 30 мин  
**Тесты**: Интеграционные тесты

---

## 4. Низкие приоритеты (Nice to Have)

### 🔵 Проблема 4.1: Параметризация HARDWARE_CONFIG

**Файл**: `services/hardwareUtils.ts`

**Описание**:
Все параметры крепежа зашиты. Нельзя использовать разные стандарты (Blum, Hettich, GTV).

```typescript
// Текущий код (жесткие значения)
export const HARDWARE_CONFIG: HardwareConfig = {
    screw: {
        diameter: 4.5,          // ❌ Жесткая константа
        minEdgeDistance: 10,
        minHardwareDistance: 20,
        edgeDist: 15
    },
    // ... еще 10 типов крепежа с жесткими значениями
};
```

**Решение**:
```typescript
export interface HardwareStandard {
    name: string;           // "Blum", "Hettich", "GTV"
    config: HardwareConfig;
}

export const HARDWARE_STANDARDS: Record<string, HardwareStandard> = {
    blum: {
        name: 'Blum (European)',
        config: { /* Blum параметры */ }
    },
    hettich: {
        name: 'Hettich (German)',
        config: { /* Hettich параметры */ }
    },
    gtv: {
        name: 'GTV (Russian)',
        config: { /* GTV параметры */ }
    }
};

// Использование
class HardwareManager {
    constructor(standard: string = 'blum') {
        this.config = HARDWARE_STANDARDS[standard].config;
    }
}
```

**Приоритет**: 🔵 НИЗКИЙ  
**Сложность**: 1 час  
**Тесты**: Unit тесты для каждого стандарта

---

### 🔵 Проблема 4.2: Отсутствует Context-aware prompting в Gemini

**Файл**: `services/geminiService.ts`

**Описание**:
Gemini не помнит предыдущие запросы пользователя (нет conversation history).

```typescript
// Текущий код (stateless)
async generateDesignFromDescription(userInput: string) {
    // Каждый запрос независимый ❌
    return this.generateContent(SYSTEM_PROMPTS.GENERATOR, userInput);
}
```

**Решение** (Multi-turn conversation):
```typescript
class GeminiService {
    private conversationHistory: Array<{
        role: 'user' | 'assistant';
        content: string;
    }> = [];
    
    async askWithHistory(userMessage: string, systemPrompt: string) {
        // Добавить новый запрос в историю
        this.conversationHistory.push({
            role: 'user',
            content: userMessage
        });
        
        // Отправить всю историю Gemini (контекст)
        const response = await this.client.generateContent({
            contents: [
                ...this.conversationHistory.map(msg => ({
                    role: msg.role,
                    parts: [{ text: msg.content }]
                }))
            ],
            systemInstruction: systemPrompt
        });
        
        const assistantMessage = response.text();
        
        // Сохранить ответ
        this.conversationHistory.push({
            role: 'assistant',
            content: assistantMessage
        });
        
        return assistantMessage;
    }
    
    clearHistory(): void {
        this.conversationHistory = [];
    }
}

// Использование
const service = new GeminiService();

const design1 = await service.askWithHistory(
    'Нужен шкаф-купе 2400мм х 2200мм х 650мм',
    SYSTEM_PROMPTS.GENERATOR
);

// Gemini помнит о previous запросе!
const design2 = await service.askWithHistory(
    'Можешь добавить 3 дополнительные полки?',
    SYSTEM_PROMPTS.GENERATOR
);  // ✅ Gemini поймет "дополнительные" в контексте первого дизайна
```

**Приоритет**: 🔵 НИЗКИЙ  
**Сложность**: 1.5 часа  
**Тесты**: Integration тесты

---

## 5. План внедрения улучшений

### Фаза 1: Критические исправления (1-2 дня)

```
День 1:
├─ Добавить валидацию входных данных в CabinetGenerator
├─ Добавить защиту от NaN/Infinity в ConstraintSolver
└─ Добавить timeout для Gemini запросов

День 2:
├─ Написать тесты для критических исправлений
└─ Testing и QA
```

### Фаза 2: Высокие приоритеты (3-4 дня)

```
День 3:
├─ ParameterCache инвалидация
├─ Dependency Injection для Solver
└─ Кеширование Gemini (LRU)

День 4:
├─ Тесты для высоких приоритетов
└─ Integration testing
```

### Фаза 3: Средние приоритеты (1 неделя)

```
День 5-7:
├─ Delta compression для History
├─ Auto-save в localStorage
├─ Параметризация HARDWARE_CONFIG
└─ Context-aware prompting
```

---

## 6. Контрольный список для проверки качества

### Код
- [ ] Все входные данные валидируются
- [ ] Нет жестких зависимостей (используется DI)
- [ ] Обработаны NaN/Infinity случаи
- [ ] Есть timeouts для внешних API
- [ ] Производительность оптимизирована (кеширование)

### Тестирование
- [ ] Unit тесты покрывают 80%+ функций
- [ ] Integration тесты для основных workflow'ов
- [ ] Edge case тесты (нулевые значения, пустые массивы)
- [ ] Stress тесты (большие сборки, 100+ компонентов)

### Документация
- [ ] Все публичные API методы документированы
- [ ] Примеры использования для каждого сервиса
- [ ] README с установкой и быстрым стартом
- [ ] Architecture docs с диаграммами

### Производительность
- [ ] Генерация < 500мс для типовой конфигурации
- [ ] Solver < 2sec для 50+ компонентов
- [ ] Memory usage < 100MB для типовой сборки
- [ ] No memory leaks при долгом использовании

---

## 7. Рекомендуемые инструменты

### Тестирование
```bash
npm install --save-dev jest @types/jest ts-jest
npm install --save-dev @testing-library/react @testing-library/react-hooks
npm test --coverage
```

### Профилирование производительности
```typescript
import { PerformanceMonitor } from './services/PerformanceMonitor';

const monitor = new PerformanceMonitor();

monitor.start('cabinet-generation');
const panels = generator.generate();
const duration = monitor.end('cabinet-generation');

console.log(`⏱️ Cabinet generation took ${duration}ms`);
```

### Анализ качества кода
```bash
npm install --save-dev eslint @typescript-eslint/eslint-plugin
npm install --save-dev prettier
npx eslint . --ext .ts,.tsx
```

---

## Итоговые рекомендации

**Приоритет 1**: Исправить критические проблемы (валидация, NaN, timeout)  
**Приоритет 2**: Улучшить DX (DI, кеширование, error handling)  
**Приоритет 3**: Оптимизировать память и производительность  

**Ожидаемый результат**: 
- ✅ Более надежный код
- ✅ Лучшая производительность  
- ✅ Проще тестировать и расширять
- ✅ Меньше bugs в production
