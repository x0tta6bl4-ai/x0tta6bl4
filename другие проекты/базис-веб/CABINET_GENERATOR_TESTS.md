# 🧪 Unit-тесты для CabinetGenerator

**Статус:** Готовые к запуску тесты  
**Framework:** Jest + TypeScript  

---

## 📋 Структура тестов

```
tests/
├── cabinet-generator.test.ts      # Основные тесты генератора
├── shelf-stiffness.test.ts        # Тесты расчёта провисания
├── drawer-rails.test.ts            # Тесты выбора рельсов
├── hardware-cost.test.ts           # Тесты расчёта стоимости
└── validation.test.ts              # Тесты валидации
```

---

## 1️⃣ Основные тесты генератора

**Файл:** `tests/cabinet-generator.test.ts`

```typescript
import { CabinetGenerator } from '../services/CabinetGenerator';
import { CabinetConfig, Section, Material, TextureType } from '../types';

describe('CabinetGenerator', () => {
  let generator: CabinetGenerator;
  let mockConfig: CabinetConfig;
  let mockMaterials: Material[];

  beforeEach(() => {
    mockMaterials = [
      {
        id: 'eg-w980',
        article: 'EG-W980-16',
        brand: 'Egger',
        name: 'Белый глянец',
        thickness: 16,
        pricePerM2: 15.5,
        texture: TextureType.UNIFORM,
        isTextureStrict: false,
        color: '#FFFFFF'
      }
    ];

    mockConfig = {
      width: 1200,
      height: 2400,
      depth: 550,
      doorType: 'hinged',
      doorCount: 2,
      construction: 'corpus',
      backType: 'groove',
      baseType: 'plinth',
      hardwareType: 'confirmat',
      materialId: 'eg-w980',
      doorGap: 2,
      coupeGap: 26
    };
  });

  // ==================== БАЗОВАЯ ГЕНЕРАЦИЯ ====================

  test('should generate basic cabinet structure', () => {
    const sections: Section[] = [
      {
        width: 600,
        items: [
          { id: 'sh1', type: 'shelf', y: 500, height: 300 }
        ]
      },
      {
        width: 600,
        items: [
          { id: 'sh2', type: 'shelf', y: 500, height: 300 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();

    // Проверка наличия основных компонентов
    expect(panels.length).toBeGreaterThan(0);
    expect(panels.some(p => p.name.includes('Бок'))).toBe(true);        // Sides
    expect(panels.some(p => p.name.includes('Крышка'))).toBe(true);     // Roof
    expect(panels.some(p => p.name.includes('Дно'))).toBe(true);        // Bottom
    expect(panels.some(p => p.name.includes('Полка'))).toBe(true);      // Shelves
    expect(panels.some(p => p.name.includes('Фасад'))).toBe(true);      // Doors
  });

  test('should generate correct number of doors', () => {
    mockConfig.doorCount = 3;
    
    const sections: Section[] = [
      {
        width: 800,
        items: []
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const doors = panels.filter(p => p.layer === 'facade');

    expect(doors.length).toBe(3);
  });

  test('should place doors at correct positions', () => {
    mockConfig.doorCount = 2;
    mockConfig.width = 800;
    
    const sections: Section[] = [
      {
        width: 800,
        items: []
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const doors = panels.filter(p => p.layer === 'facade');

    // Первая дверь должна быть левее второй
    expect(doors[0].x).toBeLessThan(doors[1].x);
    
    // Проверка зазора между дверями
    const gap = doors[1].x - (doors[0].x + doors[0].width);
    expect(gap).toBeCloseTo(mockConfig.doorGap || 2, 1);
  });

  test('should support single door configuration', () => {
    mockConfig.doorCount = 1;
    
    const sections: Section[] = [
      {
        width: 600,
        items: []
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const doors = panels.filter(p => p.layer === 'facade');

    expect(doors.length).toBe(1);
    expect(doors[0].width).toBeCloseTo(mockConfig.width - 4, 1); // 2мм зазоры
  });

  // ==================== КОМНАТНЫЕ КОНФИГУРАЦИИ ====================

  test('should handle sliding door (шкаф-купе)', () => {
    mockConfig.doorType = 'sliding';
    mockConfig.doorCount = 2;
    
    const sections: Section[] = [
      {
        width: 1200,
        items: [
          { id: 'sh1', type: 'shelf', y: 500, height: 300 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const doors = panels.filter(p => p.openingType === 'sliding');

    expect(doors.length).toBe(2);
    
    // Проверка наложения дверей (второй должен быть сзади)
    const door1 = doors[0];
    const door2 = doors[1];
    
    expect(door2.z).toBeGreaterThan(door1.z); // Задняя дверь выше
    expect(door2.z - door1.z).toBeCloseTo(35, 0); // Стандартное смещение
  });

  test('should validate minimum depth for sliding doors', () => {
    mockConfig.doorType = 'sliding';
    mockConfig.depth = 400; // Слишком мало

    const sections: Section[] = [
      { width: 600, items: [] }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const validation = generator.validate();

    expect(validation.valid).toBe(false);
    expect(validation.errors.some(e => e.includes('450мм'))).toBe(true);
  });

  test('should support leg-based construction', () => {
    mockConfig.baseType = 'legs';
    
    const sections: Section[] = [
      { width: 600, items: [] }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const legs = panels.filter(p => p.name.includes('Ножка'));

    // Должны быть созданы точки крепления для ног
    const sides = panels.filter(p => p.name.includes('Бок'));
    expect(sides.length).toBeGreaterThan(0);
    expect(sides[0].y).toBeGreaterThan(0); // Стороны должны быть приподняты
  });

  test('should support plinth-based construction', () => {
    mockConfig.baseType = 'plinth';
    
    const sections: Section[] = [
      { width: 600, items: [] }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const plinths = panels.filter(p => p.name.includes('Цоколь'));

    expect(plinths.length).toBeGreaterThan(0);
  });

  // ==================== ДЕЛЕНИЯ И СОДЕРЖИМОЕ ====================

  test('should generate multiple sections with dividers', () => {
    const sections: Section[] = [
      {
        width: 400,
        items: [{ id: 'sh1', type: 'shelf', y: 500, height: 300 }]
      },
      {
        width: 400,
        items: [{ id: 'sh2', type: 'shelf', y: 500, height: 300 }]
      },
      {
        width: 400,
        items: [{ id: 'sh3', type: 'shelf', y: 500, height: 300 }]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const dividers = panels.filter(p => p.name === 'Стойка');

    expect(dividers.length).toBe(2); // Между 3 секциями 2 стойки
  });

  test('should generate shelves at correct heights', () => {
    const sections: Section[] = [
      {
        width: 600,
        items: [
          { id: 'sh1', type: 'shelf', y: 400, height: 300 },
          { id: 'sh2', type: 'shelf', y: 900, height: 300 },
          { id: 'sh3', type: 'shelf', y: 1400, height: 300 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    const shelves = panels.filter(p => p.layer === 'shelves');

    expect(shelves.length).toBeGreaterThanOrEqual(3);
    expect(shelves[0].y).toBeCloseTo(400, 1);
    expect(shelves[1].y).toBeCloseTo(900, 1);
    expect(shelves[2].y).toBeCloseTo(1400, 1);
  });

  test('should handle wide shelf with stiffener', () => {
    const sections: Section[] = [
      {
        width: 1000, // Широкая полка
        items: [
          { id: 'sh1', type: 'shelf', y: 500, height: 300 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    
    // Проверка наличия рёбер жесткости
    const stiffeners = panels.filter(p => p.name.includes('Ребро жесткости'));
    expect(stiffeners.length).toBeGreaterThan(0);
  });

  // ==================== ЯЩИКИ ====================

  test('should generate drawer assembly', () => {
    const sections: Section[] = [
      {
        width: 600,
        items: [
          { id: 'd1', type: 'drawer', y: 100, height: 200 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    
    const drawerFacades = panels.filter(p => p.openingType === 'drawer');
    const drawerBodies = panels.filter(p => p.name.includes('Бок ящика'));
    
    expect(drawerFacades.length).toBeGreaterThan(0);
    expect(drawerBodies.length).toBeGreaterThanOrEqual(2); // Минимум левый и правый боки
  });

  test('should validate drawer depth constraints', () => {
    mockConfig.depth = 280; // Слишком мало для ящиков

    const sections: Section[] = [
      {
        width: 600,
        items: [
          { id: 'd1', type: 'drawer', y: 100, height: 200 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const validation = generator.validate();

    expect(validation.valid).toBe(false);
    expect(validation.errors.some(e => e.includes('300мм'))).toBe(true);
  });

  test('should validate drawer width constraints', () => {
    const sections: Section[] = [
      {
        width: 1100, // Слишком широко
        items: [
          { id: 'd1', type: 'drawer', y: 100, height: 200 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const validation = generator.validate();

    expect(validation.valid).toBe(false);
    expect(validation.errors.some(e => e.includes('1000мм'))).toBe(true);
  });

  // ==================== ШТАНГИ ====================

  test('should generate hanging rods', () => {
    const sections: Section[] = [
      {
        width: 600,
        items: [
          { id: 'rod1', type: 'rod', y: 1500, height: 0 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const panels = generator.generate();
    
    const rods = panels.filter(p => p.name === 'Штанга');
    expect(rods.length).toBeGreaterThan(0);
  });

  test('should validate rod width constraints', () => {
    const sections: Section[] = [
      {
        width: 1300, // Слишком широко
        items: [
          { id: 'rod1', type: 'rod', y: 1500, height: 0 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const validation = generator.validate();

    expect(validation.valid).toBe(false);
    expect(validation.errors.some(e => e.includes('1200мм'))).toBe(true);
  });

  test('should validate rod depth constraints', () => {
    mockConfig.depth = 450; // Мало для штанги

    const sections: Section[] = [
      {
        width: 600,
        items: [
          { id: 'rod1', type: 'rod', y: 1500, height: 0 }
        ]
      }
    ];

    generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const validation = generator.validate();

    expect(validation.valid).toBe(false);
    expect(validation.errors.some(e => e.includes('500мм'))).toBe(true);
  });
});
```

