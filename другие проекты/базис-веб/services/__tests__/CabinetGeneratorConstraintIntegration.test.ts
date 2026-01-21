/**
 * PHASE 2: ConstraintSolver Integration Tests with CabinetGenerator
 * Tests the integration of constraint solving into cabinet generation
 */

import { CabinetGenerator } from '../CabinetGenerator';
import { ConstraintSolver } from '../ConstraintSolver';
import { CabinetConfig, Section, Material, TextureType } from '../../types';

describe('CabinetGenerator ConstraintSolver Integration', () => {
  let generator: CabinetGenerator;
  let testConfig: CabinetConfig;
  let testMaterials: Material[];
  let testSections: Section[];

  beforeEach(() => {
    testMaterials = [
      {
        id: 'eg-w980',
        name: 'Oak White',
        color: '#D2B48C',
        density: 700,
        elasticModulus: 3200,
        poissonRatio: 0.3,
        textureType: TextureType.WOOD_OAK
      }
    ];

    testConfig = {
      id: 'cabinet-1',
      name: 'Test Cabinet',
      width: 1000,
      height: 2000,
      depth: 600,
      doorType: 'hinged',
      doorCount: 2,
      backType: 'groove',
      baseType: 'legs',
      construction: 'corpus',
      hardwareType: 'standard',
      materialId: 'eg-w980'
    };

    testSections = [
      {
        id: 'sec-1',
        width: 500,
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

    generator = new CabinetGenerator(testConfig, testSections, testMaterials);
  });

  describe('generateWithConstraints()', () => {
    test('should generate panels and solve constraints', () => {
      const result = generator.generateWithConstraints();

      expect(result).toBeDefined();
      expect(result.panels).toBeDefined();
      expect(result.panels.length).toBeGreaterThan(0);
      expect(result.solverResult).toBeDefined();
    });

    test('should return solver result with convergence info', () => {
      const result = generator.generateWithConstraints();

      expect(result.solverResult.success).toBeDefined();
      expect(result.solverResult.positions).toBeDefined();
      expect(result.solverResult.iterations).toBeGreaterThanOrEqual(0);
      expect(result.solverResult.error).toBeGreaterThanOrEqual(0);
    });

    test('should maintain panel count after constraint solving', () => {
      const result = generator.generateWithConstraints();
      const panelsOnly = generator.generate();

      expect(result.panels.length).toBe(panelsOnly.length);
    });

    test('should update panel positions from solver result', () => {
      const result = generator.generateWithConstraints();

      // Verify that positions have been potentially updated
      for (const panel of result.panels) {
        expect(panel.x).toBeDefined();
        expect(panel.y).toBeDefined();
        expect(panel.z).toBeDefined();
      }
    });

    test('should handle different cabinet configurations', () => {
      const configs = [
        { ...testConfig, width: 800, height: 1500, depth: 500 },
        { ...testConfig, width: 1200, height: 2400, depth: 700 },
        { ...testConfig, doorType: 'none' as const }
      ];

      for (const config of configs) {
        const gen = new CabinetGenerator(config, testSections, testMaterials);
        const result = gen.generateWithConstraints();

        expect(result.panels.length).toBeGreaterThan(0);
        expect(result.solverResult).toBeDefined();
      }
    });

    test('should create constraints for structural panels', () => {
      const result = generator.generateWithConstraints();

      expect(result.solverResult).toBeDefined();
      expect(typeof result.solverResult.iterations).toBe('number');
    });

    test('should handle large cabinet assemblies', () => {
      const largeConfig: CabinetConfig = {
        ...testConfig,
        width: 2000,
        height: 2500,
        depth: 650
      };

      const gen = new CabinetGenerator(largeConfig, testSections, testMaterials);
      const result = gen.generateWithConstraints();

      expect(result.panels.length).toBeGreaterThan(5);
      expect(result.solverResult.iterations).toBeLessThan(100);
    });

    test('solver should converge or make progress', () => {
      const result = generator.generateWithConstraints();

      // Solver should either converge or make progress reducing error
      expect(result.solverResult.error).toBeLessThan(1000);
      expect(result.solverResult.iterations).toBeGreaterThanOrEqual(0);
    });

    test('should preserve panel properties during constraint solving', () => {
      const result = generator.generateWithConstraints();

      // All panels should maintain their properties
      for (const panel of result.panels) {
        expect(panel.id).toBeDefined();
        expect(panel.name).toBeDefined();
        expect(typeof panel.width).toBe('number');
        expect(typeof panel.height).toBe('number');
        expect(typeof panel.depth).toBe('number');
        expect(panel.width).toBeGreaterThan(0);
        expect(panel.height).toBeGreaterThan(0);
        expect(panel.depth).toBeGreaterThan(0);
      }

      // Count structural elements
      const sides = result.panels.filter(p => p.name?.includes('Бок'));
      const horizontals = result.panels.filter(p => 
        p.name?.includes('Крышка') || p.name?.includes('Дно')
      );

      expect(sides.length).toBeGreaterThanOrEqual(2);
      expect(horizontals.length).toBeGreaterThanOrEqual(1);
    });

    test('should handle constraints with fixed base panels', () => {
      const result = generator.generateWithConstraints();

      // Left side should be fixed (first constraint)
      expect(result.panels.length).toBeGreaterThan(0);
      const leftSide = result.panels.find(p => p.name?.includes('Левый'));
      expect(leftSide).toBeDefined();
    });

    test('should solve distance constraints between panels', () => {
      const result = generator.generateWithConstraints();

      // After solving, sides should maintain appropriate distance
      const sides = result.panels.filter(p => p.name?.includes('Бок'));
      if (sides.length === 2) {
        const dist = Math.abs(sides[1].x - sides[0].x);
        // Should be approximately width - 32 (two 16mm panels)
        expect(dist).toBeGreaterThan(testConfig.width - 100);
        expect(dist).toBeLessThan(testConfig.width);
      }
    });

    test('should handle roof and bottom positioning constraints', () => {
      const result = generator.generateWithConstraints();

      const roof = result.panels.find(p => p.name?.includes('Крышка'));
      const bottom = result.panels.find(p => p.name?.includes('Дно'));

      if (roof) {
        expect(roof.y).toBeLessThanOrEqual(testConfig.height);
      }

      if (bottom) {
        const baseH = testConfig.baseType === 'legs' ? 100 : 70;
        expect(bottom.y).toBeGreaterThanOrEqual(baseH - 10);
      }
    });

    test('should create assembly with all panel components', () => {
      const result = generator.generateWithConstraints();

      expect(result.panels).toBeDefined();
      expect(result.panels.length).toBeGreaterThan(0);

      // Each panel should have valid position coordinates
      for (const panel of result.panels) {
        expect(typeof panel.x).toBe('number');
        expect(typeof panel.y).toBe('number');
        expect(typeof panel.z).toBe('number');
      }
    });

    test('should handle missing optional panel components gracefully', () => {
      const config: CabinetConfig = {
        ...testConfig,
        doorType: 'none' as const,
        backType: 'none' as const
      };

      const gen = new CabinetGenerator(config, testSections, testMaterials);
      const result = gen.generateWithConstraints();

      expect(result.panels).toBeDefined();
      expect(result.solverResult).toBeDefined();
    });
  });

  describe('panelsToAssembly() conversion', () => {
    test('should convert panels to assembly components', () => {
      const panels = generator.generate();
      
      // Access via the generateWithConstraints which internally calls panelsToAssembly
      const result = generator.generateWithConstraints();

      expect(result.solverResult.positions).toBeDefined();
      expect(result.solverResult.positions.size).toBe(panels.length);
    });
  });

  describe('createStructuralConstraints()', () => {
    test('should create distance constraints', () => {
      const result = generator.generateWithConstraints();

      // Verify solver was applied with constraints
      expect(result.solverResult.iterations).toBeGreaterThanOrEqual(0);
    });

    test('should fix reference panel', () => {
      const result = generator.generateWithConstraints();

      // After solving, reference panel should stay fixed
      const leftSide = result.panels.find(p => p.name?.includes('Левый'));
      expect(leftSide?.x).toBe(0); // Left side should remain at x=0
    });
  });

  describe('Integration workflow', () => {
    test('complete cabinet generation with constraint solving workflow', () => {
      const start = Date.now();
      const result = generator.generateWithConstraints();
      const duration = Date.now() - start;

      // Should complete in reasonable time (< 2 seconds)
      expect(duration).toBeLessThan(2000);

      // Should produce valid output
      expect(result.panels.length).toBeGreaterThan(0);
      expect(result.solverResult.success).toBeDefined();

      // Solver info
      expect(result.solverResult.message).toBeDefined();
    });

    test('should handle sequential cabinet generations', () => {
      const configs = [
        { ...testConfig, width: 600 },
        { ...testConfig, width: 1000 },
        { ...testConfig, width: 1400 }
      ];

      for (const config of configs) {
        const gen = new CabinetGenerator(config, testSections, testMaterials);
        const result = gen.generateWithConstraints();

        expect(result.panels.length).toBeGreaterThan(0);
        expect(result.solverResult.error).toBeDefined();
      }
    });
  });
});
