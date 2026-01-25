/**
 * Параметрическая система с топологической сортировкой и зависимостями
 * v2.1
 */

import { CabinetDSL, SolvedPanel, ValidationError, Mm } from './ProductionArchitecture';

// =============================================================================
// Типы для параметрической связности
// =============================================================================

export interface Parameter {
  id: string;
  name: string;
  type: 'number' | 'string' | 'boolean' | 'select';
  value: any;
  min?: number;
  max?: number;
  options?: string[];
  unit?: string;
  description?: string;
}

export interface ParametricConstraint {
  id: string;
  name: string;
  source: string;  // ID параметра источника
  target: string;  // ID параметра цели
  formula: string; // Формула привязки (например: target = source * 1.5)
  dependencies: string[]; // IDs параметров, от которых зависит формула
  isActive: boolean;
}

export interface DependencyGraphNode {
  id: string;
  parameter: Parameter;
  constraints: ParametricConstraint[];
  dependencies: string[]; // ID параметров, от которых зависит этот узел
  dependents: string[]; // ID параметров, которые зависят от этого узла
  visited?: boolean;
}

export interface DependencyGraph {
  nodes: Map<string, DependencyGraphNode>;
  edges: Map<string, string[]>;
}

export interface RecalculationResult {
  updatedParameters: string[];
  affectedPanels: SolvedPanel[];
  validationErrors: ValidationError[];
  recalculationTime: number;
}

// =============================================================================
// Типы для истории версий
// =============================================================================

export interface Version {
  id: string;
  name: string;
  description?: string;
  timestamp: number;
  author: string;
  versionNumber: string;
  changelog?: string[];
}

export interface VersionDiff {
  id: string;
  versionFrom: string;
  versionTo: string;
  added: string[];
  modified: string[];
  removed: string[];
  timestamp: number;
}

export interface Branch {
  id: string;
  name: string;
  baseVersion: string;
  currentVersion: string;
  versions: Version[];
  created: number;
  modified: number;
  author: string;
}

export interface MergeResult {
  success: boolean;
  conflicts: string[];
  mergedVersion: string;
  diff: VersionDiff;
}

// =============================================================================
// Типы для производственных допусков
// =============================================================================

export interface Tolerance {
  id: string;
  name: string;
  type: 'dimensional' | 'geometric' | 'positional';
  nominal: number;
  upper: number;
  lower: number;
  unit: string;
  description?: string;
}

export interface DimensionCheck {
  id: string;
  panelId: string;
  dimension: 'width' | 'height' | 'depth';
  nominal: Mm;
  actual: Mm;
  tolerance: Tolerance;
  isWithinTolerance: boolean;
  deviation: number;
}

export interface ToleranceReport {
  id: string;
  timestamp: number;
  title: string;
  totalChecks: number;
  passedChecks: number;
  failedChecks: number;
  dimensionChecks: DimensionCheck[];
  toleranceSummary: Record<string, number>;
}

// =============================================================================
// Типы для интерактивного редактирования
// =============================================================================

export interface DraftModeConfig {
  enabled: boolean;
  autoRecalculate: boolean;
  previewQuality: 'low' | 'medium' | 'high';
  autoSave: boolean;
  saveInterval: number;
}

export interface InteractiveEditState {
  isEditing: boolean;
  selectedComponent: string;
  editMode: '3d' | '2d' | 'properties';
  draftMode: DraftModeConfig;
  lastModified: number;
  unsavedChanges: string[];
}

export interface RealTimePreviewOptions {
  cameraPosition: { x: number; y: number; z: number };
  cameraTarget: { x: number; y: number; z: number };
  lightingPreset: 'studio' | 'natural' | 'technical';
  showDimensions: boolean;
  showConstraints: boolean;
  showHoles: boolean;
  wireframeMode: boolean;
}

// =============================================================================
// Типы для расчёта себестоимости
// =============================================================================

export interface CostItem {
  id: string;
  name: string;
  type: 'material' | 'hardware' | 'labor' | 'overhead' | 'markup';
  quantity: number;
  unitCost: number;
  totalCost: number;
  description?: string;
  details?: string;
}

export interface LaborCost {
  operation: string;
  time: number;  // минуты
  costPerMinute: number;  // руб/мин
  total: number;
}

export interface MaterialCostBreakdown {
  materialId: string;
  materialName: string;
  area: number;  // м²
  pricePerM2: number;  // руб/м²
  total: number;
}

export interface HardwareCost {
  hardwareId: string;
  hardwareName: string;
  quantity: number;
  pricePerUnit: number;
  total: number;
}

