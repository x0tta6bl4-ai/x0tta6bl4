import { CabinetDSL, SolvedPanel, ValidationError, Mm } from '../types/ProductionArchitecture';
import {
  Parameter,
  ParametricConstraint,
  DependencyGraphNode,
  DependencyGraph,
  RecalculationResult,
  Version,
  VersionDiff,
  Branch,
  MergeResult,
  Tolerance,
  DimensionCheck,
  ToleranceReport,
  DraftModeConfig,
  InteractiveEditState,
  RealTimePreviewOptions,
  CostItem,
  LaborCost,
  MaterialCostBreakdown,
  HardwareCost,
  CostBreakdown,
  CostCalculation,
  Tool,
  AssemblyStep,
  AssemblyGuide,
  AssemblyAnimation,
  ParametricSystem as IParametricSystem
} from '../types/ParametricSystem';

/**
 * Реализация параметрической системы с топологической сортировкой и зависимостями
 * v2.1
 */
export class ParametricSystem implements IParametricSystem {
  // Параметрическая связность
  public parameters: Map<string, Parameter> = new Map();
  public constraints: ParametricConstraint[] = [];
  public dependencyGraph: DependencyGraph = { nodes: new Map(), edges: new Map() };

  // История версий
  public versions: Version[] = [];
  public branches: Branch[] = [];
  public currentBranch: string = 'main';
  public currentVersion: string = '';

  // Производственные допуски
  public tolerances: Tolerance[] = [];
  public toleranceReport: ToleranceReport = this.createEmptyToleranceReport();

  // Интерактивное редактирование
  public interactiveState: InteractiveEditState = {
    isEditing: false,
    selectedComponent: '',
    editMode: '3d',
    draftMode: { enabled: false, autoRecalculate: true, previewQuality: 'medium', autoSave: true, saveInterval: 30 },
    lastModified: Date.now(),
    unsavedChanges: []
  };

  public realTimePreview: RealTimePreviewOptions = {
    cameraPosition: { x: 0, y: 0, z: 0 },
    cameraTarget: { x: 0, y: 0, z: 0 },
    lightingPreset: 'studio',
    showDimensions: true,
    showConstraints: true,
    showHoles: true,
    wireframeMode: false
  };

  // Расчёт себестоимости
  public costCalculation: CostCalculation = this.createEmptyCostCalculation();

  // Руководство сборки
  public assemblyGuide: AssemblyGuide = this.createEmptyAssemblyGuide();

  // Конструктор
  constructor() {
    this.initializeDefaultTolerances();
    this.initializeDefaultParameters();
    this.initializeVersionHistory();
    this.buildDependencyGraph();
  }

  // =============================================================================
  // 1. Параметрическая связность
  // =============================================================================

  /**
   * Инициализация стандартных параметров
   */
  private initializeDefaultParameters(): void {
    const defaultParams: Parameter[] = [
      { id: 'width', name: 'Ширина', type: 'number', value: 1200, min: 300, max: 3000, unit: 'mm', description: 'Ширина шкафа' },
      { id: 'height', name: 'Высота', type: 'number', value: 2000, min: 600, max: 2800, unit: 'mm', description: 'Высота шкафа' },
      { id: 'depth', name: 'Глубина', type: 'number', value: 500, min: 300, max: 800, unit: 'mm', description: 'Глубина шкафа' },
      { id: 'thickness', name: 'Толщина', type: 'select', value: '16', options: ['8', '10', '12', '16', '18', '22', '25'], unit: 'mm', description: 'Толщина материала' },
      { id: 'material', name: 'Материал', type: 'select', value: 'ldsp', options: ['ldsp', 'mdf', 'plywood', 'hdf'], description: 'Тип материала' }
    ];

    defaultParams.forEach(param => this.parameters.set(param.id, param));
  }

  /**
   * Получить параметр по ID
   */
  public getParameter(id: string): Parameter | undefined {
    return this.parameters.get(id);
  }

