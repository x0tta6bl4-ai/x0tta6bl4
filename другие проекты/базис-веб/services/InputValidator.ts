/**
 * InputValidator - Centralized input validation service
 * Phase 3 Implementation
 * 
 * Provides comprehensive validation for all user inputs with:
 * - Type checking and coercion
 * - Range validation
 * - Format validation
 * - Batch validation with detailed error reporting
 * - Input sanitization
 */

import { Panel, Hardware, Material, CabinetConfig } from '../types';

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  sanitized?: unknown;
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
  severity: 'critical' | 'error' | 'warning';
}

export interface ValidationWarning {
  field: string;
  message: string;
}

export interface ValidationRule {
  type: 'string' | 'number' | 'boolean' | 'object';
  required?: boolean;
  min?: number;
  max?: number;
  pattern?: RegExp;
  custom?: (value: unknown) => boolean | string;
  transform?: (value: unknown) => unknown;
}

/**
 * Constraint definitions for furniture dimensions
 * Based on industry standards (ГОСТ, Европейские стандарты)
 */
const CONSTRAINTS = {
  panel: {
    width: { min: 50, max: 5000, unit: 'мм' },
    height: { min: 50, max: 5000, unit: 'мм' },
    depth: { min: 4, max: 1000, unit: 'мм' },
    x: { min: -5000, max: 5000, unit: 'мм' },
    y: { min: -5000, max: 5000, unit: 'мм' },
    z: { min: -1000, max: 1000, unit: 'мм' },
  },
  cabinet: {
    width: { min: 200, max: 5000, unit: 'мм', description: 'Ширина шкафа' },
    height: { min: 400, max: 3000, unit: 'мм', description: 'Высота шкафа' },
    depth: { min: 350, max: 700, unit: 'мм', description: 'Глубина шкафа' },
  },
  drawer: {
    height: { min: 30, max: 500, unit: 'мм' },
    depth: { min: 300, max: 650, unit: 'мм' },
  },
  shelf: {
    thickness: { min: 15, max: 50, unit: 'мм' },
    maxSpan: { min: 800, max: 3000, unit: 'мм' }, // Max shelf span without support
  },
  name: {
    minLength: 1,
    maxLength: 100,
  },
  project: {
    nameMaxLength: 255,
  },
};

/**
 * InputValidator class - Centralized validation service
 * 
 * Usage:
 * ```typescript
 * const validator = new InputValidator();
 * const result = validator.validatePanel(panelData);
 * if (!result.isValid) {
 *   result.errors.forEach(err => console.error(err.message));
 * }
 * ```
 */
export class InputValidator {
  /**
   * Validate panel dimensions and position
   */
  validatePanel(panel: Partial<Panel>): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // Width validation
    if (panel.width !== undefined) {
      const widthResult = this.validateDimension(
        panel.width,
        CONSTRAINTS.panel.width,
        'width',
        'Ширина'
      );
      if (!widthResult.isValid) {
        errors.push(...widthResult.errors);
      }
    }

    // Height validation
    if (panel.height !== undefined) {
      const heightResult = this.validateDimension(
        panel.height,
        CONSTRAINTS.panel.height,
        'height',
        'Высота'
      );
      if (!heightResult.isValid) {
        errors.push(...heightResult.errors);
      }
    }

    // Depth validation
    if (panel.depth !== undefined) {
      const depthResult = this.validateDimension(
        panel.depth,
        CONSTRAINTS.panel.depth,
        'depth',
        'Глубина'
      );
      if (!depthResult.isValid) {
        errors.push(...depthResult.errors);
      }
    }

    // Position validation
    if (panel.x !== undefined) {
      const xResult = this.validateDimension(
        panel.x,
        CONSTRAINTS.panel.x,
        'x',
        'Позиция X'
      );
      if (!xResult.isValid) errors.push(...xResult.errors);
    }

    if (panel.y !== undefined) {
      const yResult = this.validateDimension(
        panel.y,
        CONSTRAINTS.panel.y,
        'y',
        'Позиция Y'
      );
      if (!yResult.isValid) errors.push(...yResult.errors);
    }

    if (panel.z !== undefined) {
      const zResult = this.validateDimension(
        panel.z,
        CONSTRAINTS.panel.z,
        'z',
        'Позиция Z'
      );
      if (!zResult.isValid) errors.push(...zResult.errors);
    }

    // Name validation
    if (panel.name !== undefined) {
      const nameResult = this.validateName(panel.name, 'name', 'Имя панели');
      if (!nameResult.isValid) {
        errors.push(...nameResult.errors);
      }
    }

    // Material ID validation
    if (panel.materialId !== undefined && typeof panel.materialId !== 'string') {
      errors.push({
        field: 'materialId',
        message: 'ID материала должен быть строкой',
        code: 'INVALID_TYPE',
        severity: 'error',
      });
    }

