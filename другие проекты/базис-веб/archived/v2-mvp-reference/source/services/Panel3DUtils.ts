
import { Panel, Axis } from "../types";

export interface Box3 { 
    minX: number; maxX: number; 
    minY: number; maxY: number; 
    minZ: number; maxZ: number; 
}

export interface Vec3 { x: number; y: number; z: number; }

export const vecAdd = (a: Vec3, b: Vec3): Vec3 => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z });
export const vecSub = (a: Vec3, b: Vec3): Vec3 => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
export const vecScale = (v: Vec3, s: number): Vec3 => ({ x: v.x * s, y: v.y * s, z: v.z * s });
export const vecLen = (v: Vec3): number => Math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z);

export const getPanelBounds = (p: Panel): Box3 => {
    let w=0, h=0, d=0;
    if(p.rotation === Axis.X) { w=p.depth; h=p.height; d=p.width; }
    else if(p.rotation === Axis.Y) { w=p.width; h=p.depth; d=p.height; }
    else { w=p.width; h=p.height; d=p.depth; }
    
    return { 
        minX: p.x, maxX: p.x+w, 
        minY: p.y, maxY: p.y+h, 
        minZ: p.z, maxZ: p.z+d 
    };
};

export const doPanelsIntersect = (p1: Panel, p2: Panel, tolerance = 0.5): boolean => {
    const b1 = getPanelBounds(p1);
    const b2 = getPanelBounds(p2);
    
    const overlapX = Math.min(b1.maxX, b2.maxX) - Math.max(b1.minX, b2.minX);
    const overlapY = Math.min(b1.maxY, b2.maxY) - Math.max(b1.minY, b2.minY);
    const overlapZ = Math.min(b1.maxZ, b2.maxZ) - Math.max(b1.minZ, b2.minZ);
    
    return overlapX > tolerance && overlapY > tolerance && overlapZ > tolerance;
};

export const getIntersectionInfo = (p1: Panel, p2: Panel) => {
    const b1 = getPanelBounds(p1);
    const b2 = getPanelBounds(p2);
    
    const overlapX = Math.max(0, Math.min(b1.maxX, b2.maxX) - Math.max(b1.minX, b2.minX));
    const overlapY = Math.max(0, Math.min(b1.maxY, b2.maxY) - Math.max(b1.minY, b2.minY));
    const overlapZ = Math.max(0, Math.min(b1.maxZ, b2.maxZ) - Math.max(b1.minZ, b2.minZ));
    
    return { overlapX, overlapY, overlapZ };
};

export const checkAllIntersections = (panels: Panel[], tolerance = 0.5) => {
    const intersections = [];
    const visiblePanels = panels.filter(p => p.visible);
    
    for(let i=0; i<visiblePanels.length; i++) {
        for(let j=i+1; j<visiblePanels.length; j++) {
            if(doPanelsIntersect(visiblePanels[i], visiblePanels[j], tolerance)) {
                const info = getIntersectionInfo(visiblePanels[i], visiblePanels[j]);
                intersections.push({ panelA: visiblePanels[i], panelB: visiblePanels[j], ...info });
            }
        }
    }
    return intersections;
};

export const validateAndRepairPanel = (panel: Panel) => {
    const issues: string[] = [];
    let repairedPanel: Panel | null = null;

    if(!panel.width || panel.width <= 0) issues.push("Width <= 0");
    if(!panel.height || panel.height <= 0) issues.push("Height <= 0");
    if(!panel.depth || panel.depth <= 0) issues.push("Depth <= 0");
    if(!panel.materialId) issues.push("Missing Material ID");

    // Repair logic
    if (issues.length > 0 || panel.width < 10 || panel.height < 10) {
        repairedPanel = { ...panel };
        if (!repairedPanel.width || repairedPanel.width < 10) repairedPanel.width = 100;
        if (!repairedPanel.height || repairedPanel.height < 10) repairedPanel.height = 100;
        if (!repairedPanel.depth || repairedPanel.depth <= 0) repairedPanel.depth = 16;
        if (!repairedPanel.materialId) repairedPanel.materialId = 'eg-w980';
    }
    
    return {
        isValid: issues.length === 0,
        issues,
        repairedPanel
    };
};

export const getPanelErrorDescription = (panel: Panel) => `Panel '${panel.name}' (ID: ${panel.id.slice(-4)})`;
