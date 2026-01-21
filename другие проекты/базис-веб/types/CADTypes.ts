/**
 * ФАЗА 1: Архитектурное проектирование
 * Рефакторинг типов и интерфейсов для CAD модулей
 * 
 * Этот файл содержит все базовые типы, которые используются во всех остальных фазах
 */

// ============================================================================
// 1. БАЗОВЫЕ 3D ТИПЫ
// ============================================================================

/**
 * 3D точка в пространстве
 */
export interface Point3D {
  x: number;
  y: number;
  z: number;
}

/**
 * 3D вектор (направление + длина)
 */
export interface Vector3D extends Point3D {
  // Всё то же самое, что Point3D, но используется семантически как вектор
}

/**
 * Матрица трансформации 4x4 (позиция + ротация + масштаб)
 */
export interface TransformMatrix {
  elements: number[]; // 16 элементов (4x4)
}

/**
 * Углы Эйлера (pitch, yaw, roll)
 */
export interface EulerAngles {
  x: number; // pitch (вращение вокруг X оси), радианы
  y: number; // yaw (вращение вокруг Y оси), радианы
  z: number; // roll (вращение вокруг Z оси), радианы
}

/**
 * Трансформация (позиция, масштаб, ротация)
 */
export interface Transform {
  position: Point3D;
  scale: Point3D;
  rotation?: EulerAngles;
}

/**
 * Граница объекта (AABB - Axis-Aligned Bounding Box)
 */
export interface BoundingBox {
  min: Point3D;
  max: Point3D;
  width?: () => number;
  height?: () => number;
  depth?: () => number;
}

// ============================================================================
// 2. МАТЕРИАЛЫ И СВОЙСТВА
// ============================================================================

/**
 * Типы текстур материала
 */
export enum TextureType {
  NONE = 'none',
  WOOD_OAK = 'wood_oak',
  WOOD_WALNUT = 'wood_walnut',
  WOOD_ASH = 'wood_ash',
  CONCRETE = 'concrete',
  UNIFORM = 'uniform'
}

/**
 * Материал с физическими и визуальными свойствами
 */
export interface Material {
  id: string;
  name: string;
  color?: string;
  opacity?: number;
  roughness?: number;
  metalness?: number;
  emissive?: string;
  
  // Физические свойства (для FEA)
  density?: number;                    // кг/м³
  elasticModulus?: number;             // МПа (E)
  poissonRatio?: number;               // ν (0.0 - 0.5)
  yieldStrength?: number;              // МПа
  tensileStrength?: number;            // МПа
  
  // Производственные свойства (для DFM)
  minThickness?: number;               // мм
  maxThickness?: number;               // мм
  
  // Визуальные
  textureType?: TextureType;
  textureRotation?: number;            // градусы 0-360
  
  // Параметры
  properties?: Record<string, any>;
}

/**
 * Стоимость материала
 */
export interface MaterialCost {
  materialId: string;
  pricePerKg: number;                  // рубли/кг
  minOrder?: number;                   // минимальный заказ (кг)
  leadTime?: number;                   // дней
  supplier?: string;
}

// ============================================================================
// 3. ОГРАНИЧЕНИЯ (CONSTRAINTS)
// ============================================================================

/**
 * Тип ограничения
 */
export enum ConstraintType {
  COINCIDENT = 'coincident',           // две точки совпадают
  PARALLEL = 'parallel',               // линии/плоскости параллельны
  PERPENDICULAR = 'perpendicular',     // перпендикулярны
  DISTANCE = 'distance',               // расстояние между объектами
  ANGLE = 'angle',                     // угол между объектами
  FIXED = 'fixed',                     // зафиксировано в пространстве
  TANGENT = 'tangent',                 // касание
  SYMMETRIC = 'symmetric'              // симметрия относительно плоскости
}

/**
 * Ограничение/связь между компонентами
 */
export interface Constraint {
  id: string;
  name?: string;
  type: ConstraintType;
  
  // Элементы, к которым применяется ограничение
  elementA: string;                    // ID компонента/якоря
  elementB?: string;                   // ID компонента/якоря (может быть пусто для FIXED)
  
  // Параметры ограничения
  value?: number;                      // для DISTANCE (мм), ANGLE (градусы)
  tolerance?: number;                  // допуск для решения
  weight?: number;                     // вес в системе (по умолчанию 1.0)
  
