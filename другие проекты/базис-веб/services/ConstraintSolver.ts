/**
 * ФАЗА 2: Constraint Solver
 * 
 * Решает систему ограничений методом Newton-Raphson
 * для позиционирования компонентов в сборке
 * 
 * Использует численное дифференцирование для вычисления Jacobian матрицы
 * и LU разложение для решения линейных систем
 */

import {
  Assembly,
  Component,
  Constraint,
  ConstraintType,
  ConstraintCheckResult,
  SolverOptions,
  SolvedAssembly,
  Point3D
} from '../types/CADTypes';

/**
 * Результат решения системы ограничений
 */
export interface SolverResult {
  success: boolean;
  positions: Map<string, Point3D>;
  iterations: number;
  error: number;
  converged: boolean;
  constraintErrors: Map<string, number>;
  solverTime: number;
  residuals?: number[];
  message?: string;
}

/**
 * Результат валидации системы ограничений
 */
export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  degreesOfFreedom: number;
  constraintCount: number;
}

/**
 * ConstraintSolver решает систему нелинейных уравнений ограничений
 * используя метод Newton-Raphson с численным дифференцированием
 * 
 * @example
 * const solver = new ConstraintSolver();
 * const result = solver.solve(assembly, initialPositions);
 */
export class ConstraintSolver {
  private tolerance: number = 0.001;
  private maxIterations: number = 100;
  private verbose: boolean = false;
  private stepSize: number = 0.001; // Для численного дифференцирования

  /**
   * Создать solver
   */
  constructor() {
    // Конструктор без параметров
  }

  /**
   * Решить систему ограничений методом Newton-Raphson
   * 
   * @param assembly Сборка с ограничениями
   * @param initialPositions Начальные позиции компонентов
   * @param options Опции solver
   * @returns Результат решения
   */
  solve(
    assembly: Assembly,
    initialPositions: Map<string, Point3D>,
    options?: SolverOptions
  ): SolverResult {
    if (options) {
      this.tolerance = options.tolerance ?? 0.001;
      this.maxIterations = options.maxIterations ?? 100;
      this.verbose = options.verbose ?? false;
    }

    const startTime = performance.now();
    const constraints = assembly.constraints || [];
    
    // Если нет компонентов, возвращаем пусто
    if (assembly.components.length === 0) {
      return {
        success: true,
        positions: new Map(),
        iterations: 0,
        error: 0,
        converged: true,
        constraintErrors: new Map(),
        solverTime: performance.now() - startTime
      };
    }

    // Инициализировать позиции
    let positions = new Map(initialPositions);
    let iteration = 0;
    let residual = Infinity;
    const constraintErrors = new Map<string, number>();

    // Newton-Raphson итерации
    let residualVector: number[] = [];
    while (iteration < this.maxIterations && residual > this.tolerance) {
      // Вычислить residual вектор
      residualVector = this.computeResidualVector(assembly, positions, constraints);
      
      // Вычислить L2 норму с защитой от NaN
      let sumOfSquares = 0;
      for (const r of residualVector) {
        if (isFinite(r)) {
          const val = r * r;
          if (isFinite(val)) {
            sumOfSquares += val;
          }
        }
      }
      residual = Math.sqrt(Math.max(0, sumOfSquares));

      if (this.verbose) {
        console.log(`[Solver] Iteration ${iteration}: residual = ${residual.toFixed(6)}`);
      }

      // Если сходимость достигнута, выход
      if (residual < this.tolerance) {
        break;
      }

      // Если residual стал NaN или слишком большой, выход
      if (!isFinite(residual)) {
        residual = Infinity;
        break;
      }

      // Вычислить Jacobian матрицу (численное дифференцирование)
      const jacobian = this.computeJacobianNumerical(assembly, positions, constraints);

      // Решить систему J * Δx = -f(x)
      const deltaX = this.solveLU(jacobian, residualVector.map(r => -r));

      if (!deltaX) {
        // Если решение не найдено, выход с ошибкой
        break;
      }

      // Обновить позиции
      let componentIndex = 0;
      for (const component of assembly.components) {
        const dx = deltaX[componentIndex * 3] || 0;
        const dy = deltaX[componentIndex * 3 + 1] || 0;
        const dz = deltaX[componentIndex * 3 + 2] || 0;

        // Защита от NaN при обновлении позиций
        if (!isFinite(dx) || !isFinite(dy) || !isFinite(dz)) {
          break;
        }

        const oldPos = positions.get(component.id) || { x: 0, y: 0, z: 0 };
        positions.set(component.id, {
          x: oldPos.x + dx,
          y: oldPos.y + dy,
          z: oldPos.z + dz
        });

        componentIndex++;
      }

      iteration++;
    }

    // Вычислить финальные ошибки ограничений
    for (const constraint of constraints) {
      const error = this.computeConstraintError(assembly, positions, constraint);
      constraintErrors.set(constraint.id, isFinite(error) ? error : Infinity);
    }

    // Убедиться что final error не NaN
    const finalError = isFinite(residual) ? residual : Infinity;
    const finalSuccess = residual < this.tolerance && isFinite(residual);

    const message = finalSuccess
      ? `Convergence achieved in ${iteration} iterations (error: ${residual.toFixed(6)})`
      : `Solver stopped after ${iteration}/${this.maxIterations} iterations (error: ${finalError === Infinity ? 'Infinity' : residual.toFixed(6)})`;

    return {
      success: finalSuccess,
      positions,
      iterations: iteration,
      error: finalError,
      converged: finalSuccess,
      constraintErrors,
      solverTime: performance.now() - startTime,
      residuals: residualVector,
      message
    };
  }

