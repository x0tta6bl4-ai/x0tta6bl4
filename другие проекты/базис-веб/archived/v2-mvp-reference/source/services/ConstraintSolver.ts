
import { Assembly, Point3D, ConstraintType } from "../types/CADTypes";

// Helper math
const dist = (p1: Point3D, p2: Point3D) => Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2) + Math.pow(p1.z - p2.z, 2));
const sub = (p1: Point3D, p2: Point3D) => ({ x: p1.x - p2.x, y: p1.y - p2.y, z: p1.z - p2.z });
const add = (p1: Point3D, p2: Point3D) => ({ x: p1.x + p2.x, y: p1.y + p2.y, z: p1.z + p2.z });
const mul = (p: Point3D, s: number) => ({ x: p.x * s, y: p.y * s, z: p.z * s });

export class ConstraintSolver {
  solve(assembly: Assembly, initialPositions: Map<string, Point3D>) {
    const positions = new Map<string, Point3D>();
    initialPositions.forEach((v, k) => positions.set(k, { ...v }));

    const iterations = 100;
    const tolerance = 0.1;
    let error = 0;

    const fixedNodes = new Set<string>();
    assembly.constraints.forEach(c => {
        if (c.type === ConstraintType.FIXED) fixedNodes.add(c.elementA);
    });

    for (let i = 0; i < iterations; i++) {
        error = 0;
        for (const c of assembly.constraints) {
            if (c.type === ConstraintType.DISTANCE && c.elementB && c.value !== undefined) {
                const pA = positions.get(c.elementA);
                const pB = positions.get(c.elementB);
                if (!pA || !pB) continue;

                const d = dist(pA, pB);
                const diff = d - c.value;
                error += Math.abs(diff);

                if (d > 0.0001) {
                    const correction = diff / d;
                    const move = mul(sub(pA, pB), correction * 0.5);
                    
                    const fixedA = fixedNodes.has(c.elementA);
                    const fixedB = fixedNodes.has(c.elementB);

                    if (!fixedA && !fixedB) {
                        positions.set(c.elementA, sub(pA, move));
                        positions.set(c.elementB, add(pB, move));
                    } else if (!fixedA && fixedB) {
                        positions.set(c.elementA, sub(pA, mul(move, 2)));
                    } else if (fixedA && !fixedB) {
                        positions.set(c.elementB, add(pB, mul(move, 2)));
                    }
                }
            }
        }
        if (error < tolerance) break;
    }

    return {
      converged: error < tolerance,
      iterations,
      error,
      positions
    };
  }
}