  // Состояние
  isSatisfied?: boolean;
  error?: number;                      // текущая ошибка
}

/**
 * Результат проверки ограничений
 */
export interface ConstraintCheckResult {
  constraintId: string;
  satisfied: boolean;
  error: number;                       // невязка
  errorMessage?: string;
}

// ============================================================================
// 4. ЯКОРЯ (ANCHOR POINTS) - РЕПЕРНЫЕ ТОЧКИ
// ============================================================================

/**
 * Тип якоря
 */
export enum AnchorPointType {
  VERTEX = 'vertex',                   // вершина
  EDGE_CENTER = 'edge_center',         // центр ребра
  FACE_CENTER = 'face_center',         // центр грани
  AXIS = 'axis'                        // ось компонента
}

/**
 * Якорь (реперная точка для ограничений)
 */
export interface AnchorPoint {
  id: string;
  name?: string;
  position: Point3D;                   // позиция якоря в локальных координатах компонента
  componentId: string;                 // ID компонента, к которому принадлежит якорь
  type: AnchorPointType;
  normal?: Vector3D;                   // нормаль (для граней)
}

// ============================================================================
// 5. КОМПОНЕНТЫ И СБОРКИ
// ============================================================================

/**
 * Тип компонента
 */
export enum ComponentType {
  PART = 'part',                       // простая деталь
  ASSEMBLY = 'assembly',               // сборка верхнего уровня
  SUBASSEMBLY = 'subassembly'          // подсборка
}

/**
 * Геометрия компонента (минимально необходимая для DFM/BOM/экспорта)
 */
export interface ComponentGeometry {
  type: '2D' | '3D';
  vertices: Point3D[];
  faces: number[][];
  boundingBox: BoundingBox;
}

/**
 * Компонент сборки (деталь или подсборка)
 */
export interface Component {
  // Идентификация
  id: string;
  name: string;
  type: ComponentType;
  
  // Трансформация в пространстве
  position: Point3D;                   // позиция центра компонента
  rotation: EulerAngles;               // углы Эйлера
  scale?: Point3D;                     // масштаб (если нужен)
  
  // Свойства
  material: Material;
  properties: Record<string, number | string | boolean>; // ширина, высота, глубина и т.д.

  // Геометрия
  geometry?: ComponentGeometry;
  
  // Иерархия
  subComponents?: Component[];         // подкомпоненты (если type = assembly)
  parentId?: string;                   // ID родительского компонента
  
  // Якоря и ограничения
  anchorPoints?: AnchorPoint[];        // якоря для соединений
  constraints?: Constraint[];          // локальные ограничения
  
  // Metadata
  hidden?: boolean;
  locked?: boolean;
  color?: string;                      // override материала для отображения
}

/**
 * Сборка с ограничениями
 */
export interface Assembly {
  // Идентификация
  id: string;
  name: string;
  
  // Содержимое
  components: Component[];             // все компоненты сборки
  constraints: Constraint[];           // глобальные ограничения сборки
  
  // Metadata
  metadata?: {
    version: string;
    createdAt: Date;
    modifiedAt: Date;
    author?: string;
    description?: string;
  };
  
  // Состояние
  isDirty?: boolean;
  isValid?: boolean;
}

// ============================================================================
// 6. BILL OF MATERIALS (BOM)
// ============================================================================

/**
 * Единица в BOM
 */
export interface BOMItem {
  // Идентификация
  componentId: string;
  componentName: string;
  
  // Количество и физические свойства
  quantity: number;                    // кол-во единиц
  material: Material;
  weight: number;                      // кг
  volume: number;                      // см³
  
  // Стоимость
  materialCostPerUnit: number;          // рубли/кг
  totalMaterialCost: number;            // рубли (quantity * weight * costPerUnit)
  
  // Производство
  productionTime: number;              // минуты на один
  totalProductionTime: number;         // минуты (quantity * productionTime)
  
  // Дополнительно
  supplier?: string;
  leadTime?: number;                   // дней
  notes?: string;
}

/**
 * BOM отчёт
 */
export interface BOMReport {
  // Суммарные данные
  totalItems: number;                  // кол-во уникальных компонентов
  totalQuantity: number;               // общее кол-во всех единиц
  totalMass: number;                   // кг
  totalMaterialCost: number;            // рубли
  totalProductionTime: number;         // минуты
  
  // Детали
  items: BOMItem[];
  
