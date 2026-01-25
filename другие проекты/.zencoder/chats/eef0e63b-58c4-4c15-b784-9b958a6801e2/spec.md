# Technical Specification: CAD System Implementation
## BazisLite-Web Professional CAD Architecture

**Дата:** 18 января 2026  
**Версия:** 1.0  
**Статус:** READY FOR IMPLEMENTATION

---

## 1. ТЕХНИЧЕСКИЙ КОНТЕКСТ

### 1.1 Язык и Runtime
```
Language:           TypeScript (strict mode)
Compiler Target:    ES2022
Runtime:            Node.js 18+
Package Manager:    npm
Module System:      ES Modules
```

### 1.2 Основные зависимости
```json
{
  "dependencies": {
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "zustand": "5.0.10",
    "three": "latest",
    "@babylonjs/core": "6.32.1",
    "lodash": "4.17.21",
    "recharts": "2.10.3",
    "@google/generative-ai": "latest",
    "numeric": "^1.2.6",           // ← Новая (Фаза 2: Solver)
    "xml2js": "^0.6.0",            // ← Новая (Фаза 6: STEP export)
    "three-stl-loader": "^1.0.6"   // ← Новая (Фаза 6: STL export)
  },
  "devDependencies": {
    "typescript": "5.9.0",
    "vite": "6.2.0",
    "@vitejs/plugin-react": "5.0.0",
    "jest": "30.2.0",
    "ts-jest": "29.4.6",
    "@types/jest": "30.0.0"
  }
}
```

### 1.3 Версии React, TypeScript, Vite
```
React:        19.2.3 (React DOM 19.2.3)
TypeScript:   5.9.0 (strict mode)
Vite:         6.2.0
Jest:         30.2.0
Target:       ES2022
```

---

## 2. АРХИТЕКТУРНЫЙ ПОДХОД

### 2.1 Принципы проектирования

#### 2.1.1 Модульность
- Каждая фаза — независимый модуль в `services/`
- Минимальные зависимости между фазами
- Чистые интерфейсы (interfaces) для связи

#### 2.1.2 Type Safety
- 100% TypeScript strict mode
- Не использовать `any` (разрешено только с комментарием `// @ts-ignore`)
- JSDoc для всех публичных функций

#### 2.1.3 Performance First
- Performance budgets на каждую фазу:
  - Solver: < 500 мс на 50 компонентах
  - FEA: < 5 сек на 1000 узлов
  - Export: < 2 сек для STL
- Использовать Web Workers для long-running операций
- Lazy loading компонентов

#### 2.1.4 Testability
- Unit тесты для всех сервисов (target > 85%)
- E2E тесты для критических путей
- Мокирование зависимостей (jest.mock)
- Test fixtures в `__tests__/fixtures/`

### 2.2 Архитектурные слои

```
┌─────────────────────────────────────────────┐
│  UI Layer (React Components)                │
│  ┌─────────────────────────────────────────┐│
│  │ BOMViewer │ DFMReport │ FEAPanel │ ...  ││
│  └─────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│  Business Logic Layer (Services)            │
│  ┌─────────────────────────────────────────┐│
│  │ Solver │ BOM │ DFM │ Optimizer │ Export ││
│  └─────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│  Data Model Layer (Types + State)           │
│  ┌─────────────────────────────────────────┐│
│  │ CADTypes.ts │ Zustand Store │ Cache     ││
│  └─────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│  External Integrations                      │
│  ┌─────────────────────────────────────────┐│
│  │ Three.js │ Babylon.js │ Gemini API      ││
│  └─────────────────────────────────────────┘│
```

### 2.3 Data Flow

```
User Input (UI)
    ↓
Zustand Store (projectStore)
    ↓
CabinetGenerator (конфиг → структура)
    ↓
CAD Services (Solver, BOM, DFM, FEA, Export)
    ↓
React Components (визуализация)
    ↓
Three.js / Babylon.js (рендеринг)
```

