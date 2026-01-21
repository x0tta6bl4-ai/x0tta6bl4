/**
 * WeightValidator - Проверка корректности расчета веса
 * 
 * Обнаруженные ошибки:
 * - Неправильные значения толщины (depth) для панелей
 * - Ошибки в расчете объема компонентов
 * - Несоответствие плотности материала
 */

import { Panel } from '../types';

export interface WeightValidationResult {
  valid: boolean;
  warnings: string[];
  errors: string[];
  expectedWeight: number;  // кг
  calculatedWeight: number; // кг
  components: Array<{
    name: string;
    count: number;
    volumeM3: number;
    weightKg: number;
  }>;
}

/**
 * Стандартные толщины материалов (мм)
 */
const STANDARD_THICKNESSES = {
  FACADE: 16,      // Фасады/двери - МДФ 16мм
  SIDE: 16,        // Боки - ЛДСП 16мм
  BACK: 4,         // Задняя стенка - ДВП 4мм
  SHELF: 16,       // Полки - ЛДСП 16мм
  DIVIDER: 16,     // Перегородки - ЛДСП 16мм
  PARTITION: 16,   // Секции - ЛДСП 16мм
  PLINTH: 16,      // Цоколь - ЛДСП 16мм
};

/**
 * Стандартная плотность материалов (кг/м³)
 */
const MATERIAL_DENSITY = {
  'ldsp': 730,     // Ламинированная ДСП
  'mdf': 740,      // МДФ
  'dvp': 200,      // Древесно-волокнистая плита
  'eg-hdf': 600,   // ХДФ/ДВП повышенной плотности
  'default': 730,
};

/**
 * Валидировать параметры панели
 */
export const validatePanelWeights = (panels: Panel[]): WeightValidationResult => {
  const errors: string[] = [];
  const warnings: string[] = [];
  const componentBreakdown: Map<string, any> = new Map();

  let totalWeightCalc = 0;

  panels.forEach((panel, idx) => {
    const panelType = panel.layer || 'unknown';
    
    // 1. Проверить что depth разумен
    if (panel.depth > 100) {
      errors.push(
        `[${idx}] ${panel.name}: depth=${panel.depth}мм - подозрительно велико ` +
        `(стандарт ${panelType}: ${STANDARD_THICKNESSES[panelType as keyof typeof STANDARD_THICKNESSES] || 16}мм)`
      );
    }

    // 2. Проверить что depth соответствует типу панели
    const expectedThickness = STANDARD_THICKNESSES[panelType as keyof typeof STANDARD_THICKNESSES];
    if (expectedThickness && Math.abs(panel.depth - expectedThickness) > 5) {
      warnings.push(
        `[${idx}] ${panel.name} (${panelType}): depth=${panel.depth}мм, ` +
        `ожидается ${expectedThickness}мм`
      );
    }

    // 3. Рассчитать вес
    const volumeM3 = (panel.width / 1000) * (panel.height / 1000) * (panel.depth / 1000);
    const density = MATERIAL_DENSITY[panel.materialId?.toLowerCase() || 'default'] || 730;
    const weightKg = volumeM3 * density;

    totalWeightCalc += weightKg;

    // 4. Отследить по типам
    const key = `${panelType}:${panel.depth}mm`;
    if (componentBreakdown.has(key)) {
      componentBreakdown.get(key).count += 1;
      componentBreakdown.get(key).totalWeight += weightKg;
      componentBreakdown.get(key).totalVolume += volumeM3;
    } else {
      componentBreakdown.set(key, {
        name: `${panelType} (${panel.depth}mm)`,
        count: 1,
        totalWeight: weightKg,
        totalVolume: volumeM3,
      });
    }

    // 5. Проверить нереальные веса одной панели
    if (weightKg > 500) {
      errors.push(
        `[${idx}] ${panel.name}: вес ${weightKg.toFixed(1)}кг - нереально большой! ` +
        `Проверьте размеры: ${panel.width}×${panel.height}×${panel.depth}мм`
      );
    }
  });

  // Рассчитать ожидаемый вес (корректный)
  let expectedWeight = 0;
  panels.forEach(panel => {
    const thickness = panel.depth <= 25 ? panel.depth : 16;  // Если depth > 25мм, это ошибка
    const correctedVolume = (panel.width / 1000) * (panel.height / 1000) * (thickness / 1000);
    const density = MATERIAL_DENSITY[panel.materialId?.toLowerCase() || 'default'] || 730;
    expectedWeight += correctedVolume * density;
  });

  return {
    valid: errors.length === 0,
    warnings,
    errors,
    calculatedWeight: totalWeightCalc,
    expectedWeight,
    components: Array.from(componentBreakdown.values()).map(v => ({
      name: v.name,
      count: v.count,
      volumeM3: v.totalVolume,
      weightKg: v.totalWeight,
    })),
  };
};

/**
 * Форматировать результаты валидации
 */
export const formatValidationReport = (result: WeightValidationResult): string => {
  let report = '=== WEIGHT VALIDATION REPORT ===\n\n';

  report += `Status: ${result.valid ? '✓ VALID' : '✗ INVALID'}\n`;
  report += `Calculated Weight: ${result.calculatedWeight.toFixed(1)} kg\n`;
  report += `Expected Weight: ${result.expectedWeight.toFixed(1)} kg\n`;
  
  if (result.calculatedWeight > result.expectedWeight * 1.5) {
    report += `⚠️ ALARM: Weight is ${(result.calculatedWeight / result.expectedWeight).toFixed(1)}x higher than expected!\n\n`;
  }

  if (result.errors.length > 0) {
    report += `ERRORS (${result.errors.length}):\n`;
    result.errors.forEach(e => report += `  ✗ ${e}\n`);
    report += '\n';
  }

  if (result.warnings.length > 0) {
    report += `WARNINGS (${result.warnings.length}):\n`;
    result.warnings.forEach(w => report += `  ⚠️  ${w}\n`);
    report += '\n';
  }

  report += `COMPONENT BREAKDOWN:\n`;
  result.components.forEach(c => {
    report += `  ${c.name}: ${c.count}× = ${c.volumeM3.toFixed(4)}m³ / ${c.weightKg.toFixed(1)}kg\n`;
  });

  return report;
};

/**
 * Проверить одну конкретную панель
 */
export const validateSinglePanel = (panel: Panel): { valid: boolean; message: string } => {
  // Максимальные разумные размеры для мебели
  if (panel.width > 2500 || panel.height > 2500 || panel.depth > 200) {
    return {
      valid: false,
      message: `Размеры панели неправдоподобны: ${panel.width}×${panel.height}×${panel.depth}мм`,
    };
  }

  // Проверка глубины
  if (panel.depth > 100 && panel.layer !== 'back') {
    return {
      valid: false,
      message: `Толщина ${panel.depth}мм подозрительна. Обычно: 4-18мм`,
    };
  }

  // Рассчитать вес
  const volumeM3 = (panel.width / 1000) * (panel.height / 1000) * (panel.depth / 1000);
  const weightKg = volumeM3 * 730;

  if (weightKg > 600) {
    return {
      valid: false,
      message: `Вес одной панели ${weightKg.toFixed(1)}кг - невозможно! Проверьте параметры.`,
    };
  }

  return {
    valid: true,
    message: `OK: ${panel.name} = ${weightKg.toFixed(1)}kg (${volumeM3.toFixed(4)}m³)`,
  };
};