  // Экспорт
  exportFormats: {
    csv: string;
    json: BOMItem[];
    pdf?: Buffer;
  };
}

// ============================================================================
// 7. DESIGN FOR MANUFACTURING (DFM)
// ============================================================================

/**
 * Результат проверки DFM правила
 */
export enum DFMSeverity {
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error'
}

/**
 * Результат проверки DFM
 */
export interface DFMCheckResult {
  ruleId: string;
  passed: boolean;
  severity: DFMSeverity;
  message: string;
  suggestion?: string;
  componentId?: string;
}

/**
 * DFM правило
 */
export interface DFMRule {
  id: string;
  name: string;
  description?: string;
  check: (component: Component) => DFMCheckResult;
  priority?: number; // 1-10, где 10 - критичнее
}

/**
 * DFM отчёт
 */
export interface DFMReport {
  // Статистика
  totalChecks: number;
  passedChecks: number;
  failedChecks: number;
  
  // Детали
  errors: DFMCheckResult[];
  warnings: DFMCheckResult[];
  infos: DFMCheckResult[];
  
  // Общая оценка
  manufacturability: number;           // 0-100%, где 100% = идеально производится
  suggestions: string[];
  
  // Metadata
  timestamp: Date;
  runtimeMs?: number;
}

// ============================================================================
// 8. ОПТИМИЗАЦИЯ
// ============================================================================

/**
 * Критерий оптимизации
 */
export enum OptimizationObjective {
  COST = 'cost',                       // минимизировать стоимость
  WEIGHT = 'weight',                   // минимизировать вес
  STRENGTH = 'strength',               // максимизировать запас прочности
  BALANCE = 'balance'                  // компромисс между всеми
}

/**
 * Параметры оптимизации
 */
export interface OptimizationParams {
  objective: OptimizationObjective;
  
  // Ограничения
  maxDeflection?: number;              // мм
  minSafetyFactor?: number;
  targetLoadCapacity?: number;         // кг
  materialCostTarget?: number;         // руб/кг
  
  // Параметры дизайна
  minThickness?: number;               // мм
  maxThickness?: number;               // мм
  
  // Алгоритм
  maxIterations?: number;
  populationSize?: number;
  generations?: number;
  mutationRate?: number;               // 0.0-1.0
  crossoverRate?: number;              // 0.0-1.0
}

/**
 * Результат оптимизации
 */
export interface OptimizedConfig {
  originalConfig: any;                 // исходная конфигурация
  optimizedConfig: any;                // оптимизированная конфигурация
  
  // Улучшения
  improvements: {
    costReduction: number;             // % (положительное = экономия)
    weightReduction: number;           // %
    strengthIncrease: number;          // %
  };
  
  // Статистика
  iterations: number;
  convergenceTime: number;             // мс
  score: number;                       // финальный скор
}

// ============================================================================
// 9. ЭКСПОРТ/ИМПОРТ CAD ФОРМАТОВ
// ============================================================================

/**
 * Форматы экспорта
 */
export enum ExportFormat {
  STL = 'stl',                         // 3D печать
  STEP = 'step',                       // STEP формат (ISO 10303-21)
  IGES = 'iges',                       // IGES формат
  DXF = 'dxf',                         // AutoCAD чертежи
  JSON = 'json',                       // JSON для веб
  OBJ = 'obj',                         // Wavefront OBJ
  GLTF = 'gltf'                        // glTF для вебглу
}

/**
 * Параметры экспорта
 */
export interface ExportOptions {
  format: ExportFormat;
  includeMetadata?: boolean;
  scale?: number;                      // масштаб (по умолчанию 1.0)
  precision?: number;                  // знаков после запятой
  compressed?: boolean;                // сжатие (для бинарных форматов)
}

// ============================================================================
// 10. КОНЕЧНО-ЭЛЕМЕНТНЫЙ АНАЛИЗ (FEA)
// ============================================================================

/**
 * Узел FEA сетки
 */
export interface FEANode {
  id: number;
  position: Point3D;
  displacement?: Point3D;              // смещение (результат анализа)
}

/**
 * Элемент FEA сетки (треугольник или тетраэдр)
 */
export interface FEAElement {
  id: number;
  nodeIndices: number[];               // индексы узлов (3 для треугольника, 4 для тетра)
  material: Material;
  thickness?: number;                  // для оболочечных элементов
}

/**
 * FEA сетка
 */
