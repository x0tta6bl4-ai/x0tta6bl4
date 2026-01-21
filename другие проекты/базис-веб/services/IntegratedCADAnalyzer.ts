/**
 * DFM Integration Example
 * Комбинированный workflow: BOM + DFM Validation
 */

import { Assembly, Component, Material } from '../types/CADTypes';
import { BillOfMaterials } from './BillOfMaterials';
import { DFMValidator, DFMConfig } from './DFMValidator';
import { ComponentType, ConstraintType, TextureType } from '../types/CADTypes';

/**
 * Интегрированный результат анализа: BOM + DFM
 */
export interface IntegratedAnalysisReport {
  assemblyName: string;
  bom: {
    totalComponents: number;
    totalMaterials: string[];
    totalCost: number;
    estimatedProductionTime: number;
  };
  dfm: {
    manufacturability: number;
    totalChecks: number;
    passedChecks: number;
    failedChecks: number;
    errors: string[];
    warnings: string[];
  };
  recommendations: string[];
  qualityScore: number; // 0-100
  readiness: 'ready' | 'review-needed' | 'redesign-required';
  timestamp: Date;
  runtimeMs: number;
}

/**
 * Интегрированный анализатор: BOM + DFM
 */
export class IntegratedCADAnalyzer {
  private bom: BillOfMaterials;
  private dfm: DFMValidator;

  constructor(dfmConfig?: Partial<DFMConfig>) {
    this.bom = new BillOfMaterials();
    this.dfm = new DFMValidator(dfmConfig);
  }

  /**
   * Выполнить комбинированный анализ: BOM + DFM
   */
  public analyzeAssembly(assembly: Assembly): IntegratedAnalysisReport {
    const startTime = Date.now();

    // 1. BOM анализ
    const bomResult = this.bom.generateBOM(assembly);
    const bomStats = this.bom.calculateBOMStats(bomResult);

    // 2. DFM проверка
    const dfmResult = this.dfm.validateAssembly(assembly);

    // 3. Объединённые рекомендации
    const recommendations = this.combineRecommendations(
      dfmResult.suggestions,
      bomStats
    );

    // 4. Общий качественный рейтинг (0-100)
    // Считаем: 60% от DFM + 40% от BOM оптимизации
    const dfmScore = dfmResult.manufacturability;
    const bomOptimizationScore = this.calculateBOMOptimizationScore(bomStats);
    const qualityScore = dfmScore * 0.6 + bomOptimizationScore * 0.4;

    // 5. Определяем уровень готовности
    let readiness: 'ready' | 'review-needed' | 'redesign-required';
    if (qualityScore >= 85 && dfmResult.failedChecks === 0) {
      readiness = 'ready';
    } else if (qualityScore >= 60) {
      readiness = 'review-needed';
    } else {
      readiness = 'redesign-required';
    }

    const runtimeMs = Date.now() - startTime;

    return {
      assemblyName: assembly.name,
      bom: {
        totalComponents: bomStats.totalItems || 0,
        totalMaterials: this.extractMaterialNames(bomResult),
        totalCost: bomStats.totalCost,
        estimatedProductionTime: bomStats.totalProductionTime || 0
      },
      dfm: {
        manufacturability: dfmResult.manufacturability,
        totalChecks: dfmResult.totalChecks,
        passedChecks: dfmResult.passedChecks,
        failedChecks: dfmResult.failedChecks,
        errors: (dfmResult.errors || []).map(e => e.message),
        warnings: (dfmResult.warnings || []).map(w => w.message)
      },
      recommendations,
      qualityScore: Math.round(qualityScore),
      readiness,
      timestamp: new Date(),
      runtimeMs
    };
  }

  /**
   * Объединить рекомендации из DFM и BOM
   */
  private combineRecommendations(
    dfmSuggestions: string[],
    bomStats: any
  ): string[] {
    const recommendations: string[] = [];

    // DFM рекомендации
    recommendations.push(...dfmSuggestions);

    // BOM-based рекомендации
    if (bomStats.totalCost > 1000) {
      recommendations.push('Рассмотрите использование более дешёвых материалов');
    }

    if (bomStats.estimatedProductionTime > 480) {
      recommendations.push('Оптимизируйте производственные процессы для сокращения времени');
    }

    if (bomStats.componentCount > 50) {
      recommendations.push('Рассмотрите упрощение конструкции и уменьшение количества деталей');
    }

    return recommendations;
  }

