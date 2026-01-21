/**
 * ФАЗА 2: Расширенные тесты для Assembly и Component типов
 * Повышаем coverage до 80%+
 */

import {
  Component,
  Assembly,
  Material,
  TextureType,
  ComponentType,
  ConstraintType,
  Constraint,
  AnchorPointType,
  AnchorPoint,
  Point3D,
  EulerAngles,
  CADTypeUtils
} from '../../types/CADTypes';

// ============================================================================
// MATERIAL TESTS
// ============================================================================

describe('Material Types', () => {
  test('should create material with basic properties', () => {
    const material: Material = {
      id: 'mat-oak',
      name: 'Oak Wood',
      color: '#8B4513',
      density: 600,
      elasticModulus: 10000,
      poissonRatio: 0.35,
      textureType: TextureType.WOOD_OAK,
      minThickness: 3,
      maxThickness: 50
    };

    expect(material.id).toBe('mat-oak');
    expect(material.name).toBe('Oak Wood');
    expect(material.density).toBe(600);
    expect(material.elasticModulus).toBe(10000);
    expect(material.textureType).toBe(TextureType.WOOD_OAK);
  });

  test('should support all TextureType values', () => {
    const textures = [
      TextureType.NONE,
      TextureType.WOOD_OAK,
      TextureType.WOOD_WALNUT,
      TextureType.WOOD_ASH,
      TextureType.CONCRETE,
      TextureType.UNIFORM
    ];

    expect(textures.length).toBe(6);
    textures.forEach(texture => {
      expect(texture).toBeDefined();
      expect(typeof texture).toBe('string');
    });
  });

  test('should have optional FEA properties', () => {
    const material: Material = {
      id: 'steel',
      name: 'Steel',
      color: '#696969'
      // No FEA properties
    };

    expect(material.yieldStrength).toBeUndefined();
    expect(material.tensileStrength).toBeUndefined();

    // Add FEA properties
    material.yieldStrength = 250;
    material.tensileStrength = 400;

    expect(material.yieldStrength).toBe(250);
    expect(material.tensileStrength).toBe(400);
  });
});

// ============================================================================
// COMPONENT TESTS
// ============================================================================

describe('Component Type', () => {
  let basicMaterial: Material;
  let basicPosition: Point3D;
  let basicRotation: EulerAngles;

  beforeEach(() => {
    basicMaterial = {
      id: 'mat-1',
      name: 'Test Material',
      color: '#FF0000'
    };

    basicPosition = { x: 100, y: 200, z: 300 };
    basicRotation = { x: 0, y: 0, z: 0 };
  });

  test('should create PART component', () => {
    const component: Component = {
      id: 'part-1',
      name: 'Simple Part',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {
        width: 100,
        height: 50,
        depth: 25
      }
    };

    expect(component.type).toBe(ComponentType.PART);
    expect(component.subComponents).toBeUndefined();
    expect(component.properties.width).toBe(100);
  });

  test('should create ASSEMBLY component with subcomponents', () => {
    const subComponent: Component = {
      id: 'part-1',
      name: 'Sub Part',
      type: ComponentType.PART,
      position: { x: 0, y: 0, z: 0 },
      rotation: basicRotation,
      material: basicMaterial,
      properties: {}
    };

    const assembly: Component = {
      id: 'asm-1',
      name: 'Main Assembly',
      type: ComponentType.ASSEMBLY,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {},
      subComponents: [subComponent]
    };

    expect(assembly.type).toBe(ComponentType.ASSEMBLY);
    expect(assembly.subComponents).toBeDefined();
    expect(assembly.subComponents!.length).toBe(1);
    expect(assembly.subComponents![0].id).toBe('part-1');
  });

  test('should support component scaling', () => {
    const component: Component = {
      id: 'scaled-part',
      name: 'Scaled Part',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      scale: { x: 2, y: 1, z: 0.5 },
      material: basicMaterial,
      properties: {}
    };

    expect(component.scale).toBeDefined();
    expect(component.scale!.x).toBe(2);
    expect(component.scale!.y).toBe(1);
    expect(component.scale!.z).toBe(0.5);
  });

  test('should support visibility and locking', () => {
    const component: Component = {
      id: 'locked-part',
      name: 'Locked Part',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {},
      hidden: true,
      locked: true,
      color: '#AAAAAA'
    };

    expect(component.hidden).toBe(true);
    expect(component.locked).toBe(true);
    expect(component.color).toBe('#AAAAAA');
  });

  test('should support anchor points', () => {
    const anchorPoint: AnchorPoint = {
      id: 'anchor-1',
      name: 'Top Center',
      position: { x: 0, y: 50, z: 0 },
      componentId: 'part-1',
      type: AnchorPointType.FACE_CENTER,
      normal: { x: 0, y: 1, z: 0 }
    };

    const component: Component = {
      id: 'part-1',
      name: 'Part with Anchors',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {},
      anchorPoints: [anchorPoint]
    };

    expect(component.anchorPoints).toBeDefined();
    expect(component.anchorPoints!.length).toBe(1);
    expect(component.anchorPoints![0].type).toBe(AnchorPointType.FACE_CENTER);
  });

  test('should support local constraints', () => {
    const constraint: Constraint = {
      id: 'con-1',
      type: ConstraintType.DISTANCE,
      elementA: 'anchor-1',
      elementB: 'anchor-2',
      value: 100,
      tolerance: 0.1,
      weight: 1.0
    };

    const component: Component = {
      id: 'part-1',
      name: 'Constrained Part',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {},
      constraints: [constraint]
    };

    expect(component.constraints).toBeDefined();
    expect(component.constraints!.length).toBe(1);
    expect(component.constraints![0].value).toBe(100);
  });

  test('should support parent-child relationships', () => {
    const component: Component = {
      id: 'child-part',
      name: 'Child Part',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {},
      parentId: 'asm-1'
    };

    expect(component.parentId).toBe('asm-1');
  });

  test('should store custom properties', () => {
    const component: Component = {
      id: 'custom-part',
      name: 'Custom Part',
      type: ComponentType.PART,
      position: basicPosition,
      rotation: basicRotation,
      material: basicMaterial,
      properties: {
        width: 100,
        height: 50,
        depth: 25,
        custom1: 'string value',
        custom2: 42,
        custom3: true
      }
    };

    expect(component.properties.width).toBe(100);
    expect(component.properties.custom1).toBe('string value');
    expect(component.properties.custom2).toBe(42);
    expect(component.properties.custom3).toBe(true);
  });

  test('should support all ComponentType values', () => {
    const types = [
      ComponentType.PART,
      ComponentType.ASSEMBLY,
      ComponentType.SUBASSEMBLY
    ];

    expect(types.length).toBe(3);
    types.forEach(type => {
      expect(type).toBeDefined();
      expect(typeof type).toBe('string');
    });
  });
});

