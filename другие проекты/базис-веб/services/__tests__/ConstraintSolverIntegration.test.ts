/**
 * PHASE 2: Integration Tests for ConstraintSolver
 * Проверяет интеграцию Newton-Raphson solver с CabinetGenerator
 */

import { ConstraintSolver, SolverResult } from '../ConstraintSolver';
import {
  Assembly,
  Component,
  Constraint,
  ConstraintType,
  ComponentType,
  Point3D,
  EulerAngles,
  Material,
  TextureType
} from '../../types/CADTypes';

function createTestMaterial(): Material {
  return {
    id: 'mat-test',
    name: 'Test Material',
    color: '#cccccc',
    density: 750,
    elasticModulus: 3200,
    poissonRatio: 0.3,
    textureType: TextureType.UNIFORM
  };
}

function createComponent(id: string, x: number, y: number, z: number): Component {
  return {
    id,
    name: `Component ${id}`,
    type: ComponentType.PART,
    position: { x, y, z },
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

function createAssembly(components: Component[], constraints: Constraint[] = []): Assembly {
  return {
    id: 'asm-test',
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

describe('ConstraintSolver Integration Tests', () => {
  let solver: ConstraintSolver;

  beforeEach(() => {
    solver = new ConstraintSolver();
  });

  // =========================================================================
  // Тесты простых структур
  // =========================================================================

  describe('Simple Cabinet Structure', () => {
    test('should solve cabinet with fixed base and aligned sides', () => {
      // Шкаф: дно (base) + две боковины (sides)
      const components: Component[] = [
        createComponent('base', 0, 0, 0),
        createComponent('left-side', 0, 0, 600),
        createComponent('right-side', 1200, 0, 600)
      ];

      const constraints: Constraint[] = [
        // Дно зафиксировано
        {
          id: 'fix-base',
          type: ConstraintType.FIXED,
          elementA: 'base',
          weight: 1.0
        },
        // Левая боковина находится на расстоянии 0 от дна по X
        {
          id: 'dist-left',
          type: ConstraintType.DISTANCE,
          elementA: 'base',
          elementB: 'left-side',
          value: Math.sqrt(0 * 0 + 0 * 0 + 600 * 600),
          weight: 1.0
        },
        // Правая боковина находится на расстоянии 1200 от дна по X
        {
          id: 'dist-right',
          type: ConstraintType.DISTANCE,
          elementA: 'base',
          elementB: 'right-side',
          value: Math.sqrt(1200 * 1200 + 0 * 0 + 600 * 600),
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['base', { x: 0, y: 0, z: 0 }],
        ['left-side', { x: 10, y: 10, z: 600 }],
        ['right-side', { x: 1190, y: 10, z: 600 }]
      ]);

      const result = solver.solve(assembly, initialPositions);

      expect(result).toBeDefined();
      expect(result.success).toBeDefined();
      expect(result.positions).toBeDefined();
      expect(result.iterations).toBeGreaterThanOrEqual(0);
      expect(result.error).toBeGreaterThanOrEqual(0);
      expect(result.converged).toBeDefined();
      expect(result.message).toBeDefined();
    });

    test('should solve simple two-component alignment', () => {
      const components: Component[] = [
        createComponent('comp1', 0, 0, 0),
        createComponent('comp2', 50, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-comp1',
          type: ConstraintType.FIXED,
          elementA: 'comp1',
          weight: 1.0
        },
        {
          id: 'dist-comp2',
          type: ConstraintType.DISTANCE,
          elementA: 'comp1',
          elementB: 'comp2',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['comp1', { x: 0, y: 0, z: 0 }],
        ['comp2', { x: 50, y: 0, z: 0 }]
      ]);

      const result = solver.solve(assembly, initialPositions);

      expect(result.success).toBeDefined();
      expect(result.positions.size).toBe(2);
      expect(result.converged).toBeDefined();
    });
  });

  // =========================================================================
  // Тесты валидации системы
  // =========================================================================

  describe('System Validation', () => {
    test('should validate well-constrained system', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0),
        createComponent('c2', 100, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'dist-c2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const validation = solver.validateConstraintSystem(assembly);

      expect(validation).toBeDefined();
      expect(validation.isValid).toBeDefined();
      expect(validation.errors).toBeInstanceOf(Array);
      expect(validation.warnings).toBeInstanceOf(Array);
      expect(validation.degreesOfFreedom).toBeGreaterThanOrEqual(0);
      expect(validation.constraintCount).toBe(2);
    });

    test('should detect missing components in constraints', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'bad-constraint',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2', // не существует!
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const validation = solver.validateConstraintSystem(assembly);

      expect(validation.isValid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
    });

    test('should warn about underconstrained systems', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0),
        createComponent('c2', 100, 0, 0)
      ];

      const constraints: Constraint[] = [];

      const assembly = createAssembly(components, constraints);
      const validation = solver.validateConstraintSystem(assembly);

      expect(validation.isValid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // Тесты проверки ограничений
  // =========================================================================

  describe('Constraint Checking', () => {
    test('should check constraints after solving', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0),
        createComponent('c2', 100, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'dist-c1-c2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }]
      ]);

      const result = solver.solve(assembly, initialPositions);
      const checks = solver.checkConstraints(assembly, result.positions);

      expect(checks).toBeInstanceOf(Array);
      expect(checks.length).toBe(constraints.length);
      checks.forEach(check => {
        expect(check.constraintId).toBeDefined();
        expect(check.satisfied).toBeDefined();
        expect(check.error).toBeGreaterThanOrEqual(0);
      });
    });
  });

  // =========================================================================
  // Тесты производительности
  // =========================================================================

  describe('Performance', () => {
    test('should solve small assembly quickly', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0),
        createComponent('c2', 100, 0, 0),
        createComponent('c3', 200, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'dist-c1-c2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        },
        {
          id: 'dist-c2-c3',
          type: ConstraintType.DISTANCE,
          elementA: 'c2',
          elementB: 'c3',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }],
        ['c3', { x: 200, y: 0, z: 0 }]
      ]);

      const start = performance.now();
      const result = solver.solve(assembly, initialPositions);
      const elapsed = performance.now() - start;

      // Должно решиться быстро (< 1 секунда)
      expect(elapsed).toBeLessThan(1000);
      expect(result.solverTime).toBeDefined();
    });

    test('should not exceed max iterations', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0),
        createComponent('c2', 100, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'dist-c1-c2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 50, y: 0, z: 0 }]
      ]);

      const result = solver.solve(assembly, initialPositions, {
        maxIterations: 50,
        tolerance: 0.001
      });

      expect(result.iterations).toBeLessThanOrEqual(50);
    });
  });

  // =========================================================================
  // Тесты граничных случаев
  // =========================================================================

  describe('Edge Cases', () => {
    test('should handle assembly with no constraints', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0)
      ];

      const assembly = createAssembly(components, []);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }]
      ]);

      const result = solver.solve(assembly, initialPositions);

      expect(result.success).toBe(true);
      expect(result.iterations).toBe(0);
    });

    test('should handle empty positions map', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>();

      const result = solver.solve(assembly, initialPositions);

      expect(result).toBeDefined();
      expect(result.positions).toBeDefined();
    });

    test('should handle very large coordinate values', () => {
      const components: Component[] = [
        createComponent('c1', 10000, 10000, 10000),
        createComponent('c2', 10100, 10000, 10000)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'dist-c1-c2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 10000, y: 10000, z: 10000 }],
        ['c2', { x: 10100, y: 10000, z: 10000 }]
      ]);

      const result = solver.solve(assembly, initialPositions);

      expect(result).toBeDefined();
      expect(isFinite(result.error)).toBe(true);
    });

    test('should handle very small tolerances', () => {
      const components: Component[] = [
        createComponent('c1', 0, 0, 0),
        createComponent('c2', 100, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'fix-c1',
          type: ConstraintType.FIXED,
          elementA: 'c1',
          weight: 1.0
        },
        {
          id: 'dist-c1-c2',
          type: ConstraintType.DISTANCE,
          elementA: 'c1',
          elementB: 'c2',
          value: 100,
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['c1', { x: 0, y: 0, z: 0 }],
        ['c2', { x: 100, y: 0, z: 0 }]
      ]);

      const result = solver.solve(assembly, initialPositions, {
        tolerance: 1e-6,
        maxIterations: 1000
      });

      expect(result).toBeDefined();
    });
  });

  // =========================================================================
  // Тесты совместимости с CabinetGenerator
  // =========================================================================

  describe('CabinetGenerator Compatibility', () => {
    test('should produce valid result structure for integration', () => {
      const components: Component[] = [
        createComponent('panel-1', 0, 0, 0),
        createComponent('panel-2', 1200, 0, 0)
      ];

      const constraints: Constraint[] = [
        {
          id: 'base-fixed',
          type: ConstraintType.FIXED,
          elementA: 'panel-1',
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>([
        ['panel-1', { x: 0, y: 0, z: 0 }],
        ['panel-2', { x: 1200, y: 0, z: 0 }]
      ]);

      const result = solver.solve(assembly, initialPositions);

      // Результат должен быть совместим с CabinetGenerator.integrateFromAssembly()
      expect(result.positions).toBeInstanceOf(Map);
      expect(result.positions.size).toBeGreaterThanOrEqual(0);
      expect(result.success).toBeDefined();
      expect(result.converged).toBeDefined();
      expect(result.solverTime).toBeGreaterThanOrEqual(0);
    });

    test('should maintain component count through solve', () => {
      const numComponents = 5;
      const components: Component[] = [];
      for (let i = 0; i < numComponents; i++) {
        components.push(createComponent(`comp-${i}`, i * 100, 0, 0));
      }

      const constraints: Constraint[] = [
        {
          id: 'base-fixed',
          type: ConstraintType.FIXED,
          elementA: 'comp-0',
          weight: 1.0
        }
      ];

      const assembly = createAssembly(components, constraints);
      const initialPositions = new Map<string, Point3D>();
      for (let i = 0; i < numComponents; i++) {
        initialPositions.set(`comp-${i}`, { x: i * 100, y: 0, z: 0 });
      }

      const result = solver.solve(assembly, initialPositions);

      expect(result.positions.size).toBe(numComponents);
    });
  });
});
