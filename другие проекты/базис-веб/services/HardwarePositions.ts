
import { Panel, Hardware } from "../types";

export interface PositionValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * System 32 standard mebel (меблевой) - стандарт для позиционирования фурнитуры
 * 37mm offset from edge
 * 32mm spacing between holes
 */
export const SYSTEM_32 = {
  EDGE_OFFSET: 37,
  HOLE_SPACING: 32,
} as const;

export class HardwarePositionsValidator {
  /**
   * Validate hardware positions on panels according to System 32 standard
   */
  public static validatePositions(panels: Panel[]): PositionValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    for (const panel of panels) {
      if (!panel.hardware || panel.hardware.length === 0) continue;

      // Check each hardware item
      for (const hardware of panel.hardware) {
        // Validate X position (horizontal)
        if (hardware.x < SYSTEM_32.EDGE_OFFSET) {
          warnings.push(
            `${panel.name}: ${hardware.name} слишком близко к левому краю ` +
            `(${hardware.x}мм < ${SYSTEM_32.EDGE_OFFSET}мм стандарта System 32)`
          );
        }

        if (hardware.x > panel.width - SYSTEM_32.EDGE_OFFSET) {
          warnings.push(
            `${panel.name}: ${hardware.name} слишком близко к правому краю ` +
            `(${hardware.x}мм > ${panel.width - SYSTEM_32.EDGE_OFFSET}мм)`
          );
        }

        // Validate Y position (vertical)
        if (hardware.y < SYSTEM_32.EDGE_OFFSET) {
          warnings.push(
            `${panel.name}: ${hardware.name} слишком близко к верхнему краю ` +
            `(${hardware.y}мм < ${SYSTEM_32.EDGE_OFFSET}мм)`
          );
        }

        if (hardware.y > panel.height - SYSTEM_32.EDGE_OFFSET) {
          warnings.push(
            `${panel.name}: ${hardware.name} слишком близко к нижнему краю ` +
            `(${hardware.y}мм > ${panel.height - SYSTEM_32.EDGE_OFFSET}мм)`
          );
        }

        // Validate hardware diameter if present
        if (hardware.diameter) {
          const minDiameter = 8;
          const maxDiameter = 50;

          if (hardware.diameter < minDiameter) {
            errors.push(
              `${panel.name}: ${hardware.name} имеет слишком маленький диаметр ` +
              `(${hardware.diameter}мм < ${minDiameter}мм)`
            );
          }

          if (hardware.diameter > maxDiameter) {
            errors.push(
              `${panel.name}: ${hardware.name} имеет слишком большой диаметр ` +
              `(${hardware.diameter}мм > ${maxDiameter}мм)`
            );
          }
        }
      }

      // Check spacing between hardware items
      for (let i = 0; i < panel.hardware.length; i++) {
        for (let j = i + 1; j < panel.hardware.length; j++) {
          const h1 = panel.hardware[i];
          const h2 = panel.hardware[j];

          // Calculate minimum distance
          const dx = h2.x - h1.x;
          const dy = h2.y - h1.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          // For holes/screws, maintain System 32 spacing
          if (
            (h1.type === "dowel_hole" || h1.type === "screw") &&
            (h2.type === "dowel_hole" || h2.type === "screw")
          ) {
            if (distance < SYSTEM_32.HOLE_SPACING) {
              warnings.push(
                `${panel.name}: ${h1.name} и ${h2.name} слишком близко друг к другу ` +
                `(${Math.round(distance)}мм < ${SYSTEM_32.HOLE_SPACING}мм стандарта)`
              );
            }
          }
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }
}
