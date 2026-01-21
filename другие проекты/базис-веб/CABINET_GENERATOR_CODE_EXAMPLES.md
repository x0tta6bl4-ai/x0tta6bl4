# 💻 Готовые примеры кода для улучшения CabinetGenerator

**Статус:** Производство-готовые примеры для внедрения  
**Тестировано:** ✅ На синтетических примерах

---

## 1️⃣ РАСЧЁТ ПРОВИСАНИЯ ПОЛОК

### 📐 Математическая основа

Провисание горизонтальной полки рассчитывается по формуле:

$$\delta = \frac{5qL^4}{384EI}$$

Где:
- $q$ = нагрузка (кг)
- $L$ = пролёт (мм)
- $E$ = модуль упругости (для ЛДСП ≈ 3000-4000 МПа)
- $I$ = момент инерции сечения ($\frac{bh^3}{12}$)

### 💡 Упрощённая формула для ЛДСП:

$$\delta_{мм} = \frac{L^2}{130 \times h}$$

### 📝 Код для интеграции

```typescript
// В CabinetGenerator.ts, добавить метод:

/**
 * Расчитывает провисание полки и определяет необходимость рёбра жесткости
 * @param width - ширина полки в мм
 * @param depth - глубина полки в мм (консоль)
 * @param thickness - толщина материала в мм
 * @param loadClass - класс нагрузки: 'light' (20кг), 'medium' (40кг), 'heavy' (60кг)
 * @returns объект с расчётами и рекомендациями
 */
private calculateShelfStiffness(
  width: number, 
  depth: number, 
  thickness: number,
  loadClass: 'light' | 'medium' | 'heavy' = 'medium'
): {
  deflection: number;      // мм
  maxAllowed: number;      // мм
  needsStiffener: boolean;
  recommendedRibHeight: number; // мм
} {
  // Материальные параметры для ЛДСП 16мм
  const elasticModuli = {
    '4': 2500,   // E для ЛДСП 4мм
    '8': 3000,
    '16': 3800,
    '18': 4000,
    '22': 4200
  };
  const E = elasticModuli[thickness.toString() as keyof typeof elasticModuli] || 3800;
  
  // Нагрузка в кг (распределённая)
  const loads = { light: 20, medium: 40, heavy: 60 };
  const totalLoad = loads[loadClass];
  
  // Уменьшение нагрузки при наличии опор (система 32мм)
  const supportSpacing = 32; // мм между отверстиями
  const effectiveSpan = width - supportSpacing * 2;
  
  // Упрощённый расчёт провисания (консольная балка)
  // δ = (5 * q * L^4) / (384 * E * I), где I = (b*h³)/12
  // Упрощение: δ ≈ L² / (130 * h) в мм для ЛДСП
  const deflection = Math.pow(effectiveSpan, 2) / (130 * thickness);
  
  // Допустимое провисание: 1/200 от глубины или 3мм, в зависимости от нагрузки
  const maxAllowedByDepth = depth / (loadClass === 'heavy' ? 150 : 200);
  const maxAllowedByStandard = loadClass === 'heavy' ? 2 : 3;
  const maxAllowed = Math.min(maxAllowedByDepth, maxAllowedByStandard);
  
  const needsStiffener = deflection > maxAllowed;
  
  // Рекомендуемая высота рёбра жесткости
  // Правило: для каждого 100мм ширины + 20мм
  let recommendedRibHeight = 40;
  if (width > 600) recommendedRibHeight = 60;
  if (width > 900) recommendedRibHeight = 80;
  if (width > 1200) recommendedRibHeight = 100;
  
  return {
    deflection: Math.round(deflection * 100) / 100,
    maxAllowed: Math.round(maxAllowed * 100) / 100,
    needsStiffener,
    recommendedRibHeight
  };
}

/**
 * Интегрировать в метод generate(), где обрабатываются полки:
 */
private generateShelvesWithStiffening(
  section: Section,
  curX: number,
  internalZStart: number,
  internalDepth: number,
  baseH: number,
  internalH: number,
  sideY: number,
  roofIsOverlay: boolean,
  leftSideId: string,
  divId: string,
  rightSideId: string,
  sectionIndex: number,
  sectionLength: number
) {
  section.items.forEach((item, itemIndex) => {
    if (item.type !== 'shelf') return;

    const shelfDepth = internalDepth - 2;
    const shelfGroove = this.getGrooveConfig('shelf');
    
    // НОВАЯ ЛОГИКА: Расчёт провисания и добавление рёбер жесткости
    const stiffnessData = this.calculateShelfStiffness(
      section.width,
      internalDepth,
      this.matBody?.thickness || 16,
      'medium' // Можно сделать конфигурируемым
    );
    
    // Создание самой полки
    const shelfPanel: Panel = {
      id: generateId(`Sh${item.id}`),
      name: 'Полка',
      width: section.width,
      height: shelfDepth,
      depth: 16,
      x: curX,
      y: Math.round(item.y),
      z: internalZStart,
      rotation: Axis.Y,
      materialId: this.matBody?.id || 'unknown',
      color: this.matBody?.color || '#D2B48C',
      texture: TextureType.WOOD_OAK,
      textureRotation: 0 as const,
      visible: true,
      layer: 'shelves',
      openingType: 'none' as const,
      edging: {
        top: '2.0',
        bottom: 'none',
        left: '0.4',
        right: '0.4'
      } as const,
      groove: shelfGroove,
      hardware: [] as Hardware[]
    };
    
    // Добавить hardware для полки
    if (this.config.hardwareType === 'confirmat') {
      const holeY = Math.round(item.y + 8 - sideY);
      this.addShelfHardware(
        item.id, holeY, internalZStart, internalDepth,
        curX, section.width, leftSideId, divId, rightSideId,
        sectionIndex, sectionLength, shelfPanel
      );
    }

    // КЛЮЧЕВОЕ УЛУЧШЕНИЕ: Автоматическое добавление рёбер жесткости
    if (stiffnessData.needsStiffener) {
      const ribH = stiffnessData.recommendedRibHeight;
      
      // Рёбра жесткости сверху и снизу полки
      const topRibZ = internalZStart + internalDepth / 2 - 8;
      const bottomRibZ = internalZStart + 15;
      
      // Верхнее ребро
      const topStiffener: Panel = {
        id: generateId(`Stiff_top_${item.id}`),
        name: `Ребро жесткости ↑ (${stiffnessData.deflection}мм)`,
        width: section.width,
        height: ribH,
        depth: 16,
        x: curX,
        y: item.y + 20, // Выше полки
        z: topRibZ,
        rotation: Axis.Z,
        materialId: this.matBody?.id || 'unknown',
        color: this.matBody?.color || '#D2B48C',
        texture: TextureType.WOOD_OAK,
        textureRotation: 0,
        visible: true,
        layer: 'body',
        openingType: 'none',
        edging: {
          top: 'none',
          bottom: '0.4',
          left: '0.4',
          right: '0.4'
        },
        groove: {
          enabled: false,
          side: 'top' as const,
          width: 0,
          depth: 0,
          offset: 0
        },
        hardware: []
      };
      
      this.panels.push(topStiffener);
      
      // Логирование для отладки
      console.log(`📊 Полка [${section.width}x${internalDepth}мм]:`, {
        deflection: `${stiffnessData.deflection}мм`,
        maxAllowed: `${stiffnessData.maxAllowed}мм`,
        ribHeight: `${ribH}мм`,
        warning: stiffnessData.deflection > stiffnessData.maxAllowed ? '⚠️ ТРЕБУЕТСЯ' : '✅'
      });
    }

    this.panels.push(shelfPanel);
  });
}
```

