/**
 * Phase 2 Integration Test
 * Проверяет полную интеграцию ConstraintSolver с CabinetGenerator
 */

import { CabinetGenerator } from '../CabinetGenerator';
import { ConstraintSolver } from '../ConstraintSolver';
import { Assembly, Constraint, ConstraintType } from '../../types/CADTypes';
import { CabinetConfig, Section, Material, TextureType } from '../../types';

describe('Phase 2: Full Integration - Solver with CabinetGenerator', () => {
  let generator: CabinetGenerator;
  let solver: ConstraintSolver;
  let config: CabinetConfig;
  let material: Material;

  beforeEach(() => {
    config = {
      width: 1200,
      height: 2000,
      depth: 600,
      materialId: 'eg-w980',
      doorType: 'hinged',
      doorCount: 2,
      doorGap: 2,
      backType: 'groove',
      construction: 'corpus',
      baseType: 'plinth'
    };

    material = {
      id: 'eg-w980',
      article: 'EG-W980',
      brand: 'Egger',
      name: 'Oak Veneer',
      thickness: 16,
      pricePerM2: 45,
      color: '#D2B48C',
      texture: TextureType.WOOD_OAK,
      isTextureStrict: false
    };

    const testSections: Section[] = [
      {
        id: 'sec-1',
        width: 600,
        items: [
          {
            type: 'shelf',
            id: 'item-1',
            height: 400,
            y: 500,
            name: 'Test Shelf'
          }
        ]
      }
    ];

    generator = new CabinetGenerator(config, testSections, [material]);
    solver = new ConstraintSolver();
  });

  describe('CabinetGenerator Assembly Generation', () => {
    test('should generate valid assembly from panels', () => {
      generator.generate();
      const assembly = generator.generateAssembly();

      expect(assembly).toBeDefined();
      expect(assembly.id).toBeDefined();
      expect(assembly.components).toBeInstanceOf(Array);
      expect(assembly.metadata).toBeDefined();
    });

    test('should generate constraints for assembly', () => {
      generator.generate();
      const constraints = generator.generateConstraints();

      expect(constraints).toBeInstanceOf(Array);
      expect(constraints.length).toBeGreaterThan(0);

      constraints.forEach(c => {
        expect([
          ConstraintType.FIXED,
          ConstraintType.DISTANCE,
          ConstraintType.PARALLEL,
          ConstraintType.PERPENDICULAR,
          ConstraintType.ANGLE,
          ConstraintType.COINCIDENT
        ]).toContain(c.type);
      });
    });

    test('should integrate solved assembly back to panels', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const solverResult = solver.solve(assembly, initialPositions);

      expect(solverResult).toBeDefined();
      expect(solverResult.positions).toBeDefined();

      const solvedAssembly: Assembly = {
        ...assembly,
        components: assembly.components.map(comp => ({
          ...comp,
          position: solverResult.positions.get(comp.id) || comp.position
        }))
      };

      expect(() => {
        generator.integrateFromAssembly(solvedAssembly);
      }).not.toThrow();
    });
  });

  describe('Full Workflow: Generate -> Solve -> Integrate', () => {
    test('should complete full workflow without errors', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const solverResult = solver.solve(assembly, initialPositions);

      expect(solverResult.success).toBeDefined();
      expect(solverResult.positions.size).toBeGreaterThan(0);

      const solvedAssembly: Assembly = {
        ...assembly,
        components: assembly.components.map(comp => ({
          ...comp,
          position: solverResult.positions.get(comp.id) || comp.position
        }))
      };

      expect(() => {
        generator.integrateFromAssembly(solvedAssembly);
      }).not.toThrow();
    });

    test('should use generateWithConstraints() method', () => {
      const result = generator.generateWithConstraints();

      expect(result).toBeDefined();
      expect(result.panels).toBeDefined();
      expect(result.solverResult).toBeDefined();
      expect(result.panels).toBeInstanceOf(Array);
    });
  });

  describe('Solver Options Integration', () => {
    test('should respect custom tolerance', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const resultStrict = solver.solve(assembly, initialPositions, {
        tolerance: 0.0001,
        maxIterations: 500
      });

      expect(resultStrict).toBeDefined();
    });

    test('should respect max iterations limit', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const result = solver.solve(assembly, initialPositions, {
        tolerance: 0.00001,
        maxIterations: 10
      });

      expect(result.iterations).toBeLessThanOrEqual(10);
    });
  });

  describe('Constraint Validation and Checking', () => {
    test('should validate constraint system', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const validation = solver.validateConstraintSystem(assembly);

      expect(validation).toBeDefined();
      expect(validation.isValid).toBeDefined();
      expect(validation.errors).toBeInstanceOf(Array);
      expect(validation.warnings).toBeInstanceOf(Array);
      expect(validation.degreesOfFreedom).toBeGreaterThanOrEqual(0);
      expect(validation.constraintCount).toBeGreaterThan(0);
    });

    test('should check all constraints after solving', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const solverResult = solver.solve(assembly, initialPositions);
      const checks = solver.checkConstraints(assembly, solverResult.positions);

      expect(checks).toBeInstanceOf(Array);
      expect(checks.length).toBe(constraints.length);

      checks.forEach(check => {
        expect(check.constraintId).toBeDefined();
        expect(check.satisfied).toBeDefined();
        expect(check.error).toBeGreaterThanOrEqual(0);
      });
    });
  });

  describe('Performance Metrics', () => {
    test('should track solver timing', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const result = solver.solve(assembly, initialPositions);

      expect(result.solverTime).toBeGreaterThanOrEqual(0);
      expect(result.solverTime).toBeLessThan(5000);
    });

    test('should report iteration count', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const result = solver.solve(assembly, initialPositions);

      expect(result.iterations).toBeGreaterThanOrEqual(0);
      expect(result.iterations).toBeLessThanOrEqual(1000);
    });

    test('should provide convergence status', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();
      assembly.constraints = constraints;

      const initialPositions = new Map();
      for (const comp of assembly.components) {
        initialPositions.set(comp.id, { ...comp.position });
      }

      const result = solver.solve(assembly, initialPositions);

      expect(result.converged).toBeDefined();
      expect(typeof result.converged).toBe('boolean');
      expect(result.message).toBeDefined();
      expect(typeof result.message).toBe('string');
    });
  });

  describe('Error Handling', () => {
    test('should handle missing constraint elements gracefully', () => {
      generator.generate();
      const assembly = generator.generateAssembly();
      const constraints = generator.generateConstraints();

      constraints.push({
        id: 'bad-constraint',
        type: ConstraintType.DISTANCE,
        elementA: 'non-existent-component',
        elementB: 'another-non-existent',
        value: 100,
        weight: 1.0
      });

      assembly.constraints = constraints;

      const validation = solver.validateConstraintSystem(assembly);

      expect(validation.isValid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
    });

    test('should handle empty assembly', () => {
      const emptyAssembly: Assembly = {
        id: 'empty',
        name: 'Empty Assembly',
        components: [],
        constraints: [],
        metadata: {
          version: '1.0.0',
          createdAt: new Date(),
          modifiedAt: new Date()
        }
      };

      const result = solver.solve(emptyAssembly, new Map());

      expect(result).toBeDefined();
      expect(result.success).toBe(true);
      expect(result.positions.size).toBe(0);
    });
  });
});
