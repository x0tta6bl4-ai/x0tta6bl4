/**
 * Тесты для DFMValidator (Phase 4)
 * 22 comprehensive test suite
 */

import { DFMValidator, DFMConfig } from '../DFMValidator';
import { Component, Assembly, Material, BoundingBox } from '../../types/CADTypes';

describe('DFMValidator', () => {
  let validator: DFMValidator;
  let mockComponent: Component;
  let mockAssembly: Assembly;
  let defaultConfig: DFMConfig;

  beforeEach(() => {
    validator = new DFMValidator();
    defaultConfig = validator.getConfig();

    // Создаём мок-компонент со стандартными параметрами
    mockComponent = {
      id: 'test-component-1',
      name: 'Test Component',
      geometry: {
        type: '3D',
        vertices: [],
        faces: [],
        boundingBox: {
          width: () => 100,
          height: () => 100,
          depth: () => 50,
          center: () => ({ x: 0, y: 0, z: 0 }),
          min: () => ({ x: -50, y: -50, z: -25 }),
          max: () => ({ x: 50, y: 50, z: 25 })
        }
      },
      material: {
        id: 'aluminum',
        name: 'Aluminum 6061',
        density: 2700,
        strength: 275,
        elasticity: 69000,
        thermalConductivity: 167,
        coefficient: 0.000023
      },
      constraints: [
        { id: 'c1', type: 'DISTANCE', target1: 'f1', target2: 'f2', value: 50 },
        { id: 'c2', type: 'ANGLE', target1: 'e1', target2: 'e2', value: 90 }
      ],
      subComponents: []
    };

    mockAssembly = {
      id: 'test-assembly',
      name: 'Test Assembly',
      components: [mockComponent],
      constraints: []
    };
  });

  // ==================== ИНИЦИАЛИЗАЦИЯ ====================

  describe('Инициализация валидатора', () => {
    test('1. Должен создаваться с дефолтной конфигурацией', () => {
      const v = new DFMValidator();
      expect(v).toBeDefined();
      expect(v.getConfig()).toBeDefined();
    });

    test('2. Должен инициализироваться с пользовательской конфигурацией', () => {
      const customConfig: Partial<DFMConfig> = {
        minWallThickness: 2.0,
        minFilletRadius: 0.75,
        maxAspectRatio: 100
      };
      const v = new DFMValidator(customConfig);
      const config = v.getConfig();
      expect(config.minWallThickness).toBe(2.0);
      expect(config.minFilletRadius).toBe(0.75);
      expect(config.maxAspectRatio).toBe(100);
    });

    test('3. Должны быть зарегистрированы 15 стандартных правил', () => {
      const rules = validator.getRules();
      expect(rules.length).toBe(15);
      expect(rules).toContain('wall-thickness');
      expect(rules).toContain('fillet-radius');
      expect(rules).toContain('hole-size');
      expect(rules).toContain('surface-finish');
    });
  });

  // ==================== ПРОВЕРКА КОМПОНЕНТА ====================

  describe('Проверка одного компонента', () => {
    test('4. validateComponent должен вернуть массив результатов', () => {
      const results = validator.validateComponent(mockComponent);
      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBe(15); // По одному для каждого правила
    });

    test('5. Каждый результат должен содержать требуемые поля', () => {
      const results = validator.validateComponent(mockComponent);
      results.forEach(result => {
        expect(result.ruleId).toBeDefined();
        expect(result.ruleName).toBeDefined();
        expect(result.componentId).toBe(mockComponent.id);
        expect(result.passed).toBeDefined();
        expect(result.severity).toBeDefined();
        expect(result.message).toBeDefined();
        expect(result.details).toBeDefined();
      });
    });

    test('6. Результат должен содержать suggestedFix если проверка не прошла', () => {
      const results = validator.validateComponent(mockComponent);
      results.forEach(result => {
        if (!result.passed) {
          expect(result.suggestedFix).toBeDefined();
        }
      });
    });

    test('7. Результат должен содержать severity (error/warning/info)', () => {
      const results = validator.validateComponent(mockComponent);
      results.forEach(result => {
        expect(['error', 'warning', 'info']).toContain(result.severity);
      });
    });
  });

  // ==================== ПРОВЕРКА СБОРКИ ====================

  describe('Проверка сборки (Assembly)', () => {
    test('8. validateAssembly должен вернуть DFMReport', () => {
      const report = validator.validateAssembly(mockAssembly);
      expect(report).toBeDefined();
      expect(report.totalChecks).toBeGreaterThan(0);
      expect(report.passedChecks).toBeDefined();
      expect(report.failedChecks).toBeDefined();
    });

    test('9. DFMReport должен содержать все требуемые поля', () => {
      const report = validator.validateAssembly(mockAssembly);
      expect(report.totalChecks).toBeDefined();
      expect(report.passedChecks).toBeDefined();
      expect(report.failedChecks).toBeDefined();
      expect(Array.isArray(report.errors)).toBe(true);
      expect(Array.isArray(report.warnings)).toBe(true);
      expect(Array.isArray(report.infos)).toBe(true);
      expect(report.manufacturability).toBeDefined();
      expect(Array.isArray(report.suggestions)).toBe(true);
      expect(report.timestamp).toBeDefined();
      expect(report.runtimeMs).toBeDefined();
    });

    test('10. Manufacturability должен быть в диапазоне 0-100', () => {
      const report = validator.validateAssembly(mockAssembly);
      expect(report.manufacturability).toBeGreaterThanOrEqual(0);
      expect(report.manufacturability).toBeLessThanOrEqual(100);
    });

    test('11. failedChecks должен быть errors.length + warnings.length + infos.length', () => {
      const report = validator.validateAssembly(mockAssembly);
      const failCount = report.errors.length + report.warnings.length + report.infos.length;
      expect(report.failedChecks).toBe(failCount);
    });

    test('12. passedChecks + failedChecks должны равняться totalChecks', () => {
      const report = validator.validateAssembly(mockAssembly);
      expect(report.passedChecks + report.failedChecks).toBe(report.totalChecks);
    });
  });

  // ==================== РЕКУРСИВНАЯ ПРОВЕРКА ====================

  describe('Рекурсивная проверка подкомпонентов', () => {
    test('13. Должна проверяться вложенная сборка', () => {
      const subComponent: Component = {
        id: 'sub-component',
        name: 'Sub Component',
        geometry: mockComponent.geometry,
        material: mockComponent.material,
        constraints: [],
        subComponents: []
      };

      mockComponent.subComponents = [subComponent];

      const report = validator.validateAssembly(mockAssembly);
      // Должны быть проверены оба компонента: основной + подкомпонент
      expect(report.totalChecks).toBeGreaterThanOrEqual(30); // Минимум 2 компонента × 15 правил
    });

    test('14. Глубокая рекурсия должна работать', () => {
      const level3: Component = {
        id: 'level-3',
        name: 'Level 3',
        geometry: mockComponent.geometry,
        material: mockComponent.material,
        constraints: [],
        subComponents: []
      };

      const level2: Component = {
        id: 'level-2',
        name: 'Level 2',
        geometry: mockComponent.geometry,
        material: mockComponent.material,
        constraints: [],
        subComponents: [level3]
      };

      mockComponent.subComponents = [level2];

      const report = validator.validateAssembly(mockAssembly);
      // Должны быть проверены 3 уровня
      expect(report.totalChecks).toBeGreaterThanOrEqual(45); // 3 компонента × 15 правил
    });
  });

  // ==================== ПРАВИЛА ПРОВЕРКИ ====================

  describe('Индивидуальные DFM правила', () => {
    test('15. wall-thickness правило должно проверять толщину стенок', () => {
      const results = validator.validateComponent(mockComponent);
      const wallThicknessResult = results.find(r => r.ruleId === 'wall-thickness');
      expect(wallThicknessResult).toBeDefined();
      expect(wallThicknessResult?.ruleName).toContain('толщина');
    });

    test('16. fillet-radius правило должно проверять скругления', () => {
      const results = validator.validateComponent(mockComponent);
      const filletResult = results.find(r => r.ruleId === 'fillet-radius');
      expect(filletResult).toBeDefined();
      expect(filletResult?.message).toBeDefined();
    });

    test('17. aspect-ratio правило должно проверять отношение сторон', () => {
      const results = validator.validateComponent(mockComponent);
      const aspectResult = results.find(r => r.ruleId === 'aspect-ratio');
      expect(aspectResult).toBeDefined();
      expect(aspectResult?.message).toBeDefined();
    });

    test('18. hole-size правило должно проверять размер отверстий', () => {
      const results = validator.validateComponent(mockComponent);
      const holeResult = results.find(r => r.ruleId === 'hole-size');
      expect(holeResult).toBeDefined();
      expect(holeResult?.message).toBeDefined();
    });

    test('19. material-availability должен проверять доступность материала', () => {
      const results = validator.validateComponent(mockComponent);
      const matResult = results.find(r => r.ruleId === 'material-availability');
      expect(matResult).toBeDefined();
      expect(matResult?.passed).toBe(true); // aluminum - стандартный материал
    });

    test('20. complexity правило должно проверять сложность', () => {
      const results = validator.validateComponent(mockComponent);
      const complexResult = results.find(r => r.ruleId === 'complexity');
      expect(complexResult).toBeDefined();
      expect(complexResult?.passed).toBe(true); // 2 ограничения < порога
    });
  });

  // ==================== КОНФИГУРАЦИЯ ====================

  describe('Управление конфигурацией', () => {
    test('21. updateConfig должна обновлять параметры', () => {
      const newConfig: Partial<DFMConfig> = {
        minWallThickness: 3.0,
        maxAspectRatio: 60
      };
      validator.updateConfig(newConfig);
      const config = validator.getConfig();
      expect(config.minWallThickness).toBe(3.0);
      expect(config.maxAspectRatio).toBe(60);
    });

    test('22. addRule должна добавлять пользовательское правило', () => {
      const customRule = (component: Component, config: DFMConfig) => ({
        ruleId: 'custom-rule',
        ruleName: 'Custom Rule',
        componentId: component.id,
        passed: true,
        severity: 'info' as const,
        message: 'Test',
        details: 'Test details'
      });

      validator.addRule('custom-rule', customRule);
      const rules = validator.getRules();
      expect(rules).toContain('custom-rule');
    });
  });

  // ==================== ПРОИЗВОДИТЕЛЬНОСТЬ ====================

  describe('Производительность', () => {
    test('Проверка 1 компонента < 10ms', () => {
      const start = Date.now();
      validator.validateComponent(mockComponent);
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(10);
    });

    test('Проверка сборки из 5 компонентов < 50ms', () => {
      const components = [
        mockComponent,
        { ...mockComponent, id: 'comp-2' },
        { ...mockComponent, id: 'comp-3' },
        { ...mockComponent, id: 'comp-4' },
        { ...mockComponent, id: 'comp-5' }
      ];

      const assembly: Assembly = {
        id: 'perf-test',
        name: 'Performance Test',
        components,
        constraints: []
      };

      const start = Date.now();
      const report = validator.validateAssembly(assembly);
      const elapsed = Date.now() - start;

      // Runtime should be close to elapsed time (within 5ms margin)
      expect(Math.abs(report.runtimeMs - elapsed)).toBeLessThan(5);
      expect(elapsed).toBeLessThan(50);
    });
  });

  // ==================== ГРАНИЧНЫЕ СЛУЧАИ ====================

  describe('Граничные случаи (Edge Cases)', () => {
    test('Компонент без материала должен быть проверен', () => {
      const componentNoMaterial: Component = {
        id: 'no-material',
        name: 'No Material',
        geometry: mockComponent.geometry,
        constraints: [],
        subComponents: []
      };

      const results = validator.validateComponent(componentNoMaterial);
      expect(results.length).toBe(15);
      expect(results.every(r => r.componentId === 'no-material')).toBe(true);
    });

    test('Компонент без ограничений должен быть проверен', () => {
      const componentNoConstraints: Component = {
        id: 'no-constraints',
        name: 'No Constraints',
        geometry: mockComponent.geometry,
        material: mockComponent.material,
        subComponents: []
      };

      const results = validator.validateComponent(componentNoConstraints);
      expect(results.length).toBe(15);
    });

    test('Компонент без geometry должен быть проверен', () => {
      const componentNoGeometry: Component = {
        id: 'no-geometry',
        name: 'No Geometry',
        constraints: [],
        subComponents: []
      };

      const results = validator.validateComponent(componentNoGeometry);
      expect(results.length).toBe(15);
      // Все проверки должны работать с дефолтными значениями
      expect(results.every(r => r.message)).toBe(true);
    });

    test('Пустая сборка должна быть обработана', () => {
      const emptyAssembly: Assembly = {
        id: 'empty',
        name: 'Empty',
        components: [],
        constraints: []
      };

      const report = validator.validateAssembly(emptyAssembly);
      expect(report.totalChecks).toBe(0);
      expect(report.passedChecks).toBe(0);
      expect(report.failedChecks).toBe(0);
    });
  });

  // ==================== РЕКОМЕНДАЦИИ ====================

  describe('Генерирование рекомендаций', () => {
    test('Доступны рекомендации при провале проверок', () => {
      const report = validator.validateAssembly(mockAssembly);
      expect(Array.isArray(report.suggestions)).toBe(true);
      // При хорошем компоненте, рекомендация о качестве
      expect(
        report.suggestions.length > 0 || report.failedChecks === 0
      ).toBe(true);
    });

    test('Рекомендации специфичны для типа ошибки', () => {
      // Создаём компонент с проблемами
      const problematicComponent: Component = {
        id: 'problem',
        name: 'Problematic',
        geometry: {
          type: '3D',
          vertices: [],
          faces: [],
          boundingBox: {
            width: () => 1000, // Очень широкий
            height: () => 10,   // Очень узкий
            depth: () => 10,
            center: () => ({ x: 0, y: 0, z: 0 }),
            min: () => ({ x: -500, y: -5, z: -5 }),
            max: () => ({ x: 500, y: 5, z: 5 })
          }
        },
        material: mockComponent.material,
        constraints: [],
        subComponents: []
      };

      const problematicAssembly: Assembly = {
        id: 'problem-assembly',
        name: 'Problematic Assembly',
        components: [problematicComponent],
        constraints: []
      };

      const report = validator.validateAssembly(problematicAssembly);
      // Должны быть рекомендации по улучшению
      expect(report.suggestions.length).toBeGreaterThan(0);
    });
  });

  // ==================== ИНТЕГРАЦИЯ ====================

  describe('Интеграция с другими компонентами', () => {
    test('Интеграция с BillOfMaterials должна быть возможна', () => {
      // Этот тест проверяет, что DFMValidator может работать с компонентами
      // которые используются в BOM системе
      const report = validator.validateAssembly(mockAssembly);
      expect(report).toBeDefined();
      expect(report.manufacturability).toBeDefined();
    });

    test('Multiple validators должны работать независимо', () => {
      const validator1 = new DFMValidator({ minWallThickness: 1.0 });
      const validator2 = new DFMValidator({ minWallThickness: 3.0 });

      const config1 = validator1.getConfig();
      const config2 = validator2.getConfig();

      expect(config1.minWallThickness).toBe(1.0);
      expect(config2.minWallThickness).toBe(3.0);
    });
  });
});