export interface CostBreakdown {
  materials: MaterialCostBreakdown[];
  hardware: HardwareCost[];
  labor: LaborCost[];
  overhead: number;  // % от суммы
  markup: number;    // % от себестоимости
}

export interface CostCalculation {
  id: string;
  projectId: string;
  timestamp: number;
  currency: string;
  exchangeRate: number;
  baseCost: number;
  overheadCost: number;
  markupCost: number;
  totalCost: number;
  costBreakdown: CostBreakdown;
  costItems: CostItem[];
  summary: {
    totalMaterials: number;
    totalHardware: number;
    totalLabor: number;
    totalOverhead: number;
    totalMarkup: number;
    total: number;
  };
}

// =============================================================================
// Типы для руководства сборки
// =============================================================================

export interface Tool {
  id: string;
  name: string;
  type: 'hand' | 'power' | 'special';
  description?: string;
  image?: string;
  safetyNotes?: string;
}

export interface AssemblyStep {
  id: string;
  number: number;
  title: string;
  description: string;
  duration: number;  // минуты
  difficulty: 'easy' | 'medium' | 'hard';
  tools: string[];  // IDs инструментов
  materials: string[];  // IDs материалов
  components: string[];  // IDs компонентов
  subSteps?: string[];
  images?: string[];
  video?: string;
  animation3d?: string;
  torqueValues?: { [key: string]: number };  // { "confirmat": 4.5 }
  warnings?: string[];
}

export interface AssemblyGuide {
  id: string;
  projectId: string;
  language: string;
  title: string;
  description: string;
  totalDuration: number;
  difficulty: 'beginner' | 'intermediate' | 'professional';
  requiredTools: Tool[];
  requiredMaterials: string[];
  steps: AssemblyStep[];
  sections?: {
    id: string;
    title: string;
    stepRange: [number, number];
  }[];
  safetyNotes: string[];
  troubleshooting: string[];
}

export interface AssemblyAnimation {
  id: string;
  stepId: string;
  duration: number;  // секунды
  frameCount: number;
  frames: string[];  // base64 или URL
  description: string;
}

// =============================================================================
// Интерфейсы для интеграции с 5-слойной архитектурой
// =============================================================================

export interface ParametricSystem {
  // Параметрическая связность
  parameters: Map<string, Parameter>;
  constraints: ParametricConstraint[];
  dependencyGraph: DependencyGraph;
  
  // Методы для работы с параметрами
  getParameter(id: string): Parameter | undefined;
  setParameter(id: string, value: any): RecalculationResult;
  addParameter(param: Parameter): void;
  removeParameter(id: string): void;
  addConstraint(constraint: ParametricConstraint): void;
  removeConstraint(id: string): void;
  validateParameters(): ValidationError[];
  recalculateAffected(): RecalculationResult;
  
  // История версий
  versions: Version[];
  branches: Branch[];
  currentBranch: string;
  currentVersion: string;
  
  saveVersion(name: string, description?: string): Version;
  loadVersion(versionId: string): boolean;
  undo(): boolean;
  redo(): boolean;
  createBranch(name: string, fromVersion?: string): Branch;
  mergeBranch(branchId: string, intoBranch?: string): MergeResult;
  getVersionDiff(fromVersion: string, toVersion: string): VersionDiff;
  
  // Производственные допуски
  tolerances: Tolerance[];
  toleranceReport: ToleranceReport;
  
  addTolerance(tolerance: Tolerance): void;
  removeTolerance(id: string): void;
  runToleranceCheck(): ToleranceReport;
  getDimensionChecks(): DimensionCheck[];
  
  // Интерактивное редактирование
  interactiveState: InteractiveEditState;
  realTimePreview: RealTimePreviewOptions;
  
  startEditing(): void;
  stopEditing(save: boolean): void;
  toggleDraftMode(): void;
  updateRealTimePreview(options: Partial<RealTimePreviewOptions>): void;
  getUnsavedChanges(): string[];
  
  // Расчёт себестоимости
  costCalculation: CostCalculation;
  
  calculateCost(): CostCalculation;
  updateCostBreakdown(breakdown: Partial<CostBreakdown>): CostCalculation;
  getCostItemsByType(type: string): CostItem[];
  exportCostReport(format: 'pdf' | 'csv' | 'json'): any;
  
  // Руководство сборки
  assemblyGuide: AssemblyGuide;
  
  generateAssemblyGuide(language?: string): AssemblyGuide;
  getStepDetails(stepNumber: number): AssemblyStep;
  exportAssemblyGuide(format: 'pdf' | 'html' | 'json'): any;
}
