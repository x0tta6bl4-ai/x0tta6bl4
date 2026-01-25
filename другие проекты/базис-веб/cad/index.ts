/**
 * CAD Модули - Главный индекс
 * ФАЗА 1: Архитектура и типы
 */

// =============================================================================
// Типы и интерфейсы
// =============================================================================

export * from '../types/CADTypes';
export * from '../types/ProductionArchitecture';
export * from '../types/ParametricSystem';

// =============================================================================
// Сервисы для решения задач (Фазы 2-14)
// =============================================================================

// Фаза 2: Решатель ограничений (Constraint Solver)
export { ConstraintSolver } from '../services/ConstraintSolver';

// Фаза 3: Спецификация материалов и иерархия
export { BillOfMaterials } from '../services/BillOfMaterials';
export { BOMExporter } from '../services/BOMExporter';
export { HierarchyManager } from '../services/HierarchyManager';

// Фаза 4: Design for Manufacturing анализ
export { DFMValidator } from '../services/DFMValidator';

// Фаза 5: Параметрическая оптимизация
export { CabinetOptimizer } from '../services/CabinetOptimizer';

// Фаза 6: Экспорт и импорт
export { CADExporter } from '../services/CADExporter';
export { CADImporter } from '../services/CADImporter';

// Фаза 7: Конечно-элементный анализ
export { FEAIntegration } from '../services/FEAIntegration';

// Фаза 8: Мониторинг производительности
export { PerformanceMonitor } from '../services/PerformanceMonitor';

// Фаза 9: Производственный строитель
export { ProductionCabinetBuilder } from '../services/ProductionCabinetBuilder';

// Фаза 10: Параметрическая система (v2.1)
export { ParametricSystem } from '../services/ParametricSystem';

// =============================================================================
// React компоненты
// =============================================================================

export { BOMViewer } from '../components/BOMViewer';
export { HierarchyTree } from '../components/HierarchyTree';
export { DFMReportComponent as DFMReport } from '../components/DFMReport';
export { OptimizationResults } from '../components/OptimizationResults';
export { FEAPanel } from '../components/FEAPanel';
