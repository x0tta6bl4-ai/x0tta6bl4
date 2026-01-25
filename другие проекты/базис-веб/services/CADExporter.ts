/**
 * ФАЗА 6: CAD Exporter
 * Экспорт сборки в различные CAD форматы (STL, DXF, JSON, OBJ)
 */

import { Assembly, ExportFormat, ExportOptions, Point3D, Component } from '../types/CADTypes';

export interface Triangle {
  v1: Point3D;
  v2: Point3D;
  v3: Point3D;
  normal?: Point3D;
}

/**
 * Экспортер CAD форматов
 */
export class CADExporter {
  /**
   * Экспортировать сборку в различные форматы
   */
  public export(assembly: Assembly, options: ExportOptions): Buffer | string {
    switch (options.format) {
      case ExportFormat.STL:
        return this.exportToSTL(assembly, options);
      case ExportFormat.DXF:
        return this.exportToDXF(assembly, options);
      case ExportFormat.JSON:
        return this.exportToJSON(assembly, options);
      case ExportFormat.OBJ:
        return this.exportToOBJ(assembly, options);
      case ExportFormat.STEP:
        return this.exportToSTEP(assembly, options);
      case ExportFormat.IGES:
        return this.exportToIGES(assembly, options);
      case ExportFormat.GLTF:
        return this.exportToGLTF(assembly, options);
      default:
        throw new Error(`Unsupported export format: ${options.format}`);
    }
  }

  /**
   * Экспортировать в STL (для 3D печати)
   */
  private exportToSTL(assembly: Assembly, options: ExportOptions): Buffer {
    const triangles: Triangle[] = [];

    if (assembly.components) {
      for (const component of assembly.components) {
        const componentTriangles = this.generateComponentTriangles(component);
        triangles.push(...componentTriangles);
      }
    }

    return this.generateSTLBinary(triangles, assembly.name || 'assembly');
  }

  /**
   * Генерировать STL бинарный формат
   */
  private generateSTLBinary(triangles: Triangle[], name: string): Buffer {
    const header = Buffer.alloc(80);
    header.write(name.substring(0, 79), 0, 'utf8');

    const triangleCount = triangles.length;
    const data = Buffer.alloc(84 + triangles.length * 50);

    data.writeUInt32LE(triangleCount, 80);

    for (let i = 0; i < triangles.length; i++) {
      const offset = 84 + i * 50;
      const tri = triangles[i];
      const normal = tri.normal || this.computeNormal(tri.v1, tri.v2, tri.v3);

      data.writeFloatLE(normal.x, offset);
      data.writeFloatLE(normal.y, offset + 4);
      data.writeFloatLE(normal.z, offset + 8);

      data.writeFloatLE(tri.v1.x, offset + 12);
      data.writeFloatLE(tri.v1.y, offset + 16);
      data.writeFloatLE(tri.v1.z, offset + 20);

      data.writeFloatLE(tri.v2.x, offset + 24);
      data.writeFloatLE(tri.v2.y, offset + 28);
      data.writeFloatLE(tri.v2.z, offset + 32);

      data.writeFloatLE(tri.v3.x, offset + 36);
      data.writeFloatLE(tri.v3.y, offset + 40);
      data.writeFloatLE(tri.v3.z, offset + 44);

      data.writeUInt16LE(0, offset + 48);
    }

    return Buffer.concat([header, data]);
  }

  /**
   * Экспортировать в JSON (для веб-визуализации)
   */
  private exportToJSON(assembly: Assembly, options: ExportOptions): string {
    const scale = options.scale || 1.0;
    const precision = options.precision !== undefined ? options.precision : 2;

    const exportData = {
      metadata: {
        format: 'json',
        version: '1.0',
        name: assembly.name,
        exportedAt: new Date().toISOString()
      },
      assembly: {
        id: assembly.id,
        name: assembly.name,
        components: assembly.components?.map(c => this.serializeComponent(c, scale)) || []
      }
    };

    return JSON.stringify(exportData, null, precision);
  }

  /**
   * Экспортировать в DXF (для AutoCAD)
   */
  private exportToDXF(assembly: Assembly, options: ExportOptions): string {
    const dxf: string[] = [];

    dxf.push('0');
    dxf.push('SECTION');
    dxf.push('2');
    dxf.push('HEADER');
    dxf.push('9');
    dxf.push('$ACADVER');
    dxf.push('1');
    dxf.push('AC1027');
    dxf.push('0');
    dxf.push('ENDSEC');

    dxf.push('0');
    dxf.push('SECTION');
    dxf.push('2');
    dxf.push('ENTITIES');

    if (assembly.components) {
      for (const component of assembly.components) {
        const dxfEntities = this.generateDXFEntities(component);
        dxf.push(...dxfEntities);
      }
    }

    dxf.push('0');
    dxf.push('ENDSEC');
    dxf.push('0');
    dxf.push('EOF');

    return dxf.join('\n');
  }

