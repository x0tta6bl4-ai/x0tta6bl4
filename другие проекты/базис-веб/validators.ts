import { Panel } from './types';

const PANEL_CONSTRAINTS = {
  width: { min: 50, max: 5000 },
  height: { min: 50, max: 5000 },
  depth: { min: 4, max: 1000 },
  x: { min: -5000, max: 5000 },
  y: { min: -5000, max: 5000 },
  z: { min: -1000, max: 1000 }
};

export interface ValidationError {
  field: string;
  message: string;
}

export function validatePanelDimensions(width?: number, height?: number, depth?: number): ValidationError[] {
  const errors: ValidationError[] = [];

  if (width !== undefined) {
    if (width < PANEL_CONSTRAINTS.width.min || width > PANEL_CONSTRAINTS.width.max) {
      errors.push({
        field: 'width',
        message: `Ширина должна быть между ${PANEL_CONSTRAINTS.width.min} и ${PANEL_CONSTRAINTS.width.max} мм`
      });
    }
  }

  if (height !== undefined) {
    if (height < PANEL_CONSTRAINTS.height.min || height > PANEL_CONSTRAINTS.height.max) {
      errors.push({
        field: 'height',
        message: `Высота должна быть между ${PANEL_CONSTRAINTS.height.min} и ${PANEL_CONSTRAINTS.height.max} мм`
      });
    }
  }

  if (depth !== undefined) {
    if (depth < PANEL_CONSTRAINTS.depth.min || depth > PANEL_CONSTRAINTS.depth.max) {
      errors.push({
        field: 'depth',
        message: `Глубина должна быть между ${PANEL_CONSTRAINTS.depth.min} и ${PANEL_CONSTRAINTS.depth.max} мм`
      });
    }
  }

  return errors;
}

export function validatePanelPosition(x?: number, y?: number, z?: number): ValidationError[] {
  const errors: ValidationError[] = [];

  if (x !== undefined && (x < PANEL_CONSTRAINTS.x.min || x > PANEL_CONSTRAINTS.x.max)) {
    errors.push({
      field: 'x',
      message: `Позиция X должна быть между ${PANEL_CONSTRAINTS.x.min} и ${PANEL_CONSTRAINTS.x.max} мм`
    });
  }

  if (y !== undefined && (y < PANEL_CONSTRAINTS.y.min || y > PANEL_CONSTRAINTS.y.max)) {
    errors.push({
      field: 'y',
      message: `Позиция Y должна быть между ${PANEL_CONSTRAINTS.y.min} и ${PANEL_CONSTRAINTS.y.max} мм`
    });
  }

  if (z !== undefined && (z < PANEL_CONSTRAINTS.z.min || z > PANEL_CONSTRAINTS.z.max)) {
    errors.push({
      field: 'z',
      message: `Позиция Z должна быть между ${PANEL_CONSTRAINTS.z.min} и ${PANEL_CONSTRAINTS.z.max} мм`
    });
  }

  return errors;
}

export function validatePanelUpdate(changes: Partial<Panel>): ValidationError[] {
  const errors: ValidationError[] = [];

  errors.push(...validatePanelDimensions(changes.width, changes.height, changes.depth));
  errors.push(...validatePanelPosition(changes.x, changes.y, changes.z));

  if (changes.name !== undefined && typeof changes.name === 'string') {
    if (changes.name.trim().length === 0) {
      errors.push({
        field: 'name',
        message: 'Имя панели не может быть пустым'
      });
    }
    if (changes.name.length > 100) {
      errors.push({
        field: 'name',
        message: 'Имя панели не может быть длиннее 100 символов'
      });
    }
  }

  return errors;
}

export function clampPanelValue(field: keyof typeof PANEL_CONSTRAINTS, value: number): number {
  const constraint = PANEL_CONSTRAINTS[field];
  return Math.max(constraint.min, Math.min(constraint.max, value));
}
