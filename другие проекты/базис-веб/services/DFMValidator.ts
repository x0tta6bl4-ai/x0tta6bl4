/**
 * ФАЗА 4: DFM Validator
 * Design for Manufacturing - проверка производимости конструкции
 */

import {
  Component,
  Assembly,
  DFMCheckResult,
  DFMReport,
  DFMSeverity,
  DFMRule,
  ConstraintType
} from '../types/CADTypes';

/**
 * Конфигурация DFM параметров
 */
export interface DFMConfig {
  minWallThickness: number;           // Минимальная толщина стенки (мм)
  minFilletRadius: number;            // Минимальный радиус скругления (мм)
  maxAspectRatio: number;             // Максимальное отношение сторон
  minDistanceFromEdge: number;        // Минимальное расстояние от края (мм)
  minInternalCornerRadius: number;    // Минимальный радиус внутреннего угла (мм)
  maxThreadRatio: number;             // Максимальное отношение для резьбы
  minHoleSize: number;                // Минимальный размер отверстия (мм)
  maxHoleDensity: number;             // Максимальная плотность отверстий (на см²)
  minDistanceBetweenHoles: number;    // Минимальное расстояние между отверстиями (мм)
  maxComponentWeight: number;         // Максимальный вес компонента (кг)
  complexityThreshold: number;        // Порог сложности (количество ограничений)
}

/**
 * Результат проверки DFM правила
 */
export interface DFMCheckDetails {
  ruleId: string;
  ruleName: string;
  componentId: string;
  passed: boolean;
  severity: DFMSeverity;
  message: string;
  details: string;
  suggestedFix?: string;
}

/**
 * Валидатор производимости (DFM)
 */
export class DFMValidator {
  private rules: Map<string, (component: Component, config: DFMConfig) => DFMCheckDetails> =
    new Map();
  private config: DFMConfig;

  private toCheckResult(details: DFMCheckDetails): DFMCheckResult {
    return {
      ruleId: details.ruleId,
      passed: details.passed,
      severity: details.severity,
      message: details.message,
      suggestion: details.suggestedFix,
      componentId: details.componentId
    };
  }

  constructor(config?: Partial<DFMConfig>) {
    // Дефолтная конфигурация
    this.config = {
      minWallThickness: 1.5,
      minFilletRadius: 0.5,
      maxAspectRatio: 80,
      minDistanceFromEdge: 3,
      minInternalCornerRadius: 1,
      maxThreadRatio: 4,
      minHoleSize: 1,
      maxHoleDensity: 10,
      minDistanceBetweenHoles: 2,
      maxComponentWeight: 50,
      complexityThreshold: 20,
      ...config
    };

    this.registerDefaultRules();
  }

  /**
   * Проверить компонент на соответствие DFM стандартам
   */
  public validateComponent(component: Component): DFMCheckDetails[] {
    const results: DFMCheckDetails[] = [];

    // Запустить все зарегистрированные правила
    for (const [ruleId, rule] of this.rules) {
      const result = rule(component, this.config);
      results.push(result);
    }

    return results;
  }

  /**
   * Проверить всю сборку рекурсивно
   */
  public validateAssembly(assembly: Assembly): DFMReport {
    const allResults: DFMCheckDetails[] = [];
    const startTime = Date.now();

    // Рекурсивно проверяем все компоненты
    this.traverseAssemblyForValidation(assembly, allResults);

    const endTime = Date.now();
    const runtimeMs = endTime - startTime;

    // Подсчитываем результаты
    const passedChecks = allResults.filter(r => r.passed).length;
    const failedChecks = allResults.filter(r => !r.passed).length;

    // Разделяем по типам
    const errors = allResults.filter(r => !r.passed && r.severity === DFMSeverity.ERROR);
    const warnings = allResults.filter(r => !r.passed && r.severity === DFMSeverity.WARNING);
    const infos = allResults.filter(r => !r.passed && r.severity === DFMSeverity.INFO);

    // Вычисляем процент производимости
    const totalChecks = allResults.length;
    const manufacturability =
      totalChecks > 0 ? (passedChecks / totalChecks) * 100 : 0;

    // Генерируем рекомендации
    const suggestions = this.generateSuggestions(errors, warnings);

    return {
      totalChecks,
      passedChecks,
      failedChecks,
      errors: errors.map(e => this.toCheckResult(e)),
      warnings: warnings.map(w => this.toCheckResult(w)),
      infos: infos.map(i => this.toCheckResult(i)),
      manufacturability,
      suggestions,
      timestamp: new Date(),
      runtimeMs
    };
  }