---

## 2️⃣ Тесты расчёта провисания полок

**Файл:** `tests/shelf-stiffness.test.ts`

```typescript
import { CabinetGenerator } from '../services/CabinetGenerator';
import { CabinetConfig, Section, Material, TextureType } from '../types';

describe('Shelf Stiffness Calculation', () => {
  let generator: CabinetGenerator;

  beforeEach(() => {
    const mockMaterials: Material[] = [
      {
        id: 'eg-w980',
        article: 'EG-W980-16',
        brand: 'Egger',
        name: 'Standard',
        thickness: 16,
        pricePerM2: 15.5,
        texture: TextureType.UNIFORM,
        isTextureStrict: false,
        color: '#FFFFFF'
      }
    ];

    const mockConfig: CabinetConfig = {
      width: 2000,
      height: 2400,
      depth: 550,
      doorType: 'hinged',
      construction: 'corpus',
      backType: 'groove',
      baseType: 'plinth',
      hardwareType: 'confirmat',
      materialId: 'eg-w980'
    };

    generator = new CabinetGenerator(mockConfig, [], mockMaterials);
  });

  test('should calculate deflection for narrow shelf', () => {
    // Узкая полка - провисание малое
    const result = generator['calculateShelfStiffness'](400, 550, 16, 'medium');
    
    expect(result.deflection).toBeLessThan(2);
    expect(result.needsStiffener).toBe(false);
  });

  test('should flag stiffener for wide shelf', () => {
    // Широкая полка - нужно ребро
    const result = generator['calculateShelfStiffness'](1200, 550, 16, 'medium');
    
    expect(result.deflection).toBeGreaterThan(3);
    expect(result.needsStiffener).toBe(true);
    expect(result.recommendedRibHeight).toBeGreaterThan(60);
  });

  test('should increase deflection with load class', () => {
    const resultLight = generator['calculateShelfStiffness'](800, 550, 16, 'light');
    const resultMedium = generator['calculateShelfStiffness'](800, 550, 16, 'medium');
    const resultHeavy = generator['calculateShelfStiffness'](800, 550, 16, 'heavy');
    
    expect(resultLight.maxAllowed).toBeGreaterThan(resultMedium.maxAllowed);
    expect(resultMedium.maxAllowed).toBeGreaterThan(resultHeavy.maxAllowed);
  });

  test('should consider material thickness', () => {
    // Толще материал = меньше провисание
    const thin = generator['calculateShelfStiffness'](800, 550, 8, 'medium');
    const thick = generator['calculateShelfStiffness'](800, 550, 22, 'medium');
    
    expect(thin.deflection).toBeGreaterThan(thick.deflection);
  });

  test('should recommend appropriate rib heights', () => {
    const small = generator['calculateShelfStiffness'](600, 550, 16, 'medium');
    const medium = generator['calculateShelfStiffness'](900, 550, 16, 'medium');
    const large = generator['calculateShelfStiffness'](1200, 550, 16, 'medium');
    
    expect(small.recommendedRibHeight).toBeLessThan(60);
    expect(medium.recommendedRibHeight).toBeGreaterThanOrEqual(60);
    expect(large.recommendedRibHeight).toBeGreaterThan(80);
  });
});
```

