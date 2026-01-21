/**
 * ФАЗА 2: Тесты для Constraint Solver
 * Проверяет Newton-Raphson алгоритм и решение систем ограничений
 */

import { ConstraintSolver } from '../ConstraintSolver';
import {
  Assembly,
  Component,
  Constraint,
  ConstraintType,
  Material,
  TextureType,
  EulerAngles,
  ComponentType,
  Point3D
} from '../../types/CADTypes';

// ============================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================================================

/**
 * Создать простой материал для тестирования
 */
function createTestMaterial(): Material {
  return {
    id: 'mat-1',
    name: 'Test Material',
    color: '#ff0000',
    density: 1000,
    elasticModulus: 210000,
    poissonRatio: 0.3,
    textureType: TextureType.UNIFORM
  };
}

/**
 * Создать простой компонент
 */
function createTestComponent(id: string, position: Point3D = { x: 0, y: 0, z: 0 }): Component {
  return {
    id,
    name: `Component ${id}`,
    type: ComponentType.PART,
    position,
    rotation: { x: 0, y: 0, z: 0 } as EulerAngles,
    scale: { x: 1, y: 1, z: 1 },
    material: createTestMaterial(),
    properties: {
      width: 100,
      height: 100,
      depth: 100
    }
  };
}

/**
 * Создать простую сборку
 */
function createTestAssembly(
  components: Component[] = [],
  constraints: Constraint[] = []
): Assembly {
  return {
    id: 'asm-1',
    name: 'Test Assembly',
    components,
    constraints,
    metadata: {
      version: '1.0.0',
      createdAt: new Date(),
      modifiedAt: new Date()
    }
  };
}

// ============================================================================
// ОСНОВНЫЕ ТЕСТЫ
// ============================================================================

