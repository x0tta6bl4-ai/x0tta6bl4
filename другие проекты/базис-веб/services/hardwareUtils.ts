/**
 * Утилиты для работы с крепежом (Hardware)
 * Содержит логику валидации, оптимизации и интеллектуальной расстановки
 */

import { Panel, Hardware, Axis } from '../types';

// ============= КОНФИГУРАЦИЯ =============

export interface HardwareConfig {
  screw: {
    diameter: number;
    minEdgeDistance: number;    // минимум до края
    minHardwareDistance: number; // минимум между крепежами
    edgeDist: number;            // стандартный отступ
    name: string;
    color: number;
  };
  minifix_cam: {
    diameter: number;
    minEdgeDistance: number;
    minHardwareDistance: number;
    edgeDist: number;
    name: string;
    color: number;
  };
  dowel: {
    diameter: number;
    minEdgeDistance: number;
    minHardwareDistance: number;
    edgeDist: number;
    name: string;
    color: number;
  };
  handle: {
    width: number;
    minEdgeDistance: number;
    name: string;
    color: number;
  };
  shelf_support: {
    diameter: number;
    minEdgeDistance: number;
    minHardwareDistance: number;
    edgeDist: number;
    name: string;
    color: number;
  };
  hinge_cup: {
    diameter: number;
    minEdgeDistance: number;
    minHardwareDistance: number;
    edgeDist: number;
    name: string;
    color: number;
  };
}

export const HARDWARE_CONFIG: HardwareConfig = {
  screw: {
    diameter: 5,
    minEdgeDistance: 8,
    minHardwareDistance: 20,
    edgeDist: 9,
    name: 'Конфирмат 7x50',
    color: 0x3b82f6 // blue
  },
  minifix_cam: {
    diameter: 15,
    minEdgeDistance: 20,
    minHardwareDistance: 30,
    edgeDist: 34,
    name: 'Эксцентрик Д15',
    color: 0x10b981 // green
  },
  dowel: {
    diameter: 8,
    minEdgeDistance: 8,
    minHardwareDistance: 20,
    edgeDist: 8,
    name: 'Шкант Д8',
    color: 0xf59e0b // amber
  },
  handle: {
    width: 128,
    minEdgeDistance: 30,
    name: 'Ручка',
    color: 0xec4899 // pink
  },
  shelf_support: {
    diameter: 5,
    minEdgeDistance: 8,
    minHardwareDistance: 100,
    edgeDist: 8,
    name: 'Полкодержатель',
    color: 0x8b5cf6 // purple
  },
  hinge_cup: {
    diameter: 26,
    minEdgeDistance: 20,
    minHardwareDistance: 30,
    edgeDist: 34,
    name: 'Петля мебельная 26мм',
    color: 0x8b9467 // brown
  }
};

// ============= ВАЛИДАЦИЯ =============

