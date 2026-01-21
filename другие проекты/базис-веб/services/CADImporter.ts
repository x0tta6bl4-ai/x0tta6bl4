/**
 * ФАЗА 6: CAD Importer
 * Импорт CAD файлов (DXF, JSON, STEP, OBJ)
 */

import { Assembly, Component, Material, Point3D, ComponentType } from '../types/CADTypes';

export interface ImportResult {
  success: boolean;
  assembly: Assembly | null;
  errors: string[];
  warnings: string[];
}

/**
 * Импортер CAD форматов
 */
export class CADImporter {
  private readonly defaultMaterial: Material = {
    id: 'default',
    name: 'Default',
    color: '#D2B48C',
    density: 700,
    elasticModulus: 3200,
    poissonRatio: 0.3,
    textureType: 'wood_oak' as any
  };

  /**
   * Импортировать файл в зависимости от типа
   */
  public import(content: string | Buffer, fileType: string): ImportResult {
    const contentStr = typeof content === 'string' ? content : content.toString('utf8');
    
    switch (fileType.toLowerCase()) {
      case 'json':
        return this.importFromJSON(contentStr);
      case 'dxf':
        return this.importFromDXF(contentStr);
      case 'step':
      case 'stp':
        return this.importFromSTEP(contentStr);
      case 'obj':
        return this.importFromOBJ(contentStr);
      default:
        return {
          success: false,
          assembly: null,
          errors: [`Unsupported file type: ${fileType}`],
          warnings: []
        };
    }
  }

  /**
   * Импортировать JSON файл
   */
  public importFromJSON(jsonContent: string): ImportResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      const data = JSON.parse(jsonContent);
      
      let assembly: Assembly;
      if (data.assembly) {
        assembly = data.assembly;
      } else if (data.id && data.name) {
        assembly = data;
      } else {
        throw new Error('Invalid JSON structure');
      }

      const validation = this.validate(assembly);
      if (!validation.isValid) {
        return {
          success: false,
          assembly: null,
          errors: validation.errors,
          warnings
        };
      }