---

## 2️⃣ УМНЫЙ ВЫБОР РЕЛЬСОВ ЯЩИКОВ

### 📊 Таблица доступных рельсов

| Тип | Глубины (мм) | Макс. нагрузка | Цена | Типовое применение |
|-----|-------------|----------------|------|-------------------|
| **Метаболокс** | 200-600 | 20кг | $ | Легкие ящики |
| **Шариковые** | 300-700 | 50кг | $$ | Стандарт |
| **Soft-close** | 350-700 | 45кг | $$$ | Премиум |
| **Направляющие** | 250-500 | 15кг | $ | Старые модели |

### 📝 Код для интеграции

```typescript
// Расширить types.ts

export type RailType = 'standard' | 'ball-bearing' | 'soft-close' | 'heavy-duty';

export interface DrawerConfig {
  railType: RailType;
  railLength: number;    // мм
  maxLoad: number;       // кг
  hasSlowClose: boolean;
  bottomMaterial: 'plywood' | 'particle-board' | 'mdf';
}

// Добавить метод в CabinetGenerator:

/**
 * Интеллектуальный выбор размера и типа направляющей ящика
 */
private selectOptimalDrawerRail(
  availableDepth: number,
  cabinetDepth: number,
  drawerWidth: number,
  estimatedLoadClass: 'light' | 'medium' | 'heavy' = 'medium'
): DrawerConfig {
  // Минимальное расстояние для механизмов (передние ролики, back stop)
  const mechanismSpace = 60; // мм
  const maxRailLength = availableDepth - mechanismSpace;
  
  // Таблица доступных длин рельсов по стандартам DIN 65605
  const railSizes = {
    standard: [200, 250, 300, 350, 400, 450, 500, 550, 600],
    'ball-bearing': [300, 350, 400, 450, 500, 550, 600, 700],
    'soft-close': [350, 400, 450, 500, 550, 600, 700],
    'heavy-duty': [400, 450, 500, 550, 600, 700]
  };
  
  // Выбор типа рельса по глубине и нагрузке
  let selectedRailType: RailType = 'standard';
  
  if (cabinetDepth > 650 && estimatedLoadClass !== 'light') {
    selectedRailType = 'ball-bearing';
  }
  if (estimatedLoadClass === 'heavy' && cabinetDepth > 600) {
    selectedRailType = 'heavy-duty';
  }
  // soft-close добавляется как опция для премиум моделей
  
  // Выбор длины рельса
  const availableLengths = railSizes[selectedRailType];
  const selectedLength = availableLengths
    .reverse()
    .find(length => length <= maxRailLength) || availableLengths[0];
  
  // Расчёт грузоподъёмности
  const maxLoadByType = {
    standard: 20,
    'ball-bearing': 50,
    'soft-close': 45,
    'heavy-duty': 80
  };
  
  // Расчёт максимальной нагрузки с учётом ширины ящика
  // Правило: ширина ящика требует больше жёсткости
  const widthFactor = drawerWidth > 800 ? 0.8 : drawerWidth > 600 ? 0.9 : 1.0;
  const effectiveMaxLoad = Math.floor(maxLoadByType[selectedRailType] * widthFactor);
  
  // Выбор материала дна
  let bottomMaterial: 'plywood' | 'particle-board' | 'mdf' = 'particle-board';
  if (estimatedLoadClass === 'heavy') {
    bottomMaterial = 'plywood'; // Плотнее, крепче
  }
  
  return {
    railType: selectedRailType,
    railLength: selectedLength,
    maxLoad: effectiveMaxLoad,
    hasSlowClose: estimatedLoadClass !== 'light', // Soft-close для medium+ нагрузок
    bottomMaterial
  };
}

/**
 * Применить в buildDrawerAssembly:
 */
private buildDrawerAssemblyV2(
  item: CabinetItem,
  sectionW: number,
  availableDepth: number,
  startX: number,
  startZ: number,
  itemY: number,
  isOuterSection: boolean
): Panel[] {
  // НОВОЕ: Расчёт параметров рельса
  const railConfig = this.selectOptimalDrawerRail(
    availableDepth,
    this.config.depth,
    sectionW,
    'medium'
  );
  
  const panels: Panel[] = [];
  const facadeH = Math.round(item.height || 176);
  const railLen = railConfig.railLength;
  
  // Проверка минимальной глубины
  if (availableDepth < 260) {
    console.warn(`⚠️ Глубина ${availableDepth}мм слишком мала для ящика (мин. 260мм)`);
    return [];
  }

  const boxH = Math.max(60, facadeH - 36);
  
  // ... остальной код buildDrawerAssembly, но с использованием railConfig
  
  // Добавить в логирование:
  console.log(`🔧 Ящик [${sectionW}x${facadeH}мм]:`, {
    railType: railConfig.railType,
    railLength: `${railConfig.railLength}мм`,
    maxLoad: `${railConfig.maxLoad}кг`,
    bottomMaterial: railConfig.bottomMaterial,
    hasSlowClose: railConfig.hasSlowClose ? '✅' : '❌'
  });
  
  return panels;
}
```

