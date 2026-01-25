/**
 * GEOMETRY KERNEL - Геометрическое ядро
 * 
 * B-Rep операции для мебели:
 * - Создание панелей (Box)
 * - Скругления (Fillet)
 * - Пазы (Groove)
 * - Отверстия (Hole)
 */

import { Body, Face, Edge, Vertex, Vector3, AABB } from './CADTypes';

export class GeometryKernel {
  /**
   * Создать прямоугольную панель
   */
  static createPanel(
    x: number,
    y: number,
    z: number,
    width: number,
    height: number,
    depth: number,
    name: string = 'Panel'
  ): Body {
    // Вершины прямоугольника (8 вершин куба)
    const vertices: Vertex[] = [
      // Front face
      { id: 'v0', position: { x, y, z }, edges: [], normal: { x: 0, y: 0, z: 1 } },
      { id: 'v1', position: { x: x + width, y, z }, edges: [], normal: { x: 0, y: 0, z: 1 } },
      { id: 'v2', position: { x: x + width, y: y + height, z }, edges: [], normal: { x: 0, y: 0, z: 1 } },
      { id: 'v3', position: { x, y: y + height, z }, edges: [], normal: { x: 0, y: 0, z: 1 } },
      
      // Back face
      { id: 'v4', position: { x, y, z: z + depth }, edges: [], normal: { x: 0, y: 0, z: -1 } },
      { id: 'v5', position: { x: x + width, y, z: z + depth }, edges: [], normal: { x: 0, y: 0, z: -1 } },
      { id: 'v6', position: { x: x + width, y: y + height, z: z + depth }, edges: [], normal: { x: 0, y: 0, z: -1 } },
      { id: 'v7', position: { x, y: y + height, z: z + depth }, edges: [], normal: { x: 0, y: 0, z: -1 } }
    ];

    // Рёбра (12 рёбер куба)
    const edges: Edge[] = [
      // Front face edges
      { id: 'e0', v1: vertices[0], v2: vertices[1], length: width, faces: [], isCurved: false },
      { id: 'e1', v1: vertices[1], v2: vertices[2], length: height, faces: [], isCurved: false },
      { id: 'e2', v1: vertices[2], v2: vertices[3], length: width, faces: [], isCurved: false },
      { id: 'e3', v1: vertices[3], v2: vertices[0], length: height, faces: [], isCurved: false },
      
      // Back face edges
      { id: 'e4', v1: vertices[4], v2: vertices[5], length: width, faces: [], isCurved: false },
      { id: 'e5', v1: vertices[5], v2: vertices[6], length: height, faces: [], isCurved: false },
      { id: 'e6', v1: vertices[6], v2: vertices[7], length: width, faces: [], isCurved: false },
      { id: 'e7', v1: vertices[7], v2: vertices[4], length: height, faces: [], isCurved: false },
      
      // Vertical edges
      { id: 'e8', v1: vertices[0], v2: vertices[4], length: depth, faces: [], isCurved: false },
      { id: 'e9', v1: vertices[1], v2: vertices[5], length: depth, faces: [], isCurved: false },
      { id: 'e10', v1: vertices[2], v2: vertices[6], length: depth, faces: [], isCurved: false },
      { id: 'e11', v1: vertices[3], v2: vertices[7], length: depth, faces: [], isCurved: false }
    ];

    // Грани (6 граней куба)
    const faces: Face[] = [
      // Front face
      {
        id: 'face_front',
        vertices: [vertices[0], vertices[1], vertices[2], vertices[3]],
        edges: [edges[0], edges[1], edges[2], edges[3]],
        normal: { x: 0, y: 0, z: -1 },
        area: width * height,
        isPlanar: true,
        surfaceType: 'planar',
        isVisible: true,
        isSelectable: true,
        color: '#d2b48c'
      },
      // Back face
      {
        id: 'face_back',
        vertices: [vertices[4], vertices[5], vertices[6], vertices[7]],
        edges: [edges[4], edges[5], edges[6], edges[7]],
        normal: { x: 0, y: 0, z: 1 },
        area: width * height,
        isPlanar: true,
        surfaceType: 'planar',
        isVisible: true,
        isSelectable: true,
        color: '#d2b48c'
      },
      // Top face
      {
        id: 'face_top',
        vertices: [vertices[3], vertices[2], vertices[6], vertices[7]],
        edges: [edges[2], edges[10], edges[6], edges[11]],
        normal: { x: 0, y: 1, z: 0 },
        area: width * depth,
        isPlanar: true,
        surfaceType: 'planar',
        isVisible: true,
        isSelectable: true,
        color: '#d2b48c'
      },
      // Bottom face
      {
        id: 'face_bottom',
        vertices: [vertices[0], vertices[1], vertices[5], vertices[4]],
        edges: [edges[0], edges[9], edges[4], edges[8]],
        normal: { x: 0, y: -1, z: 0 },
        area: width * depth,
        isPlanar: true,
        surfaceType: 'planar',
        isVisible: true,
        isSelectable: true,
        color: '#d2b48c'
      },
      // Left face
      {
        id: 'face_left',
        vertices: [vertices[0], vertices[3], vertices[7], vertices[4]],
        edges: [edges[3], edges[11], edges[7], edges[8]],
        normal: { x: -1, y: 0, z: 0 },
        area: height * depth,
        isPlanar: true,
        surfaceType: 'planar',
        isVisible: true,
        isSelectable: true,
        color: '#d2b48c'
      },
      // Right face
      {
        id: 'face_right',
        vertices: [vertices[1], vertices[2], vertices[6], vertices[5]],
        edges: [edges[1], edges[10], edges[5], edges[9]],
        normal: { x: 1, y: 0, z: 0 },
        area: height * depth,
        isPlanar: true,
        surfaceType: 'planar',
        isVisible: true,
        isSelectable: true,
        color: '#d2b48c'
      }
    ];

    // Bounding box
    const boundingBox: AABB = {
      min: { x, y, z },
      max: { x: x + width, y: y + height, z: z + depth },
      center: { x: x + width / 2, y: y + height / 2, z: z + depth / 2 },
      size: { x: width, y: height, z: depth }
    };

    // Вычислить объём
    const volume = width * height * depth;

    const body: Body = {
      id: `body_${Date.now()}`,
      name,
      shells: [{ id: 'shell_0', faces, isClosed: true, isWatertight: true }],
      faces,
      edges,
      vertices,
      boundingBox,
      volume,
      isVisible: true,
      isLocked: false,
      createdAt: new Date(),
      modifiedAt: new Date()
    };

    return body;
  }

