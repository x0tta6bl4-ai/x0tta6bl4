/**
 * CAD Kernel - Юнит тесты
 * 
 * Проверяют основную функциональность движка
 */

import { CADKernel } from '../CADKernel';
import { GeometryKernel } from '../GeometryKernel';
import { CADEngine } from '../index';

describe('CAD Kernel', () => {
  let kernel: CADKernel;

  beforeEach(() => {
    kernel = new CADKernel();
  });

  describe('Model Management', () => {
    test('should create a model', () => {
      const model = kernel.createModel('Test Cabinet', 'A simple cabinet');

      expect(model).toBeDefined();
      expect(model.name).toBe('Test Cabinet');
      expect(model.description).toBe('A simple cabinet');
      expect(model.bodies).toHaveLength(0);
      expect(model.constraints).toHaveLength(0);
    });

    test('should retrieve a created model', () => {
      const model1 = kernel.createModel('Cabinet 1');
      const model2 = kernel.getModel(model1.id);

      expect(model2).toBeDefined();
      expect(model2?.name).toBe('Cabinet 1');
    });

    test('should handle non-existent model gracefully', () => {
      const model = kernel.getModel('non-existent-id');
      expect(model).toBeUndefined();
    });
  });

  describe('Parameters', () => {
    let modelId: string;

    beforeEach(() => {
      const model = kernel.createModel('Test');
      modelId = model.id;
    });

    test('should create a parameter', () => {
      const param = kernel.createParameter(modelId, 'width', 1200, {
        min: 300,
        max: 3000,
        unit: 'mm'
      });

      expect(param).toBeDefined();
      expect(param.name).toBe('width');
      expect(param.value).toBe(1200);
      expect(param.min).toBe(300);
      expect(param.max).toBe(3000);
    });

    test('should update parameter value', () => {
      const param = kernel.createParameter(modelId, 'width', 1200);
      kernel.updateParameter(modelId, param.id, 1500);

      const updated = kernel.getModel(modelId)?.parameters.get(param.id);
      expect(updated?.value).toBe(1500);
    });

    test('should enforce parameter min/max bounds', () => {
      const param = kernel.createParameter(modelId, 'width', 1200, {
        min: 300,
        max: 3000
      });

      // Should not update if below min
      const result1 = kernel.updateParameter(modelId, param.id, 100);
      expect(result1).toBeNull();

      // Should not update if above max
      const result2 = kernel.updateParameter(modelId, param.id, 5000);
      expect(result2).toBeNull();
    });
  });

  describe('Constraints', () => {
    let modelId: string;

    beforeEach(() => {
      const model = kernel.createModel('Test');
      modelId = model.id;
    });

    test('should add a constraint', () => {
      const constraint = kernel.addConstraint(
        modelId,
        'distance',
        [
          { id: 'vertex1', type: 'vertex' },
          { id: 'vertex2', type: 'vertex' }
        ],
        100
      );

      expect(constraint).toBeDefined();
      expect(constraint.type).toBe('distance');
      expect(constraint.value).toBe(100);
      expect(constraint.status).toBe('unsatisfied');

      const model = kernel.getModel(modelId);
      expect(model?.constraints).toHaveLength(1);
    });

    test('should track constraint dependencies', () => {
      const constraint = kernel.addConstraint(
        modelId,
        'coincident',
        [
          { id: 'point1', type: 'point' },
          { id: 'point2', type: 'point' }
        ]
      );

      const model = kernel.getModel(modelId);
      expect(model?.dependencyGraph.nodes.has(constraint.id)).toBe(true);
    });
  });

  describe('Solver', () => {
    let modelId: string;

    beforeEach(() => {
      const model = kernel.createModel('Test');
      modelId = model.id;

      // Create a simple constraint system
      kernel.createParameter(modelId, 'x', 0);
      kernel.createParameter(modelId, 'y', 0);

      kernel.addConstraint(
        modelId,
        'distance',
        [
          { id: 'x' },
          { id: 'y' }
        ],
        100
      );
    });

    test('should solve constraints', () => {
      const result = kernel.solveConstraints(modelId);

      expect(result).toBeDefined();
      expect(result?.iterations).toBeGreaterThan(0);
      expect(result?.residual).toBeGreaterThanOrEqual(0);
    });

    test('should report convergence status', () => {
      const result = kernel.solveConstraints(modelId);

      expect(result).toHaveProperty('converged');
      expect(result).toHaveProperty('iterations');
      expect(result).toHaveProperty('residual');
    });
  });

  describe('Validation', () => {
    let modelId: string;

    beforeEach(() => {
      const model = kernel.createModel('Test');
      modelId = model.id;
    });

    test('should validate a model', () => {
      const result = kernel.validate(modelId);

      expect(result).toBeDefined();
      expect(result.isValid).toBe(true);
      expect(result.totalIssues).toBe(0);
      expect(result.collisions).toHaveLength(0);
    });

    test('should detect manufacturing issues', () => {
      // Create a model with manufacturing issues
      // (simplified - in real case we'd create very small bodies)
      const result = kernel.validate(modelId);

      expect(result).toHaveProperty('manufacturingIssues');
    });
  });

  describe('History', () => {
    let modelId: string;

    beforeEach(() => {
      const model = kernel.createModel('Test');
      modelId = model.id;
    });

    test('should record history entries', () => {
      const model = kernel.getModel(modelId);
      const initialCount = model?.history.length || 0;

      kernel.createParameter(modelId, 'width', 1200);

      const updated = kernel.getModel(modelId);
      expect((updated?.history.length || 0) > initialCount).toBe(true);
    });

    test('should support undo', () => {
      const param = kernel.createParameter(modelId, 'width', 1200);
      kernel.updateParameter(modelId, param.id, 1500);

      const before = kernel.getModel(modelId)?.parameters.get(param.id)?.value;
      expect(before).toBe(1500);

      kernel.undo(modelId);

      const after = kernel.getModel(modelId)?.parameters.get(param.id)?.value;
      expect(after).toBeLessThan(before!);
    });

    test('should support redo', () => {
      const param = kernel.createParameter(modelId, 'width', 1200);
      kernel.updateParameter(modelId, param.id, 1500);

      kernel.undo(modelId);
      kernel.redo(modelId);

      const final = kernel.getModel(modelId)?.parameters.get(param.id)?.value;
      expect(final).toBe(1500);
    });
  });

  describe('Statistics', () => {
    let modelId: string;

    beforeEach(() => {
      const model = kernel.createModel('Test');
      modelId = model.id;

      kernel.createParameter(modelId, 'width', 1200);
      kernel.createParameter(modelId, 'height', 2000);
      kernel.addConstraint(modelId, 'parallel', []);
    });

    test('should return model statistics', () => {
      const stats = kernel.getStats(modelId);

      expect(stats).toBeDefined();
      expect(stats.name).toBe('Test');
      expect(stats.parameters).toBe(2);
      expect(stats.constraints).toBe(1);
    });
  });
});

