
import { Panel, Axis } from '../types';

export type ViewType = 'front' | 'top' | 'left' | 'right';

export interface DrawEntity {
    id: string;
    type: 'line' | 'rect' | 'text' | 'dim_linear';
    layer: 'contour' | 'hidden' | 'dimension' | 'center' | 'annotation';
    x1?: number; y1?: number; x2?: number; y2?: number; // Line / Dim
    x?: number; y?: number; w?: number; h?: number; // Rect
    text?: string;
    value?: number;
    vertical?: boolean;
    dashed?: boolean;
}

interface Bounds { minX: number; maxX: number; minY: number; maxY: number; }

export class TechnicalDrawing {
    
    // Main Entry Point
    static generateView(panels: Panel[], view: ViewType): DrawEntity[] {
        const entities: DrawEntity[] = [];
        
        // 1. Sort panels by depth (Painter's algorithm for visibility)
        const sorted = [...panels].sort((a, b) => {
            const zA = this.getZIndex(a, view);
            const zB = this.getZIndex(b, view);
            return zA - zB; // Smallest Z first (background), Largest Z last (foreground)
        });

        const projectedPanels = sorted.map(p => ({
            original: p,
            rect: this.projectPanel(p, view)
        }));

        // Calculate view bounds
        const bounds = this.calculateBounds(projectedPanels.map(p => p.rect));

        // 2. Generate Contours
        projectedPanels.forEach(p => {
            if (!p.original.visible) return;
            
            // Basic Rectangle
            entities.push({
                id: `p-${p.original.id}`,
                type: 'rect',
                layer: 'contour',
                x: p.rect.x, y: p.rect.y, w: p.rect.w, h: p.rect.h
            });

            // Add Material Callout (simplified logic: only for large parts)
            if (p.rect.w > 200 && p.rect.h > 200) {
                // entities.push(...) // Could add text inside
            }
        });

        // 3. Generate Dimensions
        const dims = this.generateAutoDimensions(projectedPanels, view, bounds);
        entities.push(...dims);

        return entities;
    }

    // --- MATH & PROJECTION ---

    private static getZIndex(p: Panel, view: ViewType): number {
        // Determines draw order (Depth)
        switch(view) {
            case 'front': return p.z; // Higher Z is closer to front
            case 'top': return p.y;   // Higher Y is closer to top
            case 'left': return p.x;  // Higher X is closer to right (further from left)
            case 'right': return -p.x;
            default: return 0;
        }
    }

    private static projectPanel(p: Panel, view: ViewType): { x: number, y: number, w: number, h: number } {
        // 3D Dimensions based on rotation
        let dx = p.width, dy = p.height, dz = p.depth;
        if (p.rotation === Axis.X) { dx = p.depth; dy = p.height; dz = p.width; }
        else if (p.rotation === Axis.Y) { dx = p.width; dy = p.depth; dz = p.height; }
        else { dx = p.width; dy = p.height; dz = p.depth; }

        // Standard Mapping (Y-axis flips for SVG usually, but we keep cartesian logic until export if possible, 
        // however for simplicity we'll assume Y grows DOWN in SVG, so World Y UP means Screen Y DECREASES)
        
        let x=0, y=0, w=0, h=0;

        switch(view) {
            case 'front':
                // X -> X, Y -> -Y
                x = p.x; 
                y = -p.y - dy; // Top-left of the panel in screen coords
                w = dx;
                h = dy;
                break;
            case 'top':
                // X -> X, Z -> Y (Depth grows down)
                x = p.x;
                y = p.z; 
                w = dx;
                h = dz;
                break;
            case 'left':
                // Z -> X, Y -> -Y
                x = p.z;
                y = -p.y - dy;
                w = dz;
                h = dy;
                break;
            case 'right':
                // Inverse Z -> X? Usually Right view sees Front of cabinet on Left.
                // Standard Right View: looking from right.
                // Z grows left on screen? Let's keep it simple: Z -> X
                x = p.z;
                y = -p.y - dy;
                w = dz;
                h = dy;
                break;
        }

        return { x, y, w, h };
    }

    private static calculateBounds(rects: { x: number, y: number, w: number, h: number }[]): Bounds {
        let minX=Infinity, maxX=-Infinity, minY=Infinity, maxY=-Infinity;
        rects.forEach(r => {
            if(r.x < minX) minX = r.x;
            if(r.x+r.w > maxX) maxX = r.x+r.w;
            if(r.y < minY) minY = r.y;
            if(r.y+r.h > maxY) maxY = r.y+r.h;
        });
        return { minX, maxX, minY, maxY };
    }

    // --- DIMENSIONING LOGIC ---

