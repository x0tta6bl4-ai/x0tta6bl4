/**
 * ПРОФЕССИОНАЛЬНЫЙ CAD ДВИЖОК
 * Типы данных для моделирования
 * 
 * Вдохновлено: Autodesk, Solidworks, FreeCAD архитектурой
 * Для мебельного производства базис-веб
 */

// ============================================================================
// ОСНОВНЫЕ ГЕОМЕТРИЧЕСКИЕ ТИПЫ
// ============================================================================

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface Vector2 {
  x: number;
  y: number;
}

export interface Matrix4x4 {
  m: number[][];
}

export interface AABB {
  min: Vector3;
  max: Vector3;
  center: Vector3;
  size: Vector3;
}

// ============================================================================
// B-REP (BOUNDARY REPRESENTATION) СТРУКТУРЫ
// ============================================================================

export interface Vertex {
  id: string;
  position: Vector3;
  edges: string[]; // Edge IDs
  normal?: Vector3;
}

export interface Edge {
  id: string;
  v1: Vertex | string; // Start vertex
  v2: Vertex | string; // End vertex
  length: number;
  faces: string[]; // Face IDs using this edge
  isCurved?: boolean;
  curvatureRadius?: number;
}

export interface Face {
  id: string;
  name?: string;
  vertices: Vertex[] | string[]; // Vertex IDs
  edges: Edge[] | string[]; // Edge IDs
  normal: Vector3;
  area: number;
  isPlanar: boolean;
  
  // Surface properties
  surfaceType: 'planar' | 'cylindrical' | 'spherical' | 'nurbs';
  
  // Manufacturing
  material?: string;
  texture?: string;
  roughness?: number;
  
  // CAD properties
  isVisible: boolean;
  isSelectable: boolean;
  color?: string;
}

export interface Shell {
  id: string;
  faces: Face[];
  isClosed: boolean;
  isWatertight: boolean;
}

export interface Body {
  id: string;
  name: string;
  
  // Topology
  shells: Shell[];
  faces: Face[];
  edges: Edge[];
  vertices: Vertex[];
  
  // Geometry
  boundingBox: AABB;
  volume?: number;
  mass?: number;
  
  // Properties
  material?: string;
  isVisible: boolean;
  isLocked: boolean;
  
  // Manufacturing
  productionStatus?: 'pending' | 'in_progress' | 'completed';
  
  // Metadata
  createdAt: Date;
  modifiedAt: Date;
}

// ============================================================================
// ПАРАМЕТРИЧЕСКИЕ ОГРАНИЧЕНИЯ
// ============================================================================

export type ConstraintType =
  | 'distance'
  | 'distance_point_plane'
  | 'angle'
  | 'parallel'
  | 'perpendicular'
  | 'coincident'
  | 'tangent'
  | 'horizontal'
  | 'vertical'
  | 'symmetric'
  | 'equal'
  | 'fix'
  | 'lock';

export type ConstraintStatus =
  | 'satisfied'
  | 'unsatisfied'
  | 'over_constrained'
  | 'conflicting'
  | 'redundant';

export interface ConstraintElement {
  type: 'vertex' | 'edge' | 'face' | 'body' | 'point' | 'plane' | 'line';
  id: string;
  reference?: Vector3;
}

export interface Constraint {
  id: string;
  name?: string;
  type: ConstraintType;
  elements: ConstraintElement[];
  value?: number; // Distance, angle value
  status: ConstraintStatus;
  residual?: number;
  
  // Solver properties
  weight?: number;
  isActive: boolean;
  
  // Metadata
  createdAt: Date;
  description?: string;
}

// ============================================================================
// ПАРАМЕТРИЧЕСКИЙ ДВИЖОК
// ============================================================================

export interface Parameter {
  id: string;
  name: string;
  value: number;
  
  // Limits
  min?: number;
  max?: number;
  step?: number;
  
  // Dependencies
  dependentConstraints: string[];
  dependentBodies: string[];
  dependentFeatures: string[];
  
  // Metadata
  unit?: string;
  description?: string;
  isDriving: boolean; // User-controllable vs derived
}

export interface Feature {
  id: string;
  name: string;
  type: 'pad' | 'pocket' | 'hole' | 'fillet' | 'chamfer' | 'shell' | 'assembly';
  
  // Inputs
  inputBodies: string[];
  inputConstraints: string[];
  parameters: Parameter[];
  
  // Outputs
  outputBody?: Body;
  