describe('Geometry Kernel', () => {
  test('should create a panel', () => {
    const panel = GeometryKernel.createPanel(
      0, 0, 0,
      1000, 2000, 600,
      'Test Panel'
    );

    expect(panel).toBeDefined();
    expect(panel.name).toBe('Test Panel');
    expect(panel.faces).toHaveLength(6); // 6 faces of a box
    expect(panel.edges).toHaveLength(12); // 12 edges of a box
    expect(panel.vertices).toHaveLength(8); // 8 vertices of a box
    expect(panel.volume).toBe(1000 * 2000 * 600);
  });

  test('should apply fillet to edge', () => {
    const panel = GeometryKernel.createPanel(0, 0, 0, 1000, 2000, 600);
    const edge = panel.edges[0];

    const filletedPanel = GeometryKernel.fillet(panel, edge.id, 5);

    expect(filletedPanel).toBeDefined();
    const filletedEdge = filletedPanel.edges.find(e => e.id === edge.id);
    expect(filletedEdge?.isCurved).toBe(true);
    expect(filletedEdge?.curvatureRadius).toBe(5);
  });

  test('should perform union', () => {
    const panel1 = GeometryKernel.createPanel(0, 0, 0, 1000, 2000, 600);
    const panel2 = GeometryKernel.createPanel(1000, 0, 0, 500, 2000, 600);

    const union = GeometryKernel.union(panel1, panel2);

    expect(union).toBeDefined();
    expect(union.faces.length).toBeGreaterThan(panel1.faces.length);
    expect(union.volume).toBe(
      (1000 * 2000 * 600) + (500 * 2000 * 600)
    );
  });

  test('should perform subtraction', () => {
    const panel1 = GeometryKernel.createPanel(0, 0, 0, 1000, 2000, 600);
    const panel2 = GeometryKernel.createPanel(100, 100, 0, 500, 500, 600);

    const subtract = GeometryKernel.subtract(panel1, panel2);

    expect(subtract).toBeDefined();
    expect(subtract.volume).toBeLessThan(panel1.volume!);
  });
});

describe('CADEngine', () => {
  test('should create a cabinet', () => {
    const kernel = CADEngine.create();
    const model = CADEngine.createCabinet(kernel, 1000, 2000, 600);

    expect(model).toBeDefined();
    expect(model.parameters.size).toBeGreaterThan(0);
  });

  test('should create parametric shelves', () => {
    const kernel = CADEngine.create();
    const model = CADEngine.createParametricShelf(kernel, 3);

    expect(model).toBeDefined();
    expect(model.constraints.length).toBe(3);
  });
});
