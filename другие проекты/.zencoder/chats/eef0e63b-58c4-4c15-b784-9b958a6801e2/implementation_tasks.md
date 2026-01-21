# Implementation Tasks: CAD System Phase-by-Phase

**Дата:** 18 января 2026  
**Статус:** READY TO EXECUTE  
**Total Phases:** 8  
**Total Tasks:** 58

---

## ФАЗА 1: АРХИТЕКТУРНОЕ ПРОЕКТИРОВАНИЕ (2 недели)
**Ответственный:** 1-2 разработчика  
**Часов:** 160  
**Target:** Фундамент для остальных фаз

### Task 1.1: Завершить CADTypes.ts
**Зависит от:** —  
**Deliverables:** types/CADTypes.ts (865+ строк)

- [ ] 1.1.1 Добавить BOM типы (BOMItem, BOMHierarchy, BOMExport)
- [ ] 1.1.2 Добавить DFM типы (DFMRule, DFMReport, ManufacturabilityScore)
- [ ] 1.1.3 Добавить Optimization типы (OptimizationStrategy, OptimizationResult)
- [ ] 1.1.4 Добавить FEA типы (FEAAnalysis, SimulationResult, MeshData, Load)
- [ ] 1.1.5 Добавить Export типы (CADFormat, ExportConfig, ImportConfig)
- [ ] 1.1.6 Добавить Hierarchy типы (HierarchyNode, ComponentPath)
- [ ] 1.1.7 Добавить Performance типы (PerformanceMetrics, BenchmarkResult)
- [ ] 1.1.8 Экспортировать ВСЕ типы из index.ts

**Verification:**
```bash
npm run typecheck  # 0 errors
npm run lint       # 0 errors
```

---

### Task 1.2: Создать скеллеты сервис-модулей
**Зависит от:** 1.1  
**Deliverables:** 9 файлов в services/

- [ ] 1.2.1 services/ConstraintSolver.ts (250 строк, интерфейсы)
- [ ] 1.2.2 services/BillOfMaterials.ts (200 строк, интерфейсы)
- [ ] 1.2.3 services/HierarchyManager.ts (150 строк, интерфейсы)
- [ ] 1.2.4 services/DFMValidator.ts (200 строк, интерфейсы)
- [ ] 1.2.5 services/CabinetOptimizer.ts (150 строк, интерфейсы)
- [ ] 1.2.6 services/CADExporter.ts (150 строк, интерфейсы)
- [ ] 1.2.7 services/CADImporter.ts (120 строк, интерфейсы)
- [ ] 1.2.8 services/FEAIntegration.ts (200 строк, интерфейсы)
- [ ] 1.2.9 services/PerformanceMonitor.ts (100 строк, интерфейсы)

**Каждый файл должен содержать:**
```typescript
/**
 * [Модуль описание]
 * 
 * Зависит от:
 * - types/CADTypes.ts
 * - ... другие
 */

export interface [ModuleConfig] { ... }

export class [Module] {
  constructor(config: [ModuleConfig]) { ... }
  
  // Основные методы (заглушки пока)
}
```

**Verification:**
```bash
npm run typecheck  # 0 errors
```

---

### Task 1.3: Создать скеллеты React компонентов
**Зависит от:** 1.1  
**Deliverables:** 5 файлов в components/

- [ ] 1.3.1 components/BOMViewer.tsx (200 строк, JSX)
- [ ] 1.3.2 components/HierarchyTree.tsx (200 строк, JSX)
- [ ] 1.3.3 components/DFMReport.tsx (200 строк, JSX)
- [ ] 1.3.4 components/OptimizationResults.tsx (200 строк, JSX)
- [ ] 1.3.5 components/FEAPanel.tsx (200 строк, JSX)

**Каждый компонент должен:**
- Принимать типизированные props (из CADTypes)
- Иметь базовую структуру (div, h2, description)
- Быть экспортирован из index.ts
- Иметь JSDoc комментарий

**Пример структуры:**
```typescript
interface BOMViewerProps {
  bom: BOMHierarchy;
  onExport?: (format: 'csv' | 'json' | 'pdf') => void;
}

/**
 * BOMViewer компонент для визуализации Bill of Materials
 */
export const BOMViewer: React.FC<BOMViewerProps> = ({ bom, onExport }) => {
  return (
    <div className="bom-viewer">
      <h2>Bill of Materials</h2>
      {/* placeholder */}
    </div>
  );
};
```

**Verification:**
```bash
npm run typecheck  # 0 errors
npm run lint       # 0 errors
```

---

### Task 1.4: Обновить CabinetGenerator для Assembly
**Зависит от:** 1.1  
**Deliverables:** Расширенные методы в CabinetGenerator

- [ ] 1.4.1 Добавить метод `generateAssembly(): Assembly`
  - Преобразовать Panel[] → Component[]
  - Создать AnchorPoints на вершинах, рёбрах, гранях
  - Установить материалы и геометрию
  - Вернуть Assembly с rootComponent

- [ ] 1.4.2 Добавить метод `generateConstraints(): Constraint[]`
  - Создать FIXED constraint для дна (z=0)
  - Создать PARALLEL constraints для боковых панелей
  - Создать PERPENDICULAR constraints для перпендикулярных элементов
  - Создать DISTANCE constraints для зазоров

- [ ] 1.4.3 Добавить метод `integrateFromAssembly(assembly: Assembly): void`
  - Обновить this.panels[] с новыми позициями
  - Обновить позиции фурнитуры
  - Обновить позиции направляющих и других элементов

- [ ] 1.4.4 Добавить unit тесты (10+)

**Verification:**
```bash
npm run test -- CabinetGenerator.test.ts  # 10+ tests green
```

---

### Task 1.5: Обновить Zustand Store
**Зависит от:** 1.1  
**Deliverables:** Расширенный projectStore

- [ ] 1.5.1 Добавить поля:
  ```typescript
  solvedAssembly: Assembly | null;
  bomData: BOMHierarchy | null;
  dfmReport: DFMReport | null;
  feaResults: FEAResults | null;
  optimizationResults: OptimizationResult | null;
  ```