  // Status
  isValid: boolean;
  error?: string;
  
  // Metadata
  createdAt: Date;
  isVisible: boolean;
}

export interface DependencyGraph {
  nodes: Map<string, Feature | Parameter | Constraint>;
  edges: Map<string, string[]>; // From -> [To, ...]
}

// ============================================================================
// CAD МОДЕЛЬ
// ============================================================================

export interface CADModel {
  id: string;
  name: string;
  version: string;
  
  // Content
  bodies: Body[];
  constraints: Constraint[];
  features: Feature[];
  parameters: Map<string, Parameter>;
  
  // Structure
  dependencyGraph: DependencyGraph;
  
  // History
  history: HistoryEntry[];
  currentHistoryIndex: number;
  
  // Solver state
  solverResult?: SolverResult;
  
  // Metadata
  createdAt: Date;
  modifiedAt: Date;
  author?: string;
  description?: string;
}

export interface HistoryEntry {
  id: string;
  timestamp: Date;
  action: 'create' | 'modify' | 'delete' | 'constraint' | 'parameter';
  objectId: string;
  objectName: string;
  beforeState?: any;
  afterState?: any;
  description: string;
}

// ============================================================================
// РЕШАТЕЛЬ ОГРАНИЧЕНИЙ
// ============================================================================

export interface SolverResult {
  success: boolean;
  converged: boolean;
  iterations: number;
  residual: number;
  timestamp: number; // milliseconds
  
  // Diagnostics
  constraintStatus: Map<string, ConstraintStatus>;
  unconstrainedVariables?: string[];
  overConstraintedGroups?: string[][];
}

export interface SolverOptions {
  maxIterations?: number;
  tolerance?: number;
  damping?: number;
  verbose?: boolean;
  timeout?: number; // milliseconds
}

// ============================================================================
// ВАЛИДАЦИЯ И КАЧЕСТВО
// ============================================================================

export interface Collision {
  id: string;
  body1Id: string;
  body2Id: string;
  face1Id: string;
  face2Id: string;
  penetrationDepth: number;
  contactPoints: Vector3[];
  severity: 'error' | 'warning' | 'info';
}

export interface ManufacturingIssue {
  id: string;
  objectId: string;
  type: 'radius_too_small' | 'thickness_too_thin' | 'overhang' | 'sharp_corner' | 'tolerance_violation';
  severity: 'error' | 'warning';
  value?: number;
  suggestion?: string;
  cost?: number;
}

export interface ValidationResult {
  isValid: boolean;
  timestamp: Date;
  
  // Issues
  collisions: Collision[];
  manufacturingIssues: ManufacturingIssue[];
  constraintErrors: Array<{
    constraintId: string;
    message: string;
    severity: 'error' | 'warning';
  }>;
  
  // Warnings
  warnings: string[];
  
  // Statistics
  totalIssues: number;
  totalErrors: number;
  totalWarnings: number;
}

// ============================================================================
// ПРОИЗВОДСТВО
// ============================================================================

export interface MaterialSpec {
  id: string;
  name: string;
  type: 'ldsp' | 'mdf' | 'plywood' | 'metal' | 'glass';
  thickness: number;
  density: number;
  elasticModulus: number; // N/mm²
  tensileStrength: number;
  pricePerM2: number;
}

export interface ManufacturingPlan {
  modelId: string;
  material: MaterialSpec;
  processes: ManufacturingProcess[];
  estimatedTime: number; // minutes
  estimatedCost: number;
  warnings: string[];
}

export interface ManufacturingProcess {
  id: string;
  name: string;
  type: 'cut' | 'edge' | 'drill' | 'assemble';
  duration: number; // minutes
  cost: number;
  requiredTools: string[];
}

// ============================================================================
// ЭКСПОРТ
// ============================================================================

export type ExportFormat =
  | 'step'
  | 'iges'
  | 'stl'
  | 'obj'
  | 'dxf'
  | 'dwg'
  | 'json'
  | 'gltf';

export interface ExportOptions {
  format: ExportFormat;
  scale?: number;
  precision?: number;
  includeMaterials?: boolean;
  includeMetadata?: boolean;
}

// ============================================================================
// ОПЕРАЦИИ
// ============================================================================

export interface CADOperation {
  type: 'create_body' | 'modify_constraint' | 'update_parameter' | 'validate' | 'export';
  timestamp: Date;
  duration: number; // milliseconds
  success: boolean;
  error?: string;
}
