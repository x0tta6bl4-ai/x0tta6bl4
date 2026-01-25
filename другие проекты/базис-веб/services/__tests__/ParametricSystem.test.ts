import { ParametricSystem } from '../ParametricSystem';
import { Parameter, Tolerance, CostBreakdown } from '../../types/ParametricSystem';

describe('ParametricSystem - v2.1', () => {
  let system: ParametricSystem;

  beforeEach(() => {
    system = new ParametricSystem();
  });

  describe('Parameter management', () => {
    it('should initialize with default parameters', () => {
      expect(system.parameters.size).toBeGreaterThan(0);
      
      const widthParam = system.getParameter('width');
      expect(widthParam).toBeDefined();
      expect(widthParam?.name).toBe('Ширина');
      expect(widthParam?.type).toBe('number');
    });

    it('should retrieve and update parameters', () => {
      const initialValue = system.getParameter('width')?.value;
      expect(initialValue).toBeDefined();

      const result = system.setParameter('width', 1300);
      expect(result.validationErrors.length).toBe(0);
      
      const updatedParam = system.getParameter('width');
      expect(updatedParam?.value).toBe(1300);
    });

    it('should validate parameter values against constraints', () => {
      // Test invalid numeric value (below minimum)
      const result = system.setParameter('width', 200);
      expect(result.validationErrors.length).toBeGreaterThan(0);
      expect(result.validationErrors[0].code).toBe('VALUE_TOO_SMALL');
    });

    it('should validate select parameters against options', () => {
      const result = system.setParameter('material', 'invalid');
      expect(result.validationErrors.length).toBeGreaterThan(0);
      expect(result.validationErrors[0].code).toBe('INVALID_OPTION');
    });
  });

  describe('Tolerance management', () => {
    it('should initialize with default tolerances', () => {
      expect(system.tolerances.length).toBeGreaterThan(0);
      
      const dimensionalTol = system.tolerances.find(t => t.type === 'dimensional');
      expect(dimensionalTol).toBeDefined();
      expect(dimensionalTol?.upper).toBeGreaterThan(0);
    });

    it('should add and remove tolerances', () => {
      const initialCount = system.tolerances.length;
      
      const newTolerance: Tolerance = {
        id: 'test-tol',
        name: 'Test Tolerance',
        type: 'dimensional',
        nominal: 0,
        upper: 0.5,
        lower: -0.5,
        unit: 'mm',
        description: 'Test description'
      };

      system.addTolerance(newTolerance);
      expect(system.tolerances.length).toBe(initialCount + 1);

      system.removeTolerance('test-tol');
      expect(system.tolerances.length).toBe(initialCount);
    });

    it('should run tolerance checks', () => {
      const report = system.runToleranceCheck();
      
      expect(report.totalChecks).toBeGreaterThan(0);
      expect(report.passedChecks).toBe(report.totalChecks); // All should pass initially
      
      expect(report.dimensionChecks.length).toBeGreaterThan(0);
      expect(report.toleranceSummary).toBeDefined();
    });
  });

  describe('Interactive editing state', () => {
    it('should manage editing state', () => {
      expect(system.interactiveState.isEditing).toBe(false);
      
      system.startEditing();
      expect(system.interactiveState.isEditing).toBe(true);
      
      system.stopEditing(false);
      expect(system.interactiveState.isEditing).toBe(false);
    });

    it('should toggle draft mode', () => {
      const initialState = system.interactiveState.draftMode.enabled;
      system.toggleDraftMode();
      expect(system.interactiveState.draftMode.enabled).toBe(!initialState);
    });

    it('should update real-time preview settings', () => {
      const initialCamera = system.realTimePreview.cameraPosition;
      const newCamera = { x: 10, y: 20, z: 30 };

      system.updateRealTimePreview({ cameraPosition: newCamera });
      expect(system.realTimePreview.cameraPosition).toEqual(newCamera);
    });
  });

  describe('Cost calculation', () => {
    it('should calculate total cost', () => {
      const calculation = system.calculateCost();
      
      expect(calculation.totalCost).toBeGreaterThan(0);
      expect(calculation.costBreakdown.materials.length).toBeGreaterThan(0);
      expect(calculation.costBreakdown.hardware.length).toBeGreaterThan(0);
      expect(calculation.costBreakdown.labor.length).toBeGreaterThan(0);
    });

    it('should update cost breakdown', () => {
      const initialLaborCost = system.calculateCost().costBreakdown.labor.reduce((sum, labor) => sum + labor.total, 0);
      
      const newLabor = {
        operation: 'Test Operation',
        time: 60,
        costPerMinute: 10,
        total: 600
      };

      const updated = system.updateCostBreakdown({
        labor: [newLabor],
        overhead: 0.20,
        markup: 0.40
      });

      const newLaborCost = updated.costBreakdown.labor.reduce((sum, labor) => sum + labor.total, 0);
      expect(newLaborCost).toEqual(newLabor.total);
    });

    it('should get cost items by type', () => {
      system.calculateCost();
      const materials = system.getCostItemsByType('material');
      const hardware = system.getCostItemsByType('hardware');
      const labor = system.getCostItemsByType('labor');

      expect(materials.length).toBeGreaterThan(0);
      expect(hardware.length).toBeGreaterThan(0);
      expect(labor.length).toBeGreaterThan(0);
    });

    it('should export cost reports in different formats', () => {
      const jsonReport = system.exportCostReport('json');
      const csvReport = system.exportCostReport('csv');
      const pdfReport = system.exportCostReport('pdf');

      expect(jsonReport).toContain('"totalCost":');
      expect(csvReport).toContain('Material, Quantity, Unit Cost, Total');
      expect(pdfReport).not.toEqual('');
    });
  });

  describe('Assembly guide generation', () => {
    it('should generate assembly guide', () => {
      const guide = system.generateAssemblyGuide('ru');
      
      expect(guide.title).not.toEqual('');
      expect(guide.steps.length).toBeGreaterThan(0);
      expect(guide.requiredTools.length).toBeGreaterThan(0);
    });

    it('should get step details', () => {
      const guide = system.generateAssemblyGuide('ru');
      const step = system.getStepDetails(1);
      
      expect(step.number).toBe(1);
      expect(step.title).not.toEqual('');
      expect(step.description).not.toEqual('');
    });

    it('should export assembly guide in different formats', () => {
      const jsonGuide = system.exportAssemblyGuide('json');
      const htmlGuide = system.exportAssemblyGuide('html');
      const pdfGuide = system.exportAssemblyGuide('pdf');

      expect(jsonGuide).toContain('"title":');
      expect(htmlGuide).toContain('<h1');
      expect(pdfGuide).not.toEqual('');
    });
  });

  describe('Version history management', () => {
    it('should initialize with initial version', () => {
      expect(system.versions.length).toBeGreaterThan(0);
      expect(system.currentVersion).toBeDefined();
    });

    it('should save new versions', () => {
      const initialCount = system.versions.length;
      const version = system.saveVersion('Test Version', 'Test description');
      
      expect(system.versions.length).toBe(initialCount + 1);
      expect(system.currentVersion).toBe(version.id);
    });

    it('should create and switch branches', () => {
      const initialBranchCount = system.branches.length;
      const branch = system.createBranch('feature-branch');
      
      expect(system.branches.length).toBe(initialBranchCount + 1);
      expect(branch.id).not.toBe('main');
    });

    it('should support undo and redo operations', () => {
      const initialVersion = system.currentVersion;
      system.saveVersion('Version 1');
      const version1 = system.currentVersion;
      
      system.saveVersion('Version 2');
      const version2 = system.currentVersion;
      
      const undoResult = system.undo();
      expect(undoResult).toBe(true);
      expect(system.currentVersion).toBe(version1);
      
      const redoResult = system.redo();
      expect(redoResult).toBe(true);
      expect(system.currentVersion).toBe(version2);
    });

    it('should calculate version diff', () => {
      const initialVersion = system.currentVersion;
      system.saveVersion('Version 1');
      const version1 = system.currentVersion;
      
      const diff = system.getVersionDiff(initialVersion, version1);
      expect(diff.versionFrom).toBe(initialVersion);
      expect(diff.versionTo).toBe(version1);
    });
  });

  describe('Parametric system integration', () => {
    it('should validate all parameters', () => {
      const errors = system.validateParameters();
      expect(errors.length).toBe(0);
    });

    it('should recalculate affected components', () => {
      const result = system.recalculateAffected();
      expect(result.validationErrors.length).toBe(0);
      expect(result.recalculationTime).toBeGreaterThanOrEqual(0);
    });
  });
});