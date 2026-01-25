/**
 * CAD KERNEL - Главное ядро системы
 * 
 * Интегрирует:
 * - Параметрический движок (DAG + ConstraintSolver)
 * - Геометрическое ядро (B-Rep операции)
 * - Валидацию и производство
 * 
 * Использование:
 * const kernel = new CADKernel();
 * const model = kernel.createModel('CabinetV2');
 * kernel.updateParameter(modelId, 'width', 1200);
 * kernel.validate(modelId);
 */

import {
  CADModel,
  Body,
  Face,
  Constraint,
  Parameter,
  Feature,
  DependencyGraph,
  HistoryEntry,
  SolverResult,
  SolverOptions,
  ValidationResult,
  Collision,
  ManufacturingIssue,
  ConstraintType,
  ConstraintStatus,
  Vector3,
  AABB,
  Vertex,
  Edge
} from './CADTypes';
import { ConstraintSolver, SolverResult as ConstraintSolverResult } from '../ConstraintSolver';

/**
 * Главное ядро CAD системы
 */
export class CADKernel {
  private models: Map<string, CADModel> = new Map();
  private constraintSolver: ConstraintSolver;
  private idCounter = 0;

  constructor() {
    this.constraintSolver = new ConstraintSolver();
  }

  // ========================================================================
  // ОСНОВНОЙ API
  // ========================================================================

  /**
   * Создать новую CAD модель
   */
  createModel(name: string, description?: string): CADModel {
    const model: CADModel = {
      id: this.generateId('model'),
      name,
      version: '1.0.0',
      bodies: [],
      constraints: [],
      features: [],
      parameters: new Map(),
      dependencyGraph: {
        nodes: new Map(),
        edges: new Map()
      },
      history: [],
      currentHistoryIndex: -1,
      createdAt: new Date(),
      modifiedAt: new Date(),
      description
    };

    this.models.set(model.id, model);
    console.log(`[CADKernel] Created model: ${name} (${model.id})`);

    return model;
  }

  /**
   * Получить модель по ID
   */
  getModel(modelId: string): CADModel | undefined {
    return this.models.get(modelId);
  }

  /**
   * Создать параметр в модели
   */
  createParameter(
    modelId: string,
    name: string,
    initialValue: number,
    options?: {
      min?: number;
      max?: number;
      unit?: string;
      isDriving?: boolean;
    }
  ): Parameter {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    const parameter: Parameter = {
      id: this.generateId('param'),
      name,
      value: initialValue,
      min: options?.min,
      max: options?.max,
      unit: options?.unit,
      isDriving: options?.isDriving ?? true,
      dependentConstraints: [],
      dependentBodies: [],
      dependentFeatures: []
    };

    model.parameters.set(parameter.id, parameter);
    this.addNodeToDAG(model, parameter.id, 'parameter');

    this.recordHistory(modelId, 'create', parameter.id, name, undefined, parameter);

    return parameter;
  }

  /**
   * Обновить значение параметра
   */
  updateParameter(
    modelId: string,
    parameterId: string,
    newValue: number
  ): SolverResult | null {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    const parameter = model.parameters.get(parameterId);
    if (!parameter) throw new Error(`Parameter not found: ${parameterId}`);

    // Проверить границы
    if (parameter.min !== undefined && newValue < parameter.min) {
      console.warn(`[CADKernel] Parameter ${parameter.name} below minimum (${parameter.min})`);
      return null;
    }
    if (parameter.max !== undefined && newValue > parameter.max) {
      console.warn(`[CADKernel] Parameter ${parameter.name} exceeds maximum (${parameter.max})`);
      return null;
    }

    const oldValue = parameter.value;
    parameter.value = newValue;
    model.modifiedAt = new Date();

    this.recordHistory(modelId, 'parameter', parameterId, parameter.name, oldValue, newValue);

    // Решить зависимые ограничения
    return this.solveConstraints(modelId);
  }

  /**
   * Добавить ограничение
   */
  addConstraint(
    modelId: string,
    type: ConstraintType,
    elements: any[],
    value?: number
  ): Constraint {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    const constraint: Constraint = {
      id: this.generateId('constraint'),
      type,
      elements: elements.map(e => ({
        type: e.type || 'vertex',
        id: e.id || e
      })),
      value,
      status: 'unsatisfied',
      weight: 1.0,
      isActive: true,
      createdAt: new Date()
    };

    model.constraints.push(constraint);
    this.addNodeToDAG(model, constraint.id, 'constraint');

    this.recordHistory(modelId, 'constraint', constraint.id, `${type} constraint`, undefined, constraint);

    console.log(`[CADKernel] Added constraint: ${type} (${constraint.id})`);

    return constraint;
  }