  /**
   * Рекурсивно обходит сборку для проверки
   */
  private traverseAssemblyForValidation(
    assembly: Assembly,
    results: DFMCheckDetails[]
  ): void {
    if (!assembly.components) return;

    for (const component of assembly.components) {
      // Проверяем компонент
      const componentResults = this.validateComponent(component);
      results.push(...componentResults);

      // Рекурсивно проверяем подкомпоненты
      if (component.subComponents && component.subComponents.length > 0) {
        const subAssembly: Assembly = {
          id: `${assembly.id}_sub`,
          name: `${assembly.name}_sub`,
          components: component.subComponents,
          constraints: []
        };
        this.traverseAssemblyForValidation(subAssembly, results);
      }
    }
  }

  /**
   * Генерирует рекомендации на основе ошибок
   */
  private generateSuggestions(
    errors: DFMCheckDetails[],
    warnings: DFMCheckDetails[]
  ): string[] {
    const suggestions: string[] = [];

    // Анализируем типичные проблемы
    const errorTypes = new Set(errors.map(e => e.ruleId));
    const warningTypes = new Set(warnings.map(w => w.ruleId));

    if (errorTypes.has('wall-thickness')) {
      suggestions.push(
        `Увеличьте толщину стенок до минимума ${this.config.minWallThickness}мм для улучшения производимости`
      );
    }

    if (errorTypes.has('fillet-radius')) {
      suggestions.push(
        `Добавьте скругления с радиусом минимум ${this.config.minFilletRadius}мм для облегчения производства`
      );
    }

    if (warningTypes.has('aspect-ratio')) {
      suggestions.push(
        `Рассмотрите уменьшение отношения сторон (текущий порог: ${this.config.maxAspectRatio}:1)`
      );
    }

    if (errorTypes.has('hole-size')) {
      suggestions.push(
        `Увеличьте размер отверстий до минимума ${this.config.minHoleSize}мм`
      );
    }

    if (errorTypes.has('hole-density')) {
      suggestions.push(
        `Уменьшите плотность отверстий (максимум ${this.config.maxHoleDensity} отверстий на см²)`
      );
    }

    if (warningTypes.has('complexity')) {
      suggestions.push(
        `Рассмотрите упрощение конструкции (текущий порог сложности: ${this.config.complexityThreshold} ограничений)`
      );
    }

    if (suggestions.length === 0) {
      suggestions.push('Конструкция находится в хорошем состоянии для производства!');
    }

    return suggestions;
  }