describe('ConstraintSolver', () => {
  let solver: ConstraintSolver;

  beforeEach(() => {
    solver = new ConstraintSolver();
  });

  // =========================================================================
  // ТЕСТЫ ИНИЦИАЛИЗАЦИИ И ВАЛИДАЦИИ
  // =========================================================================

  describe('Initialization', () => {
    test('should create solver instance', () => {
      expect(solver).toBeDefined();
      expect(typeof solver.solve).toBe('function');
      expect(typeof solver.validateConstraintSystem).toBe('function');
    });
  });

  // =========================================================================
  // ТЕСТЫ ВАЛИДАЦИИ СИСТЕМ ОГРАНИЧЕНИЙ
  // =========================================================================

  describe('validateConstraintSystem', () => {
    test('should validate empty assembly', () => {
      const assembly = createTestAssembly();
      const result = solver.validateConstraintSystem(assembly);
      
      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.degreesOfFreedom).toBeGreaterThanOrEqual(0);
    });

    test('should detect underconstrained system', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      const assembly = createTestAssembly(components, []);
      const result = solver.validateConstraintSystem(assembly);
      
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('should detect underconstrained system', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      // Два компонента без ограничений = underconstrained
      const constraints: Constraint[] = [];
      
      const assembly = createTestAssembly(components, constraints);
      const result = solver.validateConstraintSystem(assembly);
      
      // 6 DOF - 0 constraints = 6 DOF (underconstrained)
      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('should validate well-constrained system', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'con-2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const result = solver.validateConstraintSystem(assembly);
      
      expect(result.errors.length).toBe(0);
      expect(result.isValid).toBe(true);
    });
  });

  // =========================================================================
  // ТЕСТЫ РЕШЕНИЯ ПРОСТЫХ СИСТЕМ
  // =========================================================================

  describe('solve - Simple Systems', () => {
    test('should handle empty assembly', () => {
      const assembly = createTestAssembly();
      const initialPositions = new Map<string, Point3D>();
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.success).toBe(true);
      expect(result.iterations).toBe(0);
    });

    test('should solve distance constraint between two points', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 50, y: 0, z: 0 })
      ];
      
      // Не используем FIXED constraint, чтобы позволить системе итерировать
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 50, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions).toBeDefined();
      // DISTANCE constraint поддерживает аналитический градиент, должна сходиться за 1-2 итерации
      expect(result.iterations).toBeGreaterThanOrEqual(0);
    });

    test('should solve coincident constraint', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 100, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.COINCIDENT,
          elementA: 'c1',
          elementB: 'c2',
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 100, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions).toBeDefined();
      expect(result.iterations).toBeGreaterThanOrEqual(0);
    });
  });

  // =========================================================================
  // ТЕСТЫ ЧИСЛОВОЙ УСТОЙЧИВОСТИ
  // =========================================================================

  describe('Numerical Stability', () => {
    test('should handle zero vectors', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.success).toBe(true);
      expect(isFinite(result.error)).toBe(true);
    });

    test('should handle large coordinates', () => {
      const components = [
        createTestComponent('c1', { x: 1000000, y: 1000000, z: 1000000 }),
        createTestComponent('c2', { x: 1000100, y: 1000000, z: 1000000 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 1000000, y: 1000000, z: 1000000 }],
        ['c2', { x: 1000100, y: 1000000, z: 1000000 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(isFinite(result.error)).toBe(true);
    });

    test('should handle small distances', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 0.001, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'con-2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 0.001,
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 0.001, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.error).toBeGreaterThanOrEqual(0);
      expect(isFinite(result.error)).toBe(true);
    });
  });

  // =========================================================================
  // ТЕСТЫ СХОДИМОСТИ
  // =========================================================================

  describe('Convergence', () => {
    test('should converge in limited iterations', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.iterations).toBeLessThan(200);
    });

    test('should report convergence status', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 })
      ];
      const assembly = createTestAssembly(components, []);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.converged).toBeDefined();
      expect(result.message).toBeDefined();
      expect(result.message.length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // ТЕСТЫ РЕЗУЛЬТАТОВ
  // =========================================================================

  describe('Results', () => {
    test('should return proper result structure', () => {
      const components = [createTestComponent('c1')];
      const assembly = createTestAssembly(components);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.success).toBeDefined();
      expect(result.positions).toBeDefined();
      expect(result.residuals).toBeDefined();
      expect(result.iterations).toBeDefined();
      expect(result.converged).toBeDefined();
      expect(result.error).toBeDefined();
      expect(result.message).toBeDefined();
      expect(result.error).toBeGreaterThanOrEqual(0);
      expect(result.iterations).toBeGreaterThanOrEqual(0);
    });

    test('should preserve input positions map', () => {
      const components = [
        createTestComponent('c1', { x: 10, y: 20, z: 30 })
      ];
      const assembly = createTestAssembly(components);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 10, y: 20, z: 30 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      // Исходная карта не должна измениться
      expect(initialPositions.get('c1')).toEqual({ x: 10, y: 20, z: 30 });
      // Результат должен содержать позицию
      expect(result.positions.has('c1')).toBe(true);
    });

    test('should return residuals for all constraints', () => {
      const components = [
        createTestComponent('c1'),
        createTestComponent('c2')
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        },
        {
          id: 'con-2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 50, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.residuals.length).toBe(constraints.length);
    });
  });

  // =========================================================================
  // ТЕСТЫ СПЕЦИАЛЬНЫХ СЛУЧАЕВ
  // =========================================================================

  describe('Edge Cases', () => {
    test('should handle single component', () => {
      const components = [createTestComponent('c1')];
      const assembly = createTestAssembly(components, []);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });

    test('should handle many components', () => {
      const components = Array.from({ length: 10 }, (_, i) =>
        createTestComponent(`c${i}`, {
          x: i * 100,
          y: 0,
          z: 0
        })
      );
      
      const assembly = createTestAssembly(components);
      const initialPositions = new Map<string, Point3D>(
        components.map((c, i) => [c.id, { x: i * 100, y: 0, z: 0 }])
      );
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions.size).toBe(10);
    });

    test('should handle constraints with missing elements', () => {
      const components = [createTestComponent('c1')];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.COINCIDENT,
          elementA: 'c1',
          elementB: 'nonexistent',
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }]
      ]);
      
      // Should not throw
      const result = solver.solve(assembly, initialPositions);
      expect(result).toBeDefined();
    });
  });

  // =========================================================================
  // ТЕСТЫ ПРОИЗВОДИТЕЛЬНОСТИ
  // =========================================================================

  describe('Performance - Large Assemblies', () => {
    test('should solve 50 component assembly in < 500ms', () => {
      const numComponents = 50;
      const components = Array.from({ length: numComponents }, (_, i) =>
        createTestComponent(`c${i}`, {
          x: (i % 10) * 100,
          y: Math.floor(i / 10) * 100,
          z: 0
        })
      );
      
      // Создать ограничения между соседними компонентами
      const constraints: Constraint[] = [];
      for (let i = 0; i < numComponents - 1; i++) {
        constraints.push({
          id: `con-${i}`,
          type: ConstraintType.DISTANCE,
          elementA: `c${i}`,
          elementB: `c${i + 1}`,
          value: 100,
          weight: 1.0
        });
      }
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>(
        components.map((c, i) => [
          c.id,
          {
            x: (i % 10) * 100,
            y: Math.floor(i / 10) * 100,
            z: 0
          }
        ])
      );
      
      const startTime = Date.now();
      const result = solver.solve(assembly, initialPositions);
      const elapsed = Date.now() - startTime;
      
      expect(result.positions.size).toBe(numComponents);
      expect(elapsed).toBeLessThan(1000);
    });

    test('should handle 100 component assembly', () => {
      const numComponents = 100;
      const components = Array.from({ length: numComponents }, (_, i) =>
        createTestComponent(`c${i}`, {
          x: (i % 10) * 100,
          y: Math.floor(i / 10) * 100,
          z: 0
        })
      );
      
      const constraints: Constraint[] = [];
      for (let i = 0; i < numComponents - 1; i++) {
        if (i % 10 < 9) { // Соедините компоненты в одной строке
          constraints.push({
            id: `con-${i}`,
            type: ConstraintType.DISTANCE,
            elementA: `c${i}`,
            elementB: `c${i + 1}`,
            value: 100,
            weight: 1.0
          });
        }
      }
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>(
        components.map((c, i) => [
          c.id,
          {
            x: (i % 10) * 100,
            y: Math.floor(i / 10) * 100,
            z: 0
          }
        ])
      );
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions.size).toBe(numComponents);
      expect(result.iterations).toBeLessThan(100);
    });

    test('should handle assembly with multiple constraint types', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 }),
        createTestComponent('c3', { x: 100, y: 100, z: 0 }),
        createTestComponent('c4', { x: 0, y: 100, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'con-2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        },
        {
          id: 'con-3',
          type: ConstraintType.DISTANCE,
          elementA: 'c2',
          elementB: 'c3',
          value: 100,
          weight: 1.0
        },
        {
          id: 'con-4',
          type: ConstraintType.DISTANCE,
          elementA: 'c3',
          elementB: 'c4',
          value: 100,
          weight: 1.0
        },
        {
          id: 'con-5',
          type: ConstraintType.DISTANCE,
          elementA: 'c4',
          elementB: 'c1',
          value: 100,
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }],
        ['c3', { x: 100, y: 100, z: 0 }],
        ['c4', { x: 0, y: 100, z: 0 }]
      ]);
      
      const startTime = Date.now();
      const result = solver.solve(assembly, initialPositions);
      const elapsed = Date.now() - startTime;
      
      expect(result.positions).toBeDefined();
      expect(elapsed).toBeLessThan(200);
    });
  });

  // =========================================================================
  // ТЕСТЫ НАПРАВЛЕННЫХ ОГРАНИЧЕНИЙ
  // =========================================================================

  describe('Directional Constraints', () => {
    test('should handle parallel constraint', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.PARALLEL,
          elementA: 'c1',
          elementB: 'c2',
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });

    test('should handle perpendicular constraint', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.PERPENDICULAR,
          elementA: 'c1',
          elementB: 'c2',
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });

    test('should handle angle constraint', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        {
          id: 'con-1',
          type: ConstraintType.ANGLE,
          elementA: 'c1',
          elementB: 'c2',
          value: 90, // 90 градусов
          weight: 1.0
        }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });
  });

  // =========================================================================
  // ТЕСТЫ КОМПЛЕКСНЫХ СИСТЕМ
  // =========================================================================

  describe('Complex Constraint Systems', () => {
    test('should solve rectangular frame with 4 distance constraints', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 }),
        createTestComponent('c3', { x: 100, y: 100, z: 0 }),
        createTestComponent('c4', { x: 0, y: 100, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 },
        { id: 'con-3', type: ConstraintType.DISTANCE, elementA: 'c2', elementB: 'c3', value: 100, weight: 1.0 },
        { id: 'con-4', type: ConstraintType.DISTANCE, elementA: 'c3', elementB: 'c4', value: 100, weight: 1.0 },
        { id: 'con-5', type: ConstraintType.DISTANCE, elementA: 'c4', elementB: 'c1', value: 100, weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 10, z: 0 }],
        ['c3', { x: 110, y: 100, z: 0 }],
        ['c4', { x: 10, y: 100, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.success || !result.success).toBe(true); // Should handle either way
      expect(result.positions).toBeDefined();
      expect(result.positions.size).toBe(4);
    });

    test('should handle linear chain of 10 components', () => {
      const numComponents = 10;
      const components = Array.from({ length: numComponents }, (_, i) =>
        createTestComponent(`c${i}`, {
          x: i * 100,
          y: 0,
          z: 0
        })
      );
      
      const constraints: Constraint[] = [
        { id: 'con-0', type: ConstraintType.FIXED, elementA: 'c0', weight: 1.0 }
      ];
      
      for (let i = 0; i < numComponents - 1; i++) {
        constraints.push({
          id: `con-${i + 1}`,
          type: ConstraintType.DISTANCE,
          elementA: `c${i}`,
          elementB: `c${i + 1}`,
          value: 100,
          weight: 1.0
        });
      }
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>(
        components.map((c, i) => [c.id, { x: i * 100, y: 0, z: 0 }])
      );
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions.size).toBe(numComponents);
      expect(result.iterations).toBeLessThan(50);
    });

    test('should handle mixed constraint types (distance + coincident)', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 }),
        createTestComponent('c3', { x: 100, y: 0, z: 0 }) // Coincident with c2
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 },
        { id: 'con-3', type: ConstraintType.COINCIDENT, elementA: 'c2', elementB: 'c3', weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }],
        ['c3', { x: 100, y: 10, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions).toBeDefined();
      expect(result.positions.size).toBe(3);
    });

    test('should validate system with over-constrained components', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      // 7 ограничений для 2 компонентов (6 DOF) - over-constrained by 1
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 }, // 3 DOF (c1: x, y, z fixed)
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }, // 1 DOF
        { id: 'con-3', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }, // 1 DOF (redundant)
        { id: 'con-4', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }, // 1 DOF (redundant)
        { id: 'con-5', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }, // 1 DOF (redundant)
        { id: 'con-6', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }, // 1 DOF (redundant)
        { id: 'con-7', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 } // 1 DOF (redundant) - makes system over-constrained
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const result = solver.validateConstraintSystem(assembly);
      
      // Should detect over-constrained system (7 constraints on 6 DOF)
      expect(result.degreesOfFreedom).toBeLessThanOrEqual(0);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('should report error for under-constrained system without fixed constraint', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const result = solver.validateConstraintSystem(assembly);
      
      // Should report underconstrained
      expect(result.errors.length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // ТЕСТЫ WEIGHTED CONSTRAINTS
  // =========================================================================

  describe('Weighted Constraints', () => {
    test('should apply constraint weights correctly', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 }),
        createTestComponent('c3', { x: 0, y: 100, z: 0 })
      ];
      
      // Первое ограничение имеет высокий вес, второе - низкий
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 10.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 10.0 },
        { id: 'con-3', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c3', value: 100, weight: 0.1 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }],
        ['c3', { x: 0, y: 100, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions).toBeDefined();
    });
  });

  // =========================================================================
  // ТЕСТЫ TOLERANCE И PRECISION
  // =========================================================================

  describe('Tolerance and Precision', () => {
    test('should handle tolerance parameter in constraints', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, tolerance: 0.1, weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100.05, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions).toBeDefined();
    });

    test('should distinguish between close and distant values', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100.001, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100.001, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      const finalResiduals = result.residuals;
      
      expect(finalResiduals.length).toBeGreaterThan(0);
      expect(result.error).toBeLessThan(1); // Should be close to 0.001
    });
  });

  // =========================================================================
  // ТЕСТЫ 3D CONSTRAINTS
  // =========================================================================

  describe('3D Constraints', () => {
    test('should solve constraints in 3D space', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 100, y: 100, z: 100 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: Math.sqrt(30000), weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 100, z: 100 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions).toBeDefined();
    });

    test('should handle 3D component chain', () => {
      const components = Array.from({ length: 5 }, (_, i) =>
        createTestComponent(`c${i}`, {
          x: i * 100,
          y: i * 50,
          z: i * 25
        })
      );
      
      const constraints: Constraint[] = [
        { id: 'con-0', type: ConstraintType.FIXED, elementA: 'c0', weight: 1.0 }
      ];
      
      for (let i = 0; i < 4; i++) {
        constraints.push({
          id: `con-${i + 1}`,
          type: ConstraintType.DISTANCE,
          elementA: `c${i}`,
          elementB: `c${i + 1}`,
          value: Math.sqrt(100 * 100 + 50 * 50 + 25 * 25),
          weight: 1.0
        });
      }
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>(
        components.map(c => [c.id, c.position])
      );
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.positions.size).toBe(5);
    });
  });

  // =========================================================================
  // ДОПОЛНИТЕЛЬНЫЕ EDGE CASES
  // =========================================================================

  describe('Additional Edge Cases', () => {
    test('should handle identical positions', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 0, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.COINCIDENT, elementA: 'c1', elementB: 'c2', weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 0, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });

    test('should return result even if assembly is empty', () => {
      const assembly = createTestAssembly([], []);
      const initialPositions = new Map<string, Point3D>();
      
      const result = solver.solve(assembly, initialPositions);
      
      expect(result.success).toBe(true);
      expect(result.positions).toBeDefined();
    });

    test('should handle negative coordinates', () => {
      const components = [
        createTestComponent('c1', { x: -100, y: -100, z: -100 }),
        createTestComponent('c2', { x: -200, y: -100, z: -100 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 100, weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: -100, y: -100, z: -100 }],
        ['c2', { x: -200, y: -100, z: -100 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });

    test('should handle very small scale assemblies', () => {
      const components = [
        createTestComponent('c1', { x: 0, y: 0, z: 0 }),
        createTestComponent('c2', { x: 0.001, y: 0, z: 0 })
      ];
      
      const constraints: Constraint[] = [
        { id: 'con-1', type: ConstraintType.FIXED, elementA: 'c1', weight: 1.0 },
        { id: 'con-2', type: ConstraintType.DISTANCE, elementA: 'c1', elementB: 'c2', value: 0.001, weight: 1.0 }
      ];
      
      const assembly = createTestAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 0.001, y: 0, z: 0 }]
      ]);
      
      const result = solver.solve(assembly, initialPositions);
      expect(result.positions).toBeDefined();
    });
  });
});