---

## 3. СТРУКТУРА ИСХОДНОГО КОДА

### 3.1 Текущая структура (Существующая)
```
базис-веб/
├── components/
│   ├── Scene3D.tsx              (3D визуализация с Three.js)
│   ├── Scene3DBabylon.tsx       (Babylon.js альтернатива)
│   ├── EditorPanel.tsx          (Редактор параметров)
│   ├── CutList.tsx              (Спецификация резки)
│   ├── DrawingView.tsx          (2D чертежи)
│   ├── NestingView.tsx          (Оптимизация раскроя)
│   ├── CabinetWizard.tsx        (Мастер создания)
│   └── ... (остальные компоненты)
├── services/
│   ├── CabinetGenerator.ts      (Основной генератор)
│   ├── geminiService.ts         (AI интеграция)
│   ├── hardwareUtils.ts         (Фурнитура)
│   ├── storageService.ts        (Сохранение данных)
│   ├── InputValidator.ts        (Валидация)
│   └── __tests__/
├── store/
│   └── projectStore.ts          (Zustand)
├── types/
│   └── CADTypes.ts              (500+ типов)
├── hooks/
│   ├── usePerformance.ts
│   └── ... (остальные hooks)
├── workers/
│   └── nesting.worker.js        (Web Worker для раскроя)
├── App.tsx                      (Главный компонент)
├── index.tsx                    (React entry point)
├── vite.config.ts              (Конфиг Vite)
├── tsconfig.json               (Конфиг TypeScript)
└── package.json
```

### 3.2 Новая структура (Фазы 1-8)

```
базис-веб/
├── types/
│   ├── CADTypes.ts              ✅ Существует (500+ строк)
│   ├── Solver.types.ts          ← Фаза 2
│   ├── BOM.types.ts             ← Фаза 3
│   └── ... (типы для остальных фаз)
│
├── services/
│   ├── CabinetGenerator.ts      ✅ (будет расширен)
│   │
│   ├── ConstraintSolver.ts      ← Фаза 2
│   ├── BillOfMaterials.ts       ← Фаза 3
│   ├── HierarchyManager.ts      ← Фаза 3
│   ├── DFMValidator.ts          ← Фаза 4
│   ├── CabinetOptimizer.ts      ← Фаза 5
│   ├── CADExporter.ts           ← Фаза 6
│   ├── CADImporter.ts           ← Фаза 6
│   ├── FEAIntegration.ts        ← Фаза 7
│   ├── PerformanceMonitor.ts    ← Фаза 8
│   │
│   ├── __tests__/
│   │   ├── ConstraintSolver.test.ts
│   │   ├── BillOfMaterials.test.ts
│   │   ├── HierarchyManager.test.ts
│   │   ├── DFMValidator.test.ts
│   │   ├── CabinetOptimizer.test.ts
│   │   ├── CADExporter.test.ts
│   │   ├── CADImporter.test.ts
│   │   ├── FEAIntegration.test.ts
│   │   ├── IntegrationTests.test.ts
│   │   └── fixtures/
│   │       ├── cabinet.fixture.ts
│   │       ├── assembly.fixture.ts
│   │       └── materials.fixture.ts
│   │
│   └── (существующие сервисы)
│
├── components/
│   ├── BOMViewer.tsx            ← Фаза 3
│   ├── HierarchyTree.tsx        ← Фаза 3
│   ├── DFMReport.tsx            ← Фаза 4
│   ├── OptimizationResults.tsx  ← Фаза 5
│   ├── FEAPanel.tsx             ← Фаза 7
│   │
│   └── (существующие компоненты)
│
├── workers/
│   ├── nesting.worker.js        ✅ (существует)
│   ├── fea.worker.js            ← Фаза 7 (параллельные вычисления)
│   └── solver.worker.js         ← Фаза 2 (опционально для больших систем)
│
├── docs/
│   ├── PHASE1_ARCHITECTURE.md
│   ├── PHASE2_SOLVER.md
│   ├── PHASE3_BOM.md
│   ├── PHASE4_DFM.md
│   ├── PHASE5_OPTIMIZATION.md
│   ├── PHASE6_EXPORT.md
│   ├── PHASE7_FEA.md
│   └── API_REFERENCE.md
│
├── App.tsx                      (Будет обновлён для новых view modes)
├── vite.config.ts              (Обновлён для Web Workers)
├── package.json                (Новые зависимости)
└── jest.config.js              (Существует)
```

