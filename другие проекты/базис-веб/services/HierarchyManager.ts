/**
 * ФАЗА 3: Hierarchy Manager
 * Управление иерархией компонентов, фильтрация и навигация
 */

import {
  Assembly,
  Component,
  ComponentType
} from '../types/CADTypes';

/**
 * Элемент иерархии (для визуализации дерева)
 */
export interface HierarchyNode {
  id: string;
  name: string;
  type: ComponentType;
  level: number;
  parent: string | null;
  children: HierarchyNode[];
  component: Component;
}

/**
 * Путь в иерархии
 */
export interface ComponentPath {
  componentId: string;
  path: Component[];        // All parents from root to component
  depth: number;
  parentId: string | null;
}

/**
 * Фильтры для поиска компонентов
 */
export interface ComponentFilter {
  type?: ComponentType;
  material?: string;
  nameContains?: string;
  minVolume?: number;
  maxVolume?: number;
}

/**
 * Результат фильтрации
 */
export interface FilterResult {
  components: Component[];
  count: number;
  filter: ComponentFilter;
}

/**
 * Hierarchy Manager
 */
export class HierarchyManager {
  /**
   * Получить путь компонента от корня
   */
  public static getComponentPath(assembly: Assembly, componentId: string): ComponentPath | null {
    const findComponent = (comps: Component[], target: string, parentPath: Component[] = []): Component[] | null => {
      for (const comp of comps) {
        if (comp.id === target) {
          return [...parentPath, comp];
        }

        if (comp.subComponents && comp.subComponents.length > 0) {
          const found = findComponent(comp.subComponents, target, [...parentPath, comp]);
          if (found) {
            return found;
          }
        }
      }
      return null;
    };

    const path = findComponent(assembly.components, componentId);
    if (!path) {
      return null;
    }

    const component = path[path.length - 1];
    const parentId = path.length > 1 ? path[path.length - 2].id : null;

    return {
      componentId,
      path,
      depth: path.length - 1,
      parentId
    };
  }

  /**
   * Получить полный путь в виде строки
   */
  public static getComponentPathString(assembly: Assembly, componentId: string): string | null {
    const pathInfo = this.getComponentPath(assembly, componentId);
    if (!pathInfo) {
      return null;
    }

    return pathInfo.path
      .map(c => c.name)
      .join(' / ');
  }

  /**
   * Создать дерево иерархии
   */
  public static buildHierarchyTree(assembly: Assembly): HierarchyNode[] {
    const buildNode = (component: Component, level: number = 0, parent: string | null = null): HierarchyNode => {
      const children: HierarchyNode[] = [];

      if (component.subComponents && component.subComponents.length > 0) {
        for (const subComp of component.subComponents) {
          children.push(buildNode(subComp, level + 1, component.id));
        }
      }

      return {
        id: component.id,
        name: component.name,
        type: component.type,
        level,
        parent,
        children,
        component
      };
    };

    return assembly.components.map(comp => buildNode(comp));
  }

  /**
   * Сплющить иерархию в плоский массив (DFS)
   */
  public static flattenAssembly(assembly: Assembly): Component[] {
    const result: Component[] = [];

    const traverse = (comps: Component[]) => {
      for (const comp of comps) {
        result.push(comp);
        if (comp.subComponents && comp.subComponents.length > 0) {
          traverse(comp.subComponents);
        }
      }
    };

    traverse(assembly.components);
    return result;
  }

  /**
   * Получить все компоненты определённого типа
   */
  public static getComponentsByType(assembly: Assembly, type: ComponentType): Component[] {
    const components = this.flattenAssembly(assembly);
    return components.filter(c => c.type === type);
  }

  /**
   * Получить все компоненты из определённого материала
   */
  public static getComponentsByMaterial(assembly: Assembly, materialId: string): Component[] {
    const components = this.flattenAssembly(assembly);
    return components.filter(c => c.material?.id === materialId);
  }

  /**
   * Получить все компоненты с частичным совпадением имени
   */
  public static getComponentsByName(assembly: Assembly, namePattern: string): Component[] {
    const components = this.flattenAssembly(assembly);
    const pattern = new RegExp(namePattern, 'i');
    return components.filter(c => pattern.test(c.name));
  }

  /**
   * Найти компонент по ID
   */
  public static findComponentById(assembly: Assembly, componentId: string): Component | null {
    const components = this.flattenAssembly(assembly);
    return components.find(c => c.id === componentId) || null;
  }

  /**
   * Получить прямые дочерние компоненты
   */
  public static getChildren(assembly: Assembly, parentId: string): Component[] {
    const parent = this.findComponentById(assembly, parentId);
    if (!parent || !parent.subComponents) {
      return [];
    }
    return parent.subComponents;
  }

  /**
   * Получить родительский компонент
   */
  public static getParent(assembly: Assembly, componentId: string): Component | null {
    const pathInfo = this.getComponentPath(assembly, componentId);
    if (!pathInfo || pathInfo.path.length < 2) {
      return null;
    }
    return pathInfo.path[pathInfo.path.length - 2];
  }

