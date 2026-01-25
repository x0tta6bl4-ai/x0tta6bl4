/**
 * ФАЗА 3: Bill of Materials
 * Расчёт материалов, стоимостей, масс и экспорт BOM в различные форматы
 */

import {
  Assembly,
  Component,
  ComponentType,
  Material,
  MaterialCost,
  Point3D
} from '../types/CADTypes';

export type MaterialPrices = {
  [materialId: string]: number;
};

export interface ManufacturingOperations {
  machining?: number;
  painting?: number;
  assembly?: number;
  qualityControl?: number;
  packaging?: number;
}

export interface BOMStats {
  totalItems?: number;
  uniqueComponents?: number;
  totalQuantity?: number;
  totalMass?: number;
  totalMaterialCost?: number;
  materialCost?: number;
  manufacturingCost?: number;
  totalCost?: number;
  productionTime?: number;
  totalProductionTime?: number;
}

export interface BOMMaterial {
  materialId: string;
  materialName: string;
  quantity: number;
  totalVolume: number;
  totalMass: number;
  totalCost: number;
  productionTime: number;
  components: string[];
}

export interface BOMItem {
  id: string;
  componentId: string;
  componentName: string;
  type: ComponentType;
  material: string;
  quantity: number;
  volume: number;
  mass: number;
  cost: number;
  materialCost?: number;
  productionTime: number;
  description?: string;
  dimensions: {
    width: number;
    height: number;
    depth: number;
  };
}

export interface BOMMeta {
  totalComponents: number;
  totalUniqueMaterials: number;
  totalVolume: number;
  totalMass: number;
  totalCost: number;
  totalProductionTime: number;
  averageCostPerUnit: number;
  averageMassPerUnit: number;
  generatedAt: Date;
  assemblyId: string;
}

export interface BOMReport {
  totalItems: number;
  totalQuantity: number;
  totalMass: number;
  totalMaterialCost: number;
  totalProductionTime: number;
  items: BOMItem[];
  materials?: BOMMaterial[];
  meta?: BOMMeta;
  exportFormats?: {
    csv: string;
    json: any[];
  };
}

export class BillOfMaterials {
  private materialPrices: MaterialPrices = {};
  private manufacturingOps: ManufacturingOperations = {};
  private registeredMaterials: Map<string, Material> = new Map();
  private readonly DEFAULT_PRICE_PER_KG = 500;

  constructor(materialPrices?: MaterialPrices | MaterialCost[] | any, manufacturingOps?: ManufacturingOperations) {
    if (materialPrices) {
      if (Array.isArray(materialPrices)) {
        // Handle MaterialCost[] array
        const priceMap: MaterialPrices = {};
        materialPrices.forEach(mc => {
          priceMap[mc.materialId] = mc.pricePerKg || 0;
        });
        this.materialPrices = priceMap;
      } else if (typeof materialPrices === 'object') {
        this.materialPrices = materialPrices;
      }
    }
    if (manufacturingOps && typeof manufacturingOps === 'object') {
      this.manufacturingOps = manufacturingOps;
    }
  }

  public registerMaterial(material: Material): void {
    this.registeredMaterials.set(material.id, material);
  }

  public setMaterialCosts(costs: MaterialCost[]): void {
    const priceMap: MaterialPrices = {};
    costs.forEach(mc => {
      priceMap[mc.materialId] = mc.pricePerKg || 0;
    });
    this.materialPrices = priceMap;
  }

  public addMaterialCost(cost: MaterialCost): void {
    this.materialPrices[cost.materialId] = cost.pricePerKg || 0;
  }