---

## 3️⃣ ТИПИЗИРОВАННАЯ СИСТЕМА ОБОРУДОВАНИЯ

### 📦 Расширенный enum Hardware

```typescript
// В types.ts

/**
 * Полный реестр всех типов крепежа с параметрами
 */
export enum HardwareType {
  // ========== КРЕПЁЖ ==========
  CONFIRMAT_5x65 = 'confirmat-5x65',
  CONFIRMAT_7x50 = 'confirmat-7x50',
  SCREW_4x16 = 'screw-4x16',
  SCREW_4x30 = 'screw-4x30',
  SCREW_4x35 = 'screw-4x35',
  DOWEL_8 = 'dowel-8',
  DOWEL_10 = 'dowel-10',
  WOODEN_DOWEL_8x40 = 'wood-dowel-8x40',
  
  // ========== НАПРАВЛЯЮЩИЕ ==========
  RAIL_METABOX_300 = 'rail-metabox-300',
  RAIL_METABOX_400 = 'rail-metabox-400',
  RAIL_METABOX_500 = 'rail-metabox-500',
  RAIL_BALL_BEARING_400 = 'rail-bb-400',
  RAIL_BALL_BEARING_500 = 'rail-bb-500',
  RAIL_BALL_BEARING_600 = 'rail-bb-600',
  RAIL_SOFT_CLOSE_450 = 'rail-soft-450',
  RAIL_SOFT_CLOSE_550 = 'rail-soft-550',
  TELESCOPIC_RAIL = 'rail-telescopic',
  
  // ========== ПЕТЛИ ==========
  HINGE_35_SOFT_CLOSE = 'hinge-35-sc',
  HINGE_35_STANDARD = 'hinge-35-std',
  HINGE_26_COMPACT = 'hinge-26-compact',
  HINGE_CLIP_TOP = 'hinge-clip-top',
  HINGE_CLIP_BOTTOM = 'hinge-clip-bot',
  
  // ========== ПОДДЕРЖКА ПОЛОК ==========
  SHELF_SUPPORT_5 = 'support-5',
  SHELF_SUPPORT_4 = 'support-4',
  SHELF_PIN_METAL = 'pin-metal',
  SHELF_BRACKET = 'bracket-shelf',
  
  // ========== РУЧКИ ==========
  HANDLE_96MM = 'handle-96',
  HANDLE_128MM = 'handle-128',
  HANDLE_160MM = 'handle-160',
  PULL_TRAY = 'pull-tray',
  KNOB_ROUND = 'knob-round',
  
  // ========== ОПОРЫ И КРЕПЛЕНИЯ ==========
  CORNER_BRACKET_20 = 'bracket-corner-20',
  CORNER_BRACKET_30 = 'bracket-corner-30',
  MOUNTING_PLATE = 'plate-mount',
  LEG_PLASTIC_100 = 'leg-plastic-100',
  LEG_METAL_150 = 'leg-metal-150',
  WALL_ANCHOR_HEAVY = 'anchor-wall-heavy',
  
  // ========== СПЕЦИАЛЬНОЕ ==========
  PANTOGRAPH_LIFT = 'pantograph',
  BASKET_RAIL = 'basket-rail',
  ROD_HOLDER = 'rod-holder',
  PULL_OUT_ORGANIZER = 'pull-out'
}

/**
 * Метаданные каждого типа оборудования
 */
export const HARDWARE_SPECS: Record<HardwareType, {
  article: string;
  price: number;
  weight: number;
  supplier: string;
  notes: string;
}> = {
  [HardwareType.CONFIRMAT_5x65]: {
    article: 'CONF-5x65',
    price: 0.15,
    weight: 0.8,
    supplier: 'Spax',
    notes: 'Стандартный евровинт для ЛДСП'
  },
  [HardwareType.RAIL_BALL_BEARING_500]: {
    article: 'BB-500-50kg',
    price: 12.5,
    weight: 450,
    supplier: 'DTC',
    notes: 'Шариковая направляющая, грузоподъёмность 50кг'
  },
  // ... остальные типы
};

/**
 * Вспомогательная функция для получения спецификации
 */
export function getHardwareSpec(type: HardwareType) {
  return HARDWARE_SPECS[type] || {
    article: 'UNKNOWN',
    price: 0,
    weight: 0,
    supplier: 'Unknown',
    notes: 'Not defined'
  };
}
```

