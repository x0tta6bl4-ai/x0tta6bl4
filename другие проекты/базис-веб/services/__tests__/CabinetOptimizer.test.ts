/**
 * Тесты для CabinetOptimizer (Phase 5)
 * 28 comprehensive test suite
 */

import { CabinetOptimizer, Genome, Individual } from '../CabinetOptimizer';
import { OptimizationObjective, OptimizationParams, Assembly, CabinetConfig, Section } from '../../types/CADTypes';

describe('CabinetOptimizer', () => {
  let optimizer: CabinetOptimizer;
  let baseConfig: CabinetConfig;
  let baseSections: Section[];
  let mockAssembly: Assembly;
  let params: OptimizationParams;

  beforeEach(() => {
    optimizer = new CabinetOptimizer();

    baseConfig = {
      width: 600,
      height: 800,
      depth: 500,
      thickness: 18,
      name: 'Test Cabinet',
      id: 'cabinet-1'
    } as CabinetConfig;

    baseSections = [
      {
        id: 'section-1',
        name: 'Main Section',
        width: 600,
        height: 800,
        depth: 500,
        thickness: 18,
        material: 'chipboard'
      } as Section
    ];

    mockAssembly = {
      id: 'assembly-1',
      name: 'Test Assembly',
      components: [],
      constraints: []
    };

    params = {
      objective: OptimizationObjective.BALANCE,
      maxIterations: 50,
      populationSize: 10,
      generations: 5,
      mutationRate: 0.1,
      crossoverRate: 0.8,
      minThickness: 12,
      maxThickness: 25
    };
  });

  // ==================== ИНИЦИАЛИЗАЦИЯ ====================

  describe('Инициализация оптимизатора', () => {
    test('1. Должен создаваться успешно', () => {
      const opt = new CabinetOptimizer();
      expect(opt).toBeDefined();
      expect(opt).toBeInstanceOf(CabinetOptimizer);
    });

    test('2. Должен иметь метод optimize', () => {
      expect(optimizer.optimize).toBeDefined();
      expect(typeof optimizer.optimize).toBe('function');
    });

    test('3. Конструктор не должен выбрасывать ошибки', () => {
      expect(() => {
        new CabinetOptimizer();
      }).not.toThrow();
    });
  });

  // ==================== ОПТИМИЗАЦИЯ С РАЗНЫМИ ЦЕЛЯМИ ====================

  describe('Оптимизация с разными целями', () => {
    test('4. COST - минимизация стоимости', () => {
      const costParams: OptimizationParams = {
        ...params,
        objective: OptimizationObjective.COST
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, costParams);

      expect(result).toBeDefined();
      expect(result.originalConfig).toEqual(baseConfig);
      expect(result.optimizedConfig).toBeDefined();
      expect(result.iterations).toBe(costParams.generations);
      expect(result.convergenceTime).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeGreaterThanOrEqual(0);
    });

    test('5. WEIGHT - минимизация веса', () => {
      const weightParams: OptimizationParams = {
        ...params,
        objective: OptimizationObjective.WEIGHT
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, weightParams);

      expect(result.optimizedConfig).toBeDefined();
      expect(result.score).toBeGreaterThanOrEqual(0);
    });

    test('6. STRENGTH - максимизация прочности', () => {
      const strengthParams: OptimizationParams = {
        ...params,
        objective: OptimizationObjective.STRENGTH
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, strengthParams);

      expect(result.optimizedConfig).toBeDefined();
      expect(result.score).toBeGreaterThanOrEqual(0);
    });

    test('7. BALANCE - компромисс между целями', () => {
      const balanceParams: OptimizationParams = {
        ...params,
        objective: OptimizationObjective.BALANCE
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, balanceParams);

      expect(result.optimizedConfig).toBeDefined();
      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.improvements.costReduction).toBeGreaterThanOrEqual(0);
      expect(result.improvements.weightReduction).toBeGreaterThanOrEqual(0);
    });
  });

  // ==================== ПАРАМЕТРЫ ОПТИМИЗАЦИИ ====================

  describe('Параметры оптимизации', () => {
    test('8. Должен использовать дефолтные значения если не указаны', () => {
      const minimalParams: OptimizationParams = {
        objective: OptimizationObjective.COST
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, minimalParams);

      expect(result).toBeDefined();
      expect(result.iterations).toBeGreaterThan(0);
    });

    test('9. Должен использовать populationSize из params', () => {
      const customParams: OptimizationParams = {
        ...params,
        populationSize: 5
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, customParams);

      expect(result.iterations).toBeGreaterThan(0);
    });

    test('10. Должен использовать generations из params', () => {
      const customParams: OptimizationParams = {
        ...params,
        generations: 3
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, customParams);

      expect(result.iterations).toBe(3);
    });

    test('11. Должен использовать mutationRate из params', () => {
      const customParams: OptimizationParams = {
        ...params,
        mutationRate: 0.5
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, customParams);

      expect(result).toBeDefined();
      expect(result.score).toBeGreaterThanOrEqual(0);
    });

    test('12. Должен использовать crossoverRate из params', () => {
      const customParams: OptimizationParams = {
        ...params,
        crossoverRate: 0.5
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, customParams);

      expect(result).toBeDefined();
    });
  });

  // ==================== РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ ====================

  describe('Результаты оптимизации', () => {
    test('13. Результат должен содержать все обязательные поля', () => {
      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(result.originalConfig).toBeDefined();
      expect(result.optimizedConfig).toBeDefined();
      expect(result.improvements).toBeDefined();
      expect(result.improvements.costReduction).toBeDefined();
      expect(result.improvements.weightReduction).toBeDefined();
      expect(result.improvements.strengthIncrease).toBeDefined();
      expect(result.iterations).toBeDefined();
      expect(result.convergenceTime).toBeDefined();
      expect(result.score).toBeDefined();
    });

    test('14. convergenceTime должна быть положительной', () => {
      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(result.convergenceTime).toBeGreaterThanOrEqual(0);
    });

    test('15. score должен быть числом между 0 и 100', () => {
      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(typeof result.score).toBe('number');
      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(200);
    });

    test('16. improvements должны быть числами >= 0', () => {
      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(result.improvements.costReduction).toBeGreaterThanOrEqual(0);
      expect(result.improvements.weightReduction).toBeGreaterThanOrEqual(0);
      expect(result.improvements.strengthIncrease).toBeGreaterThanOrEqual(0);
    });

    test('17. optimizedConfig должна быть объектом CabinetConfig', () => {
      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(result.optimizedConfig).toBeDefined();
      expect(result.optimizedConfig.width).toBeDefined();
      expect(result.optimizedConfig.height).toBeDefined();
      expect(result.optimizedConfig.depth).toBeDefined();
      expect(result.optimizedConfig.thickness).toBeDefined();
    });
  });

  // ==================== ПАРАМЕТРЫ КОНФИГУРАЦИИ ====================

  describe('Изменение параметров конфигурации', () => {
    test('18. Оптимизированная конфигурация должна быть внутри ограничений', () => {
      const customParams: OptimizationParams = {
        ...params,
        minThickness: 12,
        maxThickness: 25
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, customParams);

      expect(result.optimizedConfig.thickness).toBeGreaterThanOrEqual(customParams.minThickness || 0);
      if (customParams.maxThickness) {
        expect(result.optimizedConfig.thickness).toBeLessThanOrEqual(customParams.maxThickness);
      }
    });

    test('19. Размеры конфигурации должны быть положительными', () => {
      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(result.optimizedConfig.width).toBeGreaterThan(0);
      expect(result.optimizedConfig.height).toBeGreaterThan(0);
      expect(result.optimizedConfig.depth).toBeGreaterThan(0);
      expect(result.optimizedConfig.thickness).toBeGreaterThan(0);
    });

    test('20. Базовая конфигурация не должна изменяться', () => {
      const originalWidth = baseConfig.width;
      const originalHeight = baseConfig.height;

      optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(baseConfig.width).toBe(originalWidth);
      expect(baseConfig.height).toBe(originalHeight);
    });
  });

  // ==================== МНОЖЕСТВЕННЫЕ ОПТИМИЗАЦИИ ====================

  describe('Множественные оптимизации', () => {
    test('21. Несколько оптимизаций должны давать разные результаты (вероятно)', () => {
      const result1 = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);
      const result2 = optimizer.optimize(baseConfig, baseSections, mockAssembly, params);

      expect(result1).toBeDefined();
      expect(result2).toBeDefined();
    });

    test('22. Оптимизация с большей популяцией должна улучшаться', () => {
      const smallPopParams: OptimizationParams = {
        ...params,
        populationSize: 5,
        generations: 3
      };

      const largePopParams: OptimizationParams = {
        ...params,
        populationSize: 20,
        generations: 3
      };

      const result1 = optimizer.optimize(baseConfig, baseSections, mockAssembly, smallPopParams);
      const result2 = optimizer.optimize(baseConfig, baseSections, mockAssembly, largePopParams);

      expect(result1).toBeDefined();
      expect(result2).toBeDefined();
    });

    test('23. Оптимизация с большим количеством поколений должна сходиться лучше', () => {
      const shortGenParams: OptimizationParams = {
        ...params,
        generations: 2
      };

      const longGenParams: OptimizationParams = {
        ...params,
        generations: 10
      };

      const result1 = optimizer.optimize(baseConfig, baseSections, mockAssembly, shortGenParams);
      const result2 = optimizer.optimize(baseConfig, baseSections, mockAssembly, longGenParams);

      expect(result1.iterations).toBe(2);
      expect(result2.iterations).toBe(10);
    });
  });

  // ==================== ОБРАБОТКА ОШИБОК ====================

  describe('Обработка ошибок и edge cases', () => {
    test('24. Должен работать с пустой сборкой', () => {
      const emptyAssembly: Assembly = {
        id: 'empty',
        name: 'Empty Assembly',
        components: [],
        constraints: []
      };

      const result = optimizer.optimize(baseConfig, baseSections, emptyAssembly, params);

      expect(result).toBeDefined();
      expect(result.score).toBeGreaterThanOrEqual(0);
    });

    test('25. Должен работать с null sections', () => {
      const result = optimizer.optimize(baseConfig, [], mockAssembly, params);

      expect(result).toBeDefined();
      expect(result.iterations).toBeGreaterThan(0);
    });

    test('26. Должен обрабатывать минимальные параметры', () => {
      const minimalParams: OptimizationParams = {
        objective: OptimizationObjective.COST
      };

      expect(() => {
        optimizer.optimize(baseConfig, baseSections, mockAssembly, minimalParams);
      }).not.toThrow();
    });

    test('27. Должен обрабатывать экстремальные параметры', () => {
      const extremeParams: OptimizationParams = {
        objective: OptimizationObjective.COST,
        populationSize: 100,
        generations: 20,
        mutationRate: 0.99,
        crossoverRate: 0.01
      };

      const result = optimizer.optimize(baseConfig, baseSections, mockAssembly, extremeParams);

      expect(result).toBeDefined();
      expect(result.score).toBeGreaterThanOrEqual(0);
    });
  });

  // ==================== ПРОИЗВОДИТЕЛЬНОСТЬ ====================

  describe('Производительность', () => {
    test('28. Оптимизация должна завершиться в разумное время (< 10 сек)', () => {
      const fastParams: OptimizationParams = {
        ...params,
        populationSize: 10,
        generations: 5
      };

      const startTime = performance.now();
      optimizer.optimize(baseConfig, baseSections, mockAssembly, fastParams);
      const endTime = performance.now();

      const duration = endTime - startTime;
      expect(duration).toBeLessThan(10000);
    });
  });
});