  /**
   * Валидировать систему ограничений
   */
  validateConstraintSystem(assembly: Assembly): ValidationResult {
    const constraints = assembly.constraints || [];
    const components = assembly.components || [];
    const errors: string[] = [];
    const warnings: string[] = [];

    if (components.length === 0) {
      errors.push('Система не содержит компонентов');
    }

    if (constraints.length === 0) {
      errors.push('Система не содержит ограничений');
    }

    // Проверить что каждое ограничение ссылается на существующие компоненты
    for (const constraint of constraints) {
      if (constraint.elementA && !components.some(c => c.id === constraint.elementA)) {
        errors.push(`Constraint ${constraint.id}: elementA "${constraint.elementA}" не найден`);
      }
      if (constraint.elementB && !components.some(c => c.id === constraint.elementB)) {
        errors.push(`Constraint ${constraint.id}: elementB "${constraint.elementB}" не найден`);
      }
    }

    // Оценить степени свободы (очень упрощённо)
    // 6 DOF на компонент, минус степени ограничений
    let dof = components.length * 6;
    let fixedCount = 0;
    let otherConstraintCount = 0;
    
    for (const constraint of constraints) {
      if (constraint.type === ConstraintType.FIXED) {
        fixedCount++;
      } else {
        otherConstraintCount++;
      }
    }
    
    // Каждое FIXED ограничение убирает 6 DOF (все степени свободы)
    dof -= fixedCount * 6;
    // Каждое другое ограничение убирает 1 DOF (в усреднённом виде)
    dof -= otherConstraintCount;

    // Если нет FIXED constraints, система не привязана
    if (fixedCount === 0 && constraints.length > 0) {
      errors.push(`Система не привязана - отсутствуют FIXED constraints`);
    }

    // Проверить переопределённость: после расчёта эффективного DOF с учётом FIXED,
    // если DOF <= 0 и есть ограничения, система переопределена
    if (dof <= 0 && constraints.length > 0) {
      errors.push(`Система переопределена (DOF: ${dof}, constraints: ${constraints.length})`);
    }

    if (dof > 0 && fixedCount === 0) {
      warnings.push(`Система может быть недоопределена - нет FIXED constraints (DOF: ${dof})`);
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      degreesOfFreedom: Math.max(0, dof),
      constraintCount: constraints.length
    };
  }

  /**
   * Проверить, удовлетворены ли все ограничения
   */
  checkConstraints(assembly: Assembly, positions: Map<string, Point3D>): ConstraintCheckResult[] {
    return (assembly.constraints || []).map(constraint => {
      const error = this.computeConstraintError(assembly, positions, constraint);
      return {
        constraintId: constraint.id,
        satisfied: error < this.tolerance,
        error: error,
        errorMessage: error > this.tolerance ? `Error: ${error.toFixed(3)}` : undefined
      };
    });
  }

  /**
   * Вычислить вектор residual (невязки)
   * @private
   */
  private computeResidualVector(
    assembly: Assembly,
    positions: Map<string, Point3D>,
    constraints: Constraint[]
  ): number[] {
    const residual: number[] = [];

    for (const constraint of constraints) {
      const error = this.computeConstraintError(assembly, positions, constraint);
      residual.push(isFinite(error) ? error : 0);
    }

    return residual;
  }

  /**
   * Вычислить ошибку отдельного ограничения
   * @private
   */
  private computeConstraintError(
    assembly: Assembly,
    positions: Map<string, Point3D>,
    constraint: Constraint
  ): number {
    const pos1 = positions.get(constraint.elementA) || { x: 0, y: 0, z: 0 };

    switch (constraint.type) {
      case ConstraintType.FIXED:
        // Ошибка FIXED = расстояние от исходной позиции (которая обычно близка к 0 для базовых компонентов)
        const dx1 = pos1.x;
        const dy1 = pos1.y;
        const dz1 = pos1.z;
        return Math.sqrt(dx1 * dx1 + dy1 * dy1 + dz1 * dz1);

      case ConstraintType.DISTANCE: {
        const pos2 = positions.get(constraint.elementB) || { x: 0, y: 0, z: 0 };
        const dx = pos2.x - pos1.x;
        const dy = pos2.y - pos1.y;
        const dz = pos2.z - pos1.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        return Math.abs(dist - (constraint.value || 0));
      }

      case ConstraintType.COINCIDENT: {
        const pos2 = positions.get(constraint.elementB) || { x: 0, y: 0, z: 0 };
        const dx = pos2.x - pos1.x;
        const dy = pos2.y - pos1.y;
        const dz = pos2.z - pos1.z;
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
      }

      case ConstraintType.PARALLEL:
      case ConstraintType.PERPENDICULAR:
      case ConstraintType.ANGLE:
      default:
        return 0;
    }
  }

