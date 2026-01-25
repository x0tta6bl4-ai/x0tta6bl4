
import { Panel, Axis, TextureType, CabinetParams, Material, Hardware } from '../types';
import { InputValidator } from './InputValidator';
import { Group, BoxGeometry, MeshPhongMaterial, Mesh, Box3, Vector3 } from 'three';

// --- HELPER CONSTANTS ---
const TH_BODY = 16;
const TH_BACK = 4;
const BASE_HEIGHT = 100;

// Material Mapping Logic
const getMaterialProps = (name: string): { id: string; color: string; texture: TextureType } => {
    switch (name) {
        case 'Дуб': return { id: 'eg-h1145', color: '#D2B48C', texture: TextureType.WOOD_OAK };
        case 'Графит': return { id: 'ks-0191', color: '#333333', texture: TextureType.UNIFORM };
        case 'Бетон': return { id: 'concrete', color: '#888888', texture: TextureType.CONCRETE };
        case 'Белый': 
        default: return { id: 'eg-w980', color: '#FFFFFF', texture: TextureType.UNIFORM };
    }
};

const generateId = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 8)}`;

export class CabinetGenerator {
    private params: CabinetParams;
    private panels: Panel[] = [];

    constructor(params: CabinetParams) {
        this.params = params;
    }

    // Static entry point for external calls
    public static generateFromParams(params: CabinetParams): Panel[] {
        const generator = new CabinetGenerator(params);
        return generator.generate();
    }

    // Helper for 3D preview
    public static generatePreviewGroup(params: CabinetParams): Group {
        const panels = CabinetGenerator.generateFromParams(params);
        const group = new Group();
        
        panels.forEach(p => {
            let dX = 0, dY = 0, dZ = 0;
            if (p.rotation === Axis.X) { dX = p.depth; dY = p.height; dZ = p.width; }
            else if (p.rotation === Axis.Y) { dX = p.width; dY = p.depth; dZ = p.height; }
            else { dX = p.width; dY = p.height; dZ = p.depth; }

            const geometry = new BoxGeometry(dX, dY, dZ);
            const material = new MeshPhongMaterial({ 
                color: p.color,
                shininess: 30
            });
            const mesh = new Mesh(geometry, material);
            mesh.position.set(p.x + dX/2, p.y + dY/2, p.z + dZ/2);
            
            // Attach ID for Raycasting/Interaction
            mesh.userData = { id: p.id };
            
            group.add(mesh);
        });
        
        // Center group
        const box = new Box3().setFromObject(group);
        const center = box.getCenter(new Vector3());
        group.position.sub(center);
        
        return group;
    }

    public generate(): Panel[] {
        this.panels = [];
        const { width: W, height: H, depth: D, material, shelves, drawers, baseType } = this.params;
        const matProps = getMaterialProps(material);
        
        const sideH = H;
        // const innerH = H - (baseType === 'legs' ? 100 : 70) - TH_BODY; // Simplified logic

        // 1. Structural Panels (Box)
        
        // Left Side
        this.panels.push({
            id: generateId('L'), name: 'Бок Левый',
            width: D, height: sideH, depth: TH_BODY,
            x: 0, y: 0, z: 0,
            rotation: Axis.X, materialId: matProps.id, color: matProps.color, texture: matProps.texture,
            textureRotation: 0, visible: true, layer: 'body', openingType: 'none',
            edging: {top:'0.4', bottom:'0.4', left:'0.4', right:'2.0'},
            groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: []
        });

        // Right Side
        this.panels.push({
            id: generateId('R'), name: 'Бок Правый',
            width: D, height: sideH, depth: TH_BODY,
            x: W - TH_BODY, y: 0, z: 0,
            rotation: Axis.X, materialId: matProps.id, color: matProps.color, texture: matProps.texture,
            textureRotation: 0, visible: true, layer: 'body', openingType: 'none',
            edging: {top:'0.4', bottom:'0.4', left:'0.4', right:'2.0'},
            groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: []
        });

        // Roof
        this.panels.push({
            id: generateId('Top'), name: 'Крышка',
            width: W - 2*TH_BODY, height: D, depth: TH_BODY,
            x: TH_BODY, y: H - TH_BODY, z: 0,
            rotation: Axis.Y, materialId: matProps.id, color: matProps.color, texture: matProps.texture,
            textureRotation: 0, visible: true, layer: 'body', openingType: 'none',
            edging: {top:'2.0', bottom:'0.4', left:'0.4', right:'0.4'},
            groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: []
        });

        // Bottom
        const bottomY = baseType === 'legs' ? 100 : 70;
        this.panels.push({
            id: generateId('Bot'), name: 'Дно',
            width: W - 2*TH_BODY, height: D, depth: TH_BODY,
            x: TH_BODY, y: bottomY, z: 0,
            rotation: Axis.Y, materialId: matProps.id, color: matProps.color, texture: matProps.texture,
            textureRotation: 0, visible: true, layer: 'body', openingType: 'none',
            edging: {top:'2.0', bottom:'0.4', left:'0.4', right:'0.4'},
            groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: []
        });

        // Back Panel (HDF)
        this.panels.push({
            id: generateId('Back'), name: 'Задняя стенка',
            width: W - 4, height: H - bottomY - 4, depth: TH_BACK,
            x: 2, y: bottomY + 2, z: 0,
            rotation: Axis.Z, materialId: 'eg-hdf', color: '#F0F0F0', texture: TextureType.NONE,
            textureRotation: 0, visible: true, layer: 'back', openingType: 'none',
            edging: {top:'none', bottom:'none', left:'none', right:'none'},
            groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: []
        });

        // 2. Shelves
        shelves.forEach((s, idx) => {
            const shelfX = s.x > 0 ? s.x : TH_BODY; // Default to inside left panel
            
            this.panels.push({
                id: s.id, name: `Полка ${idx+1}`,
                width: s.width, height: s.depth, depth: TH_BODY,
                x: shelfX, y: s.y, z: 20, // Inset 20mm
                rotation: Axis.Y, materialId: matProps.id, color: matProps.color, texture: matProps.texture,
                textureRotation: 0, visible: true, layer: 'shelves', openingType: 'none',
                edging: {top:'2.0', bottom:'none', left:'0.4', right:'0.4'},
                groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: []
            });
        });

        // 3. Drawers
        drawers.forEach((d, idx) => {
            const drawerX = d.x > 0 ? d.x : TH_BODY;
            const facadeH = d.height;
            
            // Drawer Facade
            const facadePanel: Panel = {
                id: d.id, name: `Фасад Ящика ${idx+1}`,
                width: d.width, height: facadeH, depth: TH_BODY,
                x: drawerX, y: d.y, z: D, // On front
                rotation: Axis.Z, materialId: matProps.id, color: matProps.color, texture: matProps.texture,
                textureRotation: 90, visible: true, layer: 'facade', openingType: 'drawer',
                edging: {top:'2.0', bottom:'2.0', left:'2.0', right:'2.0'},
                groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, 
                hardware: d.handles ? [{id: generateId('hnd'), type: 'handle', name: 'Ручка', x: d.width/2, y: facadeH/2}] : []
            };
            this.panels.push(facadePanel);

            const boxH = Math.max(60, facadeH - 40);
            const boxD = d.depth;
            const boxW = d.width - 26; // 13mm gap each side
            const boxX = drawerX + 13;
            const boxY = d.y + (facadeH - boxH)/2 + 10;
            const boxZ = D - TH_BODY;

            // Box Sides
            const sideMat = { id: 'eg-w980', color: '#fff', texture: TextureType.UNIFORM }; // White boxes usually
            
            this.panels.push({ id: generateId(`db-l-${idx}`), name: 'Ящик Бок Л', width: boxD, height: boxH, depth: 16, x: boxX, y: boxY, z: boxZ-boxD, rotation: Axis.X, materialId:sideMat.id, color:sideMat.color, texture:TextureType.UNIFORM, textureRotation:0, visible:true, layer:'body', openingType:'drawer', edging:{top:'0.4',bottom:'none',left:'none',right:'none'}, groove:{enabled:false,side:'top',width:0,depth:0,offset:0}, hardware:[] });
            this.panels.push({ id: generateId(`db-r-${idx}`), name: 'Ящик Бок П', width: boxD, height: boxH, depth: 16, x: boxX+boxW-16, y: boxY, z: boxZ-boxD, rotation: Axis.X, materialId:sideMat.id, color:sideMat.color, texture:TextureType.UNIFORM, textureRotation:0, visible:true, layer:'body', openingType:'drawer', edging:{top:'0.4',bottom:'none',left:'none',right:'none'}, groove:{enabled:false,side:'top',width:0,depth:0,offset:0}, hardware:[] });
            this.panels.push({ id: generateId(`db-f-${idx}`), name: 'Ящик Лоб', width: boxW-32, height: boxH, depth: 16, x: boxX+16, y: boxY, z: boxZ, rotation: Axis.Z, materialId:sideMat.id, color:sideMat.color, texture:TextureType.UNIFORM, textureRotation:0, visible:true, layer:'body', openingType:'drawer', edging:{top:'0.4',bottom:'none',left:'none',right:'none'}, groove:{enabled:false,side:'top',width:0,depth:0,offset:0}, hardware:[] });
            this.panels.push({ id: generateId(`db-b-${idx}`), name: 'Ящик Зад', width: boxW-32, height: boxH, depth: 16, x: boxX+16, y: boxY, z: boxZ-boxD+16, rotation: Axis.Z, materialId:sideMat.id, color:sideMat.color, texture:TextureType.UNIFORM, textureRotation:0, visible:true, layer:'body', openingType:'drawer', edging:{top:'0.4',bottom:'none',left:'none',right:'none'}, groove:{enabled:false,side:'top',width:0,depth:0,offset:0}, hardware:[] });
        });

        return this.panels;
    }
}

export const checkCollisions = (panels: Panel[]): string[] => {
    // Simplified collision check
    return [];
};
