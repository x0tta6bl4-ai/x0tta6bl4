
export enum Axis {
  X = 'X',
  Y = 'Y',
  Z = 'Z'
}

export type MaterialCategory = 'ldsp' | 'wood' | 'plastic' | 'glass' | 'metal';

export interface Material {
  id: string;
  article: string;
  brand: 'Egger' | 'Kronospan' | 'Lamarty' | 'MDF_RAL' | 'Generic';
  name: string;
  category: MaterialCategory;
  thickness: number; // Current selected thickness
  availableThicknesses?: number[]; // Options available
  pricePerM2: number;
  texture: TextureType;
  isTextureStrict: boolean;
  color: string;
  
  // Visual Assets
  textureUrl?: string;
  normalMapUrl?: string; // For 3D depth
  roughnessMapUrl?: string;
  previewUrl?: string; // Larger preview image
  
  density?: number;
}

export enum TextureType {
  NONE = 'none',
  WOOD_OAK = 'wood_oak',
  WOOD_WALNUT = 'wood_walnut',
  WOOD_ASH = 'wood_ash',
  CONCRETE = 'concrete',
  UNIFORM = 'uniform',
  MARBLE = 'marble',
  FABRIC = 'fabric'
}

export type OpeningType = 'none' | 'left' | 'right' | 'top' | 'bottom' | 'drawer' | 'sliding' | 'folding';

export interface Hardware {
  id: string;
  article?: string;
  price?: number;
  type: 'handle' | 'hinge_cup' | 'screw' | 'minifix_cam' | 'minifix_pin' | 'dowel' | 'dowel_hole' | 'shelf_support' | 'slide_rail' | 'rod_holder' | 'pantograph' | 'basket_rail' | 'legs';
  name: string;
  x: number; 
  y: number;
  z?: number;
  diameter?: number;
  depth?: number;
  tool?: string;
  feedrate?: number;
  isThrough?: boolean;
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
  productionStatus?: ProductionStatus;
  currentStage?: ProductionStage;
}

export interface ProductionNorms {
    totalTimeMinutes: number;
    cuttingTime: number;
    edgingTime: number;
    drillingTime: number;
    assemblyTime: number;
}

// --- NEW STRICT TYPES ---

export type CabinetMaterialType = "Белый" | "Дуб" | "Графит" | "Бетон";

export interface Shelf {
  id: string;
  y: number;
  x: number; // Added for 3D positioning logic
  width: number;
  depth: number;
  type: "открытая" | "закрытая";
}

export interface Drawer {
  id: string;
  y: number;
  x: number; // Added for 3D positioning logic
  width: number;
  height: number;
  depth: number; // Added for construction logic
  handles: boolean;
}

export interface CabinetParams {
  id?: string;
  name: string;
  width: number;      // 400-3000
  height: number;     // 400-3000
  depth: number;      // 300-800
  material: CabinetMaterialType;
  shelves: Shelf[];
  drawers: Drawer[];
  
  // Optional config for compatibility with legacy systems
  baseType?: 'plinth' | 'legs';
  backType?: 'groove' | 'overlay';
}

// Legacy types support for older components not yet refactored
export interface CabinetConfig extends CabinetParams {
    type?: string;
    doorType?: string;
    doorCount?: number;
    facadeStyle?: string;
    construction?: string;
    materialId?: string;
    doorGap?: number;
    coupeGap?: number;
    hardwareType?: string;
}

export interface Section {
    id: number;
    width: number;
    items: any[];
}

export interface CabinetItem {
    id: string;
    type: string;
    y: number;
    height: number;
    name: string;
}

// --- STORAGE & VERSIONING ---
export interface ProjectSnapshot {
  id: string;
  name: string;
  timestamp: number;
  version: number;
  description?: string;
  previewImage?: string;
  panels: Panel[];
  layers?: Layer[];
  config?: CabinetConfig; 
  tags?: string[];
}
