/**
 * CAD Store Integration
 * 
 * Расширение Zustand store с CAD функциональностью
 * Синхронизирует CAD модели с React компонентами
 */

import { CADModel, Parameter, SolverResult, ValidationResult } from './CADTypes';
import { CADKernel } from './CADKernel';
import { GeometryKernel } from './GeometryKernel';

/**
 * CAD Store интерфейс
 */
export interface CADStore {
  // State
  cadKernel: CADKernel;
  activeModelId: string | null;
  models: Map<string, CADModel>;
  selectedParameterId: string | null;
  lastValidation: ValidationResult | null;
  lastSolverResult: SolverResult | null;

  // Model Management
  createModel: (name: string, description?: string) => string; // returns modelId
  getActiveModel: () => CADModel | null;
  deleteModel: (modelId: string) => void;

  // Parameters
  createParameter: (
    parameterId: string,
    name: string,
    value: number,
    options?: any
  ) => void;
  updateParameter: (parameterId: string, value: number) => void;
  selectParameter: (parameterId: string | null) => void;

  // Constraints
  addConstraint: (type: string, elements: any[], value?: number) => void;
  updateConstraint: (constraintId: string, value: number) => void;

  // Operations
  validateModel: (modelId?: string) => ValidationResult;
  solveConstraints: (modelId?: string) => SolverResult | null;
  undoAction: (modelId?: string) => boolean;
  redoAction: (modelId?: string) => boolean;

  // Geometry
  createPanel: (x: number, y: number, z: number, w: number, h: number, d: number) => void;

  // Statistics
  getStats: () => any;
}

/**
 * Создать CAD Store расширение для Zustand
 */
export function createCADStore(): CADStore {
  const cadKernel = new CADKernel();
  let activeModelId: string | null = null;
  let selectedParameterId: string | null = null;
  let lastValidation: ValidationResult | null = null;
  let lastSolverResult: SolverResult | null = null;

  const store: CADStore = {
    cadKernel,
    activeModelId,
    models: new Map(),
    selectedParameterId,
    lastValidation,
    lastSolverResult,

    // =====================================================================
    // Model Management
    // =====================================================================
    createModel: (name: string, description?: string): string => {
      const model = cadKernel.createModel(name, description);
      store.models.set(model.id, model);
      store.activeModelId = model.id;
      console.log(`[CADStore] Created model: ${model.id}`);
      return model.id;
    },

    getActiveModel: (): CADModel | null => {
      if (!store.activeModelId) return null;
      return cadKernel.getModel(store.activeModelId) || null;
    },

    deleteModel: (modelId: string): void => {
      store.models.delete(modelId);
      if (store.activeModelId === modelId) {
        store.activeModelId = store.models.size > 0 ? 
          Array.from(store.models.keys())[0] : null;
      }
      console.log(`[CADStore] Deleted model: ${modelId}`);
    },

    // =====================================================================
    // Parameters
    // =====================================================================
    createParameter: (
      parameterId: string,
      name: string,
      value: number,
      options?: any
    ): void => {
      const model = store.getActiveModel();
      if (!model) {
        console.warn('[CADStore] No active model');
        return;
      }

      cadKernel.createParameter(model.id, name, value, options);
      console.log(`[CADStore] Created parameter: ${name} = ${value}`);
    },

    updateParameter: (parameterId: string, value: number): void => {
      const model = store.getActiveModel();
      if (!model) {
        console.warn('[CADStore] No active model');
        return;
      }

      const solverResult = cadKernel.updateParameter(model.id, parameterId, value);
      store.lastSolverResult = solverResult;

      if (solverResult?.converged) {
        console.log(
          `[CADStore] Parameter ${parameterId} = ${value} ✓ (solver converged)`
        );
      } else {
        console.warn(
          `[CADStore] Parameter ${parameterId} = ${value} ⚠ (solver did not converge)`
        );
      }
    },

    selectParameter: (parameterId: string | null): void => {
      store.selectedParameterId = parameterId;
    },

    // =====================================================================
    // Constraints
    // =====================================================================
    addConstraint: (type: string, elements: any[], value?: number): void => {
      const model = store.getActiveModel();
      if (!model) {
        console.warn('[CADStore] No active model');
        return;
      }

      cadKernel.addConstraint(model.id, type as any, elements, value);
      console.log(`[CADStore] Added ${type} constraint`);
    },

    updateConstraint: (constraintId: string, value: number): void => {
      const model = store.getActiveModel();
      if (!model) {
        console.warn('[CADStore] No active model');
        return;
      }

      const constraint = model.constraints.find(c => c.id === constraintId);
      if (constraint) {
        constraint.value = value;
        constraint.status = 'unsatisfied'; // Mark as unsatisfied until solver runs

        store.solveConstraints(); // Auto-solve
        console.log(`[CADStore] Updated constraint ${constraintId} = ${value}`);
      }
    },

    // =====================================================================
    // Operations
    // =====================================================================
    validateModel: (modelId?: string): ValidationResult => {
      const id = modelId || store.activeModelId;
      if (!id) throw new Error('No active model');

      const result = cadKernel.validate(id);
      store.lastValidation = result;
      return result;
    },

    solveConstraints: (modelId?: string): SolverResult | null => {
      const id = modelId || store.activeModelId;
      if (!id) {
        console.warn('[CADStore] No active model');
        return null;
      }

      const result = cadKernel.solveConstraints(id);
      store.lastSolverResult = result;
      return result;
    },

    undoAction: (modelId?: string): boolean => {
      const id = modelId || store.activeModelId;
      if (!id) {
        console.warn('[CADStore] No active model');
        return false;
      }

      return cadKernel.undo(id);
    },

    redoAction: (modelId?: string): boolean => {
      const id = modelId || store.activeModelId;
      if (!id) {
        console.warn('[CADStore] No active model');
        return false;
      }

      return cadKernel.redo(id);
    },

    // =====================================================================
    // Geometry
    // =====================================================================
    createPanel: (
      x: number,
      y: number,
      z: number,
      w: number,
      h: number,
      d: number
    ): void => {
      const model = store.getActiveModel();
      if (!model) {
        console.warn('[CADStore] No active model');
        return;
      }

      const body = GeometryKernel.createPanel(x, y, z, w, h, d, `Panel_${Date.now()}`);
      model.bodies.push(body);
      model.modifiedAt = new Date();

      console.log(`[CADStore] Created panel: ${w}x${h}x${d}`);
    },

    // =====================================================================
    // Statistics
    // =====================================================================
    getStats: (): any => {
      const model = store.getActiveModel();
      if (!model) return null;

      return cadKernel.getStats(model.id);
    }
  };

  return store;
}

/**
 * Хук для использования в React
 */
export function useCADStore() {
  // Это будет интегрировано с вашим projectStore
  return createCADStore();
}

export default createCADStore;
