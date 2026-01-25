
import { Panel, Hardware, Axis } from '../types';

export class DxfExporter {
    
    public static export(panels: Panel[]): string {
        let dxf = "";
        
        // 1. Header (AutoCAD 2000 format)
        dxf += "999\nBazis-Web DXF Generator v2.0\n";
        dxf += "0\nSECTION\n2\nHEADER\n";
        dxf += "9\n$ACADVER\n1\nAC1015\n"; 
        dxf += "9\n$INSUNITS\n70\n4\n"; // Millimeters
        dxf += "0\nENDSEC\n";

        // 2. Tables (Layers)
        dxf += "0\nSECTION\n2\nTABLES\n";
        dxf += "0\nTABLE\n2\nLAYER\n";
        dxf += this.addLayer("0", 7);
        dxf += this.addLayer("PANELS", 7); // White/Black
        dxf += this.addLayer("DRILL_HOLES", 1); // Red - Standard for drilling
        dxf += this.addLayer("GROOVES", 5); // Blue
        dxf += "0\nENDTAB\n";
        dxf += "0\nENDSEC\n";

        // 3. Blocks (Definitions for Drills) - Optional if using pure circles, but good for structured DXF
        dxf += "0\nSECTION\n2\nBLOCKS\n";
        dxf += "0\nENDSEC\n";

        // 4. Entities
        dxf += "0\nSECTION\n2\nENTITIES\n";

        panels.forEach(panel => {
            if (!panel.visible) return;
            
            // Draw Panel Contour (Projected to Face)
            dxf += this.writePolyline(panel, "PANELS");
            
            // Draw Hardware
            panel.hardware.forEach(hw => {
               dxf += this.writeDrillHole(hw, panel);
            });

            // Draw Grooves
            if (panel.groove && panel.groove.enabled) {
               dxf += this.writeGroove(panel, "GROOVES");
            }
        });

        dxf += "0\nENDSEC\n";
        dxf += "0\nEOF\n";

        return dxf;
    }

    private static addLayer(name: string, color: number): string {
        let s = "0\nLAYER\n";
        s += `2\n${name}\n`;
        s += "70\n0\n";
        s += `62\n${color}\n`;
        s += "6\nCONTINUOUS\n";
        return s;
    }

    private static writePolyline(panel: Panel, layer: string): string {
        // Global coords corners
        const corners = this.getGlobalCorners(panel);
        
        // Draw 12 lines for the box (Wireframe)
        let s = "";
        const edges = [
            [0,1], [1,2], [2,3], [3,0], // Front face
            [4,5], [5,6], [6,7], [7,4], // Back face
            [0,4], [1,5], [2,6], [3,7]  // Connecting edges
        ];

        edges.forEach(edge => {
            const v1 = corners[edge[0]];
            const v2 = corners[edge[1]];
            s += "0\nLINE\n";
            s += `8\n${layer}\n`;
            s += `10\n${v1.x}\n20\n${v1.y}\n30\n${v1.z}\n`;
            s += `11\n${v2.x}\n21\n${v2.y}\n31\n${v2.z}\n`;
        });
        
        return s;
    }

    private static writeDrillHole(hw: Hardware, panel: Panel): string {
        // Transform local hole coords to world
        const p = this.getLocalToWorld(panel, hw.x, hw.y, hw.z || 0);
        
        // Write Circle Entity
        let s = "0\nCIRCLE\n";
        s += "8\nDRILL_HOLES\n";
        s += `10\n${p.x}\n20\n${p.y}\n30\n${p.z}\n`;
        s += `40\n${(hw.diameter || 5) / 2}\n`; // Radius

        // Determine orientation normal vector based on panel rotation
        let nx=0, ny=0, nz=1; // Default Z-up
        if (panel.rotation === Axis.X) { nx=1; ny=0; nz=0; } // Facing X
        if (panel.rotation === Axis.Y) { nx=0; ny=1; nz=0; } // Facing Y
        if (panel.rotation === Axis.Z) { nx=0; ny=0; nz=1; } // Facing Z
        
        s += `210\n${nx}\n220\n${ny}\n230\n${nz}\n`;

        // Write Text Label for CNC Operator
        // Offset text slightly from center
        const tx = p.x + (nx === 0 ? 5 : 0);
        const ty = p.y + (ny === 0 ? 5 : 0);
        const tz = p.z + (nz === 0 ? 5 : 0);
        
        s += "0\nTEXT\n";
        s += "8\nDRILL_HOLES\n";
        s += `10\n${tx}\n20\n${ty}\n30\n${tz}\n`;
        s += `40\n10\n`; // Text Height
        s += `1\nD${hw.diameter} H${hw.depth || 13}\n`; // Content
        s += `210\n${nx}\n220\n${ny}\n230\n${nz}\n`;

        return s;
    }

    private static writeGroove(panel: Panel, layer: string): string {
        // Simplified groove representation
        return ""; 
    }

    // --- MATH HELPERS ---

    private static getGlobalCorners(panel: Panel) {
        let w=0, h=0, d=0;
        if(panel.rotation === Axis.X) { w=panel.depth; h=panel.height; d=panel.width; }
        else if(panel.rotation === Axis.Y) { w=panel.width; h=panel.depth; d=panel.height; }
        else { w=panel.width; h=panel.height; d=panel.depth; }

        const x = panel.x; const y = panel.y; const z = panel.z;

        return [
            {x: x, y: y, z: z},
            {x: x+w, y: y, z: z},
            {x: x+w, y: y+h, z: z},
            {x: x, y: y+h, z: z},
            {x: x, y: y, z: z+d},
            {x: x+w, y: y, z: z+d},
            {x: x+w, y: y+h, z: z+d},
            {x: x, y: y+h, z: z+d},
        ];
    }

    private static getLocalToWorld(panel: Panel, lx: number, ly: number, lz: number) {
        // Simple mapping based on rotation axis being perpendicular to face
        // Panel origin is always minX, minY, minZ
        
        if (panel.rotation === Axis.Z) {
            // Panel plane is XY, Depth is Z
            // Local X -> World X, Local Y -> World Y
            return { x: panel.x + lx, y: panel.y + ly, z: panel.z + panel.depth };
        } else if (panel.rotation === Axis.Y) {
            // Panel plane is XZ (Horizontal), Height is Y
            // Local Width (X) -> World X
            // Local Depth (Y input from UI usually refers to 'Height' on 2D view, which maps to Depth Z here)
            return { x: panel.x + lx, y: panel.y + panel.height, z: panel.z + ly };
        } else {
            // Panel plane is YZ (Vertical Side), Width is X
            // Local Width (X in UI 2D view) -> World Z (Depth)
            // Local Height (Y in UI 2D view) -> World Y (Height)
            return { x: panel.x + panel.depth, y: panel.y + ly, z: panel.z + lx };
        }
    }
}