  public generateBOM(assembly: Assembly): BOMReport {
    const items: BOMItem[] = [];

    for (const component of assembly.components) {
      const item = this.createBOMItem(component);
      if (item) {
        items.push(item);
      }
    }

    let totalMass = 0;
    let totalMaterialCost = 0;
    let totalProductionTime = 0;

    for (const item of items) {
      totalMass += item.mass;
      totalMaterialCost += item.cost;
      totalProductionTime += item.productionTime;
    }

    // Generate materials summary
    const materialsMap = new Map<string, BOMMaterial>();
    for (const item of items) {
      const matId = this.getMaterialIdByName(item.material);
      if (!materialsMap.has(matId)) {
        materialsMap.set(matId, {
          materialId: matId,
          materialName: item.material,
          quantity: 0,
          totalVolume: 0,
          totalMass: 0,
          totalCost: 0,
          productionTime: 0,
          components: []
        });
      }
      const mat = materialsMap.get(matId)!;
      mat.quantity += item.quantity;
      mat.totalVolume += item.volume;
      mat.totalMass += item.mass;
      mat.totalCost += item.cost;
      mat.productionTime += item.productionTime;
      mat.components.push(item.componentId);
    }

    const materials = Array.from(materialsMap.values());

    // Generate meta information
    const meta: BOMMeta = {
      totalComponents: items.length,
      totalUniqueMaterials: materials.length,
      totalVolume: items.reduce((sum, item) => sum + item.volume, 0),
      totalMass,
      totalCost: totalMaterialCost,
      totalProductionTime,
      averageCostPerUnit: items.length > 0 ? totalMaterialCost / items.length : 0,
      averageMassPerUnit: items.length > 0 ? totalMass / items.length : 0,
      generatedAt: new Date(),
      assemblyId: assembly.id
    };

    const report: BOMReport = {
      totalItems: items.length,
      totalQuantity: items.length,
      totalMass,
      totalMaterialCost,
      totalProductionTime,
      items,
      materials,
      meta
    };

    report.exportFormats = {
      csv: this.generateCSV(report),
      json: this.generateJSON(report)
    };

    return report;
  }

  private createBOMItem(component: Component): BOMItem | null {
    if (component.type === ComponentType.ASSEMBLY) {
      return null;
    }

    const dims = this.extractDimensions(component);
    const volume = this.calculateVolume(component);
    const mass = this.calculateMass(component, volume);
    
    let materialName = 'Unknown';
    let materialCost = 0;
    
    if (typeof component.material === 'object' && component.material !== null) {
      materialName = component.material.name || 'Unknown';
      const matId = component.material.id;
      const pricePerKg = this.materialPrices[matId] !== undefined ? this.materialPrices[matId] : this.DEFAULT_PRICE_PER_KG;
      materialCost = mass * pricePerKg;
    }

    const productionTime = this.estimateProductionTime(component, volume);

    return {
      id: component.id,
      componentId: component.id,
      componentName: component.name,
      type: component.type,
      material: materialName,
      quantity: 1,
      volume,
      mass,
      cost: materialCost,
      materialCost: materialCost,
      productionTime,
      description: (component as any).description || '',
      dimensions: dims
    };
  }

  private extractDimensions(component: Component): { width: number; height: number; depth: number } {
    let width = 0;
    let height = 0;
    let depth = 0;

    if (component.properties) {
      width = Number(component.properties['width']) || 0;
      height = Number(component.properties['height']) || 0;
      depth = Number(component.properties['depth']) || 0;
    }

    if (component.geometry && component.geometry.boundingBox) {
      const bb = component.geometry.boundingBox;
      if (typeof bb.width === 'function') {
        width = bb.width();
      }
      if (typeof bb.height === 'function') {
        height = bb.height();
      }
      if (typeof bb.depth === 'function') {
        depth = bb.depth();
      }
    }

    return { width, height, depth };
  }

  private calculateVolume(component: Component): number {
    const dims = this.extractDimensions(component);
    const w = dims.width / 1000;
    const h = dims.height / 1000;
    const d = dims.depth / 1000;
    
    return Math.abs(w * h * d);
  }

  /**
   * Определяет плотность материала с использованием 4-уровневой системы fallback
   * Priority 1: Явно установленная плотность в Material.density
   * Priority 2: Плотность из таблицы MATERIAL_PROPERTIES по толщине
   * Priority 3: Плотность по типу материала (HDF: 900, MDF: 740, LDSP: 730)
   * Priority 4: Финальный fallback 730 kg/m³
   */
  private getMaterialDensity(component: Component): number {
    const MIN_DENSITY = 600;
    const MAX_DENSITY = 1200;
    
    if (typeof component.material === 'object' && component.material !== null) {
      // Priority 1: Явно установленная плотность
      if (component.material.density) {
        const density = component.material.density;
        return Math.max(MIN_DENSITY, Math.min(MAX_DENSITY, density));
      }

      // Priority 3: Плотность по типу материала
      if ((component.material as any).type) {
        const type = (component.material as any).type;
        switch (type) {
          case 'HDF':
            return 900; // High-density, упругий
          case 'MDF':
            return 740; // Medium-density, стандарт
          case 'LDSP':
            return 730; // Low-density chipboard
          default:
            break;
        }
      }
    }

    // Priority 4: Финальный fallback
    return 730;
  }

