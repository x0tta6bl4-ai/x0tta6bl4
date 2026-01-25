/**
 * PHASE 3: BillOfMaterials and HierarchyManager Tests
 * Comprehensive unit tests for BOM generation and hierarchy management
 */

import {
  BillOfMaterialsGenerator,
  BOMMaterial,
  BOMItem,
  BOMReport
} from '../BillOfMaterials';
import {
  HierarchyManager,
  HierarchyNode,
  ComponentFilter
} from '../HierarchyManager';
import {
  Assembly,
  Component,
  ComponentType,
  Material,
  TextureType,
  MaterialCost
} from '../../types/CADTypes';

describe('BillOfMaterials', () => {
  let generator: BillOfMaterialsGenerator;
  let testAssembly: Assembly;
  let testMaterial: Material;

  beforeEach(() => {
    testMaterial = {
      id: 'eg-w980',
      name: 'Oak White',
      color: '#D2B48C',
      density: 700,
      elasticModulus: 3200,
      poissonRatio: 0.3,
      textureType: TextureType.WOOD_OAK
    };

    const testComponent: Component = {
      id: 'comp-1',
      name: 'Test Panel',
      type: ComponentType.PART,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material: testMaterial,
      properties: {
        width: 1000,
        height: 2000,
        depth: 16
      }
    };

    testAssembly = {
      id: 'asm-1',
      name: 'Test Assembly',
      components: [testComponent],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };

    const materialCosts: MaterialCost[] = [
      {
        materialId: 'eg-w980',
        pricePerKg: 150
      }
    ];

    generator = new BillOfMaterialsGenerator(materialCosts);
  });

  describe('generateBOM', () => {
    test('should generate BOM for single component', () => {
      const report = generator.generateBOM(testAssembly);

      expect(report).toBeDefined();
      expect(report.items).toBeDefined();
      expect(report.materials).toBeDefined();
      expect(report.meta).toBeDefined();
      expect(report.items.length).toBe(1);
    });

    test('should calculate correct volume', () => {
      const report = generator.generateBOM(testAssembly);
      const item = report.items[0];

      // Volume = (1000 * 2000 * 16) / (1000^3) = 0.032 m³
      expect(item.volume).toBeCloseTo(0.032, 5);
    });

    test('should calculate correct mass', () => {
      const report = generator.generateBOM(testAssembly);
      const item = report.items[0];

      // Mass = volume * density = 0.032 * 700 = 22.4 kg
      expect(item.mass).toBeCloseTo(22.4, 1);
    });

    test('should calculate correct cost', () => {
      const report = generator.generateBOM(testAssembly);
      const item = report.items[0];

      // Cost = mass * pricePerKg = 22.4 * 150 = 3360 ₽
      expect(item.cost).toBeCloseTo(3360, 0);
    });

    test('should handle multiple components', () => {
      const component2: Component = {
        id: 'comp-2',
        name: 'Panel 2',
        type: ComponentType.PART,
        position: { x: 100, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material: testMaterial,
        properties: {
          width: 800,
          height: 2000,
          depth: 16
        }
      };

      testAssembly.components.push(component2);
      const report = generator.generateBOM(testAssembly);

      expect(report.items.length).toBe(2);
      expect(report.materials[0].quantity).toBe(2);
    });

    test('should skip ASSEMBLY type components', () => {
      const assemblyComponent: Component = {
        id: 'asm-comp',
        name: 'Subassembly',
        type: ComponentType.ASSEMBLY,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material: testMaterial,
        properties: {}
      };

      testAssembly.components.push(assemblyComponent);
      const report = generator.generateBOM(testAssembly);

      expect(report.items.length).toBe(1); // Only PART counted
    });

    test('should aggregate components by material', () => {
      const component2: Component = {
        id: 'comp-2',
        name: 'Another Panel',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material: testMaterial,
        properties: {
          width: 500,
          height: 500,
          depth: 16
        }
      };

      testAssembly.components.push(component2);
      const report = generator.generateBOM(testAssembly);

      expect(report.materials.length).toBe(1);
      expect(report.materials[0].quantity).toBe(2);
      expect(report.materials[0].materialName).toBe('Oak White');
    });
  });

  describe('setMaterialCosts', () => {
    test('should update material costs', () => {
      const newCosts: MaterialCost[] = [
        {
          materialId: 'eg-w980',
          pricePerKg: 200
        }
      ];

      generator.setMaterialCosts(newCosts);
      const report = generator.generateBOM(testAssembly);
      const item = report.items[0];

      // New cost = 22.4 * 200 = 4480 ₽
      expect(item.cost).toBeCloseTo(4480, 0);
    });

    test('should add individual material cost', () => {
      const cost: MaterialCost = {
        materialId: 'plywood',
        pricePerKg: 80
      };

      generator.addMaterialCost(cost);

      const material: Material = {
        id: 'plywood',
        name: 'Plywood',
        color: '#8B7355',
        density: 600
      };

      const component: Component = {
        id: 'comp-3',
        name: 'Plywood Panel',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material,
        properties: { width: 1000, height: 2000, depth: 18 }
      };

      testAssembly.components.push(component);
      const report = generator.generateBOM(testAssembly);

      expect(report.items.length).toBe(2);
    });
  });

  describe('exportToCSV', () => {
    test('should export to CSV format', () => {
      const report = generator.generateBOM(testAssembly);
      const csv = generator.exportToCSV(report);

      expect(csv).toBeDefined();
      expect(csv).toContain('Компонент,Тип,Материал');
      expect(csv).toContain('Test Panel');
      expect(csv).toContain('Oak White');
    });

    test('should include summary in CSV', () => {
      const report = generator.generateBOM(testAssembly);
      const csv = generator.exportToCSV(report);

      expect(csv).toContain('Материал,Количество,Общий объём');
      expect(csv).toContain('ИТОГО');
      expect(csv).toContain('Всего компонентов');
    });

    test('should format numbers correctly in CSV', () => {
      const report = generator.generateBOM(testAssembly);
      const csv = generator.exportToCSV(report);

      // Check for formatted mass (2 decimals)
      expect(csv).toMatch(/22\.\d{2}/);
    });
  });

  describe('exportToJSON', () => {
    test('should export to JSON format', () => {
      const report = generator.generateBOM(testAssembly);
      const json = generator.exportToJSON(report);

      expect(json).toBeDefined();
      const parsed = JSON.parse(json);
      expect(parsed.items).toBeDefined();
      expect(parsed.materials).toBeDefined();
      expect(parsed.meta).toBeDefined();
    });

    test('should serialize date to ISO string', () => {
      const report = generator.generateBOM(testAssembly);
      const json = generator.exportToJSON(report);
      const parsed = JSON.parse(json);

      expect(typeof parsed.meta.generatedAt).toBe('string');
      expect(parsed.meta.generatedAt).toMatch(/^\d{4}-\d{2}-\d{2}/);
    });
  });

  describe('exportToHTML', () => {
    test('should export to HTML format', () => {
      const report = generator.generateBOM(testAssembly);
      const html = generator.exportToHTML(report);

      expect(html).toBeDefined();
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<table>');
      expect(html).toContain('Bill of Materials');
    });

    test('should include all sections in HTML', () => {
      const report = generator.generateBOM(testAssembly);
      const html = generator.exportToHTML(report);

      expect(html).toContain('Components');
      expect(html).toContain('Materials Summary');
      expect(html).toContain('Summary');
    });
  });

  describe('BOMMeta calculations', () => {
    test('should calculate totalComponents correctly', () => {
      testAssembly.components.push({
        id: 'comp-2',
        name: 'Panel 2',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material: testMaterial,
        properties: { width: 800, height: 2000, depth: 16 }
      });

      const report = generator.generateBOM(testAssembly);
      expect(report.meta.totalComponents).toBe(2);
    });

    test('should calculate averages correctly', () => {
      testAssembly.components.push({
        id: 'comp-2',
        name: 'Panel 2',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material: testMaterial,
        properties: { width: 800, height: 2000, depth: 16 }
      });

      const report = generator.generateBOM(testAssembly);
      
      expect(report.meta.averageCostPerUnit).toBeGreaterThan(0);
      expect(report.meta.averageMassPerUnit).toBeGreaterThan(0);
    });
  });
});

describe('HierarchyManager', () => {
  let testAssembly: Assembly;
  let material: Material;

  beforeEach(() => {
    material = {
      id: 'mat-1',
      name: 'Wood',
      color: '#8B4513',
      density: 700
    };

    // Create hierarchical structure
    const childComponent: Component = {
      id: 'comp-child',
      name: 'Child Component',
      type: ComponentType.PART,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: { width: 100, height: 100, depth: 10 }
    };

    const parentComponent: Component = {
      id: 'comp-parent',
      name: 'Parent Component',
      type: ComponentType.ASSEMBLY,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: {},
      subComponents: [childComponent]
    };

    const rootComponent: Component = {
      id: 'comp-root',
      name: 'Root Component',
      type: ComponentType.ASSEMBLY,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: {},
      subComponents: [parentComponent]
    };

    testAssembly = {
      id: 'asm-1',
      name: 'Test Assembly',
      components: [rootComponent],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };
  });

  describe('getComponentPath', () => {
    test('should find root component path', () => {
      const path = HierarchyManager.getComponentPath(testAssembly, 'comp-root');
      
      expect(path).toBeDefined();
      expect(path!.componentId).toBe('comp-root');
      expect(path!.depth).toBe(0);
      expect(path!.parentId).toBeNull();
    });

    test('should find nested component path', () => {
      const path = HierarchyManager.getComponentPath(testAssembly, 'comp-child');
      
      expect(path).toBeDefined();
      expect(path!.path.length).toBe(3);
      expect(path!.depth).toBe(2);
      expect(path!.parentId).toBe('comp-parent');
    });

    test('should return null for non-existent component', () => {
      const path = HierarchyManager.getComponentPath(testAssembly, 'non-existent');
      expect(path).toBeNull();
    });
  });

  describe('getComponentPathString', () => {
    test('should return formatted path string', () => {
      const pathStr = HierarchyManager.getComponentPathString(testAssembly, 'comp-child');
      
      expect(pathStr).toBeDefined();
      expect(pathStr).toContain('Root Component');
      expect(pathStr).toContain('Parent Component');
      expect(pathStr).toContain('Child Component');
      expect(pathStr).toContain('/');
    });

    test('should return null for non-existent component', () => {
      const pathStr = HierarchyManager.getComponentPathString(testAssembly, 'non-existent');
      expect(pathStr).toBeNull();
    });
  });

  describe('flattenAssembly', () => {
    test('should flatten hierarchical structure', () => {
      const flattened = HierarchyManager.flattenAssembly(testAssembly);
      
      expect(flattened.length).toBe(3);
      expect(flattened.map(c => c.id)).toContain('comp-root');
      expect(flattened.map(c => c.id)).toContain('comp-parent');
      expect(flattened.map(c => c.id)).toContain('comp-child');
    });
  });

  describe('getComponentsByType', () => {
    test('should filter components by type', () => {
      const parts = HierarchyManager.getComponentsByType(testAssembly, ComponentType.PART);
      const assemblies = HierarchyManager.getComponentsByType(testAssembly, ComponentType.ASSEMBLY);
      
      expect(parts.length).toBe(1);
      expect(assemblies.length).toBe(2);
    });
  });

  describe('getComponentsByMaterial', () => {
    test('should filter components by material', () => {
      const components = HierarchyManager.getComponentsByMaterial(testAssembly, 'mat-1');
      
      expect(components.length).toBe(3);
      expect(components.every(c => c.material.id === 'mat-1')).toBe(true);
    });

    test('should return empty array for non-existent material', () => {
      const components = HierarchyManager.getComponentsByMaterial(testAssembly, 'non-existent');
      expect(components.length).toBe(0);
    });
  });

  describe('getComponentsByName', () => {
    test('should filter components by name pattern', () => {
      const components = HierarchyManager.getComponentsByName(testAssembly, 'Component');
      expect(components.length).toBe(3);
    });

    test('should be case-insensitive', () => {
      const components = HierarchyManager.getComponentsByName(testAssembly, 'root');
      expect(components.length).toBeGreaterThan(0);
      expect(components.some(c => c.name === 'Root Component')).toBe(true);
    });
  });

  describe('findComponentById', () => {
    test('should find component by ID', () => {
      const component = HierarchyManager.findComponentById(testAssembly, 'comp-child');
      
      expect(component).toBeDefined();
      expect(component!.name).toBe('Child Component');
    });

    test('should return null for non-existent ID', () => {
      const component = HierarchyManager.findComponentById(testAssembly, 'non-existent');
      expect(component).toBeNull();
    });
  });

  describe('getChildren', () => {
    test('should get direct children of component', () => {
      const children = HierarchyManager.getChildren(testAssembly, 'comp-parent');
      
      expect(children.length).toBe(1);
      expect(children[0].id).toBe('comp-child');
    });

    test('should return empty array for leaf components', () => {
      const children = HierarchyManager.getChildren(testAssembly, 'comp-child');
      expect(children.length).toBe(0);
    });
  });

  describe('getParent', () => {
    test('should get parent of component', () => {
      const parent = HierarchyManager.getParent(testAssembly, 'comp-child');
      
      expect(parent).toBeDefined();
      expect(parent!.id).toBe('comp-parent');
    });

    test('should return null for root component', () => {
      const parent = HierarchyManager.getParent(testAssembly, 'comp-root');
      expect(parent).toBeNull();
    });
  });

  describe('filterComponents', () => {
    test('should filter by type', () => {
      const filter: ComponentFilter = { type: ComponentType.PART };
      const result = HierarchyManager.filterComponents(testAssembly, filter);
      
      expect(result.count).toBe(1);
      expect(result.components[0].id).toBe('comp-child');
    });

    test('should combine multiple filters', () => {
      const filter: ComponentFilter = {
        type: ComponentType.ASSEMBLY,
        nameContains: 'Root'
      };
      const result = HierarchyManager.filterComponents(testAssembly, filter);
      
      expect(result.count).toBe(1);
      expect(result.components[0].id).toBe('comp-root');
    });
  });

  describe('getComponentTypeStats', () => {
    test('should count components by type', () => {
      const stats = HierarchyManager.getComponentTypeStats(testAssembly);
      
      expect(stats[ComponentType.PART]).toBe(1);
      expect(stats[ComponentType.ASSEMBLY]).toBe(2);
      expect(stats[ComponentType.SUBASSEMBLY]).toBe(0);
    });
  });

  describe('getMaterialStats', () => {
    test('should count components by material', () => {
      const stats = HierarchyManager.getMaterialStats(testAssembly);
      
      expect(stats['Wood']).toBe(3);
    });
  });

  describe('isLeafComponent', () => {
    test('should identify leaf components', () => {
      const child = HierarchyManager.findComponentById(testAssembly, 'comp-child')!;
      const parent = HierarchyManager.findComponentById(testAssembly, 'comp-parent')!;
      
      expect(HierarchyManager.isLeafComponent(child)).toBe(true);
      expect(HierarchyManager.isLeafComponent(parent)).toBe(false);
    });
  });

  describe('getLeafComponents', () => {
    test('should get all leaf components', () => {
      const leafs = HierarchyManager.getLeafComponents(testAssembly);
      
      expect(leafs.length).toBe(1);
      expect(leafs[0].id).toBe('comp-child');
    });
  });

  describe('getHierarchyDepth', () => {
    test('should calculate correct hierarchy depth', () => {
      const depth = HierarchyManager.getHierarchyDepth(testAssembly);
      expect(depth).toBe(2);
    });
  });

  describe('getHierarchySummary', () => {
    test('should return complete hierarchy summary', () => {
      const summary = HierarchyManager.getHierarchySummary(testAssembly);
      
      expect(summary.totalComponents).toBe(3);
      expect(summary.totalLeafComponents).toBe(1);
      expect(summary.hierarchyDepth).toBe(2);
      expect(summary.componentTypes[ComponentType.PART]).toBe(1);
      expect(summary.componentTypes[ComponentType.ASSEMBLY]).toBe(2);
      expect(summary.uniqueMaterials).toBe(1);
    });
  });

  describe('getAncestors', () => {
    test('should get all ancestors of component', () => {
      const ancestors = HierarchyManager.getAncestors(testAssembly, 'comp-child');
      
      expect(ancestors.length).toBe(2);
      expect(ancestors[0].id).toBe('comp-root');
      expect(ancestors[1].id).toBe('comp-parent');
    });

    test('should return empty array for root', () => {
      const ancestors = HierarchyManager.getAncestors(testAssembly, 'comp-root');
      expect(ancestors.length).toBe(0);
    });
  });

  describe('getDescendants', () => {
    test('should get all descendants of component', () => {
      const descendants = HierarchyManager.getDescendants(testAssembly, 'comp-root');
      
      expect(descendants.length).toBe(2);
      expect(descendants.map(c => c.id)).toContain('comp-parent');
      expect(descendants.map(c => c.id)).toContain('comp-child');
    });

    test('should return empty array for leaf components', () => {
      const descendants = HierarchyManager.getDescendants(testAssembly, 'comp-child');
      expect(descendants.length).toBe(0);
    });
  });

  describe('buildHierarchyTree', () => {
    test('should build hierarchical tree structure', () => {
      const tree = HierarchyManager.buildHierarchyTree(testAssembly);
      
      expect(tree.length).toBe(1);
      expect(tree[0].id).toBe('comp-root');
      expect(tree[0].children.length).toBe(1);
      expect(tree[0].children[0].id).toBe('comp-parent');
      expect(tree[0].children[0].children[0].id).toBe('comp-child');
    });

    test('should set correct levels in tree', () => {
      const tree = HierarchyManager.buildHierarchyTree(testAssembly);
      
      expect(tree[0].level).toBe(0);
      expect(tree[0].children[0].level).toBe(1);
      expect(tree[0].children[0].children[0].level).toBe(2);
    });
  });
});