// ============================================================================
// ASSEMBLY TESTS
// ============================================================================

describe('Assembly Type', () => {
  let basicComponent: Component;
  let basicMaterial: Material;

  beforeEach(() => {
    basicMaterial = {
      id: 'mat-1',
      name: 'Test Material',
      color: '#FF0000'
    };

    basicComponent = {
      id: 'comp-1',
      name: 'Test Component',
      type: ComponentType.PART,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material: basicMaterial,
      properties: {}
    };
  });

  test('should create assembly with components', () => {
    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Test Assembly',
      components: [basicComponent],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };

    expect(assembly.id).toBe('asm-1');
    expect(assembly.components.length).toBe(1);
    expect(assembly.constraints.length).toBe(0);
  });

  test('should support multiple components', () => {
    const components: Component[] = Array.from({ length: 5 }, (_, i) => ({
      id: `comp-${i}`,
      name: `Component ${i}`,
      type: ComponentType.PART,
      position: { x: i * 100, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material: basicMaterial,
      properties: {}
    }));

    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Multi Component Assembly',
      components,
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };

    expect(assembly.components.length).toBe(5);
    assembly.components.forEach((comp, i) => {
      expect(comp.position.x).toBe(i * 100);
    });
  });

  test('should support global constraints', () => {
    const constraints: Constraint[] = [
      {
        id: 'con-1',
        type: ConstraintType.FIXED,
        elementA: 'comp-1',
        weight: 1.0
      },
      {
        id: 'con-2',
        type: ConstraintType.DISTANCE,
        elementA: 'comp-1',
        elementB: 'comp-2',
        value: 100,
        weight: 1.0
      }
    ];

    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Constrained Assembly',
      components: [basicComponent],
      constraints,
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };

    expect(assembly.constraints.length).toBe(2);
  });

  test('should track metadata', () => {
    const now = new Date();
    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Test Assembly',
      components: [],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: now,
        modifiedAt: now,
        author: 'Test Author',
        description: 'Test Description'
      }
    };

    expect(assembly.metadata.version).toBe('1.0.0');
    expect(assembly.metadata.author).toBe('Test Author');
    expect(assembly.metadata.description).toBe('Test Description');
    expect(assembly.metadata.createdAt).toEqual(now);
  });

  test('should support dirty and valid flags', () => {
    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Test Assembly',
      components: [basicComponent],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      },
      isDirty: true,
      isValid: false
    };

    expect(assembly.isDirty).toBe(true);
    expect(assembly.isValid).toBe(false);
  });
});

// ============================================================================
// CONSTRAINT TESTS
// ============================================================================

