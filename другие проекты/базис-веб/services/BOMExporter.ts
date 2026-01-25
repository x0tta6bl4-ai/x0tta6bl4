/**
 * BOM Exporter - расширенный экспорт спецификаций материалов (Phase 3)
 */

import { BOMReport, BOMItem, BOMMaterial, BOMStats } from './BillOfMaterials';

export interface ExportOptions {
  includeStats: boolean;
  includeSummary: boolean;
  precision: number;
}

/**
 * Экспортер BOM отчётов в различные форматы
 */
export class BOMExporter {
  /**
   * Экспортирует BOM в HTML таблицу
   */
  static toHTML(bomReport: BOMReport, stats?: BOMStats): string {
    let html = '<table border="1" cellpadding="10" cellspacing="0">';
    html += '<thead><tr>';
    html += '<th>ID компонента</th>';
    html += '<th>Материал</th>';
    html += '<th>Кол-во</th>';
    html += '<th>Масса (кг)</th>';
    html += '<th>Стоимость (руб)</th>';
    html += '<th>Время (ч)</th>';
    html += '</tr></thead><tbody>';

    for (const item of bomReport.items) {
      html += '<tr>';
      html += `<td>${item.componentId}</td>`;
      html += `<td>${item.material}</td>`;
      html += `<td>${item.quantity}</td>`;
      html += `<td>${item.mass.toFixed(3)}</td>`;
      html += `<td>${item.materialCost.toFixed(2)}</td>`;
      html += `<td>${item.productionTime.toFixed(2)}</td>`;
      html += '</tr>';
    }

    // Итоговая строка
    html += '<tr style="background-color: #f0f0f0; font-weight: bold;">';
    html += `<td colspan="2">ИТОГО</td>`;
    html += `<td>${bomReport.totalQuantity}</td>`;
    html += `<td>${bomReport.totalMass.toFixed(3)}</td>`;
    html += `<td>${bomReport.totalMaterialCost.toFixed(2)}</td>`;
    html += `<td>${bomReport.totalProductionTime.toFixed(2)}</td>`;
    html += '</tr>';

    html += '</tbody></table>';

    // Добавляем статистику, если есть
    if (stats) {
      html += '<h3>Статистика</h3>';
      html += '<ul>';
      html += `<li>Уникальные компоненты: ${stats.uniqueComponents ?? ''}</li>`;
      html += `<li>Общее количество: ${stats.totalQuantity ?? ''}</li>`;
      html += `<li>Общая масса: ${(stats.totalMass ?? 0).toFixed(3)} кг</li>`;
      html += `<li>Стоимость материалов: ${(stats.materialCost ?? 0).toFixed(2)} руб</li>`;
      html += `<li>Стоимость производства: ${(stats.manufacturingCost ?? 0).toFixed(2)} руб</li>`;
      html += `<li>Общая стоимость: ${(stats.totalCost ?? 0).toFixed(2)} руб</li>`;
      html += `<li>Время производства: ${(stats.productionTime ?? 0).toFixed(2)} часов</li>`;
      html += '</ul>';
    }

    return html;
  }

  /**
   * Экспортирует BOM в Markdown таблицу
   */
  static toMarkdown(bomReport: BOMReport, stats?: BOMStats): string {
    let md = '| ID компонента | Материал | Кол-во | Масса (кг) | Стоимость (руб) | Время (ч) |\n';
    md += '|---|---|---|---|---|---|\n';

    for (const item of bomReport.items) {
      md += `| ${item.componentId} | ${item.material} | ${item.quantity} | ${item.mass.toFixed(3)} | ${item.materialCost.toFixed(2)} | ${item.productionTime.toFixed(2)} |\n`;
    }

    // Итоговая строка
    md += `| **ИТОГО** | | **${bomReport.totalQuantity}** | **${bomReport.totalMass.toFixed(3)}** | **${bomReport.totalMaterialCost.toFixed(2)}** | **${bomReport.totalProductionTime.toFixed(2)}** |\n`;

    if (stats) {
      md += '\n## Статистика\n\n';
      md += `- **Уникальные компоненты**: ${stats.uniqueComponents ?? ''}\n`;
      md += `- **Общее количество**: ${stats.totalQuantity ?? ''}\n`;
      md += `- **Общая масса**: ${(stats.totalMass ?? 0).toFixed(3)} кг\n`;
      md += `- **Стоимость материалов**: ${(stats.materialCost ?? 0).toFixed(2)} руб\n`;
      md += `- **Стоимость производства**: ${(stats.manufacturingCost ?? 0).toFixed(2)} руб\n`;
      md += `- **Общая стоимость**: ${(stats.totalCost ?? 0).toFixed(2)} руб\n`;
      md += `- **Время производства**: ${(stats.productionTime ?? 0).toFixed(2)} часов\n`;
    }

    return md;
  }