  /**
   * Вычислить Jacobian матрицу численным методом
   * @private
   */
  private computeJacobianNumerical(
    assembly: Assembly,
    positions: Map<string, Point3D>,
    constraints: Constraint[]
  ): number[][] {
    const numConstraints = constraints.length;
    const numComponents = assembly.components.length;
    const numVars = numComponents * 3; // x, y, z для каждого компонента

    const jacobian: number[][] = [];

    // Для каждого ограничения
    for (let i = 0; i < numConstraints; i++) {
      jacobian[i] = [];

      // Для каждой переменной
      for (let j = 0; j < numVars; j++) {
        const componentIndex = Math.floor(j / 3);
        const coordinate = j % 3; // 0=x, 1=y, 2=z

        // Сохранить оригинальную позицию
        const component = assembly.components[componentIndex];
        const originalPos = positions.get(component.id) || { x: 0, y: 0, z: 0 };

        if (!isFinite(originalPos.x) || !isFinite(originalPos.y) || !isFinite(originalPos.z)) {
          throw new Error(
            `Invalid position for component "${component.id}": ` +
            `x=${originalPos.x}, y=${originalPos.y}, z=${originalPos.z}. ` +
            `All coordinates must be finite numbers.`
          );
        }

        // Вычислить f(x + h)
        const perturbedPos = { ...originalPos };
        if (coordinate === 0) perturbedPos.x += this.stepSize;
        else if (coordinate === 1) perturbedPos.y += this.stepSize;
        else perturbedPos.z += this.stepSize;

        const posPerturbed = new Map(positions);
        posPerturbed.set(component.id, perturbedPos);

        const fPlus = this.computeConstraintError(assembly, posPerturbed, constraints[i]);
        const fOrig = this.computeConstraintError(assembly, positions, constraints[i]);

        if (!isFinite(fPlus) || !isFinite(fOrig)) {
          throw new Error(
            `Constraint error computation produced invalid values for constraint "${constraints[i].id}": ` +
            `fPlus=${fPlus}, fOrig=${fOrig}. This usually indicates numerical instability or invalid input data.`
          );
        }

        // Численная производная с защитой от NaN
        let derivative = (fPlus - fOrig) / this.stepSize;
        if (!isFinite(derivative)) {
          throw new Error(
            `Jacobian element [${i}][${j}] is not finite: ${derivative}. ` +
            `This indicates a degenerate constraint or numerical singularity.`
          );
        }
        jacobian[i][j] = derivative;
      }
    }

    return jacobian;
  }

  /**
   * Решить линейную систему методом Gaussian elimination с LU разложением
   * @private
   */
  private solveLU(matrix: number[][], vector: number[]): number[] | null {
    const n = matrix.length;
    if (n === 0) return vector;

    // Валидировать входные параметры
    for (let i = 0; i < n; i++) {
      if (matrix[i].length !== n) {
        return null;
      }
      for (let j = 0; j < n; j++) {
        if (!isFinite(matrix[i][j])) {
          return null;
        }
      }
      if (!isFinite(vector[i])) {
        return null;
      }
    }

    // Создать копии для манипуляции
    const A = matrix.map(row => [...row]);
    const b = [...vector];

    // Forward elimination с частичным пивотированием
    for (let col = 0; col < n; col++) {
      // Найти pivot
      let maxRow = col;
      for (let row = col + 1; row < n; row++) {
        if (Math.abs(A[row][col]) > Math.abs(A[maxRow][col])) {
          maxRow = row;
        }
      }

      // Swap rows
      [A[col], A[maxRow]] = [A[maxRow], A[col]];
      [b[col], b[maxRow]] = [b[maxRow], b[col]];

      // Проверить вырожденность
      if (Math.abs(A[col][col]) < 1e-10) {
        return null;
      }

      // Элиминировать
      for (let row = col + 1; row < n; row++) {
        const factor = A[row][col] / A[col][col];
        
        if (!isFinite(factor)) {
          return null;
        }

        for (let j = col; j < n; j++) {
          A[row][j] -= factor * A[col][j];
          
          if (!isFinite(A[row][j])) {
            return null;
          }
        }
        
        b[row] -= factor * b[col];
        
        if (!isFinite(b[row])) {
          return null;
        }
      }
    }

    // Back substitution
    const x = new Array(n);
    for (let i = n - 1; i >= 0; i--) {
      x[i] = b[i];
      for (let j = i + 1; j < n; j++) {
        x[i] -= A[i][j] * x[j];
        
        if (!isFinite(x[i])) {
          return null;
        }
      }
      
      if (Math.abs(A[i][i]) < 1e-10) {
        return null;
      }
      
      x[i] /= A[i][i];
      
      if (!isFinite(x[i])) {
        return null;
      }
    }

    return x;
  }
}