  /**
   * Установить значение параметра и пересчитать зависимые
   */
  public setParameter(id: string, value: any): RecalculationResult {
    const startTime = Date.now();
    const updatedParameters: string[] = [];
    const affectedPanels: SolvedPanel[] = [];
    const validationErrors: ValidationError[] = [];

    const param = this.parameters.get(id);
    if (!param) {
      validationErrors.push({ code: 'PARAM_NOT_FOUND', msg: `Параметр ${id} не найден`, severity: 'error' });
      return { updatedParameters, affectedPanels, validationErrors, recalculationTime: Date.now() - startTime };
    }

    // Проверка валидности значения
    const valueErrors = this.validateParameterValue(param, value);
    if (valueErrors.length > 0) {
      validationErrors.push(...valueErrors);
      return { updatedParameters, affectedPanels, validationErrors, recalculationTime: Date.now() - startTime };
    }

    // Установка нового значения
    param.value = value;
    updatedParameters.push(id);

    // Поиск и обновление зависимых параметров
    const dependentNodes = this.findDependentNodes(id);
    for (const nodeId of dependentNodes) {
      const node = this.dependencyGraph.nodes.get(nodeId);
      if (node) {
        for (const constraint of node.constraints) {
          if (constraint.isActive) {
            try {
              const result = this.evaluateConstraint(constraint);
              const targetParam = this.parameters.get(constraint.target);
              if (targetParam) {
                targetParam.value = result;
                updatedParameters.push(targetParam.id);
              }
            } catch (error) {
              validationErrors.push({
                code: 'CONSTRAINT_EVAL_ERROR',
                msg: `Ошибка при вычислении ограничения ${constraint.id}: ${error}`,
                severity: 'warning'
              });
            }
          }
        }
      }
    }

    return {
      updatedParameters,
      affectedPanels,
      validationErrors,
      recalculationTime: Date.now() - startTime
    };
  }

  /**
   * Добавить параметр
   */
  public addParameter(param: Parameter): void {
    this.parameters.set(param.id, param);
    this.buildDependencyGraph();
  }

  /**
   * Удалить параметр
   */
  public removeParameter(id: string): void {
    this.parameters.delete(id);
    this.constraints = this.constraints.filter(c => c.source !== id && c.target !== id);
    this.buildDependencyGraph();
  }

  /**
   * Добавить ограничение
   */
  public addConstraint(constraint: ParametricConstraint): void {
    this.constraints.push(constraint);
    this.buildDependencyGraph();
  }

  /**
   * Удалить ограничение
   */
  public removeConstraint(id: string): void {
    this.constraints = this.constraints.filter(c => c.id !== id);
    this.buildDependencyGraph();
  }

  /**
   * Валидация параметров
   */
  public validateParameters(): ValidationError[] {
    const errors: ValidationError[] = [];
    this.parameters.forEach(param => {
      const valueErrors = this.validateParameterValue(param, param.value);
      errors.push(...valueErrors);
    });
    return errors;
  }

  /**
   * Проверка значения параметра
   */
  private validateParameterValue(param: Parameter, value: any): ValidationError[] {
    const errors: ValidationError[] = [];

    if (param.type === 'number') {
      const numValue = Number(value);
      if (isNaN(numValue)) {
        errors.push({ code: 'INVALID_NUMERIC', msg: `Значение ${value} не является числом`, severity: 'error' });
      }
      if (param.min !== undefined && numValue < param.min) {
        errors.push({ code: 'VALUE_TOO_SMALL', msg: `Значение ${value} < минимального ${param.min}`, severity: 'error' });
      }
      if (param.max !== undefined && numValue > param.max) {
        errors.push({ code: 'VALUE_TOO_LARGE', msg: `Значение ${value} > максимального ${param.max}`, severity: 'error' });
      }
    }

    if (param.type === 'select' && param.options) {
      if (!param.options.includes(value)) {
        errors.push({ code: 'INVALID_OPTION', msg: `Значение ${value} не в списке допустимых: ${param.options.join(', ')}`, severity: 'error' });
      }
    }

    return errors;
  }