- [ ] 1.5.2 Добавить setter actions:
  ```typescript
  setSolvedAssembly: (assembly: Assembly) => void;
  setBOMData: (bom: BOMHierarchy) => void;
  setDFMReport: (report: DFMReport) => void;
  setFEAResults: (results: FEAResults) => void;
  setOptimizationResults: (results: OptimizationResult) => void;
  clearCADData: () => void;
  ```

- [ ] 1.5.3 Обновить types.ts

**Verification:**
```bash
npm run typecheck  # 0 errors
```

---

### Task 1.6: Обновить App.tsx для новых view modes
**Зависит от:** 1.1, 1.5  
**Deliverables:** Обновлённый App.tsx с новыми режимами

- [ ] 1.6.1 Добавить enum ViewMode:
  ```typescript
  CAD_SOLVER = 'CAD_SOLVER',
  CAD_BOM = 'CAD_BOM',
  CAD_DFM = 'CAD_DFM',
  CAD_OPTIMIZATION = 'CAD_OPTIMIZATION',
  CAD_FEA = 'CAD_FEA',
  CAD_EXPORT = 'CAD_EXPORT'
  ```

- [ ] 1.6.2 Добавить switch cases для каждого режима
- [ ] 1.6.3 Добавить кнопки в навигацию (CAD Tools)
- [ ] 1.6.4 Пока компоненты будут пусты (placeholder)

**Verification:**
```bash
npm run typecheck   # 0 errors
npm run build       # Builds successfully
```

---