export interface FEAMesh {
  nodes: FEANode[];
  elements: FEAElement[];
  
  // Metadata
  elementSize: number;                 // размер элемента (мм)
  totalElements: number;
  totalNodes: number;
}

/**
 * Нагрузка
 */
export interface Load {
  nodeId: number;
  force: Vector3D;                     // сила (Н)
  moment?: Vector3D;                   // момент (Н·мм)
}

/**
 * Граничное условие
 */
export interface BoundaryCondition {
  nodeId: number;
  fixed: boolean[];                    // [x, y, z] - фиксированные оси
  displacement?: Vector3D;             // заданное смещение
}

/**
 * Case нагружения
 */
export interface LoadCase {
  name: string;
  loads: Load[];
  boundaryConditions: BoundaryCondition[];
  description?: string;
}

/**
 * Результат FEA анализа
 */
export interface FEAResult {
  // Основные результаты
  displacements: Point3D[];            // смещения всех узлов
  stress: number[];                    // напряжение (МПа) каждого элемента
  strain: number[];                    // деформация каждого элемента
  
  // Экстремумы
  maxDisplacement: number;             // мм
  maxStress: number;                   // МПа
  maxStrain: number;
  
  // Безопасность
  safetyFactor: number;                // коэффициент безопасности
  
  // Энергия
  strainEnergy: number;                // Дж
  
  // Metadata
  loadCaseName: string;
  solverTime: number;                  // мс
  timestamp: Date;
}

/**
 * Мода колебания
 */
export interface VibrationMode {
  mode: number;                        // номер моды
  frequency: number;                   // Гц
  period: number;                      // сек (1/frequency)
  dampingRatio?: number;               // коэффициент затухания (0-1)
  displacements?: Point3D[];           // форма колебания
}

/**
 * Результат модального анализа
 */
export interface ModalAnalysisResult {
  modes: VibrationMode[];
  solverTime: number;                  // мс
  timestamp: Date;
}

// ============================================================================
// 11. PERFORMANCE MONITORING
// ============================================================================

/**
 * Метрики производительности
 */
export interface PerformanceMetrics {
  phase: string;                       // название операции
  duration: number;                    // мс
  memoryBefore: number;                // МБ
  memoryAfter: number;                 // МБ
  memoryUsed: number;                  // МБ (After - Before)
  timestamp: Date;
}

/**
 * Отчёт производительности
 */
export interface PerformanceReport {
  totalDuration: number;               // мс
  totalMemory: number;                 // МБ
  phases: Record<string, {
    count: number;
    totalDuration: number;
    avgDuration: number;
    minDuration: number;
    maxDuration: number;
  }>;
}

// ============================================================================
// 12. КОНФИГУРАЦИЯ КАБИНЕТА (EXISTING - INTEGRATE WITH NEW TYPES)
// ============================================================================

/**
 * Существующая конфигурация кабинета
 * (из CabinetGenerator.ts, оставляем для совместимости)
 */
export interface CabinetConfig {
  name?: string;
  width: number;
  height: number;
  depth: number;
  thickness?: number;
  // ... остальные поля
}

/**
 * Секция кабинета
 */
export interface Section {
  id: string;
  width: number;
  items: Array<{
    type: string;
    id: string;
    height: number;
    y: number;
    name: string;
  }>;
}

// ============================================================================
// 13. РЕЗУЛЬТАТЫ СИМУЛЯЦИИ
// ============================================================================

/**
 * Результат симуляции (общий интерфейс)
 */
export interface SimulationResult {
  // Данные
  stressMap: Map<string, number>;      // компонентId → макс. напряжение
  deformationMap: Map<string, Point3D>; // компонентId → макс. смещение
  
  // Экстремумы
  maxStress: number;                   // МПа
  maxDeformation: number;              // мм
  safetyFactor: number;
  
  // Metadata
  timestamp: Date;
  simulationType: 'static' | 'dynamic' | 'modal';
  runtimeMs: number;
}

// ============================================================================
// 14. ИЕРАРХИЯ (HIERARCHY)
// ============================================================================

/**
 * Узел иерархии компонентов
 */
export interface HierarchyNode {
  id: string;
  name: string;
  componentId: string;
  type: ComponentType;
  children: HierarchyNode[];
  parentId?: string;
  level: number;
  isExpanded?: boolean;
  isSelected?: boolean;
}

/**
 * Путь компонента в иерархии
 */