  /**
   * Экспортировать в OBJ (Wavefront)
   */
  private exportToOBJ(assembly: Assembly, options: ExportOptions): string {
    const obj: string[] = [];

    obj.push(`# Wavefront OBJ export of ${assembly.name}`);
    obj.push(`# Created at ${new Date().toISOString()}`);
    obj.push('');

    let vertexOffset = 1;
    const scale = options.scale || 1.0;

    if (assembly.components) {
      for (const component of assembly.components) {
        obj.push(`# Component: ${component.name}`);
        
        const triangles = this.generateComponentTriangles(component);
        const vertices: Point3D[] = [];
        const indices: number[][] = [];

        for (const tri of triangles) {
          const v1Idx = this.findOrAddVertex(vertices, tri.v1);
          const v2Idx = this.findOrAddVertex(vertices, tri.v2);
          const v3Idx = this.findOrAddVertex(vertices, tri.v3);
          indices.push([v1Idx + vertexOffset, v2Idx + vertexOffset, v3Idx + vertexOffset]);
        }

        for (const v of vertices) {
          obj.push(`v ${(v.x * scale).toFixed(4)} ${(v.y * scale).toFixed(4)} ${(v.z * scale).toFixed(4)}`);
        }

        for (const idx of indices) {
          obj.push(`f ${idx[0]} ${idx[1]} ${idx[2]}`);
        }

        vertexOffset += vertices.length;
        obj.push('');
      }
    }

    return obj.join('\n');
  }

  /**
   * Экспортировать в STEP (ISO 10303-21)
   */
  private exportToSTEP(assembly: Assembly, options: ExportOptions): Buffer {
    const step: string[] = [];

    step.push('ISO-10303-21;');
    step.push('HEADER;');
    step.push('FILE_DESCRIPTION((\'A minimal STEP file\'),\'2;1\');');
    step.push(`FILE_NAME('${assembly.name}.step',${Date.now()},(''),(''),\'CAD System\',\'\',\'\');`);
    step.push('FILE_SCHEMA((\'IFC4\'));');
    step.push('ENDSEC;');
    step.push('DATA;');

    let entityId = 1;
    if (assembly.components) {
      for (const component of assembly.components) {
        const stepEntity = `#${entityId}=PRODUCT_DEFINITION('${component.name}','${component.name}',#${entityId + 1},#${entityId + 2});`;
        step.push(stepEntity);
        entityId += 3;
      }
    }

    step.push('ENDSEC;');
    step.push('END-ISO-10303-21;');

    return Buffer.from(step.join('\n'), 'utf8');
  }

  /**
   * Экспортировать в IGES
   */
  private exportToIGES(assembly: Assembly, options: ExportOptions): Buffer {
    const iges: string[] = [];

    iges.push(`                                                                        S      1`);
    iges.push(`1H,,1H,13HCAD System,2HUU,32,308,15,308,15,${Date.now()},1.0E-07,1.0,2HUU,`);
    iges.push(`1,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,G      1`);
    iges.push(`S      1G      2D      1P      1`);

    return Buffer.from(iges.join('\n'), 'utf8');
  }

  /**
   * Экспортировать в glTF 2.0 (базовая реализация)
   */
  private exportToGLTF(assembly: Assembly, options: ExportOptions): Buffer {
    const gltf = {
      asset: { version: '2.0' },
      scene: 0,
      scenes: [{ nodes: [0] }],
      nodes: [
        {
          mesh: 0,
          translation: [0, 0, 0],
          scale: [1, 1, 1]
        }
      ],
      meshes: [
        {
          name: assembly.name,
          primitives: [
            {
              attributes: { POSITION: 0 },
              indices: 1,
              mode: 4
            }
          ]
        }
      ],
      accessors: [
        {
          bufferView: 0,
          componentType: 5126,
          count: 24,
          type: 'VEC3'
        },
        {
          bufferView: 1,
          componentType: 5125,
          count: 36,
          type: 'SCALAR'
        }
      ],
      bufferViews: [
        { buffer: 0, byteOffset: 0, byteStride: 12 },
        { buffer: 0, byteOffset: 288 }
      ],
      buffers: [{ byteLength: 432 }]
    };

    return Buffer.from(JSON.stringify(gltf), 'utf8');
  }