### Task 1.7: Написать unit тесты (50+)
**Зависит от:** 1.1-1.6  
**Deliverables:** services/__tests__/*.test.ts

- [ ] 1.7.1 Создать fixtures:
  - [ ] fixtures/cabinet.fixture.ts (пример кабинета)
  - [ ] fixtures/assembly.fixture.ts (пример сборки)
  - [ ] fixtures/materials.fixture.ts (пример материалов)

- [ ] 1.7.2 Написать тесты для CADTypes (10 тестов)
  - Создание Point3D, Vector3D
  - Создание Component, Assembly
  - Валидация ограничений

- [ ] 1.7.3 Написать тесты для CabinetGenerator (15 тестов)
  - generateAssembly() создаёт корректную структуру
  - generateConstraints() создаёт нужное количество constraints
  - integrateFromAssembly() обновляет позиции

- [ ] 1.7.4 Написать интеграционные тесты (25 тестов)
  - Full workflow: config → Assembly → constraints

**Verification:**
```bash
npm run test -- --coverage  # > 50 tests, >85% coverage
```

---

### Task 1.8: Update package.json dependencies
**Зависит от:** —  
**Deliverables:** package.json с новыми deps

- [ ] 1.8.1 Добавить dependencies:
  ```json
  "numeric": "^1.2.6",
  "xml2js": "^0.6.0",
  "three-stl-loader": "^1.0.6"
  ```

- [ ] 1.8.2 Запустить `npm install`
- [ ] 1.8.3 Убедиться что всё компилируется

**Verification:**
```bash
npm install         # No errors
npm run typecheck   # 0 errors
npm run build       # Successful
```

---

### Task 1.9: Documentation & README
**Зависит от:** 1.1-1.8  
**Deliverables:** docs/PHASE1_ARCHITECTURE.md

- [ ] 1.9.1 Написать README для Phase 1
  - Обзор типов
  - Структура модулей
  - Как запустить тесты
  - Next steps

**Verification:**
```bash
# Проверить что README существует и полезен
cat docs/PHASE1_ARCHITECTURE.md
```

---

## ФАЗА 2: CONSTRAINT SOLVER (2 недели)
**Ответственный:** 2 разработчика  
**Часов:** 180  
**Зависит от:** Фаза 1

### Task 2.1: Реализовать Newton-Raphson Solver
**Зависит от:** 1.1  
**Deliverables:** services/ConstraintSolver.ts (500+ строк)

- [ ] 2.1.1 Реализовать класс ConstraintSolver
- [ ] 2.1.2 Реализовать метод `solve(assembly, options)`:
  - Инициализировать систему уравнений
  - Вычислить Jacobian матрицу
  - Использовать `numeric.js` для LU разложения
  - Newton-Raphson итерации (< 100 итераций)
  - Сходимость когда ||residual|| < tolerance

- [ ] 2.1.3 Реализовать `checkConstraints(assembly)`:
  - Вычислить невязку (residual) для каждого constraint
  - Вернуть массив ConstraintCheckResult

- [ ] 2.1.4 Поддержка всех 8 типов ограничений:
  - COINCIDENT
  - PARALLEL
  - PERPENDICULAR
  - DISTANCE
  - ANGLE
  - FIXED
  - TANGENT
  - SYMMETRIC

**Code Structure:**
```typescript
export class ConstraintSolver {
  private assembly: Assembly;
  private constraints: Constraint[];
  private tolerance: number = 0.001;
  
  constructor(assembly: Assembly) { ... }
  
  solve(options?: SolverOptions): Promise<Assembly> {
    // Newton-Raphson algorithm
  }
  
  private computeJacobian(): number[][] { ... }
  private computeResidual(): number[] { ... }
  private applyIncrement(delta: number[]): void { ... }
}
```

**Verification:**
```bash
npm run test -- ConstraintSolver.test.ts  # All tests pass
npm run benchmark -- solver               # < 500ms on 50 components
```

---

### Task 2.2: Написать 40+ unit тестов
**Зависит от:** 2.1  
**Deliverables:** services/__tests__/ConstraintSolver.test.ts

- [ ] 2.2.1 Тесты для простых constraints (10)
  - Простое совпадение точек
  - Простое расстояние
  - Простой угол

- [ ] 2.2.2 Тесты для сложных систем (15)
  - 10 компонентов
  - 20 компонентов
  - 50 компонентов (benchmark)

- [ ] 2.2.3 Тесты для error handling (10)
  - Non-convergence
  - Singular matrix
  - Invalid constraints

- [ ] 2.2.4 Performance тесты (5)
  - 50 components: < 500ms
  - Memory usage: < 50MB
  - Convergence rate

**Verification:**
```bash
npm run test -- ConstraintSolver.test.ts --coverage  # > 40 tests
```

---

### Task 2.3: Integration с CabinetGenerator
**Зависит от:** 2.1, 1.4  
**Deliverables:** Обновлённый CabinetGenerator

- [ ] 2.3.1 Добавить метод `solveAssembly()`:
  ```typescript
  async solveAssembly(solver: ConstraintSolver): Promise<void> {
    const assembly = this.generateAssembly();
    const solved = await solver.solve(assembly);
    this.integrateFromAssembly(solved);
  }
  ```

- [ ] 2.3.2 Добавить error handling
- [ ] 2.3.3 Написать интеграционные тесты (5+)

**Verification:**
```bash
npm run test -- CabinetGenerator.test.ts  # Solver integration tests pass
```

---

### Task 2.4: Обновить App.tsx CAD_SOLVER view
**Зависит от:** 2.1, 1.6  
**Deliverables:** Функциональный CAD_SOLVER mode в App.tsx

- [ ] 2.4.1 Создать компонент ConstraintSolverPanel.tsx
  - Кнопка "Solve Constraints"
  - Показать статус solver (итерации, residual)
  - Показать результаты (constraints satisfied)
  - Error messages если не сходится

- [ ] 2.4.2 Интегрировать в App.tsx
- [ ] 2.4.3 Обновить projectStore для solver results

**Verification:**
```bash
npm run build       # Builds
npm run typecheck   # 0 errors
```

---

### Task 2.5: Documentation
**Зависит от:** 2.1-2.4  
**Deliverables:** docs/PHASE2_SOLVER.md

- [ ] 2.5.1 Написать архитектурный документ
  - Newton-Raphson algorithm explanation
  - Jacobian computation
  - Constraint types

- [ ] 2.5.2 Написать API reference
  - `solve()` parameters
  - Return types
  - Error handling

- [ ] 2.5.3 Performance guide
  - Benchmark results
  - Optimization tips
  - Known limitations

---

## ФАЗА 3: BILL OF MATERIALS (2 недели)
**Ответственный:** 1-2 разработчика  
**Часов:** 125  
**Зависит от:** Фаза 1

### Task 3.1: Реализовать BillOfMaterials service
**Зависит от:** 1.1  
**Deliverables:** services/BillOfMaterials.ts (400+ строк)

- [ ] 3.1.1 Класс BillOfMaterials с методами:
  ```typescript
  generateBOM(assembly: Assembly): BOMHierarchy
  calculateCost(bom: BOMHierarchy, costs: MaterialCost[]): CostBreakdown
  calculateWeight(bom: BOMHierarchy): WeightBreakdown
  export(bom: BOMHierarchy, format: 'csv'|'json'|'pdf'): string|Blob
  ```

- [ ] 3.1.2 Поддержка 3 форматов экспорта:
  - CSV (для Excel, ERP системы)
  - JSON (для веб и обработки)
  - PDF (для печати и документации)

- [ ] 3.1.3 Расчёты:
  - Иерархическая обход (DFS)
  - Агрегирование свойств (масса, стоимость)
  - Удаление дубликатов компонентов

**Verification:**
```bash
npm run test -- BillOfMaterials.test.ts  # All tests pass
```

---

### Task 3.2: Реализовать HierarchyManager service
**Зависит от:** 1.1  
**Deliverables:** services/HierarchyManager.ts (300+ строк)

- [ ] 3.2.1 Класс HierarchyManager с методами:
  ```typescript
  buildHierarchy(assembly: Assembly): HierarchyNode
  getComponentPath(componentId: string): ComponentPath
  findComponent(componentId: string): Component | null
  getChildren(componentId: string): Component[]
  getParent(componentId: string): Component | null
  ```

- [ ] 3.2.2 Поддержка навигации по дереву
- [ ] 3.2.3 Кеширование результатов

**Verification:**
```bash
npm run test -- HierarchyManager.test.ts  # All tests pass
```

---

### Task 3.3: Создать BOMViewer React компонент
**Зависит от:** 1.3, 3.1, 3.2  
**Deliverables:** components/BOMViewer.tsx (300+ строк)

- [ ] 3.3.1 Таблица с BOM данными:
  - Component name
  - Quantity
  - Weight
  - Cost
  - Material

- [ ] 3.3.2 Кнопки:
  - Export as CSV
  - Export as JSON
  - Export as PDF

- [ ] 3.3.3 Фильтрация и сортировка
- [ ] 3.3.4 Responsive design

**Verification:**
```bash
npm run typecheck   # 0 errors
npm run lint        # 0 errors
```

---

### Task 3.4: Создать HierarchyTree React компонент
**Зависит от:** 1.3, 3.2  
**Deliverables:** components/HierarchyTree.tsx (300+ строк)

- [ ] 3.4.1 Tree view структура:
  - Expandable nodes
  - Icon для типа компонента
  - Selection (выбор компонента)

- [ ] 3.4.2 Функциональность:
  - Поиск по имени
  - Filter by type
  - Show/hide by properties

- [ ] 3.4.3 Integration с selection (выделение в 3D)

**Verification:**
```bash
npm run typecheck   # 0 errors
```

---

### Task 3.5: Написать 35+ unit тестов
**Зависит от:** 3.1, 3.2  
**Deliverables:** services/__tests__/BOM*.test.ts

- [ ] 3.5.1 BOM generation тесты (10)
  - Simple cabinet
  - Complex assembly
  - Edge cases

- [ ] 3.5.2 Cost calculation тесты (10)
  - Material prices
  - Aggregation
  - Discounts (опционально)

- [ ] 3.5.3 Weight calculation тесты (8)
  - Density calculations
  - Aggregation

- [ ] 3.5.4 Hierarchy тесты (7)
  - Path finding
  - Component lookup
  - Parent-child relationships

**Verification:**
```bash
npm run test -- --coverage  # > 35 tests
```

---

### Task 3.6: Update App.tsx for CAD_BOM view
**Зависит от:** 3.3, 3.4  
**Deliverables:** Functional CAD_BOM view

- [ ] 3.6.1 Создать BOMPanel компонент
- [ ] 3.6.2 Интегрировать BOMViewer и HierarchyTree
- [ ] 3.6.3 Добавить в App.tsx switch case

---

### Task 3.7: Documentation
**Зависит от:** 3.1-3.6  
**Deliverables:** docs/PHASE3_BOM.md

- [ ] 3.7.1 API reference для BOM services
- [ ] 3.7.2 User guide для UI компонентов
- [ ] 3.7.3 Export format specifications

---

## ФАЗА 4: DFM VALIDATOR (2 недели)
**Ответственный:** 1 разработчик  
**Часов:** 120  
**Зависит от:** Фаза 1

### Task 4.1: Реализовать DFMValidator service
**Зависит от:** 1.1  
**Deliverables:** services/DFMValidator.ts (500+ строк)

- [ ] 4.1.1 Класс DFMValidator с методами:
  ```typescript
  validate(assembly: Assembly): DFMReport
  getManufacturabilityScore(assembly: Assembly): number
  addRule(rule: DFMRule): void
  removeRule(ruleId: string): void
  ```

- [ ] 4.1.2 Реализовать 15 встроенных правил:
  1. Min thickness (4 мм)
  2. Max thickness (25 мм)
  3. Aspect ratio (80:1)
  4. Corner radius (>= 1 мм)
  5. Edge distance (>= 5 мм)
  6. Hole size (>= 3 мм)
  7. Wall thickness (>= 1.5 мм)
  8. Assembly gap (>= 0.5 мм)
  9. Pocket depth ratio
  10. Draft angle
  11. Threading constraints
  12. Fastener spacing
  13. Material compatibility
  14. Surface finish requirements
  15. Cost optimization suggestions

- [ ] 4.1.3 Каждое правило имеет:
  - Проверка (validation)
  - Severity (error, warning, info)
  - Fix suggestion

**Verification:**
```bash
npm run test -- DFMValidator.test.ts  # 40+ tests
```

---

### Task 4.2: Создать DFMReport React компонент
**Зависит от:** 1.3, 4.1  
**Deliverables:** components/DFMReport.tsx (300+ строк)

- [ ] 4.2.1 Отчёт с:
  - Manufacturability score (0-100%)
  - Список нарушений с severity
  - Рекомендации по исправлению

- [ ] 4.2.2 Интерактивные элементы:
  - Filter by severity
  - Filter by rule type
  - Show affected components (подсвечивание в 3D)

- [ ] 4.2.3 Экспорт отчёта (PDF, JSON)

**Verification:**
```bash
npm run typecheck   # 0 errors
```

---

### Task 4.3: Написать 40+ unit тестов
**Зависит от:** 4.1  
**Deliverables:** services/__tests__/DFMValidator.test.ts

- [ ] 4.3.1 Тесты для каждого правила (15 тестов)
- [ ] 4.3.2 Score calculation тесты (10)
- [ ] 4.3.3 Custom rule support (5)
- [ ] 4.3.4 Edge cases (10)

**Verification:**
```bash
npm run test -- DFMValidator.test.ts --coverage  # > 40 tests
```

---

### Task 4.4: Update App.tsx for CAD_DFM view
**Зависит от:** 4.2  
**Deliverables:** Functional CAD_DFM view

- [ ] 4.4.1 Создать DFMValidatorPanel компонент
- [ ] 4.4.2 Интегрировать DFMReport
- [ ] 4.4.3 Добавить в App.tsx

---

### Task 4.5: Documentation
**Зависит от:** 4.1-4.4  
**Deliverables:** docs/PHASE4_DFM.md

- [ ] 4.5.1 DFM Rules reference (все 15 правил)
- [ ] 4.5.2 API reference
- [ ] 4.5.3 User guide

---

## ФАЗА 5: OPTIMIZATION (3 недели)
**Ответственный:** 2-3 разработчика  
**Часов:** 240  
**Зависит от:** Фаза 1, 4

### Task 5.1: Реализовать CabinetOptimizer service
**Зависит от:** 1.1  
**Deliverables:** services/CabinetOptimizer.ts (400+ строк)

- [ ] 5.1.1 Класс CabinetOptimizer с методами:
  ```typescript
  optimize(assembly: Assembly, strategy: OptimizationStrategy): Promise<OptimizationResult>
  ```

- [ ] 5.1.2 Реализовать Genetic Algorithm:
  - Population creation (100 особей)
  - Fitness evaluation (по стратегии)
  - Selection (tournament, 50%)
  - Crossover (uniform, 90%)
  - Mutation (gaussian, 5%)
  - Convergence (100 поколений или score улучшение < 0.1%)

- [ ] 5.1.3 Четыре встроенные стратегии:
  1. **Minimize Cost** (целевая экономия 10-20%)
  2. **Minimize Weight** (целевая экономия 5-15%)
  3. **Maximize Strength** (CoS >= 2.0)
  4. **Balance** (компромисс: cost -10%, strength +10%)

- [ ] 5.1.4 Переменные оптимизации:
  - Material (для каждого компонента)
  - Thickness (в пределах min-max)
  - Geometry (ширина, высота в пределах constraints)

**Code Structure:**
```typescript
export class CabinetOptimizer {
  private dfmValidator: DFMValidator;
  private feaIntegration: FEAIntegration;
  
  constructor() { ... }
  
  async optimize(assembly: Assembly, strategy: OptimizationStrategy): Promise<OptimizationResult> {
    // Genetic algorithm implementation
  }
  
  private evaluateFitness(candidate: Assembly, strategy: OptimizationStrategy): number { ... }
  private createMutation(assembly: Assembly): Assembly { ... }
}
```

**Verification:**
```bash
npm run test -- CabinetOptimizer.test.ts  # 50+ tests
npm run benchmark -- optimizer             # Results within budget
```

---

### Task 5.2: Написать 50+ unit тестов
**Зависит от:** 5.1  
**Deliverables:** services/__tests__/CabinetOptimizer.test.ts

- [ ] 5.2.1 Genetic algorithm тесты (15)
  - Population generation
  - Fitness evaluation
  - Selection
  - Crossover
  - Mutation

- [ ] 5.2.2 Strategy тесты (20)
  - Cost minimization (10-20% savings)
  - Weight minimization
  - Strength maximization
  - Balance strategy

- [ ] 5.2.3 Convergence тесты (10)
  - Convergence within generations
  - Fitness improvement
  - Stability of results

- [ ] 5.2.4 Performance тесты (5)
  - Runtime
  - Memory usage
  - Population size scaling

**Verification:**
```bash
npm run test -- CabinetOptimizer.test.ts --coverage  # > 50 tests
```

---

### Task 5.3: Создать OptimizationResults React компонент
**Зависит от:** 1.3, 5.1  
**Deliverables:** components/OptimizationResults.tsx (350+ строк)

- [ ] 5.3.1 Отчёт с результатами:
  - Original vs Optimized (параллельное сравнение)
  - Cost comparison ($, %)
  - Weight comparison (kg, %)
  - Strength improvement (CoS before/after)
  - Convergence graph (по поколениям)

- [ ] 5.3.2 Интерактивные элементы:
  - Accept optimized version (кнопка)
  - View generation history
  - Adjust strategy parameters
  - Re-run optimization

- [ ] 5.3.3 Экспорт результатов (PDF, JSON, CSV)

**Verification:**
```bash
npm run typecheck   # 0 errors
```

---

### Task 5.4: Update App.tsx for CAD_OPTIMIZATION view
**Зависит от:** 5.3  
**Deliverables:** Functional CAD_OPTIMIZATION view

- [ ] 5.4.1 Создать OptimizationPanel компонент
- [ ] 5.4.2 Strategy selector (dropdown)
- [ ] 5.4.3 Progress indicator (поколения, fitness)
- [ ] 5.4.4 Интегрировать в App.tsx

---

### Task 5.5: Documentation
**Зависит от:** 5.1-5.4  
**Deliverables:** docs/PHASE5_OPTIMIZATION.md

- [ ] 5.5.1 Genetic Algorithm explanation
- [ ] 5.5.2 Strategy descriptions (когда использовать)
- [ ] 5.5.3 Parameter tuning guide
- [ ] 5.5.4 Performance optimization tips

---

## ФАЗА 6: CAD EXPORT/IMPORT (2 недели)
**Ответственный:** 2 разработчика  
**Часов:** 175  
**Зависит от:** Фаза 1

### Task 6.1: Реализовать CADExporter service
**Зависит от:** 1.1  
**Deliverables:** services/CADExporter.ts (350+ строк)

- [ ] 6.1.1 Класс CADExporter с методами:
  ```typescript
  export(assembly: Assembly, format: 'stl'|'dxf'|'step'|'json', config?: ExportConfig): Promise<Blob>
  ```

- [ ] 6.1.2 STL экспорт:
  - Vertices, faces extraction
  - Binary STL format
  - Color preservation (если есть)
  - Performance: < 2 сек для среднего кабинета

- [ ] 6.1.3 DXF экспорт:
  - 2D projections (top, front, side)
  - Dimensions and annotations
  - Material callouts
  - Line styles

- [ ] 6.1.4 STEP экспорт (ISO 10303-21):
  - Full 3D geometry
  - Material definitions
  - Assembly relationships
  - Metadata (creator, date, etc.)

- [ ] 6.1.5 JSON экспорт:
  - Complete assembly structure
  - All components with properties
  - Constraints preserved
  - Material assignments

**Code Structure:**
```typescript
export class CADExporter {
  constructor(private dfmValidator?: DFMValidator) { }
  
  async export(assembly: Assembly, format: string, config?: ExportConfig): Promise<Blob> {
    switch(format) {
      case 'stl': return this.exportSTL(assembly, config);
      case 'dxf': return this.exportDXF(assembly, config);
      case 'step': return this.exportSTEP(assembly, config);
      case 'json': return this.exportJSON(assembly, config);
    }
  }
}
```

**Verification:**
```bash
npm run test -- CADExporter.test.ts  # 30+ tests
npm run benchmark -- exporter        # Performance < 2s
```

---

### Task 6.2: Реализовать CADImporter service
**Зависит от:** 1.1  
**Deliverables:** services/CADImporter.ts (250+ строк)

- [ ] 6.2.1 Класс CADImporter с методами:
  ```typescript
  import(file: File, format: 'json'|'stl'|'step'): Promise<Assembly>
  ```

- [ ] 6.2.2 JSON импорт:
  - Parse structure
  - Validate against schema
  - Reconstruct Assembly

- [ ] 6.2.3 STL импорт:
  - Parse binary/ASCII STL
  - Create single Component
  - Infer bounding box

- [ ] 6.2.4 STEP импорт:
  - Parse STEP file (xml2js)
  - Extract geometries
  - Reconstruct assembly tree
  - Map materials and properties

**Verification:**
```bash
npm run test -- CADImporter.test.ts  # 20+ tests
```

---

### Task 6.3: Написать 30+ unit тестов
**Зависит от:** 6.1, 6.2  
**Deliverables:** services/__tests__/CADExporter.test.ts, CADImporter.test.ts

- [ ] 6.3.1 Export тесты (15)
  - STL export (5)
  - DXF export (5)
  - JSON export (5)

- [ ] 6.3.2 Import тесты (10)
  - JSON import (5)
  - STL import (3)
  - Error handling (2)

- [ ] 6.3.3 Round-trip тесты (5)
  - Export → Import → compare

**Verification:**
```bash
npm run test -- CAD*porter.test.ts --coverage  # > 30 tests
```

---

### Task 6.4: Create Export/Import UI
**Зависит от:** 6.1, 6.2  
**Deliverables:** ExportPanel/ImportPanel components

- [ ] 6.4.1 ExportPanel компонент:
  - Format selector (dropdown)
  - Export options (checkboxes)
  - "Export" button
  - Progress indicator

- [ ] 6.4.2 ImportPanel компонент:
  - File upload
  - Format auto-detection
  - "Import" button
  - Validation results

- [ ] 6.4.3 Интегрировать в App.tsx (CAD_EXPORT view)

**Verification:**
```bash
npm run typecheck   # 0 errors
```

---

### Task 6.5: Documentation
**Зависит от:** 6.1-6.4  
**Deliverables:** docs/PHASE6_EXPORT.md

- [ ] 6.5.1 Format specifications (STL, DXF, STEP, JSON)
- [ ] 6.5.2 API reference for Exporter/Importer
- [ ] 6.5.3 User guide for Export/Import UI
- [ ] 6.5.4 Compatibility notes (software, versions)

---

## ФАЗА 7: FEA INTEGRATION (3 недели)
**Ответственный:** 2-3 разработчика  
**Часов:** 350  
**Зависит от:** Фаза 1, 2

### Task 7.1: Mesh Generation
**Зависит от:** 1.1  
**Deliverables:** services/FEAIntegration.ts (1000+ строк, часть 1)

- [ ] 7.1.1 Функции для mesh generation:
  ```typescript
  generateMesh(assembly: Assembly, options?: MeshOptions): Mesh
  ```

- [ ] 7.1.2 Tetrahedral mesh generation:
  - 3D boundary extraction
  - Mesh refinement (adaptive)
  - Quality metrics (aspect ratio < 100)
  - Performance: < 1 sec для 1000 узлов

- [ ] 7.1.3 Material assignment:
  - Каждому элементу присвоить материал
  - Свойства (E, ν, ρ) из Material definitions

- [ ] 7.1.4 Boundary conditions:
  - Constraints extraction
  - Applied loads from user input

**Code Structure:**
```typescript
export class FEAIntegration {
  private meshGenerator: TetrahedralMeshGenerator;
  
  generateMesh(assembly: Assembly, options?: MeshOptions): Mesh {
    // Mesh generation algorithm
  }
  
  private extractBoundaries(assembly: Assembly): Boundary[] { ... }
  private refineMesh(mesh: Mesh, options: MeshOptions): Mesh { ... }
}
```

**Verification:**
```bash
npm run test -- FEAIntegration.test.ts  # Mesh generation tests
```

---

### Task 7.2: Static Analysis Solver
**Зависит от:** 7.1  
**Deliverables:** services/FEAIntegration.ts (часть 2)

- [ ] 7.2.1 Static analysis реализация:
  ```typescript
  performStaticAnalysis(assembly: Assembly, loads: Load[]): Promise<StaticAnalysisResult>
  ```

- [ ] 7.2.2 FEA solver использует:
  - K (stiffness matrix) assembly
  - Gaussian elimination (или iterative solver)
  - Von Mises stress calculation
  - Displacement calculation
  - Reaction forces

- [ ] 7.2.3 Performance:
  - < 5 сек на 1000 узлов
  - Использовать Web Workers для параллелизма
  - Sparse matrix optimization

- [ ] 7.2.4 Output:
  - Stress field (per node)
  - Displacement field (per node)
  - Coefficient of Safety (CoS = yield strength / max stress)
  - Critical areas (high stress zones)

**Verification:**
```bash
npm run benchmark -- fea  # < 5s on 1000 nodes
```

---

### Task 7.3: Modal Analysis
**Зависит от:** 7.1  
**Deliverables:** services/FEAIntegration.ts (часть 3)

- [ ] 7.3.1 Modal analysis реализация:
  ```typescript
  performModalAnalysis(assembly: Assembly, numModes?: number): Promise<ModalAnalysisResult>
  ```

- [ ] 7.3.2 Eigenvalue problem solver:
  - K·φ = λ·M·φ (generalized eigenvalue problem)
  - Lanczos algorithm (или QR)
  - Extract first N modes (default 5)
  - Frequencies (Hz) calculation

- [ ] 7.3.3 Mode shapes:
  - Displacement patterns для каждого mode
  - Damping ratio estimation
  - MAC (Modal Assurance Criterion)

- [ ] 7.3.4 Performance:
  - < 10 сек на 1000 узлов для 5 modes
  - Используя Web Workers

**Verification:**
```bash
npm run test -- FEAIntegration.test.ts  # Modal analysis tests
```

---

### Task 7.4: Web Worker for FEA
**Зависит от:** 7.2, 7.3  
**Deliverables:** workers/fea.worker.js

- [ ] 7.4.1 Создать Web Worker для FEA вычислений
- [ ] 7.4.2 Параллелизм:
  - Main thread: UI, user input
  - Worker thread: FEA solver, matrix operations
  - Post messages для progress updates
  - Transfer arrays (большие данные)

- [ ] 7.4.3 Progress reporting:
  - Assembly generation: 10%
  - Mesh generation: 20%
  - Stiffness matrix assembly: 30%
  - Solver iteration 1-10: 40%
  - Stress calculation: 20%
  - Complete: 100%

**Verification:**
```bash
npm run build  # Web Worker bundled correctly
```

---

### Task 7.5: Create FEAPanel React component
**Зависит от:** 7.1-7.4  
**Deliverables:** components/FEAPanel.tsx (500+ строк)

- [ ] 7.5.1 UI элементы:
  - Load definition (force, direction, magnitude)
  - Constraint selection (fixed edges)
  - Material properties selector

- [ ] 7.5.2 Analysis controls:
  - "Run Static Analysis" button
  - "Run Modal Analysis" button
  - Analysis type selector

- [ ] 7.5.3 Results visualization:
  - Stress map (color gradient: blue → red)
  - Displacement field (vector arrows)
  - Deformed shape (side by side с original)
  - CoS indicator (safe/warning/critical)

- [ ] 7.5.4 Results table:
  - Max stress (MPa)
  - Max displacement (mm)
  - Min CoS
  - Critical element ID
  - Frequencies (Hz) для modal

- [ ] 7.5.5 Export:
  - Results as JSON
  - Report as PDF
  - Visualization as PNG

**Verification:**
```bash
npm run typecheck   # 0 errors
```

---

### Task 7.6: Написать 40+ unit тестов
**Зависит от:** 7.1-7.5  
**Deliverables:** services/__tests__/FEAIntegration.test.ts

- [ ] 7.6.1 Mesh generation тесты (10)
  - Simple geometry
  - Complex assembly
  - Mesh quality

- [ ] 7.6.2 Static analysis тесты (15)
  - Simple cantilever beam (known solution)
  - Plate with hole
  - Complex assembly
  - Stress calculation
  - CoS calculation

- [ ] 7.6.3 Modal analysis тесты (10)
  - Frequencies calculation
  - Mode shapes
  - Comparison с analytical solutions

- [ ] 7.6.4 Performance тесты (5)
  - 1000 nodes: < 5 sec
  - Memory usage
  - Web Worker communication

**Verification:**
```bash
npm run test -- FEAIntegration.test.ts --coverage  # > 40 tests
```

---

### Task 7.7: Update App.tsx for CAD_FEA view
**Зависит от:** 7.5  
**Deliverables:** Functional CAD_FEA view

- [ ] 7.7.1 Интегрировать FEAPanel в App.tsx
- [ ] 7.7.2 Add CAD_FEA view mode
- [ ] 7.7.3 Add to menu

---

### Task 7.8: Documentation
**Зависит от:** 7.1-7.7  
**Deliverables:** docs/PHASE7_FEA.md

- [ ] 7.8.1 FEA theory (mesh, stiffness, solvers)
- [ ] 7.8.2 API reference
- [ ] 7.8.3 User guide for FEA Panel
- [ ] 7.8.4 Validation report (comparison с known solutions)

---

## ФАЗА 8: TESTING & QA (2 недели)
**Ответственный:** 2-3 разработчика  
**Часов:** 200  
**Зависит от:** Все предыдущие фазы

### Task 8.1: Написать 150+ E2E тестов
**Зависит от:** Все фазы  
**Deliverables:** services/__tests__/IntegrationTests.test.ts (1000+ строк)

- [ ] 8.1.1 Full workflow E2E тесты (30)
  - Create cabinet → Solve → BOM → DFM → FEA
  - Create cabinet → Optimize → Export
  - Import STL → DFM check → FEA
  - Create assembly → All 8 operations

- [ ] 8.1.2 Cross-phase тесты (50)
  - Solver → BOM (constraints affect cost)
  - DFM → Optimizer (rules as constraints)
  - Optimizer → Export (check result quality)
  - FEA → DFM (strength feedback)

- [ ] 8.1.3 User journey тесты (40)
  - Designer: Design → DFM → Optimize → FEA
  - Manufacturer: Design → BOM → DFM → Export
  - Engineer: FEA → Optimize → Cost analysis

- [ ] 8.1.4 Edge case тесты (30)
  - Large assemblies (100+ components)
  - Invalid inputs
  - Non-convergence scenarios
  - File corruption handling

**Verification:**
```bash
npm run test -- IntegrationTests.test.ts  # > 150 tests
```

---

### Task 8.2: Performance Benchmarks & Profiling
**Зависит от:** 7.1-7.7  
**Deliverables:** Performance benchmark report

- [ ] 8.2.1 Benchmark каждой операции:
  - Solver: 50 компонентов → < 500 ms
  - BOM: 1000 items → < 100 ms
  - DFM: Check 15 rules → < 200 ms
  - Optimizer: 100 generations → < 60 sec
  - Export STL: < 2 sec
  - Export STEP: < 3 sec
  - FEA: 1000 nodes → < 5 sec
  - Import JSON: < 1 sec

- [ ] 8.2.2 Memory profiling:
  - Peak memory per operation
  - Memory leaks (detect via heap snapshots)
  - GC pauses

- [ ] 8.2.3 Документировать результаты:
  ```markdown
  ## Performance Report (18 January 2026)
  
  | Operation | Target | Achieved | Status |
  |-----------|--------|----------|--------|
  | Solver | <500ms | 450ms | ✅ |
  | FEA | <5s | 4.8s | ✅ |
  | ...
  ```

**Verification:**
```bash
npm run benchmark  # All operations meet targets
```

---

### Task 8.3: Code Coverage Analysis
**Зависит от:** Все фазы  
**Deliverables:** Coverage report > 85%

- [ ] 8.3.1 Запустить test coverage:
  ```bash
  npm run test:coverage
  ```

- [ ] 8.3.2 Анализировать gaps:
  - Найти неприкрытый код
  - Написать тесты для gaps
  - Целевой coverage > 85%

- [ ] 8.3.3 Генерировать HTML report:
  - coverage/index.html
  - Проверить per-file coverage

**Verification:**
```bash
npm run test:coverage  # > 85% coverage
```

---

### Task 8.4: API Documentation (JSDoc)
**Зависит от:** Все фазы  
**Deliverables:** Complete JSDoc coverage

- [ ] 8.4.1 Проверить JSDoc для всех публичных API:
  - Description
  - Parameters (@param)
  - Return type (@returns)
  - Exceptions (@throws)
  - Examples (@example)

- [ ] 8.4.2 Генерировать TypeDoc:
  ```bash
  npm run typedoc  # Generates docs/
  ```

- [ ] 8.4.3 Проверить:
  ```bash
  npm run typecheck  # 0 errors
  npx tsc --noEmit   # Full type checking
  ```

**Verification:**
```bash
# All public functions have JSDoc
grep -r "@param" services/ | wc -l  # > 100 @param blocks
```

---

### Task 8.5: Security & Error Handling Review
**Зависит от:** Все фазы  
**Deliverables:** Security audit report

- [ ] 8.5.1 Проверить:
  - Input validation (все inputs проверены)
  - No secrets in code (API keys, passwords)
  - XSS prevention (React escaping)
  - SQL injection (N/A for this app)
  - Error messages (no sensitive info leak)

- [ ] 8.5.2 Error handling:
  - Graceful degradation
  - User-friendly error messages
  - Logging (все ошибки логируются)
  - Recovery mechanisms (undo, reset)

**Verification:**
```bash
npm run audit        # No vulnerabilities
npm run lint         # Security warnings
```

---

### Task 8.6: Production Checklist
**Зависит от:** 8.1-8.5  
**Deliverables:** Production readiness checklist

- [ ] 8.6.1 Code quality:
  - [ ] 0 lint errors
  - [ ] 0 type errors (strict mode)
  - [ ] > 85% test coverage
  - [ ] No console.log in production code
  - [ ] No commented-out code

- [ ] 8.6.2 Performance:
  - [ ] All benchmarks met
  - [ ] No memory leaks
  - [ ] No N+1 queries (N/A)
  - [ ] Web Workers for long-running operations
  - [ ] Lazy loading where applicable

- [ ] 8.6.3 Documentation:
  - [ ] API docs complete
  - [ ] User guides complete
  - [ ] Deployment instructions
  - [ ] Known limitations documented

- [ ] 8.6.4 Deployment:
  - [ ] Environment variables configured
  - [ ] Build process working
  - [ ] No build warnings
  - [ ] Assets optimized
  - [ ] Source maps included for debugging

- [ ] 8.6.5 Monitoring:
  - [ ] Error logging configured
  - [ ] Performance monitoring
  - [ ] User analytics (optional)
  - [ ] Health checks

**Verification:**
```bash
# Pre-deployment checks
npm run lint
npm run typecheck
npm run test:coverage  # > 85%
npm run build
npm run preview        # Test production build
```

---

### Task 8.7: Final Integration & Smoke Tests
**Зависит от:** 8.1-8.6  
**Deliverables:** Smoke test suite

- [ ] 8.7.1 Quick smoke tests:
  - App loads
  - All views accessible
  - All buttons work
  - No console errors
  - Responsive design OK

- [ ] 8.7.2 Browser compatibility:
  - Chrome latest
  - Firefox latest
  - Safari latest
  - Edge latest

- [ ] 8.7.3 Device compatibility:
  - Desktop (1920x1080, 2560x1440)
  - Tablet (iPad)
  - Mobile (iPhone, Android)

**Verification:**
```bash
npm run preview  # Manual smoke test
```

---

### Task 8.8: Release & Documentation
**Зависит от:** 8.1-8.7  
**Deliverables:** Release notes & documentation

- [ ] 8.8.1 Release notes:
  - Features added (Phases 1-8)
  - Bug fixes
  - Performance improvements
  - Breaking changes (если есть)
  - Migration guide (для v1.0)

- [ ] 8.8.2 Documentation:
  - README.md updated
  - CHANGELOG.md created
  - Installation guide
  - Quick start guide
  - API reference (TypeDoc)

- [ ] 8.8.3 Version bump:
  ```json
  {
    "version": "2.0.0",  // Major: CAD system added
    "description": "Professional CAD system for furniture design"
  }
  ```

- [ ] 8.8.4 Tag release:
  ```bash
  git tag -a v2.0.0 -m "Release 2.0.0: CAD System"
  git push origin v2.0.0
  ```

---

## FINAL VERIFICATION

### All Phases Complete Checklist
- [ ] Phase 1: Architecture ✅
- [ ] Phase 2: Solver ✅
- [ ] Phase 3: BOM ✅
- [ ] Phase 4: DFM ✅
- [ ] Phase 5: Optimization ✅
- [ ] Phase 6: Export/Import ✅
- [ ] Phase 7: FEA ✅
- [ ] Phase 8: Testing ✅

### Final Build & Test
```bash
npm install                  # Install all deps
npm run typecheck            # 0 errors
npm run lint                 # 0 errors
npm run test:coverage        # > 85% coverage
npm run build                # Production build
npm run preview              # Test prod build
git log --oneline | head -20 # Verify commits
```

### Success Criteria Met
- ✅ 58 tasks completed
- ✅ 300+ unit tests passing
- ✅ 150+ E2E tests passing
- ✅ 85%+ code coverage
- ✅ All performance budgets met
- ✅ All API documented
- ✅ Production ready
- ✅ Team trained & ready

### Deployment
```bash
# Deploy to staging
git push origin main
# → CI/CD pipeline runs
# → All tests pass
# → Deploy to staging

# After final approval:
# → Deploy to production
# → Monitor errors & performance
```

---

## TIMELINE ESTIMATE (18 weeks)

```
WEEK 1-2:   PHASE 1 Architecture        160 hrs  ✅ Deliverables clear
WEEK 3-4:   PHASE 2 Solver              180 hrs  ✅ Algorithm defined
WEEK 5-6:   PHASE 3 BOM                 125 hrs  ✅ API clear
WEEK 7-8:   PHASE 4 DFM                 120 hrs  ✅ 15 rules defined
WEEK 9-11:  PHASE 5 Optimization        240 hrs  ✅ GA algorithm defined
WEEK 12-13: PHASE 6 Export/Import       175 hrs  ✅ 4 formats specified
WEEK 14-16: PHASE 7 FEA                 350 hrs  ✅ Solvers specified
WEEK 17-18: PHASE 8 Testing & QA        200 hrs  ✅ Coverage targets set
            ─────────────────────────────────────
            TOTAL                      1550 hrs

TEAM: 2-3 developers
PACE: 40-45 hrs/week/dev
```

---

## READY FOR IMPLEMENTATION

**All 58 tasks are defined with:**
- ✅ Clear dependencies
- ✅ Concrete deliverables
- ✅ Verification steps
- ✅ Code examples
- ✅ Test specifications
- ✅ Performance targets
- ✅ Documentation requirements

**Next step:** Start Phase 1, Task 1.1 ✅