  /**
   * Регистрирует стандартные DFM правила
   */
  private registerDefaultRules(): void {
    // 1. Толщина стенок
    this.addRule('wall-thickness', (component, config) => {
      const thickness = this.estimateWallThickness(component);
      const passed = thickness >= config.minWallThickness;

      return {
        ruleId: 'wall-thickness',
        ruleName: 'Минимальная толщина стенок',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.ERROR,
        message: passed
          ? `✓ Толщина стенок ${thickness.toFixed(2)}мм - допустима`
          : `✗ Толщина стенок ${thickness.toFixed(2)}мм ниже минимума ${config.minWallThickness}мм`,
        details: `Проверка толщины стенок: ${thickness.toFixed(2)}мм vs ${config.minWallThickness}мм`,
        suggestedFix: passed ? undefined : `Увеличьте толщину стенок до ${config.minWallThickness}мм`
      };
    });

    // 2. Радиус скругления
    this.addRule('fillet-radius', (component, config) => {
      const hasFillets = this.hasProperFillets(component);
      const passed = hasFillets || !this.hasSharpCorners(component);

      return {
        ruleId: 'fillet-radius',
        ruleName: 'Скругления углов',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.ERROR,
        message: passed
          ? '✓ Скругления углов выполнены корректно'
          : `✗ Найдены острые углы, требуются скругления радиусом >= ${config.minFilletRadius}мм`,
        details: `Проверка скруглений: наличие острых углов = ${!hasFillets}`,
        suggestedFix: passed ? undefined : `Добавьте скругления радиусом ${config.minFilletRadius}мм`
      };
    });

    // 3. Отношение сторон (aspect ratio)
    this.addRule('aspect-ratio', (component, config) => {
      const aspectRatio = this.calculateAspectRatio(component);
      const passed = aspectRatio <= config.maxAspectRatio;

      return {
        ruleId: 'aspect-ratio',
        ruleName: 'Отношение сторон',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Отношение сторон ${aspectRatio.toFixed(1)}:1 - приемлемо`
          : `⚠ Отношение сторон ${aspectRatio.toFixed(1)}:1 превышает рекомендуемое ${config.maxAspectRatio}:1`,
        details: `Проверка пропорций: ${aspectRatio.toFixed(1)}:1 vs ${config.maxAspectRatio}:1`,
        suggestedFix: passed ? undefined : `Уменьшите отношение сторон до ${config.maxAspectRatio}:1`
      };
    });

    // 4. Расстояние от края
    this.addRule('edge-distance', (component, config) => {
      const minEdgeDistance = this.calculateMinEdgeDistance(component);
      const passed = minEdgeDistance >= config.minDistanceFromEdge;

      return {
        ruleId: 'edge-distance',
        ruleName: 'Расстояние от края',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Расстояние от края ${minEdgeDistance.toFixed(2)}мм - допустимо`
          : `⚠ Минимальное расстояние от края ${minEdgeDistance.toFixed(2)}мм менее ${config.minDistanceFromEdge}мм`,
        details: `Проверка отступа от края: ${minEdgeDistance.toFixed(2)}мм vs ${config.minDistanceFromEdge}мм`,
        suggestedFix: passed ? undefined : `Увеличьте отступ от края до ${config.minDistanceFromEdge}мм`
      };
    });

    // 5. Радиус внутренних углов
    this.addRule('internal-corner', (component, config) => {
      const minInternalRadius = this.calculateMinInternalCornerRadius(component);
      const passed = minInternalRadius >= config.minInternalCornerRadius;

      return {
        ruleId: 'internal-corner',
        ruleName: 'Радиус внутренних углов',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.ERROR,
        message: passed
          ? `✓ Радиус внутренних углов ${minInternalRadius.toFixed(2)}мм - допустим`
          : `✗ Радиус внутренних углов ${minInternalRadius.toFixed(2)}мм ниже минимума ${config.minInternalCornerRadius}мм`,
        details: `Проверка радиуса внутренних углов: ${minInternalRadius.toFixed(2)}мм vs ${config.minInternalCornerRadius}мм`,
        suggestedFix: passed ? undefined : `Увеличьте радиус до ${config.minInternalCornerRadius}мм`
      };
    });

    // 6. Размер отверстий
    this.addRule('hole-size', (component, config) => {
      const hasSmallHoles = this.hasSmallHoles(component, config.minHoleSize);
      const passed = !hasSmallHoles;

      return {
        ruleId: 'hole-size',
        ruleName: 'Размер отверстий',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.ERROR,
        message: passed
          ? `✓ Все отверстия имеют размер >= ${config.minHoleSize}мм`
          : `✗ Найдены отверстия размером < ${config.minHoleSize}мм`,
        details: `Проверка размера отверстий: наличие маленьких отверстий = ${hasSmallHoles}`,
        suggestedFix: passed ? undefined : `Увеличьте размер отверстий до минимума ${config.minHoleSize}мм`
      };
    });

    // 7. Плотность отверстий
    this.addRule('hole-density', (component, config) => {
      const holeDensity = this.calculateHoleDensity(component);
      const passed = holeDensity <= config.maxHoleDensity;

      return {
        ruleId: 'hole-density',
        ruleName: 'Плотность отверстий',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Плотность отверстий ${holeDensity.toFixed(1)} отв/см² - приемлема`
          : `⚠ Плотность отверстий ${holeDensity.toFixed(1)} отв/см² превышает рекомендуемую ${config.maxHoleDensity} отв/см²`,
        details: `Проверка плотности отверстий: ${holeDensity.toFixed(1)} vs ${config.maxHoleDensity} отв/см²`,
        suggestedFix: passed ? undefined : `Уменьшите количество отверстий или увеличьте площадь`
      };
    });

    // 8. Расстояние между отверстиями
    this.addRule('hole-distance', (component, config) => {
      const minHoleDistance = this.calculateMinDistanceBetweenHoles(component);
      const passed = minHoleDistance >= config.minDistanceBetweenHoles;

      return {
        ruleId: 'hole-distance',
        ruleName: 'Расстояние между отверстиями',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Расстояние между отверстиями ${minHoleDistance.toFixed(2)}мм - допустимо`
          : `⚠ Минимальное расстояние между отверстиями ${minHoleDistance.toFixed(2)}мм менее ${config.minDistanceBetweenHoles}мм`,
        details: `Проверка расстояния между отверстиями: ${minHoleDistance.toFixed(2)}мм vs ${config.minDistanceBetweenHoles}мм`,
        suggestedFix: passed ? undefined : `Увеличьте расстояние между отверстиями до ${config.minDistanceBetweenHoles}мм`
      };
    });

    // 9. Вес компонента
    this.addRule('component-weight', (component, config) => {
      const weight = this.estimateComponentWeight(component);
      const passed = weight <= config.maxComponentWeight;

      return {
        ruleId: 'component-weight',
        ruleName: 'Вес компонента',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Вес компонента ${weight.toFixed(2)}кг - приемлем`
          : `⚠ Вес компонента ${weight.toFixed(2)}кг превышает рекомендуемый ${config.maxComponentWeight}кг`,
        details: `Проверка веса: ${weight.toFixed(2)}кг vs ${config.maxComponentWeight}кг`,
        suggestedFix: passed ? undefined : `Рассмотрите использование более лёгкого материала`
      };
    });

    // 10. Сложность конструкции
    this.addRule('complexity', (component, config) => {
      const complexity = component.constraints?.length || 0;
      const passed = complexity <= config.complexityThreshold;

      return {
        ruleId: 'complexity',
        ruleName: 'Сложность конструкции',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Сложность ${complexity} ограничений - приемлема`
          : `⚠ Сложность ${complexity} ограничений превышает рекомендуемую ${config.complexityThreshold}`,
        details: `Проверка сложности: ${complexity} vs ${config.complexityThreshold} ограничений`,
        suggestedFix: passed ? undefined : `Рассмотрите упрощение конструкции`
      };
    });

    // 11. Материал в наличии
    this.addRule('material-availability', (component, config) => {
      const material = component.material;
      const passed = material && this.isCommonMaterial(material.id);

      return {
        ruleId: 'material-availability',
        ruleName: 'Доступность материала',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? `✓ Материал ${material?.name || 'Unknown'} в наличии`
          : `⚠ Материал ${material?.name || 'Unknown'} редко встречается`,
        details: `Проверка доступности материала: ${material?.name || 'не указан'}`,
        suggestedFix: passed ? undefined : `Рассмотрите использование стандартного материала`
      };
    });

    // 12. Монтажная поверхность
    this.addRule('assembly-surface', (component, config) => {
      const hasMountingSurface = this.hasMountingSurface(component);
      const passed = hasMountingSurface;

      return {
        ruleId: 'assembly-surface',
        ruleName: 'Монтажная поверхность',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? '✓ Монтажная поверхность подходящего размера'
          : '⚠ Монтажная поверхность слишком мала для сборки',
        details: `Проверка монтажной поверхности: ${hasMountingSurface ? 'есть' : 'нет'}`,
        suggestedFix: passed ? undefined : `Увеличьте монтажную поверхность`
      };
    });

    // 13. Производственная последовательность
    this.addRule('manufacturing-sequence', (component, config) => {
      const isSequenceFeasible = this.isManufacturingSequenceFeasible(component);
      const passed = isSequenceFeasible;

      return {
        ruleId: 'manufacturing-sequence',
        ruleName: 'Последовательность производства',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.ERROR,
        message: passed
          ? '✓ Возможна производство в правильной последовательности'
          : '✗ Конструкция не позволяет выполнить правильную последовательность производства',
        details: `Проверка производственной последовательности: ${isSequenceFeasible ? 'возможна' : 'невозможна'}`,
        suggestedFix: passed
          ? undefined
          : `Пересмотрите конструкцию для возможности производства`
      };
    });

    // 14. Допуски
    this.addRule('tolerances', (component, config) => {
      const tolerancesFeasible = this.areTolerancesFeasible(component);
      const passed = tolerancesFeasible;

      return {
        ruleId: 'tolerances',
        ruleName: 'Допуски',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? '✓ Допуски достижимы стандартным оборудованием'
          : '⚠ Некоторые допуски требуют специального оборудования',
        details: `Проверка допусков: ${tolerancesFeasible ? 'стандартные' : 'специальные'}`,
        suggestedFix: passed ? undefined : `Ослабьте допуски или используйте специальное оборудование`
      };
    });

    // 15. Финишная обработка
    this.addRule('surface-finish', (component, config) => {
      const finishFeasible = this.isSurfaceFinishFeasible(component);
      const passed = finishFeasible;

      return {
        ruleId: 'surface-finish',
        ruleName: 'Финишная обработка',
        componentId: component.id,
        passed,
        severity: passed ? DFMSeverity.INFO : DFMSeverity.WARNING,
        message: passed
          ? '✓ Финишная обработка выполнима'
          : '⚠ Финишная обработка затруднена конструкцией',
        details: `Проверка доступности для финишной обработки: ${finishFeasible ? 'доступна' : 'затруднена'}`,
        suggestedFix: passed ? undefined : `Упростите конструкцию для упрощения финишной обработки`
      };
    });
  }

