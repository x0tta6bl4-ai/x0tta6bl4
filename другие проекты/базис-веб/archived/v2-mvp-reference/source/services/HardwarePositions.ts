
import { Panel, Hardware } from '../types';

export class HardwarePositions {
    
    private static generateId = () => `hw-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

    /**
     * Calculates hinge cup positions (Blum Standard)
     * @param panelHeight Height of the facade
     * @param offsetTop Distance from top edge (default 100mm)
     * @param offsetBottom Distance from bottom edge (default 100mm)
     * @param side 'left' or 'right' opening
     */
    public static calculateHinges(panel: Panel, side: 'left' | 'right' = 'left'): Hardware[] {
        const result: Hardware[] = [];
        const cupDist = 22; // Center of cup from edge
        const x = side === 'left' ? cupDist : panel.width - cupDist;
        
        // Top Hinge
        result.push({
            id: this.generateId(),
            type: 'hinge_cup',
            name: 'Петля Blum Top',
            x: x,
            y: panel.height - 100,
            diameter: 35,
            depth: 13,
            price: 150
        });

        // Bottom Hinge
        result.push({
            id: this.generateId(),
            type: 'hinge_cup',
            name: 'Петля Blum Bot',
            x: x,
            y: 100,
            diameter: 35,
            depth: 13,
            price: 150
        });

        // Middle Hinge for tall doors (> 900mm)
        if (panel.height > 900) {
            result.push({
                id: this.generateId(),
                type: 'hinge_cup',
                name: 'Петля Blum Mid',
                x: x,
                y: panel.height / 2,
                diameter: 35,
                depth: 13,
                price: 150
            });
        }

        return result;
    }

    /**
     * Generates System 32 grid for shelf pins
     * @param panelHeight Panel height
     * @param panelDepth Panel depth (width in local coords for side panels)
     */
    public static calculateSystem32(panel: Panel): Hardware[] {
        const result: Hardware[] = [];
        const startY = 200;
        const endY = panel.height - 200;
        const frontX = 37;
        const backX = panel.width - 37; // Assuming local width is depth for side panels in 2D context

        // Generate holes every 32mm
        for (let y = startY; y <= endY; y += 32) {
            // Front Column
            result.push({
                id: this.generateId(),
                type: 'shelf_support',
                name: 'Полкодержатель',
                x: frontX,
                y: y,
                diameter: 5,
                depth: 13, // Standard blind hole
                price: 5
            });

            // Back Column
            result.push({
                id: this.generateId(),
                type: 'shelf_support',
                name: 'Полкодержатель',
                x: backX,
                y: y,
                diameter: 5,
                depth: 13,
                price: 5
            });
        }

        return result;
    }

    /**
     * Calculates handle position
     * @param panelWidth Width of facade
     * @param panelHeight Height of facade
     * @param centerDist Distance between holes (96, 128, 160)
     */
    public static calculateHandle(panel: Panel, centerDist: number = 128): Hardware[] {
        const result: Hardware[] = [];
        const centerX = panel.width / 2;
        // Standard placement: 50mm from top edge for base units, or centered vertically for drawers
        const y = panel.openingType === 'drawer' ? panel.height / 2 : panel.height - 50; 

        result.push({
            id: this.generateId(),
            type: 'handle',
            name: `Ручка ${centerDist}mm`,
            x: centerX - (centerDist / 2),
            y: y,
            diameter: 5,
            depth: panel.depth, // Through hole
            isThrough: true,
            price: 100
        });

        result.push({
            id: this.generateId(),
            type: 'handle',
            name: `Ручка ${centerDist}mm`,
            x: centerX + (centerDist / 2),
            y: y,
            diameter: 5,
            depth: panel.depth,
            isThrough: true,
            price: 0 // Price included in first hole/handle object usually, but for drilling map we need holes
        });

        return result;
    }
}