---

## 4. МОДЕЛЬ ДАННЫХ И API

### 4.1 Основные типы (уже в CADTypes.ts)

```typescript
// Базовая 3D геометрия
interface Point3D {
  x: number;
  y: number;
  z: number;
}

// Компоненты и сборки
interface Component {
  id: string;
  name: string;
  type: ComponentType;
  position: Point3D;
  rotation: EulerAngles;
  material: Material;
  geometry: {
    width: number;
    height: number;
    depth: number;
  };
  subComponents?: Component[];
  anchorPoints?: AnchorPoint[];
}

interface Assembly {
  id: string;
  name: string;
  components: Component[];
  constraints: Constraint[];
  rootComponent: Component;
  metadata: {
    version: string;
    createdAt: Date;
    modifiedAt: Date;
  };
}

// Ограничения для позиционирования
interface Constraint {
  id: string;
  type: ConstraintType;  // coincident, distance, angle, fixed, etc.
  elementA: string;
  elementB?: string;
  value?: number;
  tolerance?: number;
  weight?: number;
  isSatisfied?: boolean;
  error?: number;
}
```

### 4.2 API сервисов (Фазы 1-8)

#### Фаза 2: Constraint Solver
```typescript
export class ConstraintSolver {
  /**
   * Решить систему ограничений Newton-Raphson методом
   * @param assembly Сборка с ограничениями
   * @param maxIterations Максимум итераций (по умолчанию 100)
   * @param tolerance Допуск для сходимости (по умолчанию 0.001)
   * @returns Решённая сборка с обновленными позициями компонентов
   */
  solve(
    assembly: Assembly,
    options?: SolverOptions
  ): Promise<SolvedAssembly>;

  /**
   * Проверить, удовлетворены ли все ограничения
   */
  checkConstraints(assembly: Assembly): ConstraintCheckResult[];

  /**
   * Добавить ограничение
   */
  addConstraint(constraint: Constraint): void;

  /**
   * Удалить ограничение
   */
  removeConstraint(constraintId: string): void;
}
```

#### Фаза 3: Bill of Materials
```typescript
export class BillOfMaterials {
  /**
   * Сгенерировать BOM из сборки
   */
  generateBOM(assembly: Assembly): BOMHierarchy;

  /**
   * Расчитать стоимость
   */
  calculateCost(bom: BOMHierarchy, costs: MaterialCost[]): CostBreakdown;

  /**
   * Расчитать массу
   */
  calculateWeight(bom: BOMHierarchy): WeightBreakdown;

  /**
   * Экспортировать BOM
   */
  export(
    bom: BOMHierarchy,
    format: 'csv' | 'json' | 'pdf'
  ): string | Blob;
}

export class HierarchyManager {
  /**
   * Построить дерево компонентов
   */
  buildHierarchy(assembly: Assembly): HierarchyNode;

  /**
   * Получить путь компонента в иерархии
   */
  getComponentPath(componentId: string): ComponentPath;

  /**
   * Поиск компонента по ID
   */
  findComponent(componentId: string): Component | null;
}
```

#### Фаза 4: DFM Validator
```typescript
export class DFMValidator {
  /**
   * Проверить производимость конструкции
   * @returns Список нарушений и общий score
   */
  validate(assembly: Assembly): DFMReport;

  /**
   * Получить manufacturability score (0-100%)
   */
  getManufacturabilityScore(assembly: Assembly): number;

  /**
   * Добавить пользовательское правило
   */
  addRule(rule: DFMRule): void;
}
```