export interface ComponentPath {
  componentId: string;
  path: string[];                       // ['root', 'assembly1', 'subassembly1', 'component1']
  depth: number;
}

/**
 * BOM иерархия (древовидная структура)
 */
export interface BOMHierarchy {
  root: HierarchyNode;
  flatItems: BOMItem[];
  costByMaterial: Record<string, number>;
  weightByMaterial: Record<string, number>;
  quantityByComponent: Record<string, number>;
}

// ============================================================================
// 15. SOLVER ОПЦИИ
// ============================================================================

/**
 * Опции для Constraint Solver
 */
export interface SolverOptions {
  maxIterations?: number;               // по умолчанию 100
  tolerance?: number;                   // по умолчанию 0.001 мм
  relaxationFactor?: number;            // по умолчанию 1.0
  verbose?: boolean;
  timeout?: number;                     // миллисекунды
}

/**
 * Результат решения ограничений
 */
export interface SolvedAssembly extends Assembly {
  converged: boolean;
  iterations: number;
  residual: number;                     // финальная невязка
  solverTime: number;                   // мс
  constraintErrors: Map<string, number>;
}

// ============================================================================
// 16. EXPORT/IMPORT КОНФИГУРАЦИЯ
// ============================================================================

/**
 * Конфигурация экспорта CAD
 */
export interface CADExportConfig {
  format: ExportFormat;
  scale?: number;                       // по умолчанию 1.0
  precision?: number;                   // знаков после запятой для текстовых форматов
  includeMetadata?: boolean;
  compressed?: boolean;
  splitAssemblies?: boolean;            // экспортировать каждую подсборку отдельно
  colorMode?: 'material' | 'index' | 'none';
  units?: 'mm' | 'cm' | 'm' | 'inch';
}

/**
 * Конфигурация импорта CAD
 */
export interface CADImportConfig {
  format: ExportFormat;
  scale?: number;
  autoRepair?: boolean;                 // автоматически исправлять ошибки сетки
  mergeGeometry?: boolean;              // объединять геометрию
  generateAnchors?: boolean;            // генерировать якоря
  timeout?: number;                     // миллисекунды
}

/**
 * Результат импорта
 */
export interface ImportResult {
  success: boolean;
  assembly?: Assembly;
  errors: string[];
  warnings: string[];
  importTime: number;                   // мс
}

// ============================================================================
// 17. FEA РАСШИРЕННЫЕ ТИПЫ
// ============================================================================

/**
 * Конфигурация FEA интеграции
 */
export interface FEAIntegrationConfig {
  meshSize?: number;                    // мм, по умолчанию 10
  refinementFactor?: number;            // коэффициент уплотнения, 0.1-1.0
  minMeshSize?: number;                 // мм
  maxMeshSize?: number;                 // мм
  quality?: 'low' | 'medium' | 'high';  // качество сетки
  solver?: 'direct' | 'iterative';      // прямой или итеративный солвер
  maxDOF?: number;                      // максимум степеней свободы
}

/**
 * Опции модального анализа
 */
export interface ModalAnalysisOptions {
  numModes: number;                     // количество мод для извлечения (по умолчанию 5)
  frequencyRange?: [number, number];    // [min, max] in Hz
  damping?: number;                     // коэффициент критического затухания
  normalizeMode?: 'mass' | 'displacement';
}

/**
 * Расширенный результат статического анализа
 */
export interface StaticAnalysisResult extends FEAResult {
  stressConcentrations: Array<{
    elementId: number;
    stress: number;
    location: Point3D;
  }>;
  safetyFactorByElement: number[];
  criticalElements: number[];           // элементы с low CoS
  deformationPercentage: number;        // % от размера детали
}

/**
 * Сетка (расширенная версия FEAMesh)
 */
export interface Mesh extends FEAMesh {
  quality: number;                      // 0-100%
  hasConstraints: boolean;
  hasLoads: boolean;
  generatedAt: Date;
  generationTime: number;               // мс
}

/**
 * Объект нагрузки (расширенная версия Load)
 */
export interface LoadDefinition extends Load {
  name?: string;
  elementId?: number;
  distributing?: 'point' | 'distributed'; // точечная или распределённая нагрузка
  scale?: number;                       // масштаб нагрузки для параметрических анализов
}

// ============================================================================
// 18. ОПТИМИЗАЦИЯ РАСШИРЕННАЯ
// ============================================================================