  /**
   * Решить все ограничения (Newton-Raphson)
   */
  solveConstraints(
    modelId: string,
    options?: SolverOptions
  ): SolverResult | null {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    if (model.constraints.length === 0) {
      console.log('[CADKernel] No constraints to solve');
      return null;
    }

    // Подготовить переменные (параметры + положения тел)
    const variables = new Map<string, number>();
    model.parameters.forEach((param, id) => {
      variables.set(id, param.value);
    });

    // Запустить solver
    const assembly: any = {
      components: model.bodies.map((b, i) => ({
        id: b.id,
        position: { x: 0, y: 0, z: 0 },
        name: b.name
      })),
      constraints: model.constraints
    };

    // Преобразовать переменные в позиции для solver
    const positionVariables = new Map<string, any>();
    model.parameters.forEach((param, id) => {
      positionVariables.set(id, { x: param.value, y: 0, z: 0 });
    });

    let solverResult: ConstraintSolverResult;
    try {
      solverResult = this.constraintSolver.solve(assembly, positionVariables, options);
    } catch (error) {
      console.error('[CADKernel] Solver error:', error);
      return null;
    }

    // Обновить статус ограничений
    model.constraints.forEach(constraint => {
      const status = solverResult.constraintErrors.get(constraint.id);
      if (status !== undefined) {
        constraint.residual = status;
        if (status < (options?.tolerance ?? 1e-6)) {
          constraint.status = 'satisfied';
        } else if (status < 0.1) {
          constraint.status = 'unsatisfied';
        } else {
          constraint.status = 'conflicting';
        }
      }
    });

    // Сохранить результат
    const result: SolverResult = {
      success: solverResult.success,
      converged: solverResult.converged,
      iterations: solverResult.iterations,
      residual: solverResult.error,
      timestamp: solverResult.solverTime,
      constraintStatus: new Map(
        model.constraints.map(c => [c.id, c.status])
      )
    };

    model.solverResult = result;
    model.modifiedAt = new Date();

    console.log(
      `[CADKernel] Solver: ${solverResult.converged ? 'CONVERGED' : 'FAILED'} ` +
      `(${solverResult.iterations} iterations, residual: ${solverResult.error.toFixed(6)})`
    );

    return result;
  }

  // ========================================================================
  // ВАЛИДАЦИЯ
  // ========================================================================

  /**
   * Полная валидация модели
   */
  validate(modelId: string): ValidationResult {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    const result: ValidationResult = {
      isValid: true,
      timestamp: new Date(),
      collisions: [],
      manufacturingIssues: [],
      constraintErrors: [],
      warnings: [],
      totalIssues: 0,
      totalErrors: 0,
      totalWarnings: 0
    };

    // 1. Проверить ограничения
    model.constraints.forEach(constraint => {
      if (constraint.status === 'conflicting' || constraint.status === 'over_constrained') {
        result.isValid = false;
        result.constraintErrors.push({
          constraintId: constraint.id,
          message: `Constraint is ${constraint.status}`,
          severity: 'error'
        });
        result.totalErrors++;
      } else if (constraint.status === 'unsatisfied') {
        result.warnings.push(`Constraint ${constraint.type} is unsatisfied`);
        result.totalWarnings++;
      }
    });

    // 2. Проверить коллизии между телами
    result.collisions = this.detectCollisions(model.bodies);
    if (result.collisions.length > 0) {
      result.isValid = false;
      result.totalErrors += result.collisions.length;
    }

    // 3. Проверить производимость (DFM)
    result.manufacturingIssues = this.checkDFM(model);
    result.totalIssues += result.manufacturingIssues.length;
    result.totalErrors += result.manufacturingIssues.filter(i => i.severity === 'error').length;
    result.totalWarnings += result.manufacturingIssues.filter(i => i.severity === 'warning').length;

    result.totalIssues = result.collisions.length + result.manufacturingIssues.length;

    if (result.totalErrors > 0) {
      result.isValid = false;
    }

    console.log(
      `[CADKernel] Validation: ${result.isValid ? 'PASS' : 'FAIL'} ` +
      `(${result.totalErrors} errors, ${result.totalWarnings} warnings)`
    );

    return result;
  }

  /**
   * Простая проверка коллизий (AABB)
   */
  private detectCollisions(bodies: Body[]): Collision[] {
    const collisions: Collision[] = [];

    for (let i = 0; i < bodies.length; i++) {
      for (let j = i + 1; j < bodies.length; j++) {
        const body1 = bodies[i];
        const body2 = bodies[j];

        // Простая AABB проверка
        if (this.aabbOverlap(body1.boundingBox, body2.boundingBox)) {
          collisions.push({
            id: this.generateId('collision'),
            body1Id: body1.id,
            body2Id: body2.id,
            face1Id: body1.faces[0]?.id || '',
            face2Id: body2.faces[0]?.id || '',
            penetrationDepth: 0.5,
            contactPoints: [],
            severity: 'warning'
          });
        }
      }
    }

    return collisions;
  }