#### Фаза 5: Optimization
```typescript
export class CabinetOptimizer {
  /**
   * Оптимизировать по стратегии
   */
  optimize(
    assembly: Assembly,
    strategy: OptimizationStrategy
  ): Promise<OptimizationResult>;

  /**
   * 4 встроенные стратегии
   */
  strategies: {
    minimizeCost: OptimizationStrategy;
    minimizeWeight: OptimizationStrategy;
    maximizeStrength: OptimizationStrategy;
    balanceAll: OptimizationStrategy;
  };
}
```

#### Фаза 6: CAD Export/Import
```typescript
export class CADExporter {
  /**
   * Экспортировать в различные форматы
   */
  export(
    assembly: Assembly,
    format: 'stl' | 'dxf' | 'step' | 'json',
    config?: ExportConfig
  ): Promise<Blob>;
}

export class CADImporter {
  /**
   * Импортировать из внешних форматов
   */
  import(
    file: File,
    format: 'json' | 'stl' | 'step'
  ): Promise<Assembly>;
}
```

#### Фаза 7: FEA Integration
```typescript
export class FEAIntegration {
  /**
   * Провести статический анализ (напряжения, деформации)
   */
  performStaticAnalysis(
    assembly: Assembly,
    loads: Load[]
  ): Promise<StaticAnalysisResult>;

  /**
   * Провести модальный анализ (собственные частоты)
   */
  performModalAnalysis(
    assembly: Assembly,
    numModes?: number
  ): Promise<ModalAnalysisResult>;

  /**
   * Сгенерировать сетку (mesh)
   */
  generateMesh(assembly: Assembly): Mesh;
}
```

---

## 5. СПЕЦИФИКАЦИЯ ПО ФАЗАМ (INCREMENTAL DELIVERY)

### ФАЗА 1: АРХИТЕКТУРА (2 недели)

**Deliverables:**
- ✅ types/CADTypes.ts — 500+ строк интерфейсов (уже существует)
- [ ] Скеллеты 9 сервис-модулей
- [ ] 5 React компонентов (скеллеты)
- [ ] 50+ unit тестов
- [ ] Integration tests с CabinetGenerator

**Что реализуется:**
1. Дополнить CADTypes.ts (если нужно)
2. Создать файлы-заглушки:
   - services/ConstraintSolver.ts (пусто, только интерфейсы)
   - services/BillOfMaterials.ts
   - services/HierarchyManager.ts
   - services/DFMValidator.ts
   - services/CabinetOptimizer.ts
   - services/CADExporter.ts
   - services/CADImporter.ts
   - services/FEAIntegration.ts
   - services/PerformanceMonitor.ts
3. Создать React компоненты (скеллеты):
   - components/BOMViewer.tsx
   - components/HierarchyTree.tsx
   - components/DFMReport.tsx
   - components/OptimizationResults.tsx
   - components/FEAPanel.tsx
4. Написать unit тесты для структуры
5. Обновить App.tsx для поддержки новых view modes

**Verification:**
```bash
npm run typecheck      # TypeScript compilation
npm run test           # Unit tests > 50
npm run lint          # ESLint
```

---

### ФАЗА 2: CONSTRAINT SOLVER (2 недели)

**Deliverables:**
- [ ] ConstraintSolver.ts — полная реализация (500+ строк)
- [ ] 40+ unit тестов
- [ ] Performance benchmark < 500 мс
- [ ] Integration с CabinetGenerator

**Алгоритм:**
```
Newton-Raphson method для системы нелинейных уравнений:
1. Инициализировать Jacobian матрицу
2. Вычислить невязку (residual)
3. Итеративно: ΔX = -J⁻¹ * f(X)
4. Обновить позиции: X_{n+1} = X_n + ΔX
5. Повторять пока ||f(X)|| < tolerance
```