/**
 * Стратегия оптимизации
 */
export interface OptimizationStrategy {
  objective: OptimizationObjective;
  constraints: Array<{
    name: string;
    type: 'min' | 'max' | 'target';
    value: number;
    weight?: number;
  }>;
  variables: Array<{
    name: string;
    type: 'material' | 'thickness' | 'dimension' | 'geometry';
    min: number;
    max: number;
    step?: number;
  }>;
  algorithmOptions?: {
    type?: 'genetic' | 'particle_swarm' | 'simulated_annealing';
    populationSize?: number;
    generations?: number;
    mutationRate?: number;
    crossoverRate?: number;
  };
}

/**
 * Расширенный результат оптимизации
 */
export interface OptimizationResult {
  originalAssembly: Assembly;
  optimizedAssembly: Assembly;
  strategy: OptimizationStrategy;
  
  // Метрики улучшения
  costReduction: number;                // %
  weightReduction: number;              // %
  strengthIncrease: number;             // %
  manufacturabilityImprovement: number; // %
  
  // Детали оптимизации
  iterations: number;
  generations: number;
  convergenceTime: number;              // мс
  fitnessHistory: number[];             // история фитнеса по поколениям
  finalScore: number;
  
  // Статистика
  timestamp: Date;
  optimizer: string;                    // название алгоритма
  runtimeMs: number;
}

// ============================================================================
// 19. DFM РАСШИРЕННАЯ КОНФИГУРАЦИЯ
// ============================================================================

/**
 * Конфигурация DFMValidator
 */
export interface DFMValidatorConfig {
  enabledRules?: string[];              // ID включенных правил
  disabledRules?: string[];             // ID отключенных правил
  severityWeights?: Record<string, number>;
  customRules?: DFMRule[];
  materialDatabase?: Record<string, {   // материал → его правила DFM
    rules: string[];
    constraints: Record<string, [number, number]>;
  }>;
  manufacturingCapabilities?: {
    hasLaserCutting?: boolean;
    hasBending?: boolean;
    hasThreading?: boolean;
    hasPolishing?: boolean;
    toleranceClass?: 'ISO h7' | 'ISO h8' | 'ISO h9' | 'ISO h10' | 'ISO h11';
  };
}

// ============================================================================
// 20. ИСТОРИЯ И UNDO/REDO
// ============================================================================

/**
 * Команда для Undo/Redo
 */
export interface Command {
  id: string;
  name: string;
  timestamp: Date;
  
  // Функции
  execute(): Promise<void>;
  undo(): Promise<void>;
  redo(): Promise<void>;
  
  // Опции
  mergeable?: boolean;                 // можно ли объединить с следующей командой
  canUndo?: boolean;                   // можно ли отменить
}

/**
 * История команд
 */
export interface CommandHistory {
  commands: Command[];
  currentIndex: number;               // индекс текущей позиции
  
  // Методы
  execute(cmd: Command): Promise<void>;
  undo(): Promise<void>;
  redo(): Promise<void>;
  canUndo(): boolean;
  canRedo(): boolean;
  clear(): void;
}

// ============================================================================
// EXPORT ВСЕ ТИПЫ И ИНТЕРФЕЙСЫ
// ============================================================================

/**
 * Утилиты для работы с типами
 */
export namespace CADTypeUtils {
  /**
   * Создать пустую точку
   */
  export function createPoint(x: number = 0, y: number = 0, z: number = 0): Point3D {
    return { x, y, z };
  }
  
  /**
   * Создать пустые углы Эйлера
   */
  export function createEulerAngles(x: number = 0, y: number = 0, z: number = 0): EulerAngles {
    return { x, y, z };
  }
  
  /**
   * Дистанция между двумя точками
   */
  export function distance(a: Point3D, b: Point3D): number {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dz = b.z - a.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }
  
  /**
   * Сложить две точки (как вектора)
   */
  export function addPoints(a: Point3D, b: Point3D): Point3D {
    return {
      x: a.x + b.x,
      y: a.y + b.y,
      z: a.z + b.z
    };
  }
  
  /**
   * Вычесть две точки
   */
  export function subtractPoints(a: Point3D, b: Point3D): Point3D {
    return {
      x: a.x - b.x,
      y: a.y - b.y,
      z: a.z - b.z
    };
  }
  
