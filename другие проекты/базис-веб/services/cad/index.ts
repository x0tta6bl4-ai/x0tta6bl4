/**
 * CAD Module Index
 * 
 * Экспортирует все компоненты профессионального CAD движка
 */

// Core
export { CADKernel } from './CADKernel';
export { GeometryKernel } from './GeometryKernel';
export { createCADStore, useCADStore } from './CADStore';

// Types
export type {
  CADModel,
  Body,
  Face,
  Edge,
  Vertex,
  Constraint,
  Parameter,
  Feature,
  DependencyGraph,
  Vector3,
  AABB,
  SolverResult,
  ValidationResult,
  Collision,
  ManufacturingIssue,
  ConstraintType,
  ConstraintStatus
} from './CADTypes';

// Re-export from main ConstraintSolver
export { ConstraintSolver } from '../ConstraintSolver';

import { CADKernel } from './CADKernel';
import { GeometryKernel } from './GeometryKernel';

/**
 * Быстрый старт CAD системы
 */
export const CADEngine = {
  /**
   * Создать новый CAD kernel
   */
  create(): CADKernel {
    return new CADKernel();
  },

  /**
   * Создать простой шкаф (пример)
   */
  createCabinet(kernel: CADKernel, width: number, height: number, depth: number) {
    // 1. Создать модель
    const model = kernel.createModel(`Cabinet ${width}x${height}x${depth}`);

    // 2. Создать параметры
    const widthParam = kernel.createParameter(model.id, 'width', width, {
      min: 300,
      max: 3000,
      unit: 'mm'
    });

    const heightParam = kernel.createParameter(model.id, 'height', height, {
      min: 400,
      max: 3000,
      unit: 'mm'
    });

    const depthParam = kernel.createParameter(model.id, 'depth', depth, {
      min: 300,
      max: 1000,
      unit: 'mm'
    });

    // 3. Создать панели
    const leftPanel = GeometryKernel.createPanel(
      0, 0, 0,
      16, height, depth,
      'Left Panel'
    );

    const rightPanel = GeometryKernel.createPanel(
      width - 16, 0, 0,
      16, height, depth,
      'Right Panel'
    );

    const topPanel = GeometryKernel.createPanel(
      0, height - 16, 0,
      width, 16, depth,
      'Top Panel'
    );

    const bottomPanel = GeometryKernel.createPanel(
      0, 0, 0,
      width, 16, depth,
      'Bottom Panel'
    );

    // Добавить в модель (если у вас есть такой метод)
    console.log(`[CADEngine] Created cabinet with panels:`, {
      left: leftPanel.id,
      right: rightPanel.id,
      top: topPanel.id,
      bottom: bottomPanel.id
    });

    return model;
  },

  /**
   * Пример параметрической системы
   */
  createParametricShelf(kernel: CADKernel, shelfCount: number = 3) {
    const model = kernel.createModel(`Parametric Shelves x${shelfCount}`);

    // Параметры
    const widthParam = kernel.createParameter(model.id, 'shelf_width', 1000);
    const depthParam = kernel.createParameter(model.id, 'shelf_depth', 400);
    const spacingParam = kernel.createParameter(model.id, 'shelf_spacing', 400);
    const thicknessParam = kernel.createParameter(model.id, 'shelf_thickness', 18);

    // Создать полки с ограничениями расстояния
    for (let i = 0; i < shelfCount; i++) {
      const yOffset = i * 450; // spacing + thickness

      // Добавить ограничение для позиции полки
      kernel.addConstraint(
        model.id,
        'distance',
        [
          { id: 'bottom_face', type: 'face' },
          { id: `shelf_${i}`, type: 'body' }
        ],
        yOffset
      );
    }

    // Решить ограничения
    const result = kernel.solveConstraints(model.id);

    console.log(`[CADEngine] Created parametric shelves:`, {
      count: shelfCount,
      converged: result?.converged,
      iterations: result?.iterations
    });

    return model;
  }
};

export default CADEngine;
