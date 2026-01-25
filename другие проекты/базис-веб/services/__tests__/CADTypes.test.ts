/**
 * CADTypes.test.ts
 * Тесты для типов CAD системы
 */

import {
  CADTypeUtils,
  Point3D,
  Vector3D,
  Material,
  Constraint,
  Component,
  Assembly,
  BOMItem,
  DFMCheckResult,
} from '../../types/CADTypes';

describe('CADTypeUtils', () => {
  describe('distance', () => {
    it('должно вычислить расстояние между двумя точками', () => {
      const p1: Point3D = { x: 0, y: 0, z: 0 };
      const p2: Point3D = { x: 3, y: 4, z: 0 };
      
      expect(CADTypeUtils.distance(p1, p2)).toBe(5);
    });
    
    it('должно вернуть 0 для одинаковых точек', () => {
      const p: Point3D = { x: 1, y: 2, z: 3 };
      
      expect(CADTypeUtils.distance(p, p)).toBe(0);
    });
    
    it('должно работать для 3D расстояния', () => {
      const p1: Point3D = { x: 0, y: 0, z: 0 };
      const p2: Point3D = { x: 1, y: 1, z: 1 };
      
      const dist = CADTypeUtils.distance(p1, p2);
      expect(dist).toBeCloseTo(Math.sqrt(3), 5);
    });
  });
  
  describe('dotProduct', () => {
    it('должно вычислить скалярное произведение двух векторов', () => {
      const v1: Vector3D = { x: 1, y: 2, z: 3 };
      const v2: Vector3D = { x: 4, y: 5, z: 6 };
      
      const result = CADTypeUtils.dotProduct(v1, v2);
      expect(result).toBe(32); // 1*4 + 2*5 + 3*6
    });
    
    it('должно вернуть 0 для ортогональных векторов', () => {
      const v1: Vector3D = { x: 1, y: 0, z: 0 };
      const v2: Vector3D = { x: 0, y: 1, z: 0 };
      
      const result = CADTypeUtils.dotProduct(v1, v2);
      expect(result).toBe(0);
    });
  });
  
  describe('crossProduct', () => {
    it('должно вычислить векторное произведение', () => {
      const v1: Vector3D = { x: 1, y: 0, z: 0 };
      const v2: Vector3D = { x: 0, y: 1, z: 0 };
      
      const result = CADTypeUtils.crossProduct(v1, v2);
      expect(result).toEqual({ x: 0, y: 0, z: 1 });
    });
    
    it('должно вернуть нулевой вектор для параллельных векторов', () => {
      const v1: Vector3D = { x: 1, y: 2, z: 3 };
      const v2: Vector3D = { x: 2, y: 4, z: 6 };
      
      const result = CADTypeUtils.crossProduct(v1, v2);
      expect(result.x).toBeCloseTo(0, 5);
      expect(result.y).toBeCloseTo(0, 5);
      expect(result.z).toBeCloseTo(0, 5);
    });
  });
  
  describe('magnitude', () => {
    it('должно вычислить длину вектора', () => {
      const v: Vector3D = { x: 3, y: 4, z: 0 };
      
      expect(CADTypeUtils.magnitude(v)).toBe(5);
    });
    
    it('должно вернуть 0 для нулевого вектора', () => {
      const v: Vector3D = { x: 0, y: 0, z: 0 };
      
      expect(CADTypeUtils.magnitude(v)).toBe(0);
    });
  });
  
  describe('normalize', () => {
    it('должно нормализовать вектор', () => {
      const v: Vector3D = { x: 3, y: 4, z: 0 };
      
      const normalized = CADTypeUtils.normalize(v);
      expect(CADTypeUtils.magnitude(normalized)).toBeCloseTo(1, 5);
    });
    
    it('должно обработать нулевой вектор', () => {
      const v: Vector3D = { x: 0, y: 0, z: 0 };
      
      const normalized = CADTypeUtils.normalize(v);
      expect(normalized).toEqual({ x: 0, y: 0, z: 0 });
    });
  });
  
  describe('transformPoint', () => {
    it('должно применить трансформацию к точке', () => {
      const point: Point3D = { x: 1, y: 2, z: 3 };
      const transform = {
        position: { x: 10, y: 20, z: 30 },
        rotation: { x: 0, y: 0, z: 0 },
        scale: { x: 1, y: 1, z: 1 }
      };
      
      const result = CADTypeUtils.transformPoint(point, transform);
      expect(result).toEqual({ x: 11, y: 22, z: 33 });
    });
  });
});

describe('Component типы', () => {
  it('должно создать валидный Component', () => {
    const component: Component = {
      id: 'comp-1',
      name: 'Полка',
      type: 'SHELF',
      geometry: {
        type: 'BOX',
        dimensions: { x: 1000, y: 200, z: 600 },
        center: { x: 500, y: 100, z: 0 }
      },
      material: {
        name: 'Фанера 18мм',
        density: 780,
        textureType: 'WOOD',
        color: { r: 200, g: 150, b: 100, a: 1 },
        roughness: 0.8,
        metallic: false
      },
      transform: {
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        scale: { x: 1, y: 1, z: 1 }
      }
    };
    
    expect(component.id).toBe('comp-1');
    expect(component.geometry.dimensions.x).toBe(1000);
  });
});

describe('Assembly типы', () => {
  it('должно создать валидную Assembly', () => {
    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Шкаф',
      type: 'CABINET',
      subComponents: [],
      constraints: [],
      boundingBox: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 1000, y: 600, z: 2000 }
      }
    };
    
    expect(assembly.id).toBe('asm-1');
    expect(assembly.subComponents).toEqual([]);
    expect(assembly.constraints).toEqual([]);
  });
});

describe('BOMItem типы', () => {
  it('должно создать валидный BOMItem', () => {
    const bomItem: BOMItem = {
      material: {
        name: 'Деревянный брусок',
        density: 650,
        textureType: 'WOOD',
        color: { r: 200, g: 150, b: 100, a: 1 },
        roughness: 0.5,
        metallic: false
      },
      quantity: 4,
      unit: 'штук',
      cost: 25.50
    };
    
    expect(bomItem.quantity).toBe(4);
    expect(bomItem.cost).toBe(25.50);
  });
});

describe('DFMCheckResult типы', () => {
  it('должно создать валидный DFMCheckResult', () => {
    const result: DFMCheckResult = {
      ruleId: 'dfm-rule-1',
      ruleName: 'Толщина материала',
      passed: false,
      severity: 'WARNING',
      message: 'Толщина менее 2мм',
      suggestions: ['Увеличить толщину']
    };
    
    expect(result.severity).toBe('WARNING');
    expect(result.suggestions?.length).toBe(1);
  });
});
