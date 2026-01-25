
import { CabinetConfig, Section, Shelf, Drawer } from "../types";

export interface ValidationError {
    field?: string;
    message: string;
}

export interface ValidationResult {
    valid: boolean;
    errors: string[];
    warnings: string[];
    corrected?: Shelf[];
}

export class InputValidator {
  validateCabinet(config: CabinetConfig): { isValid: boolean; errors: ValidationError[] } {
    const errors: ValidationError[] = [];
    
    if (!config) {
      return { isValid: false, errors: [{ message: "Configuration is null" }] };
    }
    
    // 1. Strict limits 400-3000
    if (config.width < 400 || config.width > 3000) {
        errors.push({ field: 'width', message: "Ширина должна быть от 400 до 3000 мм" });
    }
    if (config.height < 400 || config.height > 3000) {
        errors.push({ field: 'height', message: "Высота должна быть от 400 до 3000 мм" });
    }
    if (config.depth < 400 || config.depth > 3000) {
        errors.push({ field: 'depth', message: "Глубина должна быть от 400 до 3000 мм" });
    }

    if (config.doorType === 'sliding' && config.depth < 450) {
        errors.push({ field: 'depth', message: "Для шкафа-купе глубина должна быть не менее 450мм" });
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  validateSections(sections: Section[], config: CabinetConfig): { isValid: boolean; errors: ValidationError[] } {
      const errors: ValidationError[] = [];
      const baseH = config.baseType === 'legs' ? 100 : 70;
      
      // Effective internal height bounds
      const minY = baseH + 16; // Base + Bottom Panel thickness
      const maxY = config.height - 16; // Top Panel thickness

      sections.forEach((sec, idx) => {
          // Sort items by Y ascending
          const sortedItems = [...sec.items].sort((a, b) => a.y - b.y);
          
          for (let i = 0; i < sortedItems.length; i++) {
              const item = sortedItems[i];
              
              // 1. Check Bounds
              const itemH = (item.type === 'drawer' || item.type === 'basket') ? item.height : 16; // Shelf thickness
              const itemTop = item.y + itemH;

              if (item.y < minY) {
                  errors.push({ message: `Секция ${idx+1}: "${item.name}" слишком низко (мин Y: ${minY})` });
              }
              if (itemTop > maxY) {
                  errors.push({ message: `Секция ${idx+1}: "${item.name}" слишком высоко (макс Y: ${maxY})` });
              }

              // 2. Check Overlap with next
              const nextItem = sortedItems[i+1];
              if (nextItem) {
                  if (itemTop > nextItem.y) {
                      errors.push({ 
                          message: `Секция ${idx+1}: Пересечение "${item.name}" и "${nextItem.name}" на высоте ${Math.round(item.y)}-${Math.round(itemTop)}` 
                      });
                  }
              }
          }
      });

      return {
          isValid: errors.length === 0,
          errors
      };
  }

  validateShelves(shelves: Shelf[], cabinetHeight: number, drawers: Drawer[] = []): ValidationResult {
      const result: ValidationResult = { valid: true, errors: [], warnings: [] };
      const sorted = [...shelves].sort((a, b) => a.y - b.y);

      // d) Check sort order
      const isSorted = shelves.every((s, i) => i === 0 || s.y >= shelves[i-1].y);
      if (!isSorted) {
          result.warnings.push("Полки не отсортированы по высоте. Рекомендуется авто-сортировка.");
      }

      // c) Max 10 shelves
      if (shelves.length > 10) {
          result.errors.push(`Слишком много полок (${shelves.length}). Максимум 10.`);
      }

      // a) Bounds (50mm margin from top/bottom functional zones)
      const MIN_Y = 100;
      const MAX_Y = cabinetHeight - 100;

      sorted.forEach((shelf, idx) => {
          if (shelf.y < MIN_Y) {
              result.errors.push(`Высота полки #${idx+1} (${Math.round(shelf.y)}мм) слишком мала. Мин: ${MIN_Y}мм.`);
          }
          if (shelf.y > MAX_Y) {
              result.errors.push(`Высота полки #${idx+1} превышает высоту шкафа на ${Math.round(shelf.y - MAX_Y)}мм. Уменьшите Y-позицию.`);
          }

          // b) Gap between shelves
          if (idx > 0) {
              const gap = shelf.y - sorted[idx-1].y;
              if (gap < 200) {
                  result.errors.push(`Расстояние между полками <170мм нарушает ГОСТ. Увеличьте интервал.`);
              }
          }

          // e) Drawer collisions
          const collision = drawers.some(d => Math.abs(d.y - shelf.y) < 50);
          if (collision) {
              result.errors.push(`Полка #${idx+1} пересекается с ящиком на высоте ${Math.round(shelf.y)}`);
          }
      });

      result.valid = result.errors.length === 0;
      
      console.log(`Validation: ${result.errors.length} errors, ${result.warnings.length} warnings`);
      return result;
  }

  autoFixShelves(shelves: Shelf[], cabinetHeight: number): Shelf[] {
      let fixed = [...shelves].sort((a, b) => a.y - b.y);
      const MIN_Y = 100;
      const MAX_Y = cabinetHeight - 100;
      let movedCount = 0;

      for (let i = 0; i < fixed.length; i++) {
          const originalY = fixed[i].y;
          
          // a) Fix Low
          if (fixed[i].y < MIN_Y) {
              fixed[i].y = 300; 
          }
          
          // b) Fix High
          if (fixed[i].y > MAX_Y) {
              fixed[i].y = cabinetHeight - 300;
          }

          // c) Fix Gap
          if (i > 0) {
              const gap = fixed[i].y - fixed[i-1].y;
              if (gap < 200) {
                  // Move current shelf up
                  fixed[i].y = fixed[i-1].y + 200;
              }
          }
          
          // Clamp again if gap pushing pushed it too high
          if (fixed[i].y > MAX_Y) {
             fixed[i].y = MAX_Y;
          }

          if (fixed[i].y !== originalY) {
              console.log(`Auto-corrected: shelf ${i+1} moved from Y:${Math.round(originalY)} to Y:${Math.round(fixed[i].y)}`);
              movedCount++;
          }
      }
      
      // Re-sort just in case
      fixed.sort((a, b) => a.y - b.y);
      
      return fixed;
  }

  getOptimalSpacing(count: number, height: number): number[] {
      const usableHeight = height - 200;
      const gap = usableHeight / (count + 1);
      const result = [];
      
      // Formula: Y = gap * (i+1)
      for (let i = 1; i <= count; i++) {
          result.push(Math.round(gap * i));
      }
      
      return result;
  }
}