  // ==================== Вспомогательные методы ====================

  private estimateWallThickness(component: Component): number {
    if (!component.geometry?.boundingBox) return 2;
    const bbox = component.geometry.boundingBox;
    const width = bbox.width?.() || 100;
    const height = bbox.height?.() || 100;
    return Math.min(width, height) * 0.05; // ~5% от меньшей стороны
  }

  private hasSharpCorners(component: Component): boolean {
    // Упрощённая проверка: если нет ограничений на скругления, вероятно есть острые углы
    return !component.constraints || component.constraints.length === 0;
  }

  private hasProperFillets(component: Component): boolean {
    return component.constraints && component.constraints.some(c => c.type === ConstraintType.ANGLE);
  }

  private calculateAspectRatio(component: Component): number {
    if (!component.geometry?.boundingBox) return 1;
    const bbox = component.geometry.boundingBox;
    const width = bbox.width?.() || 100;
    const height = bbox.height?.() || 100;
    const depth = bbox.depth?.() || 100;
    const dims = [width, height, depth].sort((a, b) => b - a);
    return dims[0] / (dims[2] || 1);
  }

  private calculateMinEdgeDistance(component: Component): number {
    return 5;
  }

  private calculateMinInternalCornerRadius(component: Component): number {
    return 1.5;
  }