  /**
   * Проверка Design For Manufacturing (DFM)
   */
  private checkDFM(model: CADModel): ManufacturingIssue[] {
    const issues: ManufacturingIssue[] = [];

    model.bodies.forEach(body => {
      // Проверить радиусы скругления (минимум 1mm)
      body.faces.forEach(face => {
        if (face.surfaceType === 'cylindrical' && face.area < 100) {
          issues.push({
            id: this.generateId('dfm'),
            objectId: face.id,
            type: 'radius_too_small',
            severity: 'warning',
            suggestion: 'Increase fillet radius to at least 1mm'
          });
        }
      });

      // Проверить толщину стенок (минимум 1mm)
      if (body.boundingBox.size.x < 1 || body.boundingBox.size.y < 1) {
        issues.push({
          id: this.generateId('dfm'),
          objectId: body.id,
          type: 'thickness_too_thin',
          severity: 'error',
          suggestion: 'Increase wall thickness to at least 1mm'
        });
      }
    });

    return issues;
  }

  // ========================================================================
  // ИСТОРИЯ (Undo/Redo)
  // ========================================================================

  /**
   * Отмена последнего действия
   */
  undo(modelId: string): boolean {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    if (model.currentHistoryIndex <= 0) {
      console.warn('[CADKernel] Nothing to undo');
      return false;
    }

    model.currentHistoryIndex--;
    const entry = model.history[model.currentHistoryIndex];

    console.log(`[CADKernel] Undo: ${entry.action} - ${entry.description}`);

    // Восстановить состояние (упрощённо)
    if (entry.beforeState) {
      const param = model.parameters.get(entry.objectId);
      if (param) {
        param.value = entry.beforeState;
      }
    }

    return true;
  }

  /**
   * Повтор последнего отменённого действия
   */
  redo(modelId: string): boolean {
    const model = this.models.get(modelId);
    if (!model) throw new Error(`Model not found: ${modelId}`);

    if (model.currentHistoryIndex >= model.history.length - 1) {
      console.warn('[CADKernel] Nothing to redo');
      return false;
    }

    model.currentHistoryIndex++;
    const entry = model.history[model.currentHistoryIndex];

    console.log(`[CADKernel] Redo: ${entry.action} - ${entry.description}`);

    // Восстановить состояние (упрощённо)
    if (entry.afterState) {
      const param = model.parameters.get(entry.objectId);
      if (param) {
        param.value = entry.afterState;
      }
    }

    return true;
  }

  private recordHistory(
    modelId: string,
    action: string,
    objectId: string,
    objectName: string,
    beforeState?: any,
    afterState?: any
  ): void {
    const model = this.models.get(modelId);
    if (!model) return;

    const entry: HistoryEntry = {
      id: this.generateId('history'),
      timestamp: new Date(),
      action: action as any,
      objectId,
      objectName,
      beforeState,
      afterState,
      description: `${action}: ${objectName}`
    };

    // Удалить всё после текущей позиции (если были undo-ы)
    model.history = model.history.slice(0, model.currentHistoryIndex + 1);

    // Добавить новую запись
    model.history.push(entry);
    model.currentHistoryIndex++;
  }

  // ========================================================================
  // ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
  // ========================================================================

  private addNodeToDAG(model: CADModel, nodeId: string, type: string): void {
    model.dependencyGraph.nodes.set(nodeId, { id: nodeId, type } as any);
  }

  private aabbOverlap(box1: AABB, box2: AABB): boolean {
    return (
      box1.min.x < box2.max.x &&
      box1.max.x > box2.min.x &&
      box1.min.y < box2.max.y &&
      box1.max.y > box2.min.y &&
      box1.min.z < box2.max.z &&
      box1.max.z > box2.min.z
    );
  }

  private generateId(prefix: string): string {
    return `${prefix}_${++this.idCounter}_${Date.now()}`;
  }

  /**
   * Получить статистику модели
   */
  getStats(modelId: string): any {
    const model = this.models.get(modelId);
    if (!model) return null;

    return {
      name: model.name,
      bodies: model.bodies.length,
      constraints: model.constraints.length,
      parameters: model.parameters.size,
      history: model.history.length,
      constraintsSatisfied: model.constraints.filter(c => c.status === 'satisfied').length,
      solverConverged: model.solverResult?.converged ?? false
    };
  }
}

export default CADKernel;
