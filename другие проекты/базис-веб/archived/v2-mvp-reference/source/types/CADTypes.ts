
import { Material } from "../types";

export enum ComponentType {
  PART = 'part',
  ASSEMBLY = 'assembly'
}

export enum ConstraintType {
  FIXED = 'fixed',
  COINCIDENT = 'coincident',
  DISTANCE = 'distance',
  PARALLEL = 'parallel',
  PERPENDICULAR = 'perpendicular'
}

export interface Point3D {
  x: number;
  y: number;
  z: number;
}

export interface EulerAngles {
  x: number;
  y: number;
  z: number;
}

export interface Constraint {
  id: string;
  type: ConstraintType;
  elementA: string;
  elementB?: string;
  value?: number;
  axis?: 'x' | 'y' | 'z';
  weight?: number;
}

export interface Component {
  id: string;
  name: string;
  type: ComponentType;
  position: Point3D;
  rotation: EulerAngles;
  scale: Point3D;
  material?: Material;
  children?: Component[];
  properties?: Record<string, any>;
}

export interface Assembly {
  id: string;
  name: string;
  components: Component[];
  constraints: Constraint[];
  metadata?: Record<string, any>;
}