**Зависимости:** `numeric.js` для LU разложения Jacobian

**Verification:**
```bash
npm run test -- ConstraintSolver.test.ts
npm run benchmark -- solver  # < 500ms на 50 компонентах
```

---

### ФАЗА 3: BILL OF MATERIALS (2 недели)

**Deliverables:**
- [ ] BillOfMaterials.ts — расчёты массы, объёма, стоимости
- [ ] HierarchyManager.ts — навигация по дереву
- [ ] BOMViewer.tsx React компонент
- [ ] HierarchyTree.tsx React компонент
- [ ] 35+ unit тестов
- [ ] Export в CSV, JSON, PDF

**Функции:**
- Иерархический обход (DFS)
- Агрегирование свойств (масса, стоимость)
- Фильтрация и сортировка
- Экспорт

**Verification:**
```bash
npm run test -- BillOfMaterials.test.ts
npm run test -- HierarchyManager.test.ts
```

---

### ФАЗА 4: DFM VALIDATOR (2 недели)

**Deliverables:**
- [ ] DFMValidator.ts — 15+ правил
- [ ] DFMReport.tsx компонент
- [ ] 40+ unit тестов
- [ ] Reportinг в UI

**DFM Rules:**
1. Min thickness (4 мм)
2. Max aspect ratio (80:1)
3. Min corner radius (1 мм)
4. Edge distance (5 мм)
5. Min hole size (3 мм)
6. Min wall thickness (1.5 мм)
7. Assembly gaps (0.5 мм)
8-15. ... остальные

**Verification:**
```bash
npm run test -- DFMValidator.test.ts
```

---

### ФАЗА 5: OPTIMIZATION (3 недели)

**Deliverables:**
- [ ] CabinetOptimizer.ts — GA алгоритм
- [ ] OptimizationResults.tsx компонент
- [ ] 50+ unit тестов
- [ ] История оптимизаций

**4 стратегии:**
1. Cost minimization (10-20% экономия)
2. Weight minimization
3. Strength maximization
4. Balance (компромисс)

**Verification:**
```bash
npm run test -- CabinetOptimizer.test.ts
npm run benchmark -- optimizer
```

---

### ФАЗА 6: CAD EXPORT/IMPORT (2 недели)

**Deliverables:**
- [ ] CADExporter.ts — STL, DXF, STEP, JSON
- [ ] CADImporter.ts — JSON, STL, STEP
- [ ] 30+ unit тестов
- [ ] UI для экспорта/импорта

**Форматы:**
- **STL** (бинарный/текстовый) — для 3D печати
- **DXF** (ASCII) — для AutoCAD 2D чертежей
- **STEP** (ISO 10303-21) — профессиональный стандарт
- **JSON** — для веб-визуализации

**Зависимости:** `xml2js`, `three-stl-loader`

**Verification:**
```bash
npm run test -- CADExporter.test.ts
npm run test -- CADImporter.test.ts
```

---

### ФАЗА 7: FEA INTEGRATION (3 недели)

**Deliverables:**
- [ ] FEAIntegration.ts — solver + mesh generation
- [ ] FEAPanel.tsx компонент с визуализацией
- [ ] Web Worker для параллельных вычислений
- [ ] 40+ unit тестов
- [ ] Performance < 5 сек на 1000 узлов

**Анализы:**
1. **Static Analysis:**
   - Von Mises стресс
   - Деформации
   - Coefficient of Safety

2. **Modal Analysis:**
   - Собственные частоты
   - Формы колебаний (первые 5)

**Mesh Generation:**
- Automatic tetrahedral mesh (Open3D или собственный алгоритм)
- Адаптивное уплотнение (refinement) у концентраторов напряжений

**Verification:**
```bash
npm run test -- FEAIntegration.test.ts
npm run benchmark -- fea  # < 5 sec на 1000 узлов
```