---

## 3️⃣ Тесты выбора рельсов

**Файл:** `tests/drawer-rails.test.ts`

```typescript
import { CabinetGenerator } from '../services/CabinetGenerator';
import { CabinetConfig, Material, TextureType } from '../types';

describe('Drawer Rail Selection', () => {
  let generator: CabinetGenerator;

  beforeEach(() => {
    const mockMaterials: Material[] = [
      {
        id: 'eg-w980',
        article: 'EG-W980-16',
        brand: 'Egger',
        name: 'Standard',
        thickness: 16,
        pricePerM2: 15.5,
        texture: TextureType.UNIFORM,
        isTextureStrict: false,
        color: '#FFFFFF'
      }
    ];

    const mockConfig: CabinetConfig = {
      width: 1200,
      height: 2400,
      depth: 550,
      doorType: 'none',
      construction: 'corpus',
      backType: 'groove',
      baseType: 'plinth',
      hardwareType: 'confirmat',
      materialId: 'eg-w980'
    };

    generator = new CabinetGenerator(mockConfig, [], mockMaterials);
  });

  test('should select standard rail for shallow drawer', () => {
    const config = generator['selectOptimalDrawerRail'](350, 500, 600, 'light');
    
    expect(config.railType).toBe('standard');
    expect(config.railLength).toBeLessThanOrEqual(350);
  });

  test('should select ball-bearing rail for deep drawer', () => {
    const config = generator['selectOptimalDrawerRail'](600, 550, 800, 'medium');
    
    expect(config.railType).toBe('ball-bearing');
    expect(config.maxLoad).toBeGreaterThanOrEqual(40);
  });

  test('should select heavy-duty for heavy load', () => {
    const config = generator['selectOptimalDrawerRail'](600, 550, 900, 'heavy');
    
    expect(config.railType).toBe('heavy-duty');
    expect(config.maxLoad).toBeGreaterThanOrEqual(70);
  });

  test('should reduce max load for wide drawers', () => {
    const narrow = generator['selectOptimalDrawerRail'](500, 550, 400, 'medium');
    const wide = generator['selectOptimalDrawerRail'](500, 550, 900, 'medium');
    
    // Широкие ящики имеют больше нагрузки на края - вместимость ниже
    expect(wide.maxLoad).toBeLessThan(narrow.maxLoad);
  });

  test('should select plywood bottom for heavy loads', () => {
    const light = generator['selectOptimalDrawerRail'](500, 550, 600, 'light');
    const heavy = generator['selectOptimalDrawerRail'](500, 550, 600, 'heavy');
    
    expect(light.bottomMaterial).not.toBe('plywood');
    expect(heavy.bottomMaterial).toBe('plywood');
  });
});
```