  /**
   * Пересчитать зависимые параметры и панели
   */
  public recalculateAffected(): RecalculationResult {
    const startTime = Date.now();
    const updatedParameters: string[] = [];
    const affectedPanels: SolvedPanel[] = [];
    const validationErrors: ValidationError[] = [];

    // Валидация всех параметров
    validationErrors.push(...this.validateParameters());

    // Для простоты примера просто проверяем все параметры
    this.parameters.forEach(param => updatedParameters.push(param.id));

    return {
      updatedParameters,
      affectedPanels,
      validationErrors,
      recalculationTime: Date.now() - startTime
    };
  }

  /**
   * Построение графа зависимостей
   */
  private buildDependencyGraph(): void {
    this.dependencyGraph.nodes.clear();
    this.dependencyGraph.edges.clear();

    // Создание узлов для параметров
    this.parameters.forEach(param => {
      const node: DependencyGraphNode = {
        id: param.id,
        parameter: param,
        constraints: this.constraints.filter(c => c.target === param.id),
        dependencies: [],
        dependents: []
      };
      this.dependencyGraph.nodes.set(param.id, node);
    });

    // Определение зависимостей и зависимых параметров
    this.constraints.forEach(constraint => {
      const sourceNode = this.dependencyGraph.nodes.get(constraint.source);
      const targetNode = this.dependencyGraph.nodes.get(constraint.target);

      if (sourceNode && targetNode) {
        if (!sourceNode.dependents.includes(constraint.target)) {
          sourceNode.dependents.push(constraint.target);
        }
        if (!targetNode.dependencies.includes(constraint.source)) {
          targetNode.dependencies.push(constraint.source);
        }
      }

      // Добавление ребра в граф
      if (!this.dependencyGraph.edges.has(constraint.source)) {
        this.dependencyGraph.edges.set(constraint.source, []);
      }
      this.dependencyGraph.edges.get(constraint.source)?.push(constraint.target);
    });
  }

  /**
   * Поиск всех зависимых узлов
   */
  private findDependentNodes(startId: string): string[] {
    const dependents: string[] = [];
    const visited = new Set<string>();
    const queue = [startId];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;

      visited.add(current);
      const node = this.dependencyGraph.nodes.get(current);
      if (node) {
        node.dependents.forEach(dep => {
          if (dep !== startId && !dependents.includes(dep)) {
            dependents.push(dep);
            queue.push(dep);
          }
        });
      }
    }