export interface ValidationError {
  type: 'edge_distance' | 'hardware_distance' | 'out_of_bounds';
  hardware: Hardware;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * Проверить расстояние между крепежами и краями
 */
export const validateHardwarePositions = (
  panel: Panel,
  hardware: Hardware[]
): ValidationError[] => {
  const errors: ValidationError[] = [];
  
  hardware.forEach((hw, index) => {
    const cfg = HARDWARE_CONFIG[hw.type as keyof HardwareConfig];
    if (!cfg || 'minEdgeDistance' in cfg === false) return;

    const minEdgeDist = (cfg as any).minEdgeDistance || 10;
    const minHwDist = (cfg as any).minHardwareDistance || 20;

    // Проверка расстояния от краев
    const minDistToEdge = Math.min(
      hw.x - minEdgeDist,
      hw.y - minEdgeDist,
      panel.width - hw.x - minEdgeDist,
      panel.height - hw.y - minEdgeDist
    );

    if (minDistToEdge < 0) {
      errors.push({
        type: 'edge_distance',
        hardware: hw,
        message: `${hw.name} слишком близко к краю (расстояние ${Math.abs(minDistToEdge)}мм)`,
        severity: 'error'
      });
    }

    // Проверка расстояния между крепежами
    hardware.forEach((other, otherIndex) => {
      if (index >= otherIndex) return;

      const dist = Math.hypot(hw.x - other.x, hw.y - other.y);
      if (dist < minHwDist) {
        errors.push({
          type: 'hardware_distance',
          hardware: hw,
          message: `${hw.name} слишком близко к другому крепежу (расстояние ${Math.round(dist)}мм < ${minHwDist}мм)`,
          severity: 'warning'
        });
      }
    });

    // Проверка, что находится в пределах панели
    if (hw.x < 0 || hw.x > panel.width || hw.y < 0 || hw.y > panel.height) {
      errors.push({
        type: 'out_of_bounds',
        hardware: hw,
        message: `${hw.name} находится вне границ панели`,
        severity: 'error'
      });
    }
  });

  return errors;
};

// ============= ИНТЕЛЛЕКТУАЛЬНЫЙ ВЫБОР ТИПА =============

export interface JointInfo {
  type: 'corner' | 'tee' | 'unknown';
  length: number;           // длина линии стыка
  strength: 'light' | 'medium' | 'heavy'; // требуемая прочность
}

/**
 * Определить оптимальный тип крепежа для стыка
 */
export const selectOptimalHardwareType = (joint: JointInfo): Hardware['type'] => {
  // Угловой стык (небольшая нагрузка)
  if (joint.type === 'corner') {
    if (joint.length < 200) return 'dowel';      // Маленький угол -> шкант
    if (joint.strength === 'heavy') return 'screw'; // Тяжелая нагрузка -> конфирмат
    return 'minifix_cam'; // Средняя нагрузка -> эксцентрик
  }

  // Т-образный стык (большая нагрузка)
  if (joint.type === 'tee') {
    if (joint.strength === 'heavy') return 'screw';   // Тяжелая -> конфирмат (постоянное)
    if (joint.strength === 'medium') return 'minifix_cam'; // Средняя -> эксцентрик
    return 'dowel'; // Легкая -> шкант
  }

  return 'screw'; // По умолчанию конфирмат
};

/**
 * Определить требуемую прочность стыка на основе панелей
 */
export const estimateJointStrength = (
  panel1: Panel,
  panel2: Panel,
  overlapLength: number
): JointInfo['strength'] => {
  // Если одна из панелей - хрупкое стекло/зеркало -> легкая нагрузка
  if (panel1.materialId === 'Стекло' || panel2.materialId === 'Стекло') return 'light';

  // Тонкие панели -> легкая нагрузка
  if (panel1.depth < 8 || panel2.depth < 8) return 'light';

  // Большая площадь контакта -> тяжелая нагрузка
  if (overlapLength > 800) return 'heavy';

  // Если участвует фасад -> средняя нагрузка
  return 'medium';
};

// ============= РАСЧЕТ ПОЗИЦИЙ =============

/**
 * Вычислить позиции для стандартного комплекта (4 угла)
 */
export const calculateStandardPositions = (
  panel: Panel,
  type: Hardware['type'],
  useCenter: boolean = false,
  customOffset?: number
): { x: number; y: number }[] => {
  const cfg = HARDWARE_CONFIG[type];
  if (!cfg || 'edgeDist' in cfg === false) return [];

  const edgeDist = customOffset ?? (cfg as any).edgeDist ?? 9;
  const defaultOffset = 50;

  const positions = [
    { x: edgeDist, y: defaultOffset },                        // Верх-слева
    { x: edgeDist, y: panel.height - defaultOffset },         // Низ-слева
    { x: panel.width - edgeDist, y: defaultOffset },          // Верх-справа
    { x: panel.width - edgeDist, y: panel.height - defaultOffset } // Низ-справа
  ];

  // Добавить центральные крепежи для глубоких панелей
  if (useCenter && panel.height > 600) {
    positions.push(
      { x: edgeDist, y: panel.height / 2 },
      { x: panel.width - edgeDist, y: panel.height / 2 }
    );
  }

  return positions.filter(pos => 
    pos.x > 0 && pos.x < panel.width && 
    pos.y > 0 && pos.y < panel.height
  );
};

/**
 * Вычислить позиции вдоль линии (для автоматической расстановки)
 */
export const calculateLinePositions = (
  start: number,
  length: number,
  offset: number = 50
): number[] => {
  const positions: number[] = [];

  if (length <= 0) return positions;

  if (length > 600) {
    // Три точки: начало, центр, конец
    positions.push(start + offset);
    positions.push(start + length / 2);
    positions.push(start + length - offset);
  } else if (length > 200) {
    // Две точки: начало, конец
    positions.push(start + offset);
    positions.push(start + length - offset);
  } else {
    // Одна точка: центр
    positions.push(start + length / 2);
  }

  return positions;
};

// ============= СТАТИСТИКА =============

export interface HardwareStats {
  total: number;
  byType: Record<string, number>;
  byPanel: Record<string, number>;
  weight: number; // примерный вес в граммах
}

/**
 * Рассчитать статистику по крепежу
 */
export const calculateHardwareStats = (panels: Panel[]): HardwareStats => {
  const stats: HardwareStats = {
    total: 0,
    byType: {},
    byPanel: {},
    weight: 0
  };

  // Примерные веса (граммы)
  const weights: Record<string, number> = {
    screw: 4,      // Конфирмат 7x50
    minifix_cam: 8,    // Эксцентрик
    dowel: 3,      // Шкант
    handle: 200,   // Ручка
    hinge_cup: 150,    // Петля
    shelf_support: 5
  };

  panels.forEach(panel => {
    const panelCount = panel.hardware.length;
    stats.total += panelCount;
    stats.byPanel[panel.id] = panelCount;

    panel.hardware.forEach(hw => {
      stats.byType[hw.type] = (stats.byType[hw.type] || 0) + 1;
      stats.weight += weights[hw.type] || 10;
    });
  });

  return stats;
};

// ============= ФОРМАТИРОВАНИЕ =============

/**
 * Получить цвет для типа крепежа в 3D
 */
export const getHardwareColor = (type: Hardware['type']): number => {
  const cfg = HARDWARE_CONFIG[type];
  return (cfg as any)?.color || 0x888888;
};

/**
 * Получить размеры для рендеринга крепежа
 */
export const getHardwareDimensions = (type: Hardware['type']) => {
  const cfg = HARDWARE_CONFIG[type];
  
  switch (type) {
    case 'screw':
      return { radius: 2.5, height: 4, shape: 'cone' as const };
    case 'minifix_cam':
    case 'minifix_pin':
      return { radius: 7.5, height: 3, shape: 'cylinder' as const };
    case 'dowel':
      return { radius: 4, height: 3, shape: 'cylinder' as const };
    case 'handle':
      return { width: 64, height: 8, shape: 'bar' as const };
    case 'shelf_support':
      return { radius: 2.5, height: 4, shape: 'cone' as const };
    default:
      return { radius: 2, height: 4, shape: 'cylinder' as const };
  }
};

/**
 * Получить описание крепежа для экспорта
 */
export const formatHardwareForExport = (hw: Hardware): string => {
  const specs: Record<string, string> = {
    screw: 'Конфирмат 7×50 (Д5)',
    minifix_cam: 'Эксцентрик Д15×34',
    minifix_pin: 'Шток эксцентрика',
    dowel: 'Шкант деревянный Д8×40',
    handle: 'Ручка-скоба',
    hinge_cup: 'Петля мебельная 26мм',
    shelf_support: 'Полкодержатель Д5'
  };

  return `${specs[hw.type] || hw.type} @ (${hw.x}, ${hw.y})`;
};

// ============= ОПТИМИЗАЦИЯ =============

/**
 * Определить минимально необходимое количество крепежей
 */
export const calculateMinimalHardware = (
  panel: Panel,
  stiffnessRequired: 'light' | 'medium' | 'heavy' = 'medium'
): number => {
  const area = panel.width * panel.height;

  // На каждые 100см² нужен минимум 1 крепеж
  const baseCount = Math.ceil(area / 10000);

  switch (stiffnessRequired) {
    case 'light':
      return Math.max(2, baseCount);      // Минимум 2
    case 'medium':
      return Math.max(4, baseCount * 2);  // Минимум 4, в 2 раза больше
    case 'heavy':
      return Math.max(6, baseCount * 3);  // Минимум 6, в 3 раза больше
  }
};

/**
 * Предложить оптимальное расположение крепежа
 */
export const suggestOptimalLayout = (
  panel: Panel,
  existingHardware: Hardware[]
): { recommendations: string[]; suggested: Hardware[] } => {
  const recommendations: string[] = [];
  const suggested: Hardware[] = [];

  const errors = validateHardwarePositions(panel, existingHardware);
  if (errors.length > 0) {
    recommendations.push(`Найдено ${errors.length} ошибок размещения`);
  }

  const stats = calculateHardwareStats([panel]);
  const minimal = calculateMinimalHardware(panel, 'medium');

  if (stats.total < minimal) {
    recommendations.push(
      `Недостаточно крепежа: ${stats.total} < ${minimal} (рекомендуется)`
    );
  }

  if (panel.width > 1200 && !existingHardware.some(h => h.x > panel.width / 3 && h.x < 2 * panel.width / 3)) {
    recommendations.push('Рекомендуется добавить центральное крепление для широких панелей');
  }

  return { recommendations, suggested };
};