  private calculateMass(component: Component, volume: number): number {
    const density = this.getMaterialDensity(component);
    return volume * density;
  }

  private estimateProductionTime(component: Component, volume: number): number {
    const dims = this.extractDimensions(component);
    const thickness = dims.depth;
    const area = (dims.width * dims.height) / 1000000;
    
    let time = (area * 100) * 0.5 + (thickness / 10) * 0.1;
    const hasHoles = Number(component.properties?.['holes'] || 0);
    time += hasHoles * 1;
    
    return Math.max(5, Math.round(time * 10) / 10);
  }

  private generateCSV(report: BOMReport): string {
    const lines: string[] = [];
    lines.push('ID компонента,Компонент,Тип,Материал,Количество,Объём (м³),Масса (кг),Стоимость материала (₽),Время производства (мин),Описание');

    for (const item of report.items) {
      const desc = (item.description || '').replace(/"/g, '""');
      lines.push(
        `${item.componentId},"${item.componentName}",${item.type},"${item.material}",${item.quantity},` +
        `${item.volume.toFixed(6)},${item.mass.toFixed(2)},${item.cost.toFixed(2)},${item.productionTime.toFixed(1)},"${desc}"`
      );
    }

    lines.push('');
    lines.push('Материал,Количество,Общий объём (м³),Общая масса (кг),Общая стоимость (₽)');
    if (report.materials) {
      for (const mat of report.materials) {
        lines.push(`${mat.materialName},${mat.quantity},${mat.totalVolume.toFixed(6)},${mat.totalMass.toFixed(2)},${mat.totalCost.toFixed(2)}`);
      }
    }

    lines.push('');
    lines.push('ИТОГО');
    lines.push(`Всего компонентов,${report.totalItems}`);
    lines.push(`Общая масса (кг),${report.totalMass.toFixed(2)}`);
    lines.push(`Общая стоимость материалов (₽),${report.totalMaterialCost.toFixed(2)}`);
    lines.push(`Общее время производства (мин),${report.totalProductionTime.toFixed(1)}`);

    return lines.join('\n');
  }

  private generateJSON(report: BOMReport): any[] {
    return report.items.map(item => ({
      componentId: item.componentId,
      componentName: item.componentName,
      type: item.type,
      material: item.material,
      quantity: item.quantity,
      volume: item.volume,
      mass: item.mass,
      cost: item.cost,
      productionTime: item.productionTime
    }));
  }

  private getMaterialIdByName(materialName: string): string {
    for (const [id, material] of this.registeredMaterials) {
      if (material.name === materialName) {
        return id;
      }
    }
    // Fallback: generate ID from material name
    return materialName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  }

  public exportToCSV(report: BOMReport): string {
    return this.generateCSV(report);
  }

  public exportToJSON(report: BOMReport): string {
    return JSON.stringify({
      items: report.items,
      materials: report.materials,
      meta: report.meta,
      summary: {
        totalItems: report.totalItems,
        totalQuantity: report.totalQuantity,
        totalMass: report.totalMass,
        totalMaterialCost: report.totalMaterialCost,
        totalProductionTime: report.totalProductionTime
      }
    }, null, 2);
  }

  public exportToHTML(report: BOMReport): string {
    const html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Bill of Materials - ${report.meta?.assemblyId || 'Assembly'}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .total { font-weight: bold; background-color: #e6f3ff; }
    </style>
</head>
<body>
    <h1>Bill of Materials</h1>
    <p>Generated: ${report.meta?.generatedAt.toLocaleString() || 'Unknown'}</p>
    <p>Assembly: ${report.meta?.assemblyId || 'Unknown'}</p>

    <h2>Components</h2>
    <table>
        <thead>
            <tr>
                <th>Component</th>
                <th>Type</th>
                <th>Material</th>
                <th>Quantity</th>
                <th>Volume (m³)</th>
                <th>Mass (kg)</th>
                <th>Cost (₽)</th>
                <th>Production Time (min)</th>
            </tr>
        </thead>
        <tbody>
            ${report.items.map(item => `
                <tr>
                    <td>${item.componentName}</td>
                    <td>${item.type}</td>
                    <td>${item.material}</td>
                    <td>${item.quantity}</td>
                    <td>${item.volume.toFixed(6)}</td>
                    <td>${item.mass.toFixed(2)}</td>
                    <td>${item.cost.toFixed(2)}</td>
                    <td>${item.productionTime.toFixed(1)}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>

    ${report.materials && report.materials.length > 0 ? `
    <h2>Materials Summary</h2>
    <table>
        <thead>
            <tr>
                <th>Material</th>
                <th>Quantity</th>
                <th>Total Volume (m³)</th>
                <th>Total Mass (kg)</th>
                <th>Total Cost (₽)</th>
            </tr>
        </thead>
        <tbody>
            ${report.materials.map(mat => `
                <tr>
                    <td>${mat.materialName}</td>
                    <td>${mat.quantity}</td>
                    <td>${mat.totalVolume.toFixed(6)}</td>
                    <td>${mat.totalMass.toFixed(2)}</td>
                    <td>${mat.totalCost.toFixed(2)}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>
    ` : ''}

    <h2>Summary</h2>
    <table>
        <tr><td>Total Components:</td><td class="total">${report.totalItems}</td></tr>
        <tr><td>Total Mass:</td><td class="total">${report.totalMass.toFixed(2)} kg</td></tr>
        <tr><td>Total Material Cost:</td><td class="total">${report.totalMaterialCost.toFixed(2)} ₽</td></tr>
        <tr><td>Total Production Time:</td><td class="total">${report.totalProductionTime.toFixed(1)} min</td></tr>
    </table>
</body>
</html>`;
    return html;
  }

  public calculateBOMStats(report: BOMReport): BOMStats {
    const materialCost = report.totalMaterialCost;
    const manufacturingCost = report.totalProductionTime * 10;
    const totalCost = materialCost + manufacturingCost;
    
    return {
      totalItems: report.totalItems,
      uniqueComponents: report.totalItems,
      totalQuantity: report.totalQuantity,
      totalMass: report.totalMass,
      totalMaterialCost: report.totalMaterialCost,
      materialCost: materialCost,
      manufacturingCost: manufacturingCost,
      totalCost: totalCost,
      productionTime: report.totalProductionTime / 60,
      totalProductionTime: report.totalProductionTime
    };
  }

  public validateBOM(report: BOMReport | any): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!report || !report.items || report.items.length === 0) {
      errors.push('BOM пуста - нет компонентов');
      return { valid: false, errors };
    }

    if (report.totalMaterialCost < 0) {
      errors.push('Стоимость материалов не может быть отрицательной');
    }

    if (report.totalMass < 0) {
      errors.push('Масса не может быть отрицательной');
    }

    for (const item of report.items) {
      if (!item.material) {
        errors.push(`Компонент ${item.componentName} не имеет материала`);
      }
      if (item.volume <= 0) {
        errors.push(`Компонент ${item.componentName} имеет неверный объём`);
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  public compareBOMs(bom1: BOMReport, bom2: BOMReport): {
    itemsAdded: number;
    itemsRemoved: number;
    costChange: number;
    massChange: number;
    componentDifferences: any[];
  } {
    const set1 = new Set(bom1.items.map(i => i.componentId));
    const set2 = new Set(bom2.items.map(i => i.componentId));

    let itemsAdded = 0;
    let itemsRemoved = 0;
    const differences: any[] = [];

    for (const id of set2) {
      if (!set1.has(id)) {
        itemsAdded++;
        const item = bom2.items.find(i => i.componentId === id);
        if (item) {
          differences.push({
            type: 'added',
            component: item.componentName,
            cost: item.cost,
            mass: item.mass
          });
        }
      }
    }

    for (const id of set1) {
      if (!set2.has(id)) {
        itemsRemoved++;
        const item = bom1.items.find(i => i.componentId === id);
        if (item) {
          differences.push({
            type: 'removed',
            component: item.componentName,
            cost: item.cost,
            mass: item.mass
          });
        }
      }
    }

    return {
      itemsAdded,
      itemsRemoved,
      costChange: bom2.totalMaterialCost - bom1.totalMaterialCost,
      massChange: bom2.totalMass - bom1.totalMass,
      componentDifferences: differences
    };
  }
}

export { BillOfMaterials as BillOfMaterialsGenerator };