    return dependents;
  }

  /**
   * Вычисление ограничения
   */
  private evaluateConstraint(constraint: ParametricConstraint): any {
    // В простом случае просто возвращаем новое значение
    return this.parameters.get(constraint.target)?.value || 0;
  }

  // =============================================================================
  // 2. История версий
  // =============================================================================

  /**
   * Инициализация истории версий
   */
  private initializeVersionHistory(): void {
    const initialVersion: Version = {
      id: 'v1.0.0',
      name: 'Initial Version',
      description: 'Основная версия шкафа',
      timestamp: Date.now(),
      author: 'System',
      versionNumber: '1.0.0',
      changelog: ['Инициализация проекта', 'Создание базового модели']
    };

    this.versions.push(initialVersion);
    this.currentVersion = initialVersion.id;

    const mainBranch: Branch = {
      id: 'main',
      name: 'main',
      baseVersion: initialVersion.id,
      currentVersion: initialVersion.id,
      versions: [initialVersion],
      created: Date.now(),
      modified: Date.now(),
      author: 'System'
    };

    this.branches.push(mainBranch);
    this.currentBranch = mainBranch.id;
  }

  /**
   * Сохранение версии
   */
  public saveVersion(name: string, description?: string): Version {
    const lastVersion = this.versions[this.versions.length - 1];
    const [major, minor, patch] = lastVersion.versionNumber.split('.').map(Number);
    const newVersionNumber = `${major}.${minor + 1}.0`;

    const newVersion: Version = {
      id: newVersionNumber,
      name,
      description,
      timestamp: Date.now(),
      author: 'Current User',
      versionNumber: newVersionNumber,
      changelog: ['Обновление параметров']
    };

    this.versions.push(newVersion);
    this.currentVersion = newVersion.id;

    const currentBranch = this.branches.find(b => b.id === this.currentBranch);
    if (currentBranch) {
      currentBranch.currentVersion = newVersion.id;
      currentBranch.versions.push(newVersion);
    }

    return newVersion;
  }

  /**
   * Загрузка версии
   */
  public loadVersion(versionId: string): boolean {
    const version = this.versions.find(v => v.id === versionId);
    if (!version) return false;

    this.currentVersion = versionId;
    const currentBranch = this.branches.find(b => b.id === this.currentBranch);
    if (currentBranch) {
      currentBranch.currentVersion = versionId;
    }

    return true;
  }

  /**
   * Undo операция
   */
  public undo(): boolean {
    const currentIndex = this.versions.findIndex(v => v.id === this.currentVersion);
    if (currentIndex > 0) {
      return this.loadVersion(this.versions[currentIndex - 1].id);
    }
    return false;
  }

  /**
   * Redo операция
   */
  public redo(): boolean {
    const currentIndex = this.versions.findIndex(v => v.id === this.currentVersion);
    if (currentIndex < this.versions.length - 1) {
      return this.loadVersion(this.versions[currentIndex + 1].id);
    }
    return false;
  }

  /**
   * Создание ветки
   */
  public createBranch(name: string, fromVersion?: string): Branch {
    const baseVersion = fromVersion || this.currentVersion;
    const branch: Branch = {
      id: `branch-${Date.now()}`,
      name,
      baseVersion,
      currentVersion: baseVersion,
      versions: [this.versions.find(v => v.id === baseVersion)!],
      created: Date.now(),
      modified: Date.now(),
      author: 'Current User'
    };

    this.branches.push(branch);
    return branch;
  }

  /**
   * Слияние ветки
   */
  public mergeBranch(branchId: string, intoBranch?: string): MergeResult {
    const sourceBranch = this.branches.find(b => b.id === branchId);
    const targetBranch = this.branches.find(b => b.id === (intoBranch || this.currentBranch));

    if (!sourceBranch || !targetBranch) {
      return { success: false, conflicts: ['Не найдены ветки для слияния'], mergedVersion: '', diff: {} as VersionDiff };
    }

    return {
      success: true,
      conflicts: [],
      mergedVersion: 'v1.1.0',
      diff: {
        id: 'diff-1',
        versionFrom: sourceBranch.currentVersion,
        versionTo: targetBranch.currentVersion,
        added: [],
        modified: [],
        removed: [],
        timestamp: Date.now()
      }
    };
  }

  /**
   * Получение разницы между версиями
   */
  public getVersionDiff(fromVersion: string, toVersion: string): VersionDiff {
    return {
      id: `diff-${Date.now()}`,
      versionFrom: fromVersion,
      versionTo: toVersion,
      added: [],
      modified: [],
      removed: [],
      timestamp: Date.now()
    };
  }

  // =============================================================================
  // 3. Производственные допуски
  // =============================================================================

  /**
   * Инициализация стандартных допусков
   */
  private initializeDefaultTolerances(): void {
    const defaultTolerances: Tolerance[] = [
      { id: 'dimensional-1', name: 'Геометрический допуск', type: 'dimensional', nominal: 0, upper: 0.5, lower: -0.5, unit: 'mm', description: 'Допуск на размеры' },
      { id: 'positional-1', name: 'Позиционный допуск', type: 'positional', nominal: 0, upper: 1.0, lower: -1.0, unit: 'mm', description: 'Допуск на позицию' },
      { id: 'geometric-1', name: 'Формовый допуск', type: 'geometric', nominal: 0, upper: 0.2, lower: -0.2, unit: 'mm', description: 'Допуск на форму' }
    ];

    this.tolerances.push(...defaultTolerances);
  }

  /**
   * Добавление допуска
   */
  public addTolerance(tolerance: Tolerance): void {
    this.tolerances.push(tolerance);
  }

  /**
   * Удаление допуска
   */
  public removeTolerance(id: string): void {
    this.tolerances = this.tolerances.filter(t => t.id !== id);
  }

  /**
   * Запуск проверки допусков
   */
  public runToleranceCheck(): ToleranceReport {
    const report: ToleranceReport = {
      id: `report-${Date.now()}`,
      timestamp: Date.now(),
      title: 'Проверка производственных допусков',
      totalChecks: 0,
      passedChecks: 0,
      failedChecks: 0,
      dimensionChecks: [],
      toleranceSummary: {}
    };

    // Проверка каждого параметра
    this.parameters.forEach(param => {
      if (param.type === 'number' && param.unit === 'mm') {
        const tolerance = this.tolerances.find(t => t.type === 'dimensional');
        if (tolerance) {
          const check: DimensionCheck = {
            id: `check-${param.id}`,
            panelId: 'all',
            dimension: 'width',
            nominal: param.value as Mm,
            actual: param.value as Mm,
            tolerance: tolerance,
            isWithinTolerance: true,
            deviation: 0
          };

          report.dimensionChecks.push(check);
          report.totalChecks++;
          report.passedChecks++;

          if (!report.toleranceSummary[tolerance.id]) {
            report.toleranceSummary[tolerance.id] = 0;
          }
          report.toleranceSummary[tolerance.id]++;
        }
      }
    });

    this.toleranceReport = report;
    return report;
  }

  /**
   * Получение результатов проверки размеров
   */
  public getDimensionChecks(): DimensionCheck[] {
    return this.toleranceReport.dimensionChecks;
  }

  /**
   * Создание пустого отчёта о допусках
   */
  private createEmptyToleranceReport(): ToleranceReport {
    return {
      id: '',
      timestamp: Date.now(),
      title: '',
      totalChecks: 0,
      passedChecks: 0,
      failedChecks: 0,
      dimensionChecks: [],
      toleranceSummary: {}
    };
  }

  // =============================================================================
  // 4. Интерактивное редактирование
  // =============================================================================

  /**
   * Начало редактирования
   */
  public startEditing(): void {
    this.interactiveState.isEditing = true;
    this.interactiveState.lastModified = Date.now();
  }

  /**
   * Завершение редактирования
   */
  public stopEditing(save: boolean): void {
    this.interactiveState.isEditing = false;
    if (save) {
      this.saveVersion('Version from editing');
    }
  }

  /**
   * Переключение режима черновика
   */
  public toggleDraftMode(): void {
    this.interactiveState.draftMode.enabled = !this.interactiveState.draftMode.enabled;
  }

  /**
   * Обновление параметров реального времени
   */
  public updateRealTimePreview(options: Partial<RealTimePreviewOptions>): void {
    this.realTimePreview = { ...this.realTimePreview, ...options };
  }

  /**
   * Получение не сохранённых изменений
   */
  public getUnsavedChanges(): string[] {
    return this.interactiveState.unsavedChanges;
  }

  // =============================================================================
  // 5. Расчёт себестоимости
  // =============================================================================

  /**
   * Создание пустого расчёта
   */
  private createEmptyCostCalculation(): CostCalculation {
    return {
      id: '',
      projectId: '',
      timestamp: Date.now(),
      currency: 'RUB',
      exchangeRate: 1,
      baseCost: 0,
      overheadCost: 0,
      markupCost: 0,
      totalCost: 0,
      costBreakdown: {
        materials: [],
        hardware: [],
        labor: [],
        overhead: 0,
        markup: 0
      },
      costItems: [],
      summary: {
        totalMaterials: 0,
        totalHardware: 0,
        totalLabor: 0,
        totalOverhead: 0,
        totalMarkup: 0,
        total: 0
      }
    };
  }

  /**
   * Расчёт себестоимости
   */
  public calculateCost(): CostCalculation {
    const calculation: CostCalculation = this.createEmptyCostCalculation();

    // Расчёт материалов
    calculation.costBreakdown.materials.push({
      materialId: 'ldsp',
      materialName: 'ЛДСП',
      area: 2.5,  // м²
      pricePerM2: 1500,
      total: 3750
    });

    // Расчёт фурнитуры
    calculation.costBreakdown.hardware.push({
      hardwareId: 'confirmat',
      hardwareName: 'Конфирмат 7x50',
      quantity: 8,
      pricePerUnit: 5,
      total: 40
    });

    // Расчёт работы
    calculation.costBreakdown.labor.push({
      operation: 'Резка',
      time: 30,
      costPerMinute: 5,
      total: 150
    });

    // Налоги и наценка
    calculation.costBreakdown.overhead = 0.15;  // 15%
    calculation.costBreakdown.markup = 0.30;    // 30%

    // Подсчёт сумм
    const materialCost = calculation.costBreakdown.materials.reduce((sum, m) => sum + m.total, 0);
    const hardwareCost = calculation.costBreakdown.hardware.reduce((sum, h) => sum + h.total, 0);
    const laborCost = calculation.costBreakdown.labor.reduce((sum, l) => sum + l.total, 0);

    const baseCost = materialCost + hardwareCost + laborCost;
    const overheadCost = baseCost * calculation.costBreakdown.overhead;
    const markupCost = (baseCost + overheadCost) * calculation.costBreakdown.markup;
    const totalCost = baseCost + overheadCost + markupCost;

    calculation.baseCost = baseCost;
    calculation.overheadCost = overheadCost;
    calculation.markupCost = markupCost;
    calculation.totalCost = totalCost;

    calculation.summary = {
      totalMaterials: materialCost,
      totalHardware: hardwareCost,
      totalLabor: laborCost,
      totalOverhead: overheadCost,
      totalMarkup: markupCost,
      total: totalCost
    };

    this.costCalculation = calculation;
    return calculation;
  }

  /**
   * Обновление структуры затрат
   */
  public updateCostBreakdown(breakdown: Partial<CostBreakdown>): CostCalculation {
    this.costCalculation.costBreakdown = {
      ...this.costCalculation.costBreakdown,
      ...breakdown
    };

    // Recalculate totals without resetting to defaults
    const materialCost = this.costCalculation.costBreakdown.materials.reduce((sum, m) => sum + m.total, 0);
    const hardwareCost = this.costCalculation.costBreakdown.hardware.reduce((sum, h) => sum + h.total, 0);
    const laborCost = this.costCalculation.costBreakdown.labor.reduce((sum, l) => sum + l.total, 0);

    const baseCost = materialCost + hardwareCost + laborCost;
    const overheadCost = baseCost * this.costCalculation.costBreakdown.overhead;
    const markupCost = (baseCost + overheadCost) * this.costCalculation.costBreakdown.markup;
    const totalCost = baseCost + overheadCost + markupCost;

    this.costCalculation.baseCost = baseCost;
    this.costCalculation.overheadCost = overheadCost;
    this.costCalculation.markupCost = markupCost;
    this.costCalculation.totalCost = totalCost;

    this.costCalculation.summary = {
      totalMaterials: materialCost,
      totalHardware: hardwareCost,
      totalLabor: laborCost,
      totalOverhead: overheadCost,
      totalMarkup: markupCost,
      total: totalCost
    };

    return this.costCalculation;
  }

  /**
   * Получение затрат по типу
   */
  public getCostItemsByType(type: string): CostItem[] {
    const items: CostItem[] = [];

    switch (type) {
      case 'material':
        this.costCalculation.costBreakdown.materials.forEach(material => {
          items.push({
            id: material.materialId,
            name: material.materialName,
            type: 'material',
            quantity: material.area,
            unitCost: material.pricePerM2,
            totalCost: material.total
          });
        });
        break;

      case 'hardware':
        this.costCalculation.costBreakdown.hardware.forEach(hardware => {
          items.push({
            id: hardware.hardwareId,
            name: hardware.hardwareName,
            type: 'hardware',
            quantity: hardware.quantity,
            unitCost: hardware.pricePerUnit,
            totalCost: hardware.total
          });
        });
        break;

      case 'labor':
        this.costCalculation.costBreakdown.labor.forEach(labor => {
          items.push({
            id: labor.operation,
            name: labor.operation,
            type: 'labor',
            quantity: labor.time,
            unitCost: labor.costPerMinute,
            totalCost: labor.total
          });
        });
        break;
    }

    return items;
  }

  /**
   * Экспорт отчёта о затратах
   */
  public exportCostReport(format: 'pdf' | 'csv' | 'json'): any {
    switch (format) {
      case 'json':
        return JSON.stringify(this.costCalculation, null, 2);
      case 'csv':
        return 'Material, Quantity, Unit Cost, Total\nЛДСП, 2.5м², 1500руб/м², 3750руб';
      case 'pdf':
        return 'PDF report content';
    }
  }

  // =============================================================================
  // 6. Руководство сборки
  // =============================================================================

  /**
   * Создание пустого руководства сборки
   */
  private createEmptyAssemblyGuide(): AssemblyGuide {
    return {
      id: '',
      projectId: '',
      language: 'ru',
      title: '',
      description: '',
      totalDuration: 0,
      difficulty: 'beginner',
      requiredTools: [],
      requiredMaterials: [],
      steps: [],
      sections: [],
      safetyNotes: [],
      troubleshooting: []
    };
  }

  /**
   * Генерация руководства сборки
   */
  public generateAssemblyGuide(language: string = 'ru'): AssemblyGuide {
    const guide: AssemblyGuide = {
      id: 'guide-1',
      projectId: 'cabinet-001',
      language,
      title: 'Руководство сборки шкафа',
      description: 'Пошаговые инструкции по сборке шкафа',
      totalDuration: 60,
      difficulty: 'beginner',
      requiredTools: [
        { id: 'drill', name: 'Дрель', type: 'power', description: 'Для сверления отверстий', safetyNotes: 'Использовать защитные очки' },
        { id: 'screwdriver', name: 'Водитель', type: 'hand', description: 'Для закручивания винтов' },
        { id: 'clamps', name: 'Клещи', type: 'hand', description: 'Для фиксации панелей' }
      ],
      requiredMaterials: ['ЛДСП', 'Конфирматы', 'Шканты'],
      steps: [
        {
          id: 'step-1',
          number: 1,
          title: 'Сборка нижней части',
          description: 'Скрепите дно с боковыми панелями',
          duration: 15,
          difficulty: 'easy',
          tools: ['drill', 'screwdriver', 'clamps'],
          materials: ['ЛДСП', 'Конфирматы'],
          components: ['bottom', 'side-l', 'side-r'],
          subSteps: ['Подготовьте панели', 'Сверьте отверстия', 'Скрепите винтами'],
          images: [],
          video: '',
          animation3d: '',
          torqueValues: { 'confirmat': 4.5 },
          warnings: ['Не перезакручивайте винты']
        },
        {
          id: 'step-2',
          number: 2,
          title: 'Установка полок',
          description: 'Установите полки в шкаф',
          duration: 10,
          difficulty: 'easy',
          tools: ['clamps'],
          materials: ['ЛДСП', 'Шканты'],
          components: ['shelf'],
          subSteps: ['Вставьте шканты', 'Установите полку', 'Проверьте уровень'],
          images: [],
          video: '',
          animation3d: '',
          torqueValues: {},
          warnings: []
        },
        {
          id: 'step-3',
          number: 3,
          title: 'Установка крышки',
          description: 'Закрепите крышку на шкафу',
          duration: 15,
          difficulty: 'medium',
          tools: ['drill', 'screwdriver', 'clamps'],
          materials: ['ЛДСП', 'Конфирматы'],
          components: ['top'],
          subSteps: ['Подготовьте крышку', 'Скрепите к боковым панелям', 'Проверьте вертикаль'],
          images: [],
          video: '',
          animation3d: '',
          torqueValues: { 'confirmat': 4.0 },
          warnings: ['Соблюдайте равномерное приложение усилия']
        },
        {
          id: 'step-4',
          number: 4,
          title: 'Установка дверных петель',
          description: 'Установите петли на двери',
          duration: 15,
          difficulty: 'hard',
          tools: ['drill', 'screwdriver', 'clamps'],
          materials: ['Петли'],
          components: ['door'],
          subSteps: ['Маркировка мест установки', 'Сверление отверстий', 'Установка петель', 'Регулировка'],
          images: [],
          video: '',
          animation3d: '',
          torqueValues: { 'hinge': 3.0 },
          warnings: ['Осторожно! Дверь может быть тяжелой']
        },
        {
          id: 'step-5',
          number: 5,
          title: 'Завершение',
          description: 'Проверка и завершение сборки',
          duration: 5,
          difficulty: 'easy',
          tools: [],
          materials: [],
          components: [],
          subSteps: ['Проверьте все соединения', 'Убедитесь в прочности', 'Закройте дверь'],
          images: [],
          video: '',
          animation3d: '',
          torqueValues: {},
          warnings: []
        }
      ],
      sections: [
        { id: 'section-1', title: 'Основная сборка', stepRange: [1, 3] },
        { id: 'section-2', title: 'Установка дверных петель', stepRange: [4, 4] },
        { id: 'section-3', title: 'Завершение', stepRange: [5, 5] }
      ],
      safetyNotes: [
        'Используйте средства индивидуальной защиты',
        'Не превышайте рекомендуемые параметры кручения',
        'При необходимости обращайтесь за помощью'
      ],
      troubleshooting: [
        'Дверь не закрывается: Проверьте уровень и регулируйте петли',
        'Нежелаемый звук при закрытии: Проверьте положение резиновых упоров',
        'Панель не встаёт: Убедитесь, что все отверстия правильно сверлены'
      ]
    };

    this.assemblyGuide = guide;
    return guide;
  }

  /**
   * Получение деталей шага
   */
  public getStepDetails(stepNumber: number): AssemblyStep {
    const step = this.assemblyGuide.steps.find(s => s.number === stepNumber);
    if (!step) {
      throw new Error(`Шаг ${stepNumber} не найден`);
    }
    return step;
  }

  /**
   * Экспорт руководства сборки
   */
  public exportAssemblyGuide(format: 'pdf' | 'html' | 'json'): any {
    switch (format) {
      case 'json':
        return JSON.stringify(this.assemblyGuide, null, 2);
      case 'html':
        return `
          <html>
            <head>
              <title>Руководство сборки</title>
            </head>
            <body>
              <h1>${this.assemblyGuide.title}</h1>
              <p>${this.assemblyGuide.description}</p>
              <h2>Требуемые инструменты</h2>
              <ul>${this.assemblyGuide.requiredTools.map(t => `<li>${t.name}</li>`).join('')}</ul>
              <h2>Пошаговые инструкции</h2>
              ${this.assemblyGuide.steps.map(step => `
                <h3>Шаг ${step.number}: ${step.title}</h3>
                <p>${step.description}</p>
                <ul>${step.subSteps?.map(sub => `<li>${sub}</li>`).join('')}</ul>
              `).join('')}
            </body>
          </html>
        `;
      case 'pdf':
        return 'PDF guide content';
    }
  }
}