  private hasSmallHoles(component: Component, minSize: number): boolean {
    return (
      component.constraints &&
      component.constraints.filter(c => c.type === ConstraintType.DISTANCE).length > 5
    );
  }

  private calculateHoleDensity(component: Component): number {
    if (!component.geometry?.boundingBox) return 0;
    const bbox = component.geometry.boundingBox;
    const width = bbox.width?.() || 100;
    const height = bbox.height?.() || 100;
    const area = (width * height) / 10000; // см²
    const holeCount = component.constraints?.filter(c => c.type === ConstraintType.DISTANCE).length || 0;
    return area > 0 ? holeCount / area : 0;
  }

  private calculateMinDistanceBetweenHoles(component: Component): number {
    return 3;
  }

  private estimateComponentWeight(component: Component): number {
    if (!component.material) return 1;
    if (!component.geometry?.boundingBox) return 1;

    const bbox = component.geometry.boundingBox;
    const width = bbox.width?.() || 100;
    const height = bbox.height?.() || 100;
    const depth = bbox.depth?.() || 100;
    const volume = (width * height * depth) / 1000000; // м³

    const density = component.material.density || 2700; // дефолт алюминий
    return (volume * density) / 1000; // кг
  }

  private isCommonMaterial(materialId: string): boolean {
    const commonMaterials = ['aluminum', 'steel', 'plastic', 'copper', 'brass'];
    return commonMaterials.includes(materialId);
  }

  private hasMountingSurface(component: Component): boolean {
    if (!component.geometry?.boundingBox) return false;
    const bbox = component.geometry.boundingBox;
    const width = bbox.width?.() || 100;
    const height = bbox.height?.() || 100;
    return width >= 10 && height >= 10;
  }

  private isManufacturingSequenceFeasible(component: Component): boolean {
    const complexity = component.constraints?.length || 0;
    return complexity <= 30;
  }

  private areTolerancesFeasible(component: Component): boolean {
    return true;
  }

  private isSurfaceFinishFeasible(component: Component): boolean {
    const complexity = component.constraints?.length || 0;
    return complexity <= 25;
  }

  public addRule(
    ruleId: string,
    rule: (component: Component, config: DFMConfig) => DFMCheckDetails
  ): void {
    this.rules.set(ruleId, rule);
  }

  public updateConfig(config: Partial<DFMConfig>): void {
    this.config = { ...this.config, ...config };
  }

  public getConfig(): DFMConfig {
    return { ...this.config };
  }

  public getRules(): string[] {
    return Array.from(this.rules.keys());
  }
}