---

### ФАЗА 8: TESTING & QA (2 недели)

**Deliverables:**
- [ ] 150+ E2E тестов
- [ ] Performance отчёты
- [ ] API documentation (JSDoc)
- [ ] Production checklist
- [ ] Total test coverage > 85%

**Benchmarks:**
```
Solver:     < 500 мс (50 компонентов)
FEA:        < 5 сек (1000 узлов)
Export:     < 2 сек (STL)
Import:     < 1 сек (JSON)
UI render:  < 60 fps
Memory:     < 200 MB (типовая сборка)
```

**Verification:**
```bash
npm run test -- --coverage
npm run lint
npm run typecheck
npm run build
npm run preview
```

---

## 6. ИНТЕГРАЦИЯ С СУЩЕСТВУЮЩЕЙ CODEBASE

### 6.1 CabinetGenerator расширение

**Текущая функция:**
```typescript
generateCabinet(): CabinetItem {
  // Генерирует шкаф с панелями, фурнитурой, и т.д.
}
```

**Новые методы (Фаза 1):**
```typescript
/**
 * Сгенерировать Assembly из конфигурации кабинета
 * @returns Assembly с компонентами и якорями
 */
generateAssembly(): Assembly {
  // Преобразовать Panel[] → Component[]
  // Создать AnchorPoints на гранях, рёбрах
  // Вернуть Assembly
}

/**
 * Сгенерировать ограничения для сборки
 */
generateConstraints(): Constraint[] {
  // Создать constraints для позиционирования
  // Например: боковые панели перпендикулярны дну
  // Фасады совпадают на передней плоскости
}

/**
 * Интегрировать решённую сборку обратно
 */
integrateFromAssembly(assembly: Assembly): void {
  // Обновить this.panels[] с новыми позициями
  // Обновить позиции фурнитуры
}
```

### 6.2 Zustand Store

**Текущее:**
```typescript
export const projectStore = create<ProjectState>((set) => ({
  projects: [],
  currentProject: null,
  // ...
}));
```

**Добавить:**
```typescript
export const projectStore = create<ProjectState>((set) => ({
  // ... существующее
  
  // Новое для CAD
  solvedAssembly: null,
  bomData: null,
  dfmReport: null,
  feaResults: null,
  optimizationResults: null,
  
  setSolvedAssembly: (assembly: Assembly) => set({ solvedAssembly: assembly }),
  setBOMData: (bom: BOMHierarchy) => set({ bomData: bom }),
  // ... остальные setter'ы
}));
```

### 6.3 App.tsx View Modes

**Текущие view modes:**
- DESIGN (CabinetWizard)
- CUT_LIST (CutList)
- DRAWING (DrawingView)
- NESTING (NestingView)
- PRODUCTION (ProductionPipeline)
- WIZARD (CabinetWizard)
- SCRIPT (ScriptEditor)

**Новые view modes (Фаза 1):**
```typescript
enum ViewMode {
  // ... существующие
  CAD_SOLVER = 'CAD_SOLVER',
  CAD_BOM = 'CAD_BOM',
  CAD_DFM = 'CAD_DFM',
  CAD_OPTIMIZATION = 'CAD_OPTIMIZATION',
  CAD_FEA = 'CAD_FEA',
  CAD_EXPORT = 'CAD_EXPORT'
}
```

### 6.4 UI Integration

**Навигация:**
Добавить в главное меню:
```
┌─────────────────────────┐
│ Design / Edit / Tools   │
├─────────────────────────┤
│ > CAD Tools             │
│   ├─ Constraint Solver  │
│   ├─ Bill of Materials  │
│   ├─ DFM Validator      │
│   ├─ Optimize           │
│   ├─ FEA Analysis       │
│   └─ Export/Import      │
│ > Production            │
│ > Settings              │
└─────────────────────────┘
```

---