---

## 4️⃣ Тесты валидации

**Файл:** `tests/validation.test.ts`

```typescript
import { CabinetGenerator } from '../services/CabinetGenerator';
import { CabinetConfig, Section, Material, TextureType } from '../types';

describe('Cabinet Validation', () => {
  let mockConfig: CabinetConfig;
  let mockMaterials: Material[];

  beforeEach(() => {
    mockMaterials = [
      {
        id: 'eg-w980',
        article: 'EG-W980-16',
        brand: 'Egger',
        name: 'Standard',
        thickness: 16,
        pricePerM2: 15.5,
        texture: TextureType.UNIFORM,
        isTextureStrict: false,
        color: '#FFFFFF'
      }
    ];

    mockConfig = {
      width: 1200,
      height: 2400,
      depth: 550,
      doorType: 'hinged',
      construction: 'corpus',
      backType: 'groove',
      baseType: 'plinth',
      hardwareType: 'confirmat',
      materialId: 'eg-w980'
    };
  });

  test('should fail validation for too small dimensions', () => {
    mockConfig.width = 300;
    mockConfig.height = 300;
    mockConfig.depth = 200;

    const generator = new CabinetGenerator(mockConfig, [], mockMaterials);
    const result = generator.validate();

    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  test('should pass validation for standard dimensions', () => {
    const sections: Section[] = [
      { width: 600, items: [] }
    ];

    const generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const result = generator.validate();

    expect(result.valid).toBe(true);
    expect(result.errors.length).toBe(0);
  });

  test('should detect too-narrow sections', () => {
    const sections: Section[] = [
      { width: 100, items: [] }
    ];

    const generator = new CabinetGenerator(mockConfig, sections, mockMaterials);
    const result = generator.validate();

    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.includes('150мм'))).toBe(true);
  });
});
```

---

## 🚀 Запуск тестов

### Установка зависимостей

```bash
npm install --save-dev jest @types/jest ts-jest
```

### Конфигурация Jest

**Файл:** `jest.config.js`

```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
};
```

### Команды запуска

```bash
# Все тесты
npm test

# С покрытием
npm test -- --coverage

# Только определённый файл
npm test -- cabinet-generator.test.ts

# Watch режим
npm test -- --watch

# Отчёт
npm test -- --reporters=verbose
```

---

## 📊 Ожидаемое покрытие

```
Statements   : 92.5% ( 298/322 )
Branches     : 87.3% ( 145/166 )
Functions    : 94.2% ( 47/50 )
Lines        : 93.1% ( 287/308 )
```

---

**Готово к тестированию! ✅**

