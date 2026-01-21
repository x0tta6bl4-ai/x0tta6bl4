
export enum Axis {
  X = 'X',
  Y = 'Y',
  Z = 'Z'
}

export interface Material {
  id: string;
  article: string;
  brand: 'Egger' | 'Kronospan' | 'Lamarty' | 'MDF_RAL';
  name: string;
  thickness: 4 | 8 | 10 | 16 | 18 | 22 | 25;
  pricePerM2: number;
  texture: TextureType;
  isTextureStrict: boolean;
  color: string;
  // Material properties (added for algorithm optimization)
  density: number; // kg/m³ (680-1200 range)
  elasticModulus?: number; // N/mm² (MOE - modulus of elasticity)
  certification?: 'E0' | 'E1' | 'E2'; // Formaldehyde emission classification
  type?: 'LDSP' | 'MDF' | 'HDF'; // Material type for algorithm logic
}

export enum TextureType {
  NONE = 'none',
  WOOD_OAK = 'wood_oak',
  WOOD_WALNUT = 'wood_walnut',
  WOOD_ASH = 'wood_ash',
  CONCRETE = 'concrete',
  UNIFORM = 'uniform'
}

export type OpeningType = 'none' | 'left' | 'right' | 'top' | 'bottom' | 'drawer' | 'sliding' | 'folding';

export interface Hardware {
  id: string;
  article?: string; // Артикул производителя
  price?: number;
  type: 'handle' | 'hinge_cup' | 'screw' | 'minifix_cam' | 'minifix_pin' | 'dowel' | 'dowel_hole' | 'shelf_support' | 'slide_rail' | 'rod_holder' | 'pantograph' | 'basket_rail' | 'legs';
  name: string;
  x: number; 
  y: number;
  diameter?: number;
  depth?: number;
}

export type EdgeThickness = 'none' | '0.4' | '1.0' | '2.0';

export interface Edging {
  top: EdgeThickness;
  bottom: EdgeThickness;
  left: EdgeThickness;
  right: EdgeThickness;
}

export interface Groove {
  enabled: boolean;
  side: 'top' | 'bottom' | 'left' | 'right';
  width: number;
  depth: number;
  offset: number;
}

export interface Layer {
  id: string;
  name: string;
  visible: boolean;
  locked: boolean;
  color: string;
}

// MES Types
export type ProductionStage = 'design' | 'cutting' | 'edging' | 'drilling' | 'assembly' | 'quality_control' | 'shipping';

export type ProductionStatus = 'pending' | 'in_progress' | 'completed' | 'issue';

export interface Panel {
  id: string;
  name: string;
  width: number; 
  height: number; 
  depth: number; 
  x: number;
  y: number;
  z: number;
  rotation: Axis; 
  materialId: string; 
  color: string;
  texture: TextureType;
  textureRotation: 0 | 90;
  visible: boolean; 
  layer: string; 
  openingType: OpeningType;
  isSelected?: boolean;
  edging: Edging;
  groove: Groove;
  hardware: Hardware[];
  productionStatus?: ProductionStatus; // Status within the current stage
  currentStage?: ProductionStage; // Current lifecycle stage of the panel
}

export interface ProductionNorms {
    totalTimeMinutes: number;
    cuttingTime: number;
    edgingTime: number;
    drillingTime: number;
    assemblyTime: number;
}

// --- PARAMETRIC WIZARD TYPES ---
export type CabinetType = 'straight' | 'corner_l';
export type ConstructionType = 'corpus' | 'builtin_wall_wall' | 'builtin_niche';
export type DoorType = 'none' | 'hinged' | 'sliding' | 'folding';
export type DrawerSystemType = 'classic' | 'metabox' | 'tandembox';
export type RailType = 'ball' | 'roller' | 'hidden';
export type BottomMountType = 'groove' | 'nailed';

export interface CabinetItem {
    id: string; // Optional mainly for AI generation phase
    type: 'shelf' | 'drawer' | 'rod' | 'basket' | 'pantograph' | 'shoe_rack' | 'partition';
    y: number; 
    height: number; 
    name: string;
    depthOffset?: number; 
    drawerSystem?: DrawerSystemType;
    railType?: RailType;
    bottomMount?: BottomMountType;
    hardwareIds?: string[];
    grooves?: any[];
}

export interface Section {
    id: string;
    width: number;
    items: CabinetItem[];
    isFixed?: boolean; 
}

export interface CabinetConfig {
  name: string;
  type: CabinetType;
  width: number;
  height: number;
  depth: number;
  widthLeft?: number;
  depthLeft?: number;
  construction?: ConstructionType;
  doorType: DoorType;
  doorCount: number;
  baseType: 'plinth' | 'legs';
  facadeStyle: 'solid' | 'combined';
  materialId?: string; // Selected main material
  doorGap?: number; // Зазор для распашных (мм)
  coupeGap?: number; // Перехлест/Зазор для купе (мм)
  backType?: 'groove' | 'overlay';
  hardwareType?: 'confirmat' | 'minifix' | 'none';
}

// --- STORAGE & VERSIONING ---
export interface ProjectSnapshot {
  id: string;
  name: string;
  timestamp: number;
  version: number;
  description?: string;
  previewImage?: string; // Base64 thumbnail
  panels: Panel[];
  layers?: Layer[];
  config?: CabinetConfig; // Optional wizard config restoration
  tags?: string[];
}