## 7. ВЕРИФИКАЦИЯ И ТЕСТИРОВАНИЕ

### 7.1 Unit Test Strategy

**Coverage Target:** > 85% для новых модулей

**Файловая структура:**
```
services/__tests__/
├── fixtures/
│   ├── cabinet.fixture.ts       (Пример кабинета)
│   ├── assembly.fixture.ts      (Пример сборки)
│   ├── materials.fixture.ts     (Пример материалов)
│   └── constraints.fixture.ts   (Пример ограничений)
├── ConstraintSolver.test.ts
├── BillOfMaterials.test.ts
├── HierarchyManager.test.ts
├── DFMValidator.test.ts
├── CabinetOptimizer.test.ts
├── CADExporter.test.ts
├── CADImporter.test.ts
├── FEAIntegration.test.ts
└── IntegrationTests.test.ts
```

**Пример теста:**
```typescript
describe('ConstraintSolver', () => {
  let solver: ConstraintSolver;
  let assembly: Assembly;

  beforeEach(() => {
    solver = new ConstraintSolver();
    assembly = createTestAssembly(); // fixture
  });

  it('should solve simple distance constraint', async () => {
    const solved = await solver.solve(assembly);
    expect(solved.components[0].position.x).toBeCloseTo(100, 1);
  });

  it('should converge within tolerance', async () => {
    const solved = await solver.solve(assembly, { tolerance: 0.001 });
    const checks = solver.checkConstraints(solved);
    checks.forEach(check => {
      expect(check.satisfied).toBe(true);
    });
  });

  it('should handle 50 components in < 500ms', async () => {
    const largeAssembly = createLargeAssembly(50);
    const start = performance.now();
    await solver.solve(largeAssembly);
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(500);
  });
});
```

### 7.2 Integration Test Strategy

**End-to-End workflow:**
```
1. Create cabinet (CabinetGenerator)
2. Generate Assembly (новый метод)
3. Solve constraints (ConstraintSolver)
4. Generate BOM (BillOfMaterials)
5. Validate DFM (DFMValidator)
6. Run optimization (CabinetOptimizer)
7. Export to STL (CADExporter)
8. Verify result (DFM check)
```

### 7.3 Performance Benchmarks

**Jest benchmark setup:**
```typescript
describe('Performance Benchmarks', () => {
  it('ConstraintSolver: < 500ms on 50 components', async () => {
    const assembly = createAssembly(50);
    const start = performance.now();
    await solver.solve(assembly);
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(500);
  });

  it('FEA: < 5s on 1000 nodes', async () => {
    const mesh = createMesh(1000);
    const start = performance.now();
    await fea.performStaticAnalysis(mesh, loads);
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(5000);
  });
});
```

**Запуск benchmarks:**
```bash
npm run test -- --testNamePattern="Performance Benchmarks"
```

### 7.4 Linting & Type Checking

```bash
npm run lint          # ESLint (0 errors)
npm run typecheck     # TypeScript strict mode (0 errors)
npm run build         # Vite build (no errors)
npm test              # Jest (all green)
npm run test:coverage # Coverage report (>85%)
```

---

## 8. DEPLOYMENT STRATEGY

### 8.1 Feature Branches & CI/CD

**Branch naming:**
```
feature/phase-1-architecture
feature/phase-2-solver
feature/phase-3-bom
... и т.д.
```

**PR Requirements:**
- [ ] All tests pass
- [ ] Coverage > 85% (только для новых файлов)
- [ ] Code review (2 approvals)
- [ ] No lint errors
- [ ] TypeScript strict mode passes
- [ ] Performance benchmarks pass

**Merge strategy:** Squash commits (сохранять историю в commit message)

### 8.2 Staging & Production

**Dev deployment:** После каждого merge в `develop`
**Staging deployment:** После каждого merge в `staging`
**Production deployment:** Manual trigger, требует ✅ production checklist

---

## 9. DOCUMENTATION REQUIREMENTS

