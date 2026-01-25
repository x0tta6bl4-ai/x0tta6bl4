/**
 * FEA Integration Tests
 * Полное тестирование конечно-элементного анализа
 */

import { FEAIntegration, FEAComponent } from '../FEAIntegration';
import { FEAMesh, LoadCase, Material, Point3D } from '../../types/CADTypes';

describe('FEAIntegration', () => {
  let fea: FEAIntegration;
  let testComponent: FEAComponent;
  let testMaterial: Material;

  beforeEach(() => {
    fea = new FEAIntegration();

    testComponent = {
      geometry: {
        boundingBox: {
          min: { x: 0, y: 0, z: 0 },
          max: { x: 100, y: 100, z: 100 }
        }
      }
    };

    testMaterial = {
      id: 'steel',
      name: 'Steel'
    };
  });

  describe('Mesh Generation', () => {
    test('should generate FEA mesh from component', () => {
      const mesh = fea.generateMesh(testComponent, 10);

      expect(mesh).toBeDefined();
      expect(mesh.nodes.length).toBeGreaterThan(0);
      expect(mesh.elements.length).toBeGreaterThan(0);
    });

    test('should have correct element size metadata', () => {
      const elementSize = 20;
      const mesh = fea.generateMesh(testComponent, elementSize);

      expect(mesh.elementSize).toBe(elementSize);
    });

    test('should calculate total nodes correctly', () => {
      const mesh = fea.generateMesh(testComponent, 10);

      expect(mesh.totalNodes).toBe(mesh.nodes.length);
      expect(mesh.totalNodes).toBeGreaterThan(0);
    });

    test('should calculate total elements correctly', () => {
      const mesh = fea.generateMesh(testComponent, 10);

      expect(mesh.totalElements).toBe(mesh.elements.length);
      expect(mesh.totalElements).toBeGreaterThan(0);
    });

    test('should generate nodes within bounding box', () => {
      const mesh = fea.generateMesh(testComponent, 10);

      for (const node of mesh.nodes) {
        expect(node.position.x).toBeGreaterThanOrEqual(0);
        expect(node.position.x).toBeLessThanOrEqual(100);
        expect(node.position.y).toBeGreaterThanOrEqual(0);
        expect(node.position.y).toBeLessThanOrEqual(100);
        expect(node.position.z).toBeGreaterThanOrEqual(0);
        expect(node.position.z).toBeLessThanOrEqual(100);
      }
    });

    test('should assign unique node IDs', () => {
      const mesh = fea.generateMesh(testComponent, 10);
      const ids = new Set(mesh.nodes.map(n => n.id));

      expect(ids.size).toBe(mesh.nodes.length);
    });

    test('should create tetrahedral elements', () => {
      const mesh = fea.generateMesh(testComponent, 10);

      for (const element of mesh.elements) {
        expect(element.nodeIndices.length).toBe(4);
        expect(element.material).toBeDefined();
      }
    });

    test('should handle small element size', () => {
      const mesh = fea.generateMesh(testComponent, 5);

      expect(mesh.totalNodes).toBeGreaterThan(0);
      expect(mesh.totalElements).toBeGreaterThan(0);
    });

    test('should handle large element size', () => {
      const mesh = fea.generateMesh(testComponent, 50);

      expect(mesh.totalNodes).toBeGreaterThan(0);
      expect(mesh.totalElements).toBeGreaterThan(0);
    });

    test('should handle component without geometry', () => {
      const emptyComponent: FEAComponent = {};

      const mesh = fea.generateMesh(emptyComponent, 10);

      expect(mesh.nodes.length).toBe(0);
      expect(mesh.elements.length).toBe(0);
    });

    test('should handle component without bounding box', () => {
      const componentNoBbox: FEAComponent = { geometry: {} };

      const mesh = fea.generateMesh(componentNoBbox, 10);

      expect(mesh.nodes.length).toBe(0);
      expect(mesh.elements.length).toBe(0);
    });
  });

  describe('Static Linear Analysis', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 20);
    });

    test('should perform linear static analysis', () => {
      const loadCase: LoadCase = {
        name: 'Vertical Load',
        loads: [
          {
            nodeId: 0,
            force: { x: 0, y: -1000, z: 0 }
          }
        ],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [true, true, true]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.displacements.length).toBe(mesh.nodes.length);
      expect(result.stress.length).toBe(mesh.elements.length);
    });

    test('should calculate displacements', () => {
      const loadCase: LoadCase = {
        name: 'Test Load',
        loads: [
          { nodeId: 0, force: { x: 100, y: 0, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.maxDisplacement).toBeGreaterThanOrEqual(0);
      expect(result.displacements.some(d => Math.abs(d.x) > 0 || Math.abs(d.y) > 0 || Math.abs(d.z) > 0)).toBe(true);
    });

    test('should calculate stress', () => {
      const loadCase: LoadCase = {
        name: 'Stress Test',
        loads: [
          { nodeId: 0, force: { x: 500, y: 500, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.maxStress).toBeGreaterThanOrEqual(0);
      expect(result.stress.length).toBeGreaterThan(0);
    });

    test('should calculate strain', () => {
      const loadCase: LoadCase = {
        name: 'Strain Test',
        loads: [
          { nodeId: 0, force: { x: 200, y: 200, z: 200 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.maxStrain).toBeGreaterThanOrEqual(0);
      expect(result.strain.length).toBe(result.stress.length);
    });

    test('should calculate safety factor', () => {
      const loadCase: LoadCase = {
        name: 'Safety Test',
        loads: [
          { nodeId: 0, force: { x: 50, y: 50, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.safetyFactor).toBeGreaterThanOrEqual(0);
    });

    test('should calculate strain energy', () => {
      const loadCase: LoadCase = {
        name: 'Energy Test',
        loads: [
          { nodeId: 0, force: { x: 100, y: 0, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.strainEnergy).toBeGreaterThanOrEqual(0);
    });

    test('should handle multiple loads', () => {
      const loadCase: LoadCase = {
        name: 'Multi-Load',
        loads: [
          { nodeId: 0, force: { x: 100, y: 100, z: 0 } },
          { nodeId: 1, force: { x: 0, y: 100, z: 100 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.displacements).toBeDefined();
      expect(result.stress).toBeDefined();
    });

    test('should handle multiple boundary conditions', () => {
      const lastNode = mesh.nodes.length - 1;
      const loadCase: LoadCase = {
        name: 'Multi-BC',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: lastNode, fixed: [true, true, true] },
          { nodeId: lastNode - 1, fixed: [false, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.maxDisplacement).toBeGreaterThanOrEqual(0);
    });

    test('should track solver execution time', () => {
      const loadCase: LoadCase = {
        name: 'Time Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.solverTime).toBeGreaterThanOrEqual(0);
    });

    test('should store load case name in result', () => {
      const loadCaseName = 'Custom Load Case';
      const loadCase: LoadCase = {
        name: loadCaseName,
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.loadCaseName).toBe(loadCaseName);
    });

    test('should set timestamp', () => {
      const loadCase: LoadCase = {
        name: 'Timestamp Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const before = new Date();
      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);
      const after = new Date();

      expect(result.timestamp.getTime()).toBeGreaterThanOrEqual(before.getTime());
      expect(result.timestamp.getTime()).toBeLessThanOrEqual(after.getTime());
    });
  });

  describe('Modal Analysis', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 30);
    });

    test('should perform modal analysis', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 3);

      expect(result).toBeDefined();
      expect(result.modes.length).toBeGreaterThan(0);
    });

    test('should calculate frequencies', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 3);

      for (const mode of result.modes) {
        expect(mode.frequency).toBeGreaterThanOrEqual(0);
      }
    });

    test('should calculate periods', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 3);

      for (const mode of result.modes) {
        expect(mode.period).toBeGreaterThanOrEqual(0);
        if (mode.frequency > 0) {
          expect(mode.period).toBeCloseTo(1 / mode.frequency, 2);
        }
      }
    });

    test('should assign mode numbers', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 5);

      for (let i = 0; i < result.modes.length; i++) {
        expect(result.modes[i].mode).toBe(i + 1);
      }
    });

    test('should calculate vibration displacements', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 2);

      for (const mode of result.modes) {
        if (mode.displacements) {
          expect(mode.displacements.length).toBeGreaterThan(0);
          expect(mode.displacements[0]).toHaveProperty('x');
          expect(mode.displacements[0]).toHaveProperty('y');
          expect(mode.displacements[0]).toHaveProperty('z');
        }
      }
    });

    test('should set damping ratio', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 2);

      for (const mode of result.modes) {
        expect(mode.dampingRatio).toBeGreaterThanOrEqual(0);
        expect(mode.dampingRatio).toBeLessThanOrEqual(1);
      }
    });

    test('should request correct number of modes', () => {
      const numModes = 3;
      const result = fea.runModalAnalysis(mesh, testMaterial, numModes);

      expect(result.modes.length).toBeLessThanOrEqual(numModes);
    });

    test('should track modal analysis time', () => {
      const result = fea.runModalAnalysis(mesh, testMaterial, 2);

      expect(result.solverTime).toBeGreaterThanOrEqual(0);
    });

    test('should set timestamp', () => {
      const before = new Date();
      const result = fea.runModalAnalysis(mesh, testMaterial, 2);
      const after = new Date();

      expect(result.timestamp.getTime()).toBeGreaterThanOrEqual(before.getTime());
      expect(result.timestamp.getTime()).toBeLessThanOrEqual(after.getTime());
    });
  });

  describe('Material Properties', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 25);
    });

    test('should use steel material properties', () => {
      const steel: Material = { id: 'steel', name: 'Steel' };
      const loadCase: LoadCase = {
        name: 'Steel Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, steel, loadCase);

      expect(result).toBeDefined();
      expect(result.stress.length).toBeGreaterThan(0);
    });

    test('should use aluminum material properties', () => {
      const aluminum: Material = { id: 'aluminum', name: 'Aluminum' };
      const loadCase: LoadCase = {
        name: 'Aluminum Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, aluminum, loadCase);

      expect(result).toBeDefined();
      expect(result.stress.length).toBeGreaterThan(0);
    });

    test('should use plastic material properties', () => {
      const plastic: Material = { id: 'plastic', name: 'Plastic' };
      const loadCase: LoadCase = {
        name: 'Plastic Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, plastic, loadCase);

      expect(result).toBeDefined();
      expect(result.stress.length).toBeGreaterThan(0);
    });

    test('should use copper material properties', () => {
      const copper: Material = { id: 'copper', name: 'Copper' };
      const loadCase: LoadCase = {
        name: 'Copper Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, copper, loadCase);

      expect(result).toBeDefined();
      expect(result.stress.length).toBeGreaterThan(0);
    });

    test('should use default properties for unknown material', () => {
      const unknownMaterial: Material = { id: 'unknown', name: 'Unknown' };
      const loadCase: LoadCase = {
        name: 'Unknown Test',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, unknownMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.stress.length).toBeGreaterThan(0);
    });
  });

  describe('Boundary Conditions', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 25);
    });

    test('should handle fixed displacement in X', () => {
      const loadCase: LoadCase = {
        name: 'Fixed X',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [true, false, false]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.maxDisplacement).toBeGreaterThanOrEqual(0);
    });

    test('should handle fixed displacement in Y', () => {
      const loadCase: LoadCase = {
        name: 'Fixed Y',
        loads: [{ nodeId: 0, force: { x: 0, y: 100, z: 0 } }],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [false, true, false]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
    });

    test('should handle fixed displacement in Z', () => {
      const loadCase: LoadCase = {
        name: 'Fixed Z',
        loads: [{ nodeId: 0, force: { x: 0, y: 0, z: 100 } }],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [false, false, true]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
    });

    test('should handle completely fixed support', () => {
      const loadCase: LoadCase = {
        name: 'Fully Fixed',
        loads: [{ nodeId: 0, force: { x: 100, y: 100, z: 100 } }],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [true, true, true]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.maxStress).toBeGreaterThanOrEqual(0);
    });

    test('should handle free support', () => {
      const loadCase: LoadCase = {
        name: 'Free Support',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [false, false, false]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
    });
  });

  describe('Load Cases', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 25);
    });

    test('should handle empty loads', () => {
      const loadCase: LoadCase = {
        name: 'No Load',
        loads: [],
        boundaryConditions: [
          {
            nodeId: mesh.nodes.length - 1,
            fixed: [true, true, true]
          }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.maxStress).toBe(0);
    });

    test('should handle tensile load', () => {
      const loadCase: LoadCase = {
        name: 'Tension',
        loads: [
          { nodeId: 0, force: { x: 1000, y: 0, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.maxStress).toBeGreaterThan(0);
    });

    test('should handle compressive load', () => {
      const loadCase: LoadCase = {
        name: 'Compression',
        loads: [
          { nodeId: 0, force: { x: -1000, y: 0, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
    });

    test('should handle shear load', () => {
      const loadCase: LoadCase = {
        name: 'Shear',
        loads: [
          { nodeId: 0, force: { x: 0, y: 500, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.maxStress).toBeGreaterThanOrEqual(0);
    });

    test('should handle torsional load', () => {
      const loadCase: LoadCase = {
        name: 'Torsion',
        loads: [
          { nodeId: 0, force: { x: 100, y: 100, z: 100 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
    });

    test('should handle combined loads', () => {
      const loadCase: LoadCase = {
        name: 'Combined',
        loads: [
          { nodeId: 0, force: { x: 500, y: 500, z: 500 } },
          { nodeId: 1, force: { x: 300, y: 0, z: 300 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result).toBeDefined();
      expect(result.maxStress).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Element and Node Validation', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 15);
    });

    test('should have all elements with 4 nodes (tetrahedral)', () => {
      for (const element of mesh.elements) {
        expect(element.nodeIndices.length).toBe(4);
      }
    });

    test('should have all nodes with unique IDs', () => {
      const ids = new Set(mesh.nodes.map(n => n.id));
      expect(ids.size).toBe(mesh.nodes.length);
    });

    test('should have all element node indices within bounds', () => {
      for (const element of mesh.elements) {
        for (const nodeIdx of element.nodeIndices) {
          expect(nodeIdx).toBeGreaterThanOrEqual(0);
          expect(nodeIdx).toBeLessThan(mesh.nodes.length);
        }
      }
    });

    test('should have all nodes with positions', () => {
      for (const node of mesh.nodes) {
        expect(node.position).toBeDefined();
        expect(typeof node.position.x).toBe('number');
        expect(typeof node.position.y).toBe('number');
        expect(typeof node.position.z).toBe('number');
      }
    });
  });

  describe('Safety Factor Calculation', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 25);
    });

    test('should calculate safety factor greater than 1 for low stress', () => {
      const loadCase: LoadCase = {
        name: 'Low Stress',
        loads: [
          { nodeId: 0, force: { x: 10, y: 0, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.safetyFactor).toBeGreaterThan(1);
    });

    test('should calculate safety factor correctly for higher stress', () => {
      const loadCase: LoadCase = {
        name: 'Higher Stress',
        loads: [
          { nodeId: 0, force: { x: 1000, y: 0, z: 0 } }
        ],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const result = fea.runLinearStaticAnalysis(mesh, testMaterial, loadCase);

      expect(result.safetyFactor).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Comparison Between Different Loads', () => {
    let mesh: FEAMesh;

    beforeEach(() => {
      mesh = fea.generateMesh(testComponent, 25);
    });

    test('larger load should produce larger displacement', () => {
      const smallLoadCase: LoadCase = {
        name: 'Small Load',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const largeLoadCase: LoadCase = {
        name: 'Large Load',
        loads: [{ nodeId: 0, force: { x: 1000, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const smallResult = fea.runLinearStaticAnalysis(mesh, testMaterial, smallLoadCase);
      const largeResult = fea.runLinearStaticAnalysis(mesh, testMaterial, largeLoadCase);

      expect(largeResult.maxDisplacement).toBeGreaterThanOrEqual(smallResult.maxDisplacement);
    });

    test('larger load should produce larger stress', () => {
      const smallLoadCase: LoadCase = {
        name: 'Small Load',
        loads: [{ nodeId: 0, force: { x: 100, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const largeLoadCase: LoadCase = {
        name: 'Large Load',
        loads: [{ nodeId: 0, force: { x: 1000, y: 0, z: 0 } }],
        boundaryConditions: [
          { nodeId: mesh.nodes.length - 1, fixed: [true, true, true] }
        ]
      };

      const smallResult = fea.runLinearStaticAnalysis(mesh, testMaterial, smallLoadCase);
      const largeResult = fea.runLinearStaticAnalysis(mesh, testMaterial, largeLoadCase);

      expect(largeResult.maxStress).toBeGreaterThanOrEqual(smallResult.maxStress);
    });
  });
});