    // Hardware validation
    if (panel.hardware !== undefined && !Array.isArray(panel.hardware)) {
      errors.push({
        field: 'hardware',
        message: 'Hardware должен быть массивом',
        code: 'INVALID_TYPE',
        severity: 'error',
      });
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      sanitized: this.sanitizePanel(panel),
    };
  }

  /**
   * Validate cabinet configuration
   */
  validateCabinet(cabinet: Partial<CabinetConfig>): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // Width validation
    if (cabinet.width !== undefined) {
      const widthResult = this.validateDimension(
        cabinet.width,
        CONSTRAINTS.cabinet.width,
        'width',
        'Ширина шкафа'
      );
      if (!widthResult.isValid) errors.push(...widthResult.errors);
    }

    // Height validation
    if (cabinet.height !== undefined) {
      const heightResult = this.validateDimension(
        cabinet.height,
        CONSTRAINTS.cabinet.height,
        'height',
        'Высота шкафа'
      );
      if (!heightResult.isValid) errors.push(...heightResult.errors);
    }

    // Depth validation
    if (cabinet.depth !== undefined) {
      const depthResult = this.validateDimension(
        cabinet.depth,
        CONSTRAINTS.cabinet.depth,
        'depth',
        'Глубина шкафа'
      );
      if (!depthResult.isValid) errors.push(...depthResult.errors);
    }

    // Name validation
    if (cabinet.name !== undefined) {
      const nameResult = this.validateName(
        cabinet.name,
        'name',
        'Имя шкафа'
      );
      if (!nameResult.isValid) errors.push(...nameResult.errors);
    }

    // Material ID validation
    if (cabinet.materialId !== undefined) {
      if (typeof cabinet.materialId !== 'string' || cabinet.materialId.length === 0) {
        errors.push({
          field: 'materialId',
          message: 'ID материала должен быть непустой строкой',
          code: 'INVALID_VALUE',
          severity: 'error',
        });
      }
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      sanitized: this.sanitizeCabinet(cabinet),
    };
  }

  /**
   * Validate user input string with constraints
   */
  validateInput(value: unknown, rules: ValidationRule, fieldName: string): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    let sanitized = value;

    // Type checking
    const actualType = Array.isArray(value) ? 'array' : typeof value;
    if (value === null || value === undefined) {
      if (rules.required) {
        errors.push({
          field: fieldName,
          message: `${fieldName} обязателен`,
          code: 'REQUIRED',
          severity: 'error',
        });
      }
      return { isValid: errors.length === 0, errors, warnings, sanitized: null };
    }

    // Type coercion and validation
    if (rules.type === 'number') {
      const num = Number(value);
      if (isNaN(num)) {
        errors.push({
          field: fieldName,
          message: `${fieldName} должен быть числом`,
          code: 'INVALID_TYPE',
          severity: 'error',
        });
      } else {
        if (rules.min !== undefined && num < rules.min) {
          errors.push({
            field: fieldName,
            message: `${fieldName} должен быть больше или равен ${rules.min}`,
            code: 'MIN_CONSTRAINT',
            severity: 'error',
          });
        }
        if (rules.max !== undefined && num > rules.max) {
          errors.push({
            field: fieldName,
            message: `${fieldName} должен быть меньше или равен ${rules.max}`,
            code: 'MAX_CONSTRAINT',
            severity: 'error',
          });
        }
        sanitized = num;
      }
    } else if (rules.type === 'string') {
      if (typeof value !== 'string') {
        sanitized = String(value);
      }
      if (rules.pattern && !rules.pattern.test(String(sanitized))) {
        errors.push({
          field: fieldName,
          message: `${fieldName} не соответствует требуемому формату`,
          code: 'PATTERN_MISMATCH',
          severity: 'error',
        });
      }
    }

    // Custom validation
    if (rules.custom) {
      const result = rules.custom(sanitized);
      if (result !== true && typeof result === 'string') {
        errors.push({
          field: fieldName,
          message: result,
          code: 'CUSTOM_VALIDATION',
          severity: 'error',
        });
      }
    }

    // Transform
    if (rules.transform) {
      try {
        sanitized = rules.transform(sanitized);
      } catch (error) {
        errors.push({
          field: fieldName,
          message: `Ошибка при преобразовании ${fieldName}`,
          code: 'TRANSFORM_ERROR',
          severity: 'error',
        });
      }
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      sanitized,
    };
  }

  /**
   * Validate multiple fields at once
   */
  validateBatch(data: Record<string, unknown>, schema: Record<string, ValidationRule>): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    const sanitized: Record<string, unknown> = {};

    for (const [field, rules] of Object.entries(schema)) {
      const result = this.validateInput(data[field], rules, field);
      errors.push(...result.errors);
      warnings.push(...result.warnings);
      if (result.sanitized !== undefined) {
        sanitized[field] = result.sanitized;
      }
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      sanitized,
    };
  }

  /**
   * Private helper methods
   */

  private validateDimension(
    value: unknown,
    constraint: { min: number; max: number; unit: string },
    fieldCode: string,
    fieldLabel: string
  ): ValidationResult {
    const errors: ValidationError[] = [];

    const num = Number(value);
    if (isNaN(num)) {
      errors.push({
        field: fieldCode,
        message: `${fieldLabel} должна быть числом`,
        code: 'INVALID_TYPE',
        severity: 'error',
      });
      return { isValid: false, errors, warnings: [] };
    }

    if (num < constraint.min) {
      errors.push({
        field: fieldCode,
        message: `${fieldLabel} не может быть меньше ${constraint.min} ${constraint.unit}`,
        code: 'MIN_CONSTRAINT',
        severity: 'error',
      });
    }

    if (num > constraint.max) {
      errors.push({
        field: fieldCode,
        message: `${fieldLabel} не может быть больше ${constraint.max} ${constraint.unit}`,
        code: 'MAX_CONSTRAINT',
        severity: 'error',
      });
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings: [],
      sanitized: num,
    };
  }

  private validateName(
    value: unknown,
    fieldCode: string,
    fieldLabel: string
  ): ValidationResult {
    const errors: ValidationError[] = [];

    if (typeof value !== 'string') {
      errors.push({
        field: fieldCode,
        message: `${fieldLabel} должно быть строкой`,
        code: 'INVALID_TYPE',
        severity: 'error',
      });
      return { isValid: false, errors, warnings: [] };
    }

    const trimmed = value.trim();
    if (trimmed.length < CONSTRAINTS.name.minLength) {
      errors.push({
        field: fieldCode,
        message: `${fieldLabel} не может быть пустым`,
        code: 'MIN_LENGTH',
        severity: 'error',
      });
    }

    if (trimmed.length > CONSTRAINTS.name.maxLength) {
      errors.push({
        field: fieldCode,
        message: `${fieldLabel} не может быть длиннее ${CONSTRAINTS.name.maxLength} символов`,
        code: 'MAX_LENGTH',
        severity: 'error',
      });
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings: [],
      sanitized: trimmed,
    };
  }

  private sanitizePanel(panel: Partial<Panel>): Partial<Panel> {
    const sanitized: Partial<Panel> = {};

    if (panel.id !== undefined) sanitized.id = String(panel.id);
    if (panel.width !== undefined) sanitized.width = Math.max(
      CONSTRAINTS.panel.width.min,
      Math.min(CONSTRAINTS.panel.width.max, Number(panel.width) || 0)
    );
    if (panel.height !== undefined) sanitized.height = Math.max(
      CONSTRAINTS.panel.height.min,
      Math.min(CONSTRAINTS.panel.height.max, Number(panel.height) || 0)
    );
    if (panel.depth !== undefined) sanitized.depth = Math.max(
      CONSTRAINTS.panel.depth.min,
      Math.min(CONSTRAINTS.panel.depth.max, Number(panel.depth) || 0)
    );
    if (panel.x !== undefined) sanitized.x = Math.max(
      CONSTRAINTS.panel.x.min,
      Math.min(CONSTRAINTS.panel.x.max, Number(panel.x) || 0)
    );
    if (panel.y !== undefined) sanitized.y = Math.max(
      CONSTRAINTS.panel.y.min,
      Math.min(CONSTRAINTS.panel.y.max, Number(panel.y) || 0)
    );
    if (panel.z !== undefined) sanitized.z = Math.max(
      CONSTRAINTS.panel.z.min,
      Math.min(CONSTRAINTS.panel.z.max, Number(panel.z) || 0)
    );
    if (panel.name !== undefined) sanitized.name = String(panel.name).trim();
    if (panel.materialId !== undefined) sanitized.materialId = String(panel.materialId);

    return sanitized;
  }

  private sanitizeCabinet(cabinet: Partial<CabinetConfig>): Partial<CabinetConfig> {
    const sanitized: Partial<CabinetConfig> = {};

    if (cabinet.name !== undefined) sanitized.name = String(cabinet.name).trim();
    if (cabinet.width !== undefined) sanitized.width = Math.max(
      CONSTRAINTS.cabinet.width.min,
      Math.min(CONSTRAINTS.cabinet.width.max, Number(cabinet.width) || 0)
    );
    if (cabinet.height !== undefined) sanitized.height = Math.max(
      CONSTRAINTS.cabinet.height.min,
      Math.min(CONSTRAINTS.cabinet.height.max, Number(cabinet.height) || 0)
    );
    if (cabinet.depth !== undefined) sanitized.depth = Math.max(
      CONSTRAINTS.cabinet.depth.min,
      Math.min(CONSTRAINTS.cabinet.depth.max, Number(cabinet.depth) || 0)
    );
    if (cabinet.materialId !== undefined) sanitized.materialId = String(cabinet.materialId);

    return sanitized;
  }

  /**
   * Clamp dimension value to valid range
   */
  clampDimension(field: keyof typeof CONSTRAINTS.panel, value: number): number {
    const constraint = CONSTRAINTS.panel[field];
    return Math.max(constraint.min, Math.min(constraint.max, value));
  }

  /**
   * Get all available constraints
   */
  getConstraints() {
    return CONSTRAINTS;
  }
}

// Export singleton instance for application-wide use
export const inputValidator = new InputValidator();
