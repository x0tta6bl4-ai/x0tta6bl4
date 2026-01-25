import { Panel } from "../types";

export interface CollisionResult {
  panelA: string;
  panelB: string;
  distance: number;
}

export class CollisionValidator {
  public static validate(panels: Panel[]): CollisionResult[] {
    const results: CollisionResult[] = [];
    
    // Проверяем каждую пару панелей на пересечение
    for (let i = 0; i < panels.length; i++) {
      for (let j = i + 1; j < panels.length; j++) {
        const p1 = panels[i];
        const p2 = panels[j];
        
        // Проверяем 3D бокс пересечения
        const xOverlap = !(p1.x + p1.width <= p2.x || p2.x + p2.width <= p1.x);
        const yOverlap = !(p1.y + p1.height <= p2.y || p2.y + p2.height <= p1.y);
        const zOverlap = !(p1.z + p1.depth <= p2.z || p2.z + p2.depth <= p1.z);
        
        if (xOverlap && yOverlap && zOverlap) {
          const distance = Math.sqrt(
            Math.pow((p1.x + p1.width/2) - (p2.x + p2.width/2), 2) +
            Math.pow((p1.y + p1.height/2) - (p2.y + p2.height/2), 2) +
            Math.pow((p1.z + p1.depth/2) - (p2.z + p2.depth/2), 2)
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