  /**
   * Создать скругление (fillet) на ребре
   */
  static fillet(body: Body, edgeId: string, radius: number): Body {
    const edge = body.edges.find(e => e.id === edgeId);
    if (!edge) {
      console.warn(`Edge not found: ${edgeId}`);
      return body;
    }

    // Отметить ребро как скруглённое
    edge.isCurved = true;
    edge.curvatureRadius = radius;

    // Обновить связанные грани для скругления
    edge.faces.forEach(faceId => {
      const face = body.faces.find(f => f.id === faceId);
      if (face) {
        face.surfaceType = 'cylindrical';
      }
    });

    return body;
  }

  /**
   * Создать паз (groove) на грани
   */
  static groove(
    body: Body,
    faceId: string,
    width: number,
    depth: number,
    offset: number
  ): Body {
    const face = body.faces.find(f => f.id === faceId);
    if (!face) {
      console.warn(`Face not found: ${faceId}`);
      return body;
    }

    // Паз представлен как изменение геометрии грани
    // В реальности это требует булевой операции
    console.log(`[GeometryKernel] Groove on ${faceId}: width=${width}, depth=${depth}, offset=${offset}`);

    return body;
  }

  /**
   * Создать отверстие (hole)
   */
  static hole(
    body: Body,
    faceId: string,
    position: Vector3,
    diameter: number,
    depth: number
  ): Body {
    const face = body.faces.find(f => f.id === faceId);
    if (!face) {
      console.warn(`Face not found: ${faceId}`);
      return body;
    }

    // Отверстие - это вычитание цилиндра из панели
    console.log(
      `[GeometryKernel] Hole on ${faceId}: ` +
      `position=(${position.x},${position.y},${position.z}), ` +
      `diameter=${diameter}, depth=${depth}`
    );

    return body;
  }

  /**
   * Булева операция - объединение (union)
   */
  static union(body1: Body, body2: Body): Body {
    const result: Body = {
      id: `union_${Date.now()}`,
      name: `${body1.name} ∪ ${body2.name}`,
      shells: [...body1.shells, ...body2.shells],
      faces: [...body1.faces, ...body2.faces],
      edges: [...body1.edges, ...body2.edges],
      vertices: [...body1.vertices, ...body2.vertices],
      boundingBox: this.mergeBounds(body1.boundingBox, body2.boundingBox),
      volume: (body1.volume || 0) + (body2.volume || 0),
      isVisible: true,
      isLocked: false,
      createdAt: new Date(),
      modifiedAt: new Date()
    };

    return result;
  }

  /**
   * Булева операция - вычитание (subtract)
   */
  static subtract(body1: Body, body2: Body): Body {
    const result: Body = {
      id: `subtract_${Date.now()}`,
      name: `${body1.name} - ${body2.name}`,
      shells: body1.shells,
      faces: body1.faces,
      edges: body1.edges,
      vertices: body1.vertices,
      boundingBox: body1.boundingBox,
      volume: Math.max(0, (body1.volume || 0) - (body2.volume || 0)),
      isVisible: true,
      isLocked: false,
      createdAt: new Date(),
      modifiedAt: new Date()
    };

    return result;
  }

  /**
   * Вычислить пересечение двух AABB
   */
  static intersectBounds(box1: AABB, box2: AABB): AABB | null {
    const min = {
      x: Math.max(box1.min.x, box2.min.x),
      y: Math.max(box1.min.y, box2.min.y),
      z: Math.max(box1.min.z, box2.min.z)
    };

    const max = {
      x: Math.min(box1.max.x, box2.max.x),
      y: Math.min(box1.max.y, box2.max.y),
      z: Math.min(box1.max.z, box2.max.z)
    };

    if (min.x >= max.x || min.y >= max.y || min.z >= max.z) {
      return null; // No intersection
    }

    return {
      min,
      max,
      center: {
        x: (min.x + max.x) / 2,
        y: (min.y + max.y) / 2,
        z: (min.z + max.z) / 2
      },
      size: {
        x: max.x - min.x,
        y: max.y - min.y,
        z: max.z - min.z
      }
    };
  }

  /**
   * Объединить AABB двух тел
   */
  private static mergeBounds(box1: AABB, box2: AABB): AABB {
    const min = {
      x: Math.min(box1.min.x, box2.min.x),
      y: Math.min(box1.min.y, box2.min.y),
      z: Math.min(box1.min.z, box2.min.z)
    };

    const max = {
      x: Math.max(box1.max.x, box2.max.x),
      y: Math.max(box1.max.y, box2.max.y),
      z: Math.max(box1.max.z, box2.max.z)
    };

    return {
      min,
      max,
      center: {
        x: (min.x + max.x) / 2,
        y: (min.y + max.y) / 2,
        z: (min.z + max.z) / 2
      },
      size: {
        x: max.x - min.x,
        y: max.y - min.y,
        z: max.z - min.z
      }
    };
  }
}

export default GeometryKernel;