  /**
   * Рассчитать оптимизационный рейтинг BOM
   */
  private calculateBOMOptimizationScore(bomStats: any): number {
    let score = 100;

    // Штраф за высокую стоимость
    if (bomStats.totalCost > 1000) score -= (bomStats.totalCost - 1000) / 10;

    // Штраф за долгое производство
    if (bomStats.estimatedProductionTime > 480) {
      score -= (bomStats.estimatedProductionTime - 480) / 10;
    }

    // Штраф за много деталей
    if (bomStats.componentCount > 50) score -= (bomStats.componentCount - 50) / 2;

    return Math.max(0, Math.min(100, score));
  }

  /**
   * Извлечь имена материалов из BOM
   */
  private extractMaterialNames(bom: any): string[] {
    const materials = new Set<string>();

    if (bom.materials && Array.isArray(bom.materials)) {
      bom.materials.forEach((material: any) => {
        if (material.name) materials.add(material.name);
      });
    }

    return Array.from(materials);
  }

  /**
   * Получить детальный отчёт в HTML формате
   */
  public generateHTMLReport(assembly: Assembly): string {
    const report = this.analyzeAssembly(assembly);

    return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CAD Анализ: ${report.assemblyName}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .header { border-bottom: 3px solid #0066cc; padding-bottom: 10px; }
        .section { margin: 20px 0; padding: 15px; background: #f9f9f9; border-left: 4px solid #0066cc; }
        .quality-score { 
            font-size: 48px; 
            font-weight: bold; 
            color: ${report.qualityScore >= 85 ? '#00aa00' : report.qualityScore >= 60 ? '#ff9900' : '#cc0000'};
            text-align: center;
            padding: 20px;
        }
        .readiness { 
            text-align: center; 
            font-size: 18px;
            padding: 10px;
            border-radius: 4px;
            ${
              report.readiness === 'ready'
                ? 'background: #00ff00; color: #000;'
                : report.readiness === 'review-needed'
                  ? 'background: #ffcc00; color: #000;'
                  : 'background: #ff0000; color: #fff;'
            }
        }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #0066cc; color: white; }
        .error { color: #cc0000; }
        .warning { color: #ff9900; }
        .success { color: #00aa00; }
        ul { padding-left: 20px; }
        li { margin: 5px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Интегрированный CAD Анализ</h1>
            <p>Сборка: ${report.assemblyName}</p>
            <p>Дата: ${report.timestamp.toLocaleString('ru-RU')}</p>
        </div>

        <div class="quality-score">${report.qualityScore}%</div>
        <div class="readiness">${this.readinessText(report.readiness)}</div>

        <div class="section">
            <h2>📊 BOM Информация</h2>
            <table>
                <tr>
                    <td>Всего компонентов:</td>
                    <td><strong>${report.bom.totalComponents}</strong></td>
                </tr>
                <tr>
                    <td>Материалы:</td>
                    <td><strong>${report.bom.totalMaterials.join(', ') || 'Не указаны'}</strong></td>
                </tr>
                <tr>
                    <td>Общая стоимость:</td>
                    <td><strong>\$${report.bom.totalCost.toFixed(2)}</strong></td>
                </tr>
                <tr>
                    <td>Расчётное время производства:</td>
                    <td><strong>${report.bom.estimatedProductionTime.toFixed(1)} мин</strong></td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>🔧 DFM Проверка</h2>
            <table>
                <tr>
                    <td>Производимость:</td>
                    <td><strong class="success">${report.dfm.manufacturability.toFixed(1)}%</strong></td>
                </tr>
                <tr>
                    <td>Всего проверок:</td>
                    <td><strong>${report.dfm.totalChecks}</strong></td>
                </tr>
                <tr>
                    <td>Успешных:</td>
                    <td><strong class="success">${report.dfm.passedChecks}</strong></td>
                </tr>
                <tr>
                    <td>Не успешных:</td>
                    <td><strong class="error">${report.dfm.failedChecks}</strong></td>
                </tr>
            </table>

            ${
              report.dfm.errors.length > 0
                ? `<h3 class="error">❌ Ошибки (${report.dfm.errors.length}):</h3><ul>${report.dfm.errors.map(e => `<li class="error">${e}</li>`).join('')}</ul>`
                : ''
            }

            ${
              report.dfm.warnings.length > 0
                ? `<h3 class="warning">⚠️ Предупреждения (${report.dfm.warnings.length}):</h3><ul>${report.dfm.warnings.map(w => `<li class="warning">${w}</li>`).join('')}</ul>`
                : ''
            }
        </div>

        <div class="section">
            <h2>💡 Рекомендации</h2>
            <ul>
                ${report.recommendations.map(r => `<li>${r}</li>`).join('')}
            </ul>
        </div>

        <div class="section">
            <p><small>Время анализа: ${report.runtimeMs}ms</small></p>
        </div>
    </div>
</body>
</html>
    `;
  }

  private readinessText(readiness: string): string {
    switch (readiness) {
      case 'ready':
        return '✅ ГОТОВО К ПРОИЗВОДСТВУ';
      case 'review-needed':
        return '🔄 ТРЕБУЕТСЯ ПРОВЕРКА';
      case 'redesign-required':
        return '❌ ТРЕБУЕТСЯ ПЕРЕДЕЛКА';
      default:
        return 'НЕИЗВЕСТНОЕ СОСТОЯНИЕ';
    }
  }
}

// ==================== ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ====================

/**
 * Пример 1: Базовый анализ сборки
 */
export function exampleBasicAnalysis() {
  const analyzer = new IntegratedCADAnalyzer();

  // Создаём простую сборку
  const assembly: Assembly = {
    id: 'example-assembly',
    name: 'Пример сборки',
    metadata: {
      version: '1.0.0',
      createdAt: new Date(),
      modifiedAt: new Date()
    },
    components: [
      {
        id: 'comp-1',
        name: 'Корпус',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        properties: {
          width: 100,
          height: 100,
          depth: 50
        },
        material: {
          id: 'aluminum',
          name: 'Алюминий 6061',
          color: '#B0B0B0',
          density: 2700,
          elasticModulus: 69000,
          yieldStrength: 275,
          textureType: TextureType.UNIFORM
        },
        geometry: {
          type: '3D',
          vertices: [],
          faces: [],
          boundingBox: {
            width: () => 100,
            height: () => 100,
            depth: () => 50,
            min: { x: -50, y: -50, z: -25 },
            max: { x: 50, y: 50, z: 25 }
          }
        },
        constraints: [
          { id: 'c1', type: ConstraintType.DISTANCE, elementA: 'f1', elementB: 'f2', value: 50 },
          { id: 'c2', type: ConstraintType.ANGLE, elementA: 'e1', elementB: 'e2', value: 90 }
        ],
        subComponents: []
      }
    ],
    constraints: []
  };

  // Выполнить анализ
  const report = analyzer.analyzeAssembly(assembly);

  console.log('=== Integrated CAD Analysis Report ===');
  console.log(`Assembly: ${report.assemblyName}`);
  console.log(`Quality Score: ${report.qualityScore}%`);
  console.log(`Readiness: ${report.readiness}`);
  console.log(`\nBOM:`);
  console.log(`  Components: ${report.bom.totalComponents}`);
  console.log(`  Total Cost: $${report.bom.totalCost.toFixed(2)}`);
  console.log(`\nDFM:`);
  console.log(`  Manufacturability: ${report.dfm.manufacturability.toFixed(1)}%`);
  console.log(`  Passed checks: ${report.dfm.passedChecks}/${report.dfm.totalChecks}`);

  return report;
}

/**
 * Пример 2: Экспорт в HTML
 */
export function exampleHTMLReport() {
  const analyzer = new IntegratedCADAnalyzer();

  const assembly: Assembly = {
    id: 'test-assembly',
    name: 'Test Assembly',
    metadata: {
      version: '1.0.0',
      createdAt: new Date(),
      modifiedAt: new Date()
    },
    components: [
      {
        id: 'comp-1',
        name: 'Component 1',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        properties: {
          width: 50,
          height: 50,
          depth: 25
        },
        material: {
          id: 'steel',
          name: 'Steel',
          color: '#777777',
          density: 7850,
          elasticModulus: 210000,
          yieldStrength: 400,
          textureType: TextureType.UNIFORM
        },
        geometry: {
          type: '3D',
          vertices: [],
          faces: [],
          boundingBox: {
            width: () => 50,
            height: () => 50,
            depth: () => 25,
            min: { x: -25, y: -25, z: -12.5 },
            max: { x: 25, y: 25, z: 12.5 }
          }
        },
        constraints: [],
        subComponents: []
      }
    ],
    constraints: []
  };

  const html = analyzer.generateHTMLReport(assembly);
  // Можно сохранить в файл или отправить в браузер
  return html;
}

/**
 * Пример 3: Пользовательская конфигурация DFM
 */
export function exampleCustomDFMConfig() {
  const customConfig = {
    minWallThickness: 2.5,
    minFilletRadius: 1.0,
    maxAspectRatio: 50,
    minDistanceFromEdge: 5,
    minHoleSize: 2.0
  };

  const analyzer = new IntegratedCADAnalyzer(customConfig);

  // Анализировать с пользовательскими параметрами
  const assembly: Assembly = {
    id: 'custom-assembly',
    name: 'Custom Assembly',
    metadata: {
      version: '1.0.0',
      createdAt: new Date(),
      modifiedAt: new Date()
    },
    components: [],
    constraints: []
  };

  const report = analyzer.analyzeAssembly(assembly);
  return report;
}