  /**
   * Применить фильтры к сборке
   */
  public static filterComponents(assembly: Assembly, filter: ComponentFilter): FilterResult {
    let components = this.flattenAssembly(assembly);

    // Filter by type
    if (filter.type) {
      components = components.filter(c => c.type === filter.type);
    }

    // Filter by material
    if (filter.material) {
      components = components.filter(c => c.material?.id === filter.material);
    }

    // Filter by name
    if (filter.nameContains) {
      const pattern = new RegExp(filter.nameContains, 'i');
      components = components.filter(c => pattern.test(c.name));
    }

    // Filter by volume
    if (filter.minVolume !== undefined || filter.maxVolume !== undefined) {
      components = components.filter(c => {
        const volume = this.calculateComponentVolume(c);
        const minOk = filter.minVolume === undefined || volume >= filter.minVolume;
        const maxOk = filter.maxVolume === undefined || volume <= filter.maxVolume;
        return minOk && maxOk;
      });
    }

    return {
      components,
      count: components.length,
      filter
    };
  }

  /**
   * Рассчитать объём компонента (м³)
   */
  private static calculateComponentVolume(component: Component): number {
    const props = component.properties || {};
    const width = Number(props['width']) || 0;
    const height = Number(props['height']) || 0;
    const depth = Number(props['depth']) || 0;

    const w = width / 1000;
    const h = height / 1000;
    const d = depth / 1000;

    return Math.abs(w * h * d);
  }

  /**
   * Получить количество компонентов каждого типа
   */
  public static getComponentTypeStats(assembly: Assembly): Record<ComponentType, number> {
    const components = this.flattenAssembly(assembly);
    const stats: Record<ComponentType, number> = {
      [ComponentType.PART]: 0,
      [ComponentType.ASSEMBLY]: 0,
      [ComponentType.SUBASSEMBLY]: 0
    };

    for (const comp of components) {
      stats[comp.type]++;
    }

    return stats;
  }

  /**
   * Получить материальную статистику
   */
  public static getMaterialStats(assembly: Assembly): Record<string, number> {
    const components = this.flattenAssembly(assembly);
    const stats: Record<string, number> = {};

    for (const comp of components) {
      const material = comp.material?.name || 'Unknown';
      stats[material] = (stats[material] || 0) + 1;
    }

    return stats;
  }

  /**
   * Проверить, является ли компонент листовым (без подкомпонентов)
   */
  public static isLeafComponent(component: Component): boolean {
    return !component.subComponents || component.subComponents.length === 0;
  }

  /**
   * Получить все листовые компоненты
   */
  public static getLeafComponents(assembly: Assembly): Component[] {
    const components = this.flattenAssembly(assembly);
    return components.filter(c => this.isLeafComponent(c));
  }

  /**
   * Получить глубину иерархии
   */
  public static getHierarchyDepth(assembly: Assembly): number {
    const getMaxDepth = (comps: Component[], currentDepth: number = 0): number => {
      let maxDepth = currentDepth;

      for (const comp of comps) {
        if (comp.subComponents && comp.subComponents.length > 0) {
          const depth = getMaxDepth(comp.subComponents, currentDepth + 1);
          maxDepth = Math.max(maxDepth, depth);
        }
      }

      return maxDepth;
    };

    return getMaxDepth(assembly.components);
  }

  /**
   * Получить сводку по иерархии
   */
  public static getHierarchySummary(assembly: Assembly) {
    const components = this.flattenAssembly(assembly);
    const typeStats = this.getComponentTypeStats(assembly);
    const materialStats = this.getMaterialStats(assembly);
    const leafComponents = this.getLeafComponents(assembly);
    const depth = this.getHierarchyDepth(assembly);

    return {
      totalComponents: components.length,
      totalLeafComponents: leafComponents.length,
      hierarchyDepth: depth,
      componentTypes: typeStats,
      materialStats,
      uniqueMaterials: Object.keys(materialStats).length
    };
  }

  /**
   * Перемещение компонента в нового родителя (если поддерживается)
   */
  public static moveComponent(
    assembly: Assembly,
    componentId: string,
    newParentId: string | null
  ): boolean {
    const component = this.findComponentById(assembly, componentId);
    if (!component) {
      return false;
    }

    // Find and remove from old parent
    const oldPathInfo = this.getComponentPath(assembly, componentId);
    if (oldPathInfo && oldPathInfo.parentId) {
      const oldParent = this.findComponentById(assembly, oldPathInfo.parentId);
      if (oldParent && oldParent.subComponents) {
        oldParent.subComponents = oldParent.subComponents.filter(c => c.id !== componentId);
      }
    } else {
      // Remove from root
      assembly.components = assembly.components.filter(c => c.id !== componentId);
    }

    // Add to new parent
    if (newParentId) {
      const newParent = this.findComponentById(assembly, newParentId);
      if (newParent) {
        if (!newParent.subComponents) {
          newParent.subComponents = [];
        }
        newParent.subComponents.push(component);
        component.parentId = newParentId;
        return true;
      }
    } else {
      // Add to root
      assembly.components.push(component);
      component.parentId = undefined;
      return true;
    }

    return false;
  }

  /**
   * Получить все предки компонента
   */
  public static getAncestors(assembly: Assembly, componentId: string): Component[] {
    const pathInfo = this.getComponentPath(assembly, componentId);
    if (!pathInfo || pathInfo.path.length < 2) {
      return [];
    }
    // Remove the component itself
    return pathInfo.path.slice(0, -1);
  }

  /**
   * Получить все потомки компонента
   */
  public static getDescendants(assembly: Assembly, componentId: string): Component[] {
    const component = this.findComponentById(assembly, componentId);
    if (!component) {
      return [];
    }

    const descendants: Component[] = [];

    const traverse = (comp: Component) => {
      if (comp.subComponents) {
        for (const subComp of comp.subComponents) {
          descendants.push(subComp);
          traverse(subComp);
        }
      }
    };

    traverse(component);
    return descendants;
  }
}
