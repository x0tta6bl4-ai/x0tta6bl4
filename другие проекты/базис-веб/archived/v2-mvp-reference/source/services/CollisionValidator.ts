
import { CabinetParams } from "../types";

export interface CollisionResult {
  hasCriticalErrors: boolean;
  errors: Map<string, string>;
  warnings: Map<string, string>;
}

export class CollisionValidator {
  public validate(params: CabinetParams): CollisionResult {
    const errors = new Map<string, string>();
    const warnings = new Map<string, string>();
    
    const { height, shelves, drawers, baseType } = params;
    const baseHeight = baseType === 'legs' ? 100 : 70;
    const THICKNESS = 16; // Standard panel thickness

    // Define vertical usable space
    // Bottom: Base + Bottom Panel
    const minUsableY = baseHeight + THICKNESS;
    // Top: Cabinet Height - Top Panel
    const maxUsableY = height - THICKNESS; 

    // Combine all horizontal elements to check vertical spacing
    const items = [
      ...shelves.map(s => ({ ...s, type: 'shelf' as const, h: THICKNESS })), 
      ...drawers.map(d => ({ ...d, type: 'drawer' as const, h: d.height }))
    ].sort((a, b) => a.y - b.y);

    // 1. Boundary Checks
    items.forEach(item => {
      // Check Bottom (Item Y is usually the bottom-left corner of the item geometry, or center depending on origin. 
      // In this system, Y seems to be bottom coordinate of the element based on addShelf logic).
      if (item.y < minUsableY) {
        errors.set(item.id, `Ниже дна! Мин Y: ${minUsableY}мм`);
      }

      // Check Top
      // Note: item.y is bottom of item. Top of item is y + h.
      if ((item.y + item.h) > maxUsableY) {
        errors.set(item.id, `Выше крыши! Макс Y: ${maxUsableY}мм`);
      }
    });

    // 2. Intersection & Spacing Checks
    for (let i = 0; i < items.length; i++) {
      const current = items[i];
      
      // Check against previous item (if any)
      if (i > 0) {
          const prev = items[i-1];
          const prevTop = prev.y + prev.h;
          const currentBottom = current.y;
          const gap = currentBottom - prevTop;

          if (gap < 0) {
              // Exact Overlap
              const overlapAmount = Math.abs(gap);
              const msg = `Наложение ${overlapAmount}мм!`;
              errors.set(current.id, msg);
              errors.set(prev.id, msg);
          } else if (gap === 0) {
              // Touching
              // Usually okay technically, but often design error if unintended
              // warnings.set(current.id, "Детали касаются");
          } else if (gap < 100) {
              // Functional warning
              // warnings.set(current.id, `Малый зазор (${Math.round(gap)}мм)`);
          } 
          
          // Duplicate position check
          if (Math.abs(gap) < 1) {
               errors.set(current.id, "Дубликат позиции!");
          }
      }
    }

    return {
      hasCriticalErrors: errors.size > 0,
      errors,
      warnings
    };
  }
}