### 9.1 Code Documentation (JSDoc)

**Каждый public метод должен иметь:**
```typescript
/**
 * Решить систему ограничений Newton-Raphson методом
 *
 * @param assembly Сборка с ограничениями
 * @param options Опции решателя (maxIterations, tolerance)
 * @returns Promise<SolvedAssembly> Решённая сборка
 * @throws {Error} Если solver не сходится за maxIterations
 *
 * @example
 * const solved = await solver.solve(assembly, { maxIterations: 100 });
 */
async solve(
  assembly: Assembly,
  options?: SolverOptions
): Promise<SolvedAssembly> {
  // ...
}
```

### 9.2 User Documentation

**По каждой фазе:**
- Architecture overview
- Feature walkthrough
- API reference
- Code examples
- Performance considerations
- Known limitations

**Места сохранения:**
- `/docs/PHASE1_ARCHITECTURE.md`
- `/docs/PHASE2_SOLVER.md`
- И т.д.

---

## 10. УСПЕХ И ПРИЁМОЧНЫЕ КРИТЕРИИ

### 10.1 Per Phase Success

Каждая фаза считается успешной когда:
- ✅ Все unit тесты зелёные (> 85% coverage)
- ✅ `npm run lint` без ошибок
- ✅ `npm run typecheck` без ошибок
- ✅ Performance benchmarks достигнуты
- ✅ JSDoc документация 100%
- ✅ Code review одобрен
- ✅ Интегрирована с App.tsx и projectStore

### 10.2 Final Delivery Success

**Production ready когда:**
- ✅ 300+ unit tests, all green
- ✅ 150+ E2E tests, all green
- ✅ Coverage > 85%
- ✅ Performance benchmarks: Solver <500ms, FEA <5s, Export <2s
- ✅ Full API documentation
- ✅ All DFM rules implemented (15+)
- ✅ All export formats working (STL, DXF, STEP, JSON)
- ✅ FEA с static + modal analysis
- ✅ 4 optimization strategies работают
- ✅ Production checklist ✅

---

## 11. RISK MITIGATION

| Риск | Вероятность | Смягчение | Ответственный |
|------|-------------|----------|---------------|
| Solver не сходится | 35% | Использовать numeric.js, benchmarking рано | Backend dev |
| FEA требует много памяти | 50% | Web Workers, WebAssembly для критических путей | Performance dev |
| Scope creep | 55% | Strict feature freeze, все v2.0 в backlog | PM |
| Type safety issues | 20% | Strict TypeScript mode, linting | All |
| Performance regression | 40% | Benchmarks на каждую PR | DevOps |

---

## 12. TIMELINE ESTIMATE

```
Неделя 1-2:   Фаза 1 Архитектура        (160 часов)
Неделя 3-4:   Фаза 2 Solver            (180 часов)
Неделя 5-6:   Фаза 3 BOM               (125 часов)
Неделя 7-8:   Фаза 4 DFM               (120 часов)
Неделя 9-11:  Фаза 5 Optimization      (240 часов)
Неделя 12-13: Фаза 6 Export/Import     (175 часов)
Неделя 14-16: Фаза 7 FEA               (350 часов)
Неделя 17-18: Фаза 8 Testing           (200 часов)
              ────────────────────────────────
              ИТОГО:                  1550 часов
```

**Ресурсы:** 2-3 разработчика
**Скорость:** 40-45 часов/неделя на разработчика

---

## CONCLUSION

Эта техническая спецификация определяет **чистую архитектуру** для трансформации BazisLite-Web в professional CAD систему. 

**Ключевые преимущества подхода:**
- ✅ Incremental delivery (каждая фаза самостоятельна)
- ✅ High test coverage (> 85%)
- ✅ Performance budgets на каждую операцию
- ✅ Type-safe (TypeScript strict)
- ✅ Well-documented (JSDoc + guides)
- ✅ Production-ready quality
