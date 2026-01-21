/**
 * BillOfMaterials Service Tests
 * Полное тестирование функции генерирования спецификации материалов
 */

import {
  BillOfMaterials,
  MaterialPrices,
  ManufacturingOperations,
  BOMStats
} from '../BillOfMaterials';
import {
  Assembly,
  Component,
  Material,
  BOMReport,
  BOMItem,
  ConstraintType
} from '../../types/CADTypes';

describe('BillOfMaterials Service', () => {
  let bom: BillOfMaterials;
  let materialPrices: MaterialPrices;
  let manufacturingOps: ManufacturingOperations;

  beforeEach(() => {
    // Стандартные цены на материалы (руб/кг)
    materialPrices = {
      'aluminum': 300,
      'steel': 250,
      'plastic': 150,
      'copper': 500,
      'default': 200
    };

    // Стоимость операций
    manufacturingOps = {
      machining: 100,      // руб/кг
      painting: 50,        // руб/м²
      assembly: 200,       // руб/компонент
      qualityControl: 100, // руб/компонент
      packaging: 50        // руб/компонент
    };

    bom = new BillOfMaterials(materialPrices, manufacturingOps);

    // Регистрируем материалы
    const aluminum: Material = {
      id: 'aluminum',
      name: 'Алюминий',
      density: 2700, // кг/м³
      cost: 300
    };

    const steel: Material = {
      id: 'steel',
      name: 'Сталь',
      density: 7850, // кг/м³
      cost: 250
    };

    const plastic: Material = {
      id: 'plastic',
      name: 'Пластик',
      density: 1200, // кг/м³
      cost: 150
    };

    bom.registerMaterial(aluminum);
    bom.registerMaterial(steel);
    bom.registerMaterial(plastic);
  });

  describe('Инициализация', () => {
    test('должен создать экземпляр с цены материалов', () => {
      expect(bom).toBeDefined();
      expect(bom).toBeInstanceOf(BillOfMaterials);
    });

    test('должен использовать дефолтные параметры, если не переданы', () => {
      const simpleBOM = new BillOfMaterials(materialPrices);
      expect(simpleBOM).toBeDefined();
    });

    test('должен регистрировать материалы', () => {
      const newMaterial: Material = {
        id: 'titanium',
        name: 'Титан',
        density: 4500,
        cost: 1000
      };
      
      expect(() => {
        bom.registerMaterial(newMaterial);
      }).not.toThrow();
    });
  });

  describe('Генерирование BOM', () => {
    test('должен генерировать BOM для простой сборки', () => {
      const component: Component = {
        id: 'comp-1',
        name: 'Простой компонент',
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: 'Тестовый компонент'
      };

      const assembly: Assembly = {
        id: 'asm-1',
        name: 'Простая сборка',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      expect(report).toBeDefined();
      expect(report.totalItems).toBeGreaterThan(0);
      expect(report.totalQuantity).toBeGreaterThan(0);
      expect(report.totalMass).toBeGreaterThan(0);
    });

    test('должен корректно подсчитывать массу компонента', () => {
      // Объём: 0.1м * 0.1м * 0.1м = 0.001м³ = 1000 см³
      // Масса (алюминий): 0.001м³ * 2700 кг/м³ = 2.7 кг

      const component: Component = {
        id: 'comp-2',
        name: 'Алюминиевый компонент',
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-2',
        name: 'Сборка с алюминием',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);
      
      // Проверяем, что масса разумна
      expect(report.totalMass).toBeGreaterThan(0);
      expect(report.items.length).toBe(1);
    });

    test('должен обрабатывать множественные компоненты', () => {
      const components: Component[] = [
        {
          id: 'comp-a',
          name: 'Алюминиевая деталь',
          type: 'PART',
          material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
          geometry: {
            type: 'box',
            boundingBox: {
              min: { x: 0, y: 0, z: 0 },
              max: { x: 50, y: 50, z: 50 },
              width: () => 50,
              height: () => 50,
              depth: () => 50
            }
          },
          constraints: [],
          description: ''
        },
        {
          id: 'comp-b',
          name: 'Стальная деталь',
          type: 'PART',
          material: { id: 'steel', name: 'Сталь', density: 7850, cost: 250 },
          geometry: {
            type: 'box',
            boundingBox: {
              min: { x: 0, y: 0, z: 0 },
              max: { x: 100, y: 100, z: 100 },
              width: () => 100,
              height: () => 100,
              depth: () => 100
            }
          },
          constraints: [],
          description: ''
        }
      ];

      const assembly: Assembly = {
        id: 'asm-3',
        name: 'Комплексная сборка',
        components,
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      expect(report.totalItems).toBe(2);
      expect(report.totalQuantity).toBe(2);
      expect(report.items.length).toBe(2);
    });

    test('должен обрабатывать пустую сборку', () => {
      const assembly: Assembly = {
        id: 'asm-empty',
        name: 'Пустая сборка',
        components: [],
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      expect(report.totalItems).toBe(0);
      expect(report.totalQuantity).toBe(0);
      expect(report.totalMass).toBe(0);
    });
  });

  describe('Расчёт стоимости', () => {
    test('должен корректно вычислять стоимость материала', () => {
      const component: Component = {
        id: 'comp-cost',
        name: 'Компонент для расчёта стоимости',
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-cost',
        name: 'Сборка для расчёта',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      // Стоимость должна быть больше нуля
      expect(report.totalMaterialCost).toBeGreaterThan(0);
      // Стоимость должна зависеть от цены материала
      expect(report.items[0].materialCost).toBeGreaterThan(0);
    });

    test('должен использовать дефолтную цену для неизвестного материала', () => {
      const component: Component = {
        id: 'comp-unknown',
        name: 'Компонент с неизвестным материалом',
        type: 'PART',
        material: { id: 'unknown-new-99', name: 'Неизвестный материал', density: 1000, cost: 100 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-unknown',
        name: 'Сборка с неизвестным материалом',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      // Стоимость должна быть рассчитана на основе дефолтной цены (500 руб/кг)
      expect(report.totalMaterialCost).toBeGreaterThan(0);
    });
  });

  describe('Экспорт', () => {
    test('должен экспортировать BOM в CSV формат', () => {
      const component: Component = {
        id: 'comp-export',
        name: 'Компонент для экспорта',
        type: 'PART',
        material: { id: 'steel', name: 'Сталь', density: 7850, cost: 250 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: 'Экспортируемый компонент'
      };

      const assembly: Assembly = {
        id: 'asm-export',
        name: 'Сборка для экспорта',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      expect(report.exportFormats.csv).toBeDefined();
      expect(report.exportFormats.csv.length).toBeGreaterThan(0);
      expect(report.exportFormats.csv).toContain('ID компонента');
      expect(report.exportFormats.csv).toContain('ИТОГО');
    });

    test('должен экспортировать BOM в JSON формат', () => {
      const component: Component = {
        id: 'comp-json',
        name: 'Компонент для JSON экспорта',
        type: 'PART',
        material: { id: 'plastic', name: 'Пластик', density: 1200, cost: 150 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-json',
        name: 'Сборка для JSON',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);

      expect(Array.isArray(report.exportFormats.json)).toBe(true);
      expect(report.exportFormats.json.length).toBeGreaterThan(0);
    });

    test('CSV должен содержать все необходимые поля', () => {
      const component: Component = {
        id: 'comp-fields',
        name: 'Тестовый компонент',
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: 'Тестовый компонент для проверки полей'
      };

      const assembly: Assembly = {
        id: 'asm-fields',
        name: 'Сборка для проверки',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);
      const csv = report.exportFormats.csv;

      expect(csv).toContain('ID компонента');
      expect(csv).toContain('Материал');
      expect(csv).toContain('Количество');
      expect(csv).toContain('Масса');
      expect(csv).toContain('Стоимость материала');
      expect(csv).toContain('Время производства');
      expect(csv).toContain('Описание');
    });
  });

  describe('Статистика и анализ', () => {
    test('должен вычислять статистику BOM', () => {
      const component: Component = {
        id: 'comp-stats',
        name: 'Компонент для статистики',
        type: 'PART',
        material: { id: 'steel', name: 'Сталь', density: 7850, cost: 250 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-stats',
        name: 'Сборка для статистики',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);
      const stats = bom.calculateBOMStats(report);

      expect(stats).toBeDefined();
      expect(stats.uniqueComponents).toBe(1);
      expect(stats.totalQuantity).toBe(1);
      expect(stats.totalMass).toBeGreaterThan(0);
      expect(stats.materialCost).toBeGreaterThan(0);
      expect(stats.manufacturingCost).toBeGreaterThan(0);
      expect(stats.totalCost).toBe(stats.materialCost + stats.manufacturingCost);
    });

    test('должен вычислять правильное общее время производства', () => {
      const components: Component[] = [
        {
          id: 'comp-time-1',
          name: 'Компонент 1',
          type: 'PART',
          material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
          geometry: {
            type: 'box',
            boundingBox: {
              min: { x: 0, y: 0, z: 0 },
              max: { x: 100, y: 100, z: 100 },
              width: () => 100,
              height: () => 100,
              depth: () => 100
            }
          },
          constraints: [],
          description: ''
        },
        {
          id: 'comp-time-2',
          name: 'Компонент 2',
          type: 'PART',
          material: { id: 'steel', name: 'Сталь', density: 7850, cost: 250 },
          geometry: {
            type: 'box',
            boundingBox: {
              min: { x: 0, y: 0, z: 0 },
              max: { x: 50, y: 50, z: 50 },
              width: () => 50,
              height: () => 50,
              depth: () => 50
            }
          },
          constraints: [],
          description: ''
        }
      ];

      const assembly: Assembly = {
        id: 'asm-time',
        name: 'Сборка для времени',
        components,
        constraints: []
      };

      const report = bom.generateBOM(assembly);
      const stats = bom.calculateBOMStats(report);

      // Общее время должно быть больше нуля
      expect(stats.productionTime).toBeGreaterThan(0);
      // Время должно быть разумным (менее 1.5 часа на 2 компонента)
      expect(stats.productionTime).toBeLessThan(1.5); // Разумный лимит
    });
  });

  describe('Валидирование', () => {
    test('должен валидировать корректный BOM', () => {
      const component: Component = {
        id: 'comp-valid',
        name: 'Валидный компонент',
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-valid',
        name: 'Валидная сборка',
        components: [component],
        constraints: []
      };

      const report = bom.generateBOM(assembly);
      const validation = bom.validateBOM(report);

      expect(validation.valid).toBe(true);
      expect(validation.errors.length).toBe(0);
    });

    test('должен обнаружить пустой BOM', () => {
      const emptyReport: BOMReport = {
        totalItems: 0,
        totalQuantity: 0,
        totalMass: 0,
        totalMaterialCost: 0,
        totalProductionTime: 0,
        items: [],
        exportFormats: {
          csv: '',
          json: []
        }
      };

      const validation = bom.validateBOM(emptyReport);

      expect(validation.valid).toBe(false);
      expect(validation.errors).toContain('BOM пуста - нет компонентов');
    });
  });

  describe('Сравнение BOM', () => {
    test('должен сравнивать две спецификации', () => {
      const createComponent = (id: string, name: string): Component => ({
        id,
        name,
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      });

      const assembly1: Assembly = {
        id: 'asm-compare-1',
        name: 'Сборка 1',
        components: [createComponent('comp-1', 'Компонент 1')],
        constraints: []
      };

      const assembly2: Assembly = {
        id: 'asm-compare-2',
        name: 'Сборка 2',
        components: [
          createComponent('comp-1', 'Компонент 1'),
          createComponent('comp-2', 'Компонент 2')
        ],
        constraints: []
      };

      const bom1 = bom.generateBOM(assembly1);
      const bom2 = bom.generateBOM(assembly2);

      const comparison = bom.compareBOMs(bom1, bom2);

      expect(comparison).toBeDefined();
      expect(comparison.massChange).not.toBeNaN();
      expect(comparison.costChange).not.toBeNaN();
      expect(comparison.componentDifferences.length).toBeGreaterThan(0);
    });
  });

  describe('Обработка исключений', () => {
    test('должен обрабатывать компоненты без материала', () => {
      const component: Component = {
        id: 'comp-no-mat',
        name: 'Компонент без материала',
        type: 'PART',
        material: undefined as any,
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-no-mat',
        name: 'Сборка без материала',
        components: [component],
        constraints: []
      };

      // Не должно выкидывать исключение
      expect(() => {
        bom.generateBOM(assembly);
      }).not.toThrow();
    });

    test('должен обрабатывать компоненты без геометрии', () => {
      const component: Component = {
        id: 'comp-no-geom',
        name: 'Компонент без геометрии',
        type: 'PART',
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: undefined as any,
        constraints: [],
        description: ''
      };

      const assembly: Assembly = {
        id: 'asm-no-geom',
        name: 'Сборка без геометрии',
        components: [component],
        constraints: []
      };

      // Должен использовать дефолтный объём
      expect(() => {
        bom.generateBOM(assembly);
      }).not.toThrow();
    });
  });

  describe('Производительность', () => {
    test('должен быстро обрабатывать большой BOM (10 компонентов)', () => {
      const components: Component[] = Array.from({ length: 10 }, (_, i) => ({
        id: `comp-perf-${i}`,
        name: `Компонент ${i}`,
        type: 'PART' as const,
        material: { id: 'aluminum', name: 'Алюминий', density: 2700, cost: 300 },
        geometry: {
          type: 'box',
          boundingBox: {
            min: { x: 0, y: 0, z: 0 },
            max: { x: 100, y: 100, z: 100 },
            width: () => 100,
            height: () => 100,
            depth: () => 100
          }
        },
        constraints: [],
        description: ''
      }));

      const assembly: Assembly = {
        id: 'asm-perf',
        name: 'Большая сборка',
        components,
        constraints: []
      };

      const startTime = performance.now();
      const report = bom.generateBOM(assembly);
      const endTime = performance.now();

      expect(report.totalItems).toBe(10);
      expect(endTime - startTime).toBeLessThan(100); // Должно выполниться за <100ms
    });
  });
});