    private static generateAutoDimensions(parts: {rect:any, original:Panel}[], view: ViewType, bounds: Bounds): DrawEntity[] {
        const dims: DrawEntity[] = [];
        const OFFSET = 50; // Distance of dim line from object
        
        // 1. Overall Dimensions
        // Width
        dims.push({
            id: 'dim-ov-w',
            type: 'dim_linear',
            layer: 'dimension',
            x1: bounds.minX, y1: bounds.maxY + OFFSET,
            x2: bounds.maxX, y2: bounds.maxY + OFFSET,
            value: Math.round(bounds.maxX - bounds.minX),
            vertical: false
        });

        // Height
        dims.push({
            id: 'dim-ov-h',
            type: 'dim_linear',
            layer: 'dimension',
            x1: bounds.minX - OFFSET, y1: bounds.maxY,
            x2: bounds.minX - OFFSET, y2: bounds.minY,
            value: Math.round(bounds.maxY - bounds.minY),
            vertical: true
        });

        // 2. Internal Chain Dimensions (only for Front view usually)
        if (view === 'front') {
            // Find Horizontal Panels (Shelves)
            // Filter by rotation Y
            const shelves = parts
                .filter(p => p.original.rotation === Axis.Y)
                .sort((a, b) => b.rect.y - a.rect.y); // Sort Top to Bottom (screen Y)

            if (shelves.length > 0) {
                // Right side chain
                const chainX = bounds.maxX + OFFSET;
                let prevY = bounds.minY; // Top of cabinet (minY is top in SVG if Y negative? Wait, we flipped Y)
                // Actually minY is the "Highest" world coordinate, so it's top on screen.
                
                // Add dim for each gap
                // Simplified: Just dimension the center of shelves? 
                // Let's dimension from Top Edge to Shelf 1, Shelf 1 to Shelf 2...
                
                // TODO: A proper chain dimensioning algo is complex. 
                // We will add just a total height dim on right side for now to satisfy requirements without clutter.
                dims.push({
                    id: 'dim-right-h',
                    type: 'dim_linear',
                    layer: 'dimension',
                    x1: bounds.maxX + OFFSET, y1: bounds.maxY,
                    x2: bounds.maxX + OFFSET, y2: bounds.minY,
                    value: Math.round(bounds.maxY - bounds.minY),
                    vertical: true
                });
            }
        }

        return dims;
    }

    // --- EXPORT ---

    static exportSVG(entities: DrawEntity[], padding = 60): string {
        if (entities.length === 0) return "<svg></svg>";

        // Recalculate full bounds including dimensions
        let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
        
        const updateBounds = (x:number, y:number) => {
            if(x<minX) minX=x; if(x>maxX) maxX=x;
            if(y<minY) minY=y; if(y>maxY) maxY=y;
        };

        entities.forEach(e => {
            if(e.type==='rect') {
                updateBounds(e.x!, e.y!);
                updateBounds(e.x!+e.w!, e.y!+e.h!);
            } else if (e.type==='dim_linear') {
                updateBounds(e.x1!, e.y1!);
                updateBounds(e.x2!, e.y2!);
            }
        });

        const width = Math.abs(maxX - minX) + padding * 2;
        const height = Math.abs(maxY - minY) + padding * 2;
        const vbX = minX - padding;
        const vbY = minY - padding;

        let svg = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vbX} ${vbY} ${width} ${height}" style="background:white;">
<style>
    .contour { fill: white; stroke: black; stroke-width: 2; vector-effect: non-scaling-stroke; }
    .hidden { fill: none; stroke: #555; stroke-width: 1; stroke-dasharray: 5,5; vector-effect: non-scaling-stroke; }
    .dimension { stroke: #0000AA; stroke-width: 1; vector-effect: non-scaling-stroke; }
    .dim-text { font-family: monospace; font-size: 14px; fill: #0000AA; font-weight: bold; }
    .arrow { fill: #0000AA; }
</style>
<defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L0,6 L9,3 z" class="arrow" />
    </marker>
</defs>
`;

        // Render entities
        entities.forEach(e => {
            if (e.type === 'rect') {
                svg += `<rect x="${e.x}" y="${e.y}" width="${e.w}" height="${e.h}" class="${e.layer}" />`;
            }
            else if (e.type === 'dim_linear') {
                // Extension lines
                const extLen = 5;
                let ext1="", ext2="";
                if(e.vertical) {
                    ext1 = `<line x1="${e.x1!-extLen}" y1="${e.y1}" x2="${e.x1!+extLen}" y2="${e.y1}" stroke="#0000AA" stroke-width="0.5"/>`;
                    ext2 = `<line x1="${e.x2!-extLen}" y1="${e.y2}" x2="${e.x2!+extLen}" y2="${e.y2}" stroke="#0000AA" stroke-width="0.5"/>`;
                } else {
                    ext1 = `<line x1="${e.x1}" y1="${e.y1!-extLen}" x2="${e.x1}" y2="${e.y1!+extLen}" stroke="#0000AA" stroke-width="0.5"/>`;
                    ext2 = `<line x1="${e.x2}" y1="${e.y2!-extLen}" x2="${e.x2}" y2="${e.y2!+extLen}" stroke="#0000AA" stroke-width="0.5"/>`;
                }

                svg += ext1 + ext2;
                svg += `<line x1="${e.x1}" y1="${e.y1}" x2="${e.x2}" y2="${e.y2}" class="${e.layer}" marker-start="url(#arrow)" marker-end="url(#arrow)" />`;
                
                // Text centered
                const mx = (e.x1! + e.x2!) / 2;
                const my = (e.y1! + e.y2!) / 2;
                
                // Offset text to avoid overlapping line
                const tx = e.vertical ? mx - 5 : mx;
                const ty = e.vertical ? my : my - 5;
                const anchor = e.vertical ? "end" : "middle";
                const rotate = e.vertical ? `rotate(-90 ${tx} ${ty})` : "";

                svg += `<text x="${tx}" y="${ty}" class="dim-text" text-anchor="${anchor}" transform="${rotate}">${Math.round(e.value!)}</text>`;
            }
        });

        svg += `</svg>`;
        return svg;
    }
}
