import { Panel, Axis } from "../types";

export interface CollisionResult {
  panelA: string;
  panelB: string;
  distance: number;
}

interface BoundingBox {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  minZ: number;
  maxZ: number;
}

export class CollisionValidator {
  /**
   * Вычисляет bounding box панели с учётом rotation
   */
  private static getBoundingBox(panel: Panel): BoundingBox {
    let dimX = 0, dimY = 0, dimZ = 0;
    
    // Определяем реальные размеры в 3D пространстве с учётом rotation
    // depth это толщина, всегда occupies одну ось
    if (panel.rotation === Axis.X) {
      // Поворот вокруг X: width->Z, height->Y, depth->X
      dimX = panel.depth;
      dimY = panel.height;
      dimZ = panel.width;
    } else if (panel.rotation === Axis.Y) {
      // Поворот вокруг Y: width->Z, height->Y, depth->X
      dimX = panel.depth;
      dimY = panel.height;
      dimZ = panel.width;
    } else {
      // Нет поворота (Axis.Z): width->X, height->Y, depth->Z
      dimX = panel.width;
      dimY = panel.height;
      dimZ = panel.depth;
    }
    
    return {
      minX: panel.x,
      maxX: panel.x + dimX,
      minY: panel.y,
      maxY: panel.y + dimY,
      minZ: panel.z,
      maxZ: panel.z + dimZ
    };
  }

  public static validate(panels: Panel[]): CollisionResult[] {
    const results: CollisionResult[] = [];
    const tolerance = 0.5; // Минимальный зазор в мм для избегания ложных срабатываний
    
    // Проверяем каждую пару панелей на пересечение
    for (let i = 0; i < panels.length; i++) {
      for (let j = i + 1; j < panels.length; j++) {
        const p1 = panels[i];
        const p2 = panels[j];
        
        // Пропускаем невидимые панели
        if (!p1.visible || !p2.visible) continue;
        
        const box1 = this.getBoundingBox(p1);
        const box2 = this.getBoundingBox(p2);
        
        // Проверяем 3D AABB пересечение с толерансом
        const xOverlap = box1.minX < box2.maxX - tolerance && box1.maxX > box2.minX + tolerance;
        const yOverlap = box1.minY < box2.maxY - tolerance && box1.maxY > box2.minY + tolerance;
        const zOverlap = box1.minZ < box2.maxZ - tolerance && box1.maxZ > box2.minZ + tolerance;
        
        if (xOverlap && yOverlap && zOverlap) {
          const distance = Math.sqrt(
            Math.pow((box1.minX + (box1.maxX - box1.minX)/2) - (box2.minX + (box2.maxX - box2.minX)/2), 2) +
            Math.pow((box1.minY + (box1.maxY - box1.minY)/2) - (box2.minY + (box2.maxY - box2.minY)/2), 2) +
            Math.pow((box1.minZ + (box1.maxZ - box1.minZ)/2) - (box2.minZ + (box2.maxZ - box2.minZ)/2), 2)
          );
          
          results.push({
            panelA: p1.name,
            panelB: p2.name,
            distance
          });
        }
      }
    }
    
    return results;
  }
}