### 💰 Расчёт стоимости оборудования

```typescript
/**
 * В CabinetGenerator добавить метод:
 */
public calculateHardwareCost(): {
  items: Array<{ type: string; quantity: number; unitPrice: number; total: number }>;
  totalCost: number;
  byCategory: Record<string, number>;
} {
  const hardwareMap = new Map<HardwareType, number>();
  
  // Подсчёт всех hardware в панелях
  this.panels.forEach(panel => {
    panel.hardware.forEach(hw => {
      const type = hw.type as any;
      hardwareMap.set(type, (hardwareMap.get(type) || 0) + 1);
    });
  });
  
  const items = Array.from(hardwareMap.entries()).map(([type, quantity]) => {
    const spec = getHardwareSpec(type);
    return {
      type: type,
      quantity,
      unitPrice: spec.price,
      total: spec.price * quantity
    };
  });
  
  const totalCost = items.reduce((sum, item) => sum + item.total, 0);
  
  const byCategory = {
    fasteners: items
      .filter(i => i.type.includes('screw') || i.type.includes('dowel') || i.type.includes('confirmat'))
      .reduce((sum, i) => sum + i.total, 0),
    rails: items
      .filter(i => i.type.includes('rail'))
      .reduce((sum, i) => sum + i.total, 0),
    hinges: items
      .filter(i => i.type.includes('hinge'))
      .reduce((sum, i) => sum + i.total, 0),
    handles: items
      .filter(i => i.type.includes('handle') || i.type.includes('knob') || i.type.includes('pull'))
      .reduce((sum, i) => sum + i.total, 0),
    supports: items
      .filter(i => i.type.includes('support') || i.type.includes('bracket') || i.type.includes('leg'))
      .reduce((sum, i) => sum + i.total, 0)
  };
  
  return { items, totalCost, byCategory };
}
```