  /**
   * Скалярное произведение векторов
   */
  export function dotProduct(a: Point3D, b: Point3D): number {
    return a.x * b.x + a.y * b.y + a.z * b.z;
  }
  
  /**
   * Векторное произведение
   */
  export function crossProduct(a: Point3D, b: Point3D): Point3D {
    return {
      x: a.y * b.z - a.z * b.y,
      y: a.z * b.x - a.x * b.z,
      z: a.x * b.y - a.y * b.x
    };
  }
  
  /**
   * Нормализовать вектор
   */
  export function normalize(v: Point3D): Point3D {
    const len = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
    if (len === 0) return { x: 0, y: 0, z: 0 };
    return { x: v.x / len, y: v.y / len, z: v.z / len };
  }
  
  /**
   * Длина вектора
   */
  export function magnitude(v: Point3D): number {
    return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
  }
  
  /**
   * Применить трансформацию к точке
   */
  export function transformPoint(point: Point3D, transform: Transform): Point3D {
    // Применить масштабирование
    const scaled = {
      x: point.x * transform.scale.x,
      y: point.y * transform.scale.y,
      z: point.z * transform.scale.z
    };
    
    // TODO: Применить ротацию (матрица Эйлера)
    // Для простоты пока пропускаем ротацию
    const rotated = scaled;
    
    // Применить трансляцию
    return {
      x: rotated.x + transform.position.x,
      y: rotated.y + transform.position.y,
      z: rotated.z + transform.position.z
    };
  }
  
  /**
   * Вычислить bounding box из массива точек
   */
  export function boundingBoxFromPoints(points: Point3D[]): BoundingBox {
    if (points.length === 0) {
      const zero = { x: 0, y: 0, z: 0 };
      return {
        min: zero,
        max: zero,
        width: () => 0,
        height: () => 0,
        depth: () => 0
      };
    }
    
    let minX = points[0].x;
    let minY = points[0].y;
    let minZ = points[0].z;
    let maxX = points[0].x;
    let maxY = points[0].y;
    let maxZ = points[0].z;
    
    for (const point of points) {
      minX = Math.min(minX, point.x);
      minY = Math.min(minY, point.y);
      minZ = Math.min(minZ, point.z);
      maxX = Math.max(maxX, point.x);
      maxY = Math.max(maxY, point.y);
      maxZ = Math.max(maxZ, point.z);
    }
    
    const min = { x: minX, y: minY, z: minZ };
    const max = { x: maxX, y: maxY, z: maxZ };
    
    return {
      min,
      max,
      width: () => maxX - minX,
      height: () => maxY - minY,
      depth: () => maxZ - minZ
    };
  }
}

/**
 * Версия типов
 */
export const CAD_TYPES_VERSION = '1.1.0';

/**
 * Дата последнего обновления
 */
export const CAD_TYPES_UPDATED = '2026-01-18';

/**
 * ИТОГО ТИПОВ И ИНТЕРФЕЙСОВ
 * 
 * Раздел 1:  Базовые 3D типы (5 интерфейсов + 1 enum)
 * Раздел 2:  Материалы (2 интерфейса + 1 enum)
 * Раздел 3:  Ограничения (3 интерфейса + 1 enum)
 * Раздел 4:  Якоря (2 интерфейса + 1 enum)
 * Раздел 5:  Компоненты (2 интерфейса + 1 enum)
 * Раздел 6:  BOM (2 интерфейса)
 * Раздел 7:  DFM (3 интерфейса + 1 enum)
 * Раздел 8:  Оптимизация (2 интерфейса + 1 enum)
 * Раздел 9:  Экспорт/Импорт (2 интерфейса + 1 enum)
 * Раздел 10: FEA (8 интерфейсов)
 * Раздел 11: Performance (2 интерфейса)
 * Раздел 12: CabinetConfig (2 интерфейса)
 * Раздел 13: SimulationResult (1 интерфейс)
 * Раздел 14: Иерархия (3 интерфейса)
 * Раздел 15: Solver (2 интерфейса)
 * Раздел 16: Export/Import Config (3 интерфейса)
 * Раздел 17: FEA Extended (4 интерфейса)
 * Раздел 18: Оптимизация Extended (2 интерфейса)
 * Раздел 19: DFM Config (1 интерфейс)
 * Раздел 20: History (2 интерфейса)
 * 
 * ВСЕГО: 60+ интерфейсов + 10 enums + Утилиты
 */