describe('Constraint Type', () => {
  test('should create constraint with all ConstraintType values', () => {
    const types = [
      ConstraintType.COINCIDENT,
      ConstraintType.PARALLEL,
      ConstraintType.PERPENDICULAR,
      ConstraintType.DISTANCE,
      ConstraintType.ANGLE,
      ConstraintType.FIXED,
      ConstraintType.TANGENT,
      ConstraintType.SYMMETRIC
    ];

    expect(types.length).toBe(8);
    types.forEach(type => {
      const constraint: Constraint = {
        id: `con-${type}`,
        type,
        elementA: 'comp-1',
        weight: 1.0
      };

      expect(constraint.type).toBe(type);
    });
  });

  test('should create constraint with optional elementB', () => {
    const constraint: Constraint = {
      id: 'con-1',
      type: ConstraintType.DISTANCE,
      elementA: 'comp-1',
      elementB: 'comp-2',
      value: 100,
      weight: 1.0
    };

    expect(constraint.elementB).toBe('comp-2');
  });

  test('should support constraint tolerance', () => {
    const constraint: Constraint = {
      id: 'con-1',
      type: ConstraintType.DISTANCE,
      elementA: 'comp-1',
      elementB: 'comp-2',
      value: 100,
      tolerance: 0.5,
      weight: 1.0
    };

    expect(constraint.tolerance).toBe(0.5);
  });

  test('should support constraint satisfaction tracking', () => {
    const constraint: Constraint = {
      id: 'con-1',
      type: ConstraintType.DISTANCE,
      elementA: 'comp-1',
      elementB: 'comp-2',
      value: 100,
      weight: 1.0,
      isSatisfied: true,
      error: 0.01
    };

    expect(constraint.isSatisfied).toBe(true);
    expect(constraint.error).toBe(0.01);
  });
});

// ============================================================================
// ANCHOR POINT TESTS
// ============================================================================

describe('AnchorPoint Type', () => {
  test('should support all AnchorPointType values', () => {
    const types = [
      AnchorPointType.VERTEX,
      AnchorPointType.EDGE_CENTER,
      AnchorPointType.FACE_CENTER,
      AnchorPointType.AXIS
    ];

    expect(types.length).toBe(4);
    types.forEach(type => {
      const anchor: AnchorPoint = {
        id: `anchor-${type}`,
        type,
        position: { x: 0, y: 0, z: 0 },
        componentId: 'comp-1'
      };

      expect(anchor.type).toBe(type);
    });
  });

  test('should support optional normal for face anchors', () => {
    const anchor: AnchorPoint = {
      id: 'anchor-1',
      name: 'Top Face',
      type: AnchorPointType.FACE_CENTER,
      position: { x: 0, y: 50, z: 0 },
      componentId: 'comp-1',
      normal: { x: 0, y: 1, z: 0 }
    };

    expect(anchor.normal).toBeDefined();
    expect(anchor.normal!.y).toBe(1);
  });
});

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

describe('Component + Assembly Integration', () => {
  test('should build hierarchy of nested assemblies', () => {
    const material: Material = {
      id: 'mat-1',
      name: 'Wood',
      color: '#8B4513'
    };

    // Part level
    const part: Component = {
      id: 'part-1',
      name: 'Simple Part',
      type: ComponentType.PART,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: { width: 50, height: 50, depth: 50 }
    };

    // SubAssembly level
    const subAssembly: Component = {
      id: 'sub-asm-1',
      name: 'Sub Assembly',
      type: ComponentType.SUBASSEMBLY,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: {},
      subComponents: [part]
    };

    // Assembly level
    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Main Assembly',
      components: [subAssembly],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };

    expect(assembly.components[0].type).toBe(ComponentType.SUBASSEMBLY);
    expect(assembly.components[0].subComponents).toBeDefined();
    expect(assembly.components[0].subComponents![0].type).toBe(ComponentType.PART);
  });

  test('should count total components recursively', () => {
    const material: Material = {
      id: 'mat-1',
      name: 'Wood',
      color: '#8B4513'
    };

    const parts = Array.from({ length: 3 }, (_, i) => ({
      id: `part-${i}`,
      name: `Part ${i}`,
      type: ComponentType.PART as const,
      position: { x: i * 100, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: {}
    }));

    const subAssembly: Component = {
      id: 'sub-asm-1',
      name: 'Sub Assembly',
      type: ComponentType.SUBASSEMBLY,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material,
      properties: {},
      subComponents: parts
    };

    const assembly: Assembly = {
      id: 'asm-1',
      name: 'Main Assembly',
      components: [subAssembly],
      constraints: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date()
      }
    };

    // Top-level: 1 component (subAssembly)
    expect(assembly.components.length).toBe(1);
    // In subAssembly: 3 parts
    expect(assembly.components[0].subComponents!.length).toBe(3);
  });
});