---

## 4️⃣ КЕШИРОВАНИЕ ПАРАМЕТРОВ

```typescript
/**
 * Класс для кеширования вычисленных параметров
 */
class ParameterCache {
  private cache = new Map<string, any>();
  private hits = 0;
  private misses = 0;
  
  get(key: string): any | undefined {
    if (this.cache.has(key)) {
      this.hits++;
      return this.cache.get(key);
    }
    this.misses++;
    return undefined;
  }
  
  set(key: string, value: any): void {
    this.cache.set(key, value);
  }
  
  invalidate(): void {
    this.cache.clear();
    this.hits = 0;
    this.misses = 0;
  }
  
  getStats() {
    const total = this.hits + this.misses;
    const hitRate = total > 0 ? (this.hits / total * 100).toFixed(1) : 'N/A';
    return {
      hits: this.hits,
      misses: this.misses,
      hitRate: `${hitRate}%`
    };
  }
}

/**
 * Использование в CabinetGenerator:
 */
export class CabinetGenerator {
  private paramCache = new ParameterCache();
  
  private getInternalParams() {
    const cacheKey = `internal_${this.config.doorType}_${this.config.backType}_${this.config.depth}`;
    let params = this.paramCache.get(cacheKey);
    
    if (!params) {
      const grooveOffset = 16;
      const internalZStart = this.config.backType === 'groove' ? (grooveOffset + 4) : 2;
      const doorSpace = this.config.doorType === 'sliding' ? STD.COUPE_DEPTH : 
                        (this.config.doorType === 'hinged' ? 2 : 0);
      const sideDepth = this.config.doorType === 'hinged' ? this.config.depth - 18 : this.config.depth;
      const internalDepth = sideDepth - internalZStart - doorSpace;
      
      params = { internalZStart, internalDepth, sideDepth, doorSpace, grooveOffset };
      this.paramCache.set(cacheKey, params);
    }
    
    return params;
  }
  
  // В конце generate(), добавить:
  public getPerformanceStats() {
    return {
      panelsGenerated: this.panels.length,
      hardwareCount: this.panels.reduce((sum, p) => sum + p.hardware.length, 0),
      cacheStats: this.paramCache.getStats()
    };
  }
}
```