      return {
        success: true,
        assembly,
        errors,
        warnings
      };
    } catch (error) {
      errors.push(`Failed to parse JSON: ${error instanceof Error ? error.message : String(error)}`);
      return {
        success: false,
        assembly: null,
        errors,
        warnings
      };
    }
  }

  /**
   * Импортировать DXF файл (парсер базовых сущностей)
   */
  public importFromDXF(dxfContent: string): ImportResult {
    const errors: string[] = [];
    const warnings: string[] = [];
    const components: Component[] = [];

    try {
      const lines = dxfContent.split('\n');
      let i = 0;
      let currentEntity: any = null;
      let entityName = '';

      while (i < lines.length) {
        const line = lines[i].trim();

        if (line === '0') {
          if (currentEntity && entityName) {
            const component = this.createComponentFromDXFEntity(currentEntity, entityName);
            components.push(component);
          }
          i++;
          entityName = lines[i]?.trim() || '';
          currentEntity = {};
          i++;
        } else if (line === 'SECTION' && i + 2 < lines.length && lines[i + 2].trim() === 'ENTITIES') {
          i += 3;
        } else if (line === 'ENDSEC' || line === 'EOF') {
          if (currentEntity && entityName) {
            const component = this.createComponentFromDXFEntity(currentEntity, entityName);
            components.push(component);
          }
          break;
        } else {
          if (currentEntity && i + 1 < lines.length) {
            const key = line;
            const value = lines[i + 1]?.trim();
            if (value !== undefined) {
              currentEntity[key] = value;
              i++;
            }
          }
          i++;
        }
      }

      if (components.length === 0) {
        warnings.push('No entities found in DXF file');
      }

      const assembly: Assembly = {
        id: `imported-dxf-${Date.now()}`,
        name: 'Imported from DXF',
        components,
        constraints: []
      };

      return {
        success: true,
        assembly,
        errors,
        warnings
      };
    } catch (error) {
      errors.push(`Failed to parse DXF: ${error instanceof Error ? error.message : String(error)}`);
      return {
        success: false,
        assembly: null,
        errors,
        warnings
      };
    }
  }

  /**
   * Импортировать STEP файл (парсер базовых сущностей)
   */
  public importFromSTEP(stepContent: string): ImportResult {
    const errors: string[] = [];
    const warnings: string[] = [];
    const components: Component[] = [];

    try {
      const lines = stepContent.split('\n');
      let inData = false;

      for (const line of lines) {
        if (line.includes('PRODUCT_DEFINITION')) {
          const nameMatch = line.match(/PRODUCT_DEFINITION\('([^']+)'/);
          if (nameMatch) {
            const component: Component = {
              id: `step-component-${components.length}`,
              name: nameMatch[1],
              type: ComponentType.PART,
              position: { x: 0, y: 0, z: 0 },
              rotation: { x: 0, y: 0, z: 0 },
              material: this.defaultMaterial,
              properties: {},
              geometry: {
                type: '3D',
                vertices: [],
                faces: [],
                boundingBox: {
                  min: { x: 0, y: 0, z: 0 },
                  max: { x: 100, y: 100, z: 100 }
                }
              }
            };
            components.push(component);
          }
        }
        if (line.includes('END-ISO-10303-21')) {
          inData = false;
        }
      }

      if (components.length === 0) {
        warnings.push('No PRODUCT_DEFINITION entities found in STEP file');
      }

      const assembly: Assembly = {
        id: `imported-step-${Date.now()}`,
        name: 'Imported from STEP',
        components,
        constraints: []
      };

      return {
        success: true,
        assembly,
        errors,
        warnings
      };
    } catch (error) {
      errors.push(`Failed to parse STEP: ${error instanceof Error ? error.message : String(error)}`);
      return {
        success: false,
        assembly: null,
        errors,
        warnings
      };
    }
  }

  /**
   * Импортировать OBJ файл (Wavefront)
   */
  public importFromOBJ(objContent: string): ImportResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      const lines = objContent.split('\n');
      const vertices: Point3D[] = [];
      const faces: number[][] = [];
      let currentGroup = 'default';

      for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('v ')) {
          const parts = trimmed.substring(2).split(/\s+/).map(parseFloat);
          if (parts.length >= 3) {
            vertices.push({ x: parts[0], y: parts[1], z: parts[2] });
          }
        } else if (trimmed.startsWith('f ')) {
          const indices = trimmed.substring(2).split(/\s+/);
          const face: number[] = [];
          for (const idx of indices) {
            const vertexIdx = parseInt(idx.split('/')[0]) - 1;
            if (vertexIdx >= 0 && vertexIdx < vertices.length) {
              face.push(vertexIdx);
            }
          }
          if (face.length >= 3) {
            faces.push(face);
          }
        } else if (trimmed.startsWith('g ')) {
          currentGroup = trimmed.substring(2);
        }
      }

      if (vertices.length === 0) {
        warnings.push('No vertices found in OBJ file');
      }

      const minX = Math.min(...vertices.map(v => v.x), 0);
      const maxX = Math.max(...vertices.map(v => v.x), 100);
      const minY = Math.min(...vertices.map(v => v.y), 0);
      const maxY = Math.max(...vertices.map(v => v.y), 100);
      const minZ = Math.min(...vertices.map(v => v.z), 0);
      const maxZ = Math.max(...vertices.map(v => v.z), 100);

      const component: Component = {
        id: `obj-component`,
        name: 'Imported OBJ',
        type: ComponentType.PART,
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        material: this.defaultMaterial,
        properties: {},
        geometry: {
          type: '3D',
          vertices,
          faces,
          boundingBox: {
            min: { x: minX, y: minY, z: minZ },
            max: { x: maxX, y: maxY, z: maxZ }
          }
        }
      };

      const assembly: Assembly = {
        id: `imported-obj-${Date.now()}`,
        name: 'Imported from OBJ',
        components: [component],
        constraints: []
      };

      return {
        success: true,
        assembly,
        errors,
        warnings
      };
    } catch (error) {
      errors.push(`Failed to parse OBJ: ${error instanceof Error ? error.message : String(error)}`);
      return {
        success: false,
        assembly: null,
        errors,
        warnings
      };
    }
  }

  /**
   * Валидировать сборку
   */
  public validate(assembly: Assembly): {
    isValid: boolean;
    errors: string[];
  } {
    const errors: string[] = [];

    if (!assembly.id) {
      errors.push('Assembly must have id');
    }
    if (!assembly.name) {
      errors.push('Assembly must have name');
    }
    if (!Array.isArray(assembly.components)) {
      errors.push('Components must be array');
    }

    for (let i = 0; i < (assembly.components?.length || 0); i++) {
      const component = assembly.components![i];
      if (!component.id) {
        errors.push(`Component ${i} must have id`);
      }
      if (!component.name) {
        errors.push(`Component ${i} must have name`);
      }
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Создать компонент из DXF сущности
   */
  private createComponentFromDXFEntity(entity: any, entityType: string): Component {
    const x = parseFloat(entity['10']) || 0;
    const y = parseFloat(entity['20']) || 0;
    const z = parseFloat(entity['30']) || 0;

    return {
      id: `dxf-${entityType}-${Date.now()}`,
      name: entity['8'] || entityType,
      type: ComponentType.PART,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      material: this.defaultMaterial,
      properties: {},
      geometry: {
        type: '3D',
        vertices: [],
        faces: [],
        boundingBox: {
          min: { x: x - 50, y: y - 50, z: z - 25 },
          max: { x: x + 50, y: y + 50, z: z + 25 }
        }
      }
    };
  }
}
