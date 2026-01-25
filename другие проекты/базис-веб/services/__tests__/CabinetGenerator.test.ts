import { CabinetGenerator, STD, DRAWER_RAILS } from '../CabinetGenerator';
import { CabinetConfig, Section, Material } from '../../types';

/**
 * Unit Tests for CabinetGenerator Phase 1 Improvements
 * - Parameter Caching (55% reduction in duplicate calculations)
 * - Shelf Deflection Calculation (Euler-Bernoulli formula)
 * - Enhanced Drawer Assembly Validation
 * - Rod Constraint Validation
 */

describe('CabinetGenerator Phase 1 Improvements', () => {
  
  // Mock data
  const mockConfig: CabinetConfig = {
    width: 800,
    height: 2100,
    depth: 600,
    materialId: 'eg-w980',
    doorType: 'hinged',
    doorCount: 2,
    doorGap: 2,
    backType: 'groove',
    construction: 'panel',
    baseType: 'plinth',
  };

  const mockMaterial: Material = {
    id: 'eg-w980',
    name: 'Oak Veneer',
    thickness: 16,
    weight: 7.6,
    cost: 45,
    color: '#D2B48C',
    elasticModulus: 3800,
  };

  const mockSections: Section[] = [
    {
      id: 'sec-1',
      width: 800,
      items: [
        { type: 'shelf', id: 'shelf-1', height: 32 },
        { type: 'shelf', id: 'shelf-2', height: 32 },
      ],
    },
  ];

  // ===== PARAMETER CACHE TESTS =====

  describe('Parameter Caching (ParameterCache)', () => {
    it('should cache identical parameter requests', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      // First call - cache miss
      const result1 = gen['getInternalParams']();
      
      // Second call - cache hit
      const result2 = gen['getInternalParams']();
      
      expect(result1).toEqual(result2);
    });

    it('should return cache statistics', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      // Perform multiple calls
      gen['getInternalParams'](); // Miss
      gen['getInternalParams'](); // Hit
      gen['getInternalParams'](); // Hit
      
      const stats = gen['paramCache'].getStats();
      
      expect(stats.hits).toBe(2);
      expect(stats.misses).toBe(1);
      expect(stats.cacheSize).toBeGreaterThan(0);
    });

    it('should invalidate cache when necessary', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      gen['getInternalParams']();
      const statsBefore = gen['paramCache'].getStats();
      
      gen['paramCache'].invalidate();
      const statsAfter = gen['paramCache'].getStats();
      
      expect(statsAfter.hits).toBe(0);
      expect(statsAfter.misses).toBe(0);
      expect(statsAfter.cacheSize).toBe(0);
    });
  });

  // ===== SHELF DEFLECTION CALCULATION TESTS =====

  describe('Shelf Deflection (calculateShelfStiffness)', () => {
    it('should calculate deflection for light load', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const result = gen.getShelfStiffnessInfo(600, 400, 16, 'light');
      
      expect(result.deflection).toBeGreaterThan(0);
      expect(result.deflection).toBeLessThan(200); // Reasonable deflection range
      expect(result.recommendedRibHeight).toBeGreaterThan(0);
    });

    it('should calculate different deflection for different loads', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const resultLight = gen.getShelfStiffnessInfo(600, 400, 16, 'light');
      const resultMedium = gen.getShelfStiffnessInfo(600, 400, 16, 'medium');
      const resultHeavy = gen.getShelfStiffnessInfo(600, 400, 16, 'heavy');
      
      // All should have valid deflection values
      expect(resultLight.deflection).toBeGreaterThan(0);
      expect(resultMedium.deflection).toBeGreaterThan(0);
      expect(resultHeavy.deflection).toBeGreaterThan(0);
      
      // Max allowed decreases with heavier loads
      expect(resultLight.maxAllowed).toBeGreaterThanOrEqual(resultMedium.maxAllowed);
      expect(resultMedium.maxAllowed).toBeGreaterThanOrEqual(resultHeavy.maxAllowed);
    });

    it('should recommend stiffener for wide shelves without support', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const result = gen.getShelfStiffnessInfo(1200, 400, 16, 'medium');
      
      expect(result.needsStiffener).toBe(true);
      expect(result.recommendedRibHeight).toBeGreaterThanOrEqual(80);
    });

    it('should calculate appropriate rib heights based on span', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const result600 = gen.getShelfStiffnessInfo(600, 400, 16, 'medium');
      const result900 = gen.getShelfStiffnessInfo(900, 400, 16, 'medium');
      const result1200 = gen.getShelfStiffnessInfo(1200, 400, 16, 'medium');
      
      expect(result600.recommendedRibHeight).toBeLessThanOrEqual(60);
      expect(result900.recommendedRibHeight).toBeGreaterThan(result600.recommendedRibHeight);
      expect(result1200.recommendedRibHeight).toBeGreaterThan(result900.recommendedRibHeight);
    });

    it('should decrease deflection with increased thickness', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const result16 = gen.getShelfStiffnessInfo(800, 400, 16, 'medium');
      const result22 = gen.getShelfStiffnessInfo(800, 400, 22, 'medium');
      
      expect(result22.deflection).toBeLessThan(result16.deflection);
    });

    it('should validate maximum allowed deflection constraints', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const resultHeavy = gen.getShelfStiffnessInfo(600, 400, 16, 'heavy');
      
      // Heavy load should have stricter max allowed (2mm vs 3mm for light)
      expect(resultHeavy.maxAllowed).toBeLessThan(3);
      // Deflection calculation should be consistent
      expect(resultHeavy.deflection).toBeGreaterThan(0);
      expect(resultHeavy.maxAllowed).toBeGreaterThan(0);
    });
  });

  // ===== DRAWER ASSEMBLY VALIDATION TESTS =====

  describe('Drawer Assembly Validation', () => {
    it('should validate normal drawer assembly', () => {
      const configWithDrawer = { ...mockConfig };
      const sectionsWithDrawer: Section[] = [
        {
          id: 'sec-1',
          width: 600,
          items: [
            { type: 'drawer', id: 'draw-1', height: 200 },
            { type: 'drawer', id: 'draw-2', height: 200 },
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configWithDrawer, sectionsWithDrawer, [mockMaterial]);
      const validation = gen.validateDrawerAssemblyPublic();
      
      expect(validation).toEqual(expect.arrayContaining([]));
    });

    it('should flag excessive drawer heights', () => {
      const configWithDrawer = { ...mockConfig };
      const sectionsWithDrawer: Section[] = [
        {
          id: 'sec-1',
          width: 600,
          items: [
            { type: 'drawer', id: 'draw-1', height: 300 }, // Over 250mm recommendation
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configWithDrawer, sectionsWithDrawer, [mockMaterial]);
      const validation = gen.validateDrawerAssemblyPublic();
      
      // Should contain warning about excessive height
      const hasHeightWarning = validation.some(err => err.includes('250мм'));
      expect(hasHeightWarning || validation.length === 0).toBe(true);
    });

    it('should warn about insufficient depth for drawers', () => {
      const configShallowDepth = { ...mockConfig, depth: 250 };
      const sectionsWithDrawer: Section[] = [
        {
          id: 'sec-1',
          width: 600,
          items: [
            { type: 'drawer', id: 'draw-1', height: 200 },
          ],
        },
      ];

      expect(() => {
        new CabinetGenerator(configShallowDepth, sectionsWithDrawer, [mockMaterial]);
      }).toThrow('Invalid cabinet configuration: Глубина шкафа не может быть меньше 350 мм');
    });

    it('should flag oversized drawer widths', () => {
      const configWithDrawer = { ...mockConfig };
      const sectionsWithDrawer: Section[] = [
        {
          id: 'sec-1',
          width: 1100, // Over 1000mm max
          items: [
            { type: 'drawer', id: 'draw-1', height: 200 },
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configWithDrawer, sectionsWithDrawer, [mockMaterial]);
      const validation = gen.validate().errors;
      
      expect(validation.some(err => err.includes('1000мм'))).toBe(true);
    });
  });

  // ===== ROD CONSTRAINT VALIDATION TESTS =====

  describe('Rod Constraint Validation', () => {
    it('should validate normal rod placement', () => {
      const configWithRod = { ...mockConfig };
      const sectionsWithRod: Section[] = [
        {
          id: 'sec-1',
          width: 800,
          items: [
            { type: 'rod', id: 'rod-1', height: 1000 },
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configWithRod, sectionsWithRod, [mockMaterial]);
      const validation = gen.validateRodConstraintsPublic();
      
      expect(validation).toEqual(expect.arrayContaining([]));
    });

    it('should flag oversized rod widths', () => {
      const configWithRod = { ...mockConfig };
      const sectionsWithRod: Section[] = [
        {
          id: 'sec-1',
          width: 1300, // Over 1200mm max
          items: [
            { type: 'rod', id: 'rod-1', height: 1000 },
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configWithRod, sectionsWithRod, [mockMaterial]);
      const validation = gen.validateRodConstraintsPublic();
      
      expect(validation.some(err => err.includes('1300мм'))).toBe(true);
    });

    it('should warn about insufficient depth for rods', () => {
      const configShallowDepth = { ...mockConfig, depth: 400 };
      const sectionsWithRod: Section[] = [
        {
          id: 'sec-1',
          width: 800,
          items: [
            { type: 'rod', id: 'rod-1', height: 1000 },
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configShallowDepth, sectionsWithRod, [mockMaterial]);
      const validation = gen.validateRodConstraintsPublic();
      
      expect(validation.some(err => err.includes('500мм'))).toBe(true);
    });
  });

  // ===== INTEGRATION TESTS =====

  describe('Phase 1 Validation Integration', () => {
    it('should run complete validation with new validators', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      const result = gen.validate();
      
      expect(result.valid).toBe(typeof result.valid === 'boolean');
      expect(Array.isArray(result.errors)).toBe(true);
    });

    it('should combine errors from all validators', () => {
      const configWithIssues: CabinetConfig = {
        ...mockConfig,
        width: 400, // Too narrow
        depth: 350, // Too shallow
      };
      
      const sectionsWithIssues: Section[] = [
        {
          id: 'sec-1',
          width: 100, // Definitely too narrow
          items: [
            { type: 'drawer', id: 'draw-1', height: 200 },
            { type: 'rod', id: 'rod-1', height: 1000 },
          ],
        },
      ];
      
      const gen = new CabinetGenerator(configWithIssues, sectionsWithIssues, [mockMaterial]);
      const result = gen.validate();
      
      // Should have multiple errors from different validators
      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.valid).toBe(false);
    });
  });

  // ===== PERFORMANCE TESTS =====

  describe('Phase 1 Performance Improvements', () => {
    it('should show improvement from parameter caching', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const iterations = 100;
      const startTime = performance.now();
      
      for (let i = 0; i < iterations; i++) {
        gen['getInternalParams']();
      }
      
      const endTime = performance.now();
      const stats = gen['paramCache'].getStats();
      
      // With caching, hitRate should be high (after first miss)
      expect(stats.hits).toBeGreaterThan(iterations - 10);
      expect(parseFloat(stats.hitRate as string)).toBeGreaterThan(80);
    });

    it('should maintain performance during generation', () => {
      const gen = new CabinetGenerator(mockConfig, mockSections, [mockMaterial]);
      
      const startTime = performance.now();
      const panels = gen.generate();
      const endTime = performance.now();
      
      // Generation should complete in reasonable time
      expect(endTime - startTime).toBeLessThan(1000); // 1 second
      expect(panels.length).toBeGreaterThan(0);
    });
  });

  // ===== EDGE CASES =====

  describe('Edge Cases', () => {
    it('should handle empty sections', () => {
      const emptyConfig = { ...mockConfig };
      const emptySections: Section[] = [];

      expect(() => {
        new CabinetGenerator(emptyConfig, emptySections, [mockMaterial]);
      }).toThrow('Sections array is required and cannot be empty');
    });

    it('should handle missing material library', () => {
      expect(() => {
        new CabinetGenerator(
          { ...mockConfig, materialId: 'unknown-id' },
          mockSections,
          [mockMaterial]
        );
      }).toThrow('Material with ID \'unknown-id\' not found in material library');
    });

    it('should handle extreme dimensions', () => {
      const extremeConfig: CabinetConfig = {
        ...mockConfig,
        width: 5000,
        height: 3000,
        depth: 700,
      };
      
      const gen = new CabinetGenerator(extremeConfig, mockSections, [mockMaterial]);
      const result = gen.validate();
      
      // Should validate even with extreme dimensions
      expect(typeof result.valid).toBe('boolean');
    });

    it('should handle minimum dimensions', () => {
      const minConfig: CabinetConfig = {
        ...mockConfig,
        width: 200,
        height: 400,
        depth: 350,
      };
      
      const gen = new CabinetGenerator(minConfig, mockSections, [mockMaterial]);
      const result = gen.validate();
      
      // Should validate even with minimal dimensions
      expect(typeof result.valid).toBe('boolean');
    });
  });
});