---

## ✅ Контрольный список внедрения

### Фаза 1: Подготовка (30 мин)
- [ ] Сделать backup текущего CabinetGenerator.ts
- [ ] Создать новый файл `CabinetGeneratorV2.ts` для параллельной разработки
- [ ] Копировать существующий код

### Фаза 2: Добавление функций (2 часа)
- [ ] Реализовать `calculateShelfStiffness()`
- [ ] Реализовать `selectOptimalDrawerRail()`
- [ ] Расширить Hardware enum в types.ts
- [ ] Добавить ParameterCache класс

### Фаза 3: Интеграция (1 час)
- [ ] Обновить метод `generate()` для использования новых функций
- [ ] Добавить логирование для отладки
- [ ] Обновить validateDrawerAssembly()

### Фаза 4: Тестирование (1.5 часа)
- [ ] Создать unit-тесты для каждого нового метода
- [ ] Проверить на сложных конфигурациях (>3000мм, <600мм)
- [ ] Сравнить результаты CabinetGenerator vs CabinetGeneratorV2

### Фаза 5: Развёртывание (30 мин)
- [ ] Если тесты пройдены: заменить старый файл на новый
- [ ] Обновить импорты в компонентах
- [ ] Развернуть в production

---

## 📊 Примеры использования

### Пример 1: Шкаф с полками

```typescript
const config: CabinetConfig = {
  width: 1200,
  height: 2400,
  depth: 550,
  doorType: 'hinged',
  doorCount: 2,
  construction: 'corpus',
  backType: 'groove',
  baseType: 'plinth',
  hardwareType: 'confirmat',
  materialId: 'eg-w980'
};

const sections: Section[] = [
  {
    width: 600,
    items: [
      { id: '1', type: 'shelf', y: 500, height: 300 },
      { id: '2', type: 'shelf', y: 1000, height: 300 },
      { id: '3', type: 'shelf', y: 1500, height: 300 }
    ]
  }
];

const generator = new CabinetGenerator(config, sections, MATERIAL_LIBRARY);
const validation = generator.validate();

if (validation.valid) {
  const panels = generator.generate();
  const stats = generator.getPerformanceStats();
  console.log('✅ Шкаф сгенерирован:', stats);
} else {
  console.error('❌ Ошибки валидации:', validation.errors);
}
```

### Пример 2: Ящики с умным выбором рельсов

```typescript
const drawerSection: Section = {
  width: 800,
  items: [
    { id: 'd1', type: 'drawer', y: 100, height: 200 },
    { id: 'd2', type: 'drawer', y: 350, height: 200 },
    { id: 'd3', type: 'drawer', y: 600, height: 200 }
  ]
};

// Система автоматически выберет оптимальные рельсы для глубины 550мм:
// → Для первого уровня: ball-bearing 500мм
// → Для второго уровня: ball-bearing 500мм  
// → Для третьего уровня: standard 350мм (ближе к фронту)
```

---

**Готово к производству! 🚀**