  /**
   * Экспортирует BOM в TSV формат
   */
  static toTSV(bomReport: BOMReport): string {
    const headers = [
      'ID компонента',
      'Материал',
      'Количество',
      'Масса (кг)',
      'Стоимость материала (руб)',
      'Время производства (ч)',
      'Описание'
    ];

    const rows: string[] = [headers.join('\t')];

    for (const item of bomReport.items) {
      const row = [
        item.componentId,
        item.material,
        item.quantity.toString(),
        item.mass.toFixed(3),
        item.materialCost.toFixed(2),
        item.productionTime.toFixed(2),
        item.description
      ];
      rows.push(row.join('\t'));
    }

    // Итоговая строка
    rows.push('');
    rows.push(
      `ИТОГО\t\t${bomReport.totalQuantity}\t${bomReport.totalMass.toFixed(3)}\t${bomReport.totalMaterialCost.toFixed(2)}\t${bomReport.totalProductionTime.toFixed(2)}`
    );

    return rows.join('\n');
  }

  /**
   * Экспортирует BOM в формате с группировкой по материалам
   */
  static toMaterialSummary(bomReport: BOMReport): string {
    const materialMap = new Map<string, { items: BOMItem[]; totalMass: number; totalCost: number }>();

    for (const item of bomReport.items) {
      const materialKey = item.material;
      const existing = materialMap.get(materialKey);
      if (existing) {
        existing.items.push(item);
        existing.totalMass += item.mass;
        existing.totalCost += item.materialCost;
      } else {
        materialMap.set(materialKey, {
          items: [item],
          totalMass: item.mass,
          totalCost: item.materialCost
        });
      }
    }

    let result = '=== СВОДКА ПО МАТЕРИАЛАМ ===\n\n';

    for (const [materialName, data] of materialMap) {
      result += `Материал: ${materialName}\n`;
      result += `  Компонентов: ${data.items.length}\n`;
      result += `  Общее количество: ${data.items.reduce((sum, i) => sum + i.quantity, 0)}\n`;
      result += `  Общая масса: ${data.totalMass.toFixed(3)} кг\n`;
      result += `  Общая стоимость: ${data.totalCost.toFixed(2)} руб\n`;
      result += `  Компоненты:\n`;

      for (const item of data.items) {
        result += `    - ${item.componentId} (кол-во: ${item.quantity})\n`;
      }

      result += '\n';
    }

    return result;
  }

  /**
   * Экспортирует BOM в формате сводки по стоимости
   */
  static toCostBreakdown(bomReport: BOMReport, manufacturingCost: number): string {
    const totalCost = bomReport.totalMaterialCost + manufacturingCost;
    const materialPercent = (bomReport.totalMaterialCost / totalCost) * 100;
    const manufacturingPercent = (manufacturingCost / totalCost) * 100;

    let result = '=== АНАЛИЗ СТОИМОСТИ ===\n\n';
    result += `Стоимость материалов: ${bomReport.totalMaterialCost.toFixed(2)} руб (${materialPercent.toFixed(1)}%)\n`;
    result += `Стоимость производства: ${manufacturingCost.toFixed(2)} руб (${manufacturingPercent.toFixed(1)}%)\n`;
    result += `Общая стоимость: ${totalCost.toFixed(2)} руб\n`;
    result += `\nСредняя стоимость на компонент: ${(totalCost / bomReport.totalQuantity).toFixed(2)} руб\n`;
    result += `Средняя стоимость на кг: ${(totalCost / bomReport.totalMass).toFixed(2)} руб/кг\n`;

    return result;
  }

  /**
   * Экспортирует в формате, удобном для закупок
   */
  static toPurchaseList(bomReport: BOMReport): string {
    const materialMap = new Map<string, number>();

    for (const item of bomReport.items) {
      const existing = materialMap.get(item.material) || 0;
      materialMap.set(item.material, existing + item.mass);
    }

    let result = '=== СПИСОК ЗАКУПОК ===\n\n';
    result += 'Материал\tМасса (кг)\tЦена за кг\tСумма (руб)\n';
    result += '---\t---\t---\t---\n';

    let totalPurchaseCost = 0;

    for (const [materialName, mass] of materialMap) {
      const item = bomReport.items.find(i => i.material === materialName);
      if (item) {
        const pricePerKg = item.materialCost / item.mass;
        const cost = mass * pricePerKg;
        totalPurchaseCost += cost;

        result += `${materialName}\t${mass.toFixed(3)}\t${pricePerKg.toFixed(2)}\t${cost.toFixed(2)}\n`;
      }
    }

    result += `\nОбщая сумма закупок: ${totalPurchaseCost.toFixed(2)} руб\n`;

    return result;
  }
}