  /**
   * Сгенерировать треугольники компонента
   */
  private generateComponentTriangles(component: Component): Triangle[] {
    const triangles: Triangle[] = [];

    if (!component.geometry) {
      return triangles;
    }

    const geom = component.geometry;
    if (geom.type === '3D' && geom.vertices && geom.faces) {
      for (const face of geom.faces) {
        if (Array.isArray(face) && face.length >= 3) {
          const v1 = geom.vertices[face[0]];
          const v2 = geom.vertices[face[1]];
          const v3 = geom.vertices[face[2]];

          if (v1 && v2 && v3) {
            triangles.push({
              v1: { x: v1.x || 0, y: v1.y || 0, z: v1.z || 0 },
              v2: { x: v2.x || 0, y: v2.y || 0, z: v2.z || 0 },
              v3: { x: v3.x || 0, y: v3.y || 0, z: v3.z || 0 }
            });
          }
        }
      }
    }

    if (triangles.length === 0) {
      triangles.push(...this.generateBoxTriangles(component));
    }

    return triangles;
  }

  /**
   * Генерировать треугольники для прямоугольного ящика
   */
  private generateBoxTriangles(component: Component): Triangle[] {
    const triangles: Triangle[] = [];
    const bbox = component.geometry?.boundingBox;

    if (!bbox) return triangles;

    const minX = bbox.min?.x ?? -50;
    const minY = bbox.min?.y ?? -50;
    const minZ = bbox.min?.z ?? -25;
    const maxX = bbox.max?.x ?? 50;
    const maxY = bbox.max?.y ?? 50;
    const maxZ = bbox.max?.z ?? 25;

    const vertices = [
      { x: minX, y: minY, z: minZ },
      { x: maxX, y: minY, z: minZ },
      { x: maxX, y: maxY, z: minZ },
      { x: minX, y: maxY, z: minZ },
      { x: minX, y: minY, z: maxZ },
      { x: maxX, y: minY, z: maxZ },
      { x: maxX, y: maxY, z: maxZ },
      { x: minX, y: maxY, z: maxZ }
    ];

    const faces = [
      [0, 1, 2], [0, 2, 3],
      [4, 6, 5], [4, 7, 6],
      [0, 4, 5], [0, 5, 1],
      [2, 6, 7], [2, 7, 3],
      [0, 3, 7], [0, 7, 4],
      [1, 5, 6], [1, 6, 2]
    ];

    for (const face of faces) {
      triangles.push({
        v1: vertices[face[0]],
        v2: vertices[face[1]],
        v3: vertices[face[2]]
      });
    }

    return triangles;
  }

  /**
   * Вычислить нормаль треугольника
   */
  private computeNormal(v1: Point3D, v2: Point3D, v3: Point3D): Point3D {
    const a = { x: v2.x - v1.x, y: v2.y - v1.y, z: v2.z - v1.z };
    const b = { x: v3.x - v1.x, y: v3.y - v1.y, z: v3.z - v1.z };

    const normal = {
      x: a.y * b.z - a.z * b.y,
      y: a.z * b.x - a.x * b.z,
      z: a.x * b.y - a.y * b.x
    };

    const len = Math.sqrt(normal.x ** 2 + normal.y ** 2 + normal.z ** 2);
    if (len > 0) {
      normal.x /= len;
      normal.y /= len;
      normal.z /= len;
    }

    return normal;
  }

  /**
   * Генерировать DXF сущности для компонента
   */
  private generateDXFEntities(component: Component): string[] {
    const entities: string[] = [];
    const bbox = component.geometry?.boundingBox;

    if (!bbox) return entities;

    entities.push('0');
    entities.push('3DSOLID');
    entities.push('8');
    entities.push(component.name || 'Component');
    entities.push('10');
    entities.push((bbox.min?.x ?? 0).toString());
    entities.push('20');
    entities.push((bbox.min?.y ?? 0).toString());
    entities.push('30');
    entities.push((bbox.min?.z ?? 0).toString());

    return entities;
  }

  /**
   * Сериализовать компонент для JSON
   */
  private serializeComponent(component: Component, scale: number): any {
    return {
      id: component.id,
      name: component.name,
      type: component.type,
      boundingBox: component.geometry?.boundingBox ? {
        min: {
          x: (component.geometry.boundingBox.min?.x ?? 0) * scale,
          y: (component.geometry.boundingBox.min?.y ?? 0) * scale,
          z: (component.geometry.boundingBox.min?.z ?? 0) * scale
        },
        max: {
          x: (component.geometry.boundingBox.max?.x ?? 0) * scale,
          y: (component.geometry.boundingBox.max?.y ?? 0) * scale,
          z: (component.geometry.boundingBox.max?.z ?? 0) * scale
        }
      } : null
    };
  }

  /**
   * Найти или добавить вершину в массив
   */
  private findOrAddVertex(vertices: Point3D[], vertex: Point3D): number {
    const epsilon = 0.0001;
    for (let i = 0; i < vertices.length; i++) {
      const v = vertices[i];
      if (Math.abs(v.x - vertex.x) < epsilon &&
          Math.abs(v.y - vertex.y) < epsilon &&
          Math.abs(v.z - vertex.z) < epsilon) {
        return i;
      }
    }
    vertices.push(vertex);
    return vertices.length - 1;
  }
}
