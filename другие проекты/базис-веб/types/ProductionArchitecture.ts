/**
 * Производственная архитектура v2.0
 * 5-слойная модель:
 * 1. DSL (Input)
 * 2. Rules Engine
 * 3. Solved Model
 * 4. Manufacturing Layer
 * 5. Views
 */

// =============================================================================
// 1. DSL Layer (Parameter Input)
// =============================================================================

export type Mm = number & { readonly __brand: 'mm' };
export type EdgeType = 'none' | '1mm_pvc' | '2mm_abs' | '0.4mm_melamine';
export type JointType = 'confirmat' | 'minifix' | 'dowel' | 'lamello';
export type DrillTool = 'DRILL_5_HSS' | 'DRILL_6_HSS' | 'DRILL_7_HSS';

export interface MaterialSpec {
  type: 'ldsp' | 'mdf' | 'plywood' | 'hdf';
  thickness: Mm;
  density: number;      // кг/м³
  pricePerM2: number;   // руб/м²
}

export interface EdgeSpec {
  front: EdgeType;
  left: EdgeType;
  right: EdgeType;
  back: EdgeType;
  top: EdgeType;
  bottom: EdgeType;
}

export interface DoorSpec {
  count: number;
  type: 'swing' | 'coupe' | 'lift' | 'pocket';
  gap: Mm;
  coupeOverlap?: Mm;
}

export interface ShelfSpec {
  count: number;
  supports: 'dowel_5x30' | 'pin_5' | 'rail';
  position: 'auto' | Mm[];
}

export interface CabinetDSL {
  envelope: { width: Mm; height: Mm; depth: Mm };
  structure: { scheme: 'box' | 'frame' | 'frameless'; backInset?: Mm };
  material: { board: MaterialSpec; back?: MaterialSpec; edge: EdgeSpec };
  doors?: DoorSpec;
  shelves?: ShelfSpec;
  constraints?: {
    maxDeflection: Mm;
    minSafetyFactor: number;
    manufacturingTolerance: Mm;
    jointType: JointType;
  };
}

// =============================================================================
// 2. Rules Engine Layer
// =============================================================================

export type PanelType = 'top' | 'bottom' | 'side-l' | 'side-r' | 'shelf' | 'back' | 'door';

export interface ValidationError {
  code: string;
  msg: string;
  severity: 'error' | 'warning';
  suggestion?: string;
}

export interface ConstructionRule {
  id: string;
  name: string;
  appliesTo: PanelType;
  requires: PanelType[];
  calculate: (solved: Map<string, SolvedPanel>, params: CabinetDSL) => Partial<SolvedPanel>;
  validate: (panel: SolvedPanel) => ValidationError[];
}

// =============================================================================
// 3. Solved Model Layer
// =============================================================================

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface Axis { X: 'X'; Y: 'Y'; Z: 'Z' }
export type AxisType = 'X' | 'Y' | 'Z';

export interface DrillHole {
  id: string;
  position: Vec3;
  diameter: Mm;
  depth: Mm;
  tool: DrillTool;
  feedrate: number;
  spindle: number;
}

export interface EdgeTreatment {
  side: 'left' | 'right' | 'top' | 'bottom' | 'front' | 'back';
  type: EdgeType;
  length: number;
}

export interface SolvedPanel {
  id: string;
  role: PanelType;
  position: Vec3;
  size: Vec3;
  orientation: AxisType;
  edges: EdgeTreatment[];
  holes: DrillHole[];
  operationSequence: string[];
  rulesApplied: string[];
  metadata: {
    material: MaterialSpec;
    weight: number;
    costMaterial: number;
    machiningTime: number;
  };
}

// =============================================================================
// 4. Manufacturing Layer
// =============================================================================

export type JointGeometryType = 'tee' | 'corner' | 'butt' | 'overlap';

export interface GeometricJoint {
  panelA: string;
  panelB: string;
  type: string;
  length: Mm;
}

export interface JointTechSpec {
  id: string;
  type: JointGeometryType;
  panelA: string;
  panelB: string;
  fastener: {
    type: 'confirmat_7x50' | 'dowel_8x30' | 'minifix_10';
    quantity: number;
    spacing: number;
    minDistFromEdge: number;
  };
  drillPattern: {
    direction: 'into_panelB';
    holes: DrillHole[];
  };
}

export interface CutDetail {
  id: string;
  size: Vec3;
  grain: 'horizontal' | 'vertical' | 'any';
  edgeProtectedSides: string[];
  priority: number;
  operations: {
    edgeBanding: EdgeTreatment[];
    drilling: DrillHole[];
    bevel?: { angle: number; depth: Mm };
  };
}

export interface SheetCutting {
  sheetNumber: number;
  material: MaterialSpec;
  details: CutDetail[];
  metrics: {
    usedArea: number;
    wasteArea: number;
    utilizationRatio: number;
  };
}

export interface CuttingPlan {
  sheets: SheetCutting[];
  metrics: {
    totalSheets: number;
    KIM: number;
    totalWaste: number;
    estimatedCuttingTime: number;
  };
}

// =============================================================================
// 5. Views Layer
// =============================================================================

export interface CADExportOptions {
  format: 'dxf' | 'json' | 'pdf' | 'gcode';
  version?: string;
}

export interface ExportResult {
  [key: string]: string | Buffer;
}
