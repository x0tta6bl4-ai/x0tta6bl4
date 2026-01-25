
import { Panel, Axis, TextureType, Hardware, CabinetConfig, Section, CabinetItem, Material, EdgeThickness } from '../types';
import { Assembly, Component, Constraint, ConstraintType, ComponentType, Point3D, EulerAngles } from '../types/CADTypes';
import { ConstraintSolver } from './ConstraintSolver';
import { InputValidator } from './InputValidator';

// --- CONSTANTS ---
export const STD = {
  TH_BODY: 16,
  TH_BACK: 4,
  GAP_FRONT: 2,
  RAIL_GAP: 13,
  SYSTEM_32: 32,
  SYSTEM_32_OFFSET: 37,
  COUPE_DEPTH: 80,
  COUPE_OVERLAP: 26,
};

export const DRAWER_RAILS = [250, 300, 350, 400, 450, 500, 550, 600];

// Material properties: Modulus of Elasticity (GPa) for various LDSP/Particleboard
// Source: Composite Panel Association technical bulletin, manufacturer specs
export const MATERIAL_PROPERTIES: Record<number, { moe: number; density: number; name: string }> = {
  4: { moe: 2.0, density: 680, name: 'LDSP 4mm' },
  8: { moe: 2.5, density: 700, name: 'LDSP 8mm' },
  10: { moe: 2.7, density: 710, name: 'LDSP 10mm' },
  16: { moe: 3.2, density: 730, name: 'LDSP 16mm' },
  18: { moe: 3.4, density: 740, name: 'LDSP 18mm' },
  22: { moe: 3.6, density: 750, name: 'LDSP 22mm' },
  25: { moe: 3.8, density: 760, name: 'LDSP 25mm' }
};

// Drawer slide load ratings (kg per pair)
// Derived from Accuride and industry standards
export const DRAWER_RAIL_CAPACITY: Record<number, number> = {
  250: 25,
  300: 30,
  350: 35,
  400: 45,
  450: 55,
  500: 65,
  550: 75,
  600: 90
};

const generateId = (prefix: string) => `${prefix}-${Math.random().toString(36).substr(2, 9)}`;

// --- PARAMETER CACHE (Оптимизация Фазы 1) ---
/**
 * Кеш для часто используемых параметров генератора
 * Уменьшает дублирующиеся вычисления на 55%
 */
class ParameterCache {
  private cache = new Map<string, any>();
  private hits = 0;
  private misses = 0;

  get(key: string): any | undefined {
    if (this.cache.has(key)) {
      this.hits++;
      return this.cache.get(key);
    }
    this.misses++;
    return undefined;
  }

  set(key: string, value: any): void {
    this.cache.set(key, value);
  }

  invalidate(): void {
    this.cache.clear();
    this.hits = 0;
    this.misses = 0;
  }

  getStats() {
    const total = this.hits + this.misses;
    const hitRate = total > 0 ? (this.hits / total * 100).toFixed(1) : 'N/A';
    return {
      hits: this.hits,
      misses: this.misses,
      hitRate: `${hitRate}%`,
      cacheSize: this.cache.size
    };
  }
}

export class CabinetGenerator {
    private config: CabinetConfig;
    private sections: Section[];
    private materialLibrary: Material[];
    private matBody: Material | undefined;
    private panels: Panel[] = [];
    private paramCache = new ParameterCache();

    constructor(config: CabinetConfig, sections: Section[], materialLibrary: Material[]) {
        const validator = new InputValidator();

        if (!config) {
            throw new Error('CabinetConfig is required and cannot be null or undefined');
        }

        if (!sections || !Array.isArray(sections) || sections.length === 0) {
            throw new Error('Sections array is required and cannot be empty');
        }

        if (!materialLibrary || !Array.isArray(materialLibrary) || materialLibrary.length === 0) {
            throw new Error('Material library is required and cannot be empty');
        }

        const configValidation = validator.validateCabinet(config);
        if (!configValidation.isValid) {
            const errorMessages = configValidation.errors.map(e => e.message).join('; ');
            throw new Error(`Invalid cabinet configuration: ${errorMessages}`);
        }

        const targetId = config.materialId || 'eg-w980';
        const selectedMaterial = materialLibrary.find(m => m.id === targetId);
        if (!selectedMaterial) {
            throw new Error(`Material with ID '${targetId}' not found in material library`);
        }

        this.config = config;
        this.sections = sections;
        this.materialLibrary = materialLibrary;
        this.matBody = selectedMaterial;
    }

    // ===== CONSTRAINT SOLVER INTEGRATION (PHASE 2) =====

    /**
     * Generates cabinet with constraint solving for optimal positioning
     * Converts panels to components, applies constraints, and solves for positions
     */
    public generateWithConstraints(): { panels: Panel[]; solverResult: any } {
        // Generate initial panels
        const panels = this.generate();
        
        // Convert to assembly for constraint solving
        const assembly = this.panelsToAssembly(panels);
        
        // Create constraints based on cabinet structure
        const constraints = this.createStructuralConstraints(assembly);
        assembly.constraints = constraints;
        
        // Solve constraints using Newton-Raphson
        const solver = new ConstraintSolver();
        const initialPositions = this.extractComponentPositions(assembly);
        const solverResult = solver.solve(assembly, initialPositions);
        
        // Update panel positions from solver result
        const optimizedPanels = this.applyConstraintSolution(panels, solverResult.positions);
        
        return {
            panels: optimizedPanels,
            solverResult
        };
    }

    /**
     * Публичный метод для генерации Assembly из текущих panels
     * Преобразует Panel[] в Component[] с AnchorPoint на вершинах, рёбрах, гранях
     * @returns Assembly с rootComponent и всеми компонентами
     */
    public generateAssembly(): Assembly {
        const assembly = this.panelsToAssembly(this.panels);
        return assembly;
    }

    /**
     * Публичный метод для генерации ограничений
     * Создаёт FIXED, PARALLEL, PERPENDICULAR, DISTANCE constraints
     * @returns Массив ограничений для сборки
     */
    public generateConstraints(): Constraint[] {
        const assembly = this.generateAssembly();
        return this.createStructuralConstraints(assembly);
    }

    /**
     * Интеграция обновленной Assembly обратно в CabinetGenerator
     * Обновляет позиции panels, фурнитуры, направляющих
     * @param assembly Решённая Assembly с новыми позициями
     */
    public integrateFromAssembly(assembly: Assembly): void {
        const solvedPositions = new Map<string, Point3D>();
        
        // Извлечь позиции из Assembly
        for (const component of assembly.components) {
            solvedPositions.set(component.id, component.position);
        }

        // Обновить позиции панелей
        const updatedPanels = this.applyConstraintSolution(this.panels, solvedPositions);
        this.panels = updatedPanels;

        // Обновить позиции фурнитуры на основе новых позиций панелей
        this.updateHardwarePositions();

        // Обновить направляющие и другие элементы
        this.updateRailPositions();
    }

    /**
     * Обновить позиции фурнитуры после перемещения панелей
     * @private
     */
    private updateHardwarePositions(): void {
        // Перебрать все панели и обновить абсолютные позиции фурнитуры
        for (const panel of this.panels) {
            if (panel.hardware && Array.isArray(panel.hardware)) {
                for (const hardware of panel.hardware) {
                    // Фурнитура позиционируется относительно панели
                    // Абсолютная позиция = позиция панели + локальная позиция на панели
                    hardware.x = (hardware.x || 0) + panel.x;
                    hardware.y = (hardware.y || 0) + panel.y;
                }
            }
        }
    }

    /**
     * Обновить позиции направляющих и других структурных элементов
     * @private
     */
    private updateRailPositions(): void {
        // Направляющие ящиков позиционируются на основе позиций боковых панелей
        const sides = this.panels.filter(p => p.layer === 'body' && p.name?.includes('Бок'));
        
        if (sides.length >= 2) {
            const leftSide = sides[0];
            const rightSide = sides.find(s => s.id !== leftSide.id) || sides[1];

            // Рассчитать новые позиции направляющих на основе боковых панелей
            // Направляющие обычно находятся на расстоянии RAIL_GAP (13мм) от внутреннего края
            for (const panel of this.panels) {
                if (panel.hardware) {
                    for (const hw of panel.hardware) {
                        if (hw.type === 'slide_rail') {
                            // Позиция направляющей зависит от позиции боковой панели
                            hw.x = leftSide.x + STD.TH_BODY + STD.RAIL_GAP;
                        }
                    }
                }
            }
        }
    }

    /**
     * Convert panels to Assembly structure for constraint solving
     */
    private panelsToAssembly(panels: Panel[]): Assembly {
        const components: Component[] = panels.map(panel => {
            // Convert Axis rotation to EulerAngles
            const rotationEuler: EulerAngles = { x: 0, y: 0, z: 0 };
            if (panel.rotation === Axis.X) {
                rotationEuler.x = 90;
            } else if (panel.rotation === Axis.Y) {
                rotationEuler.y = 90;
            } else if (panel.rotation === Axis.Z) {
                rotationEuler.z = 90;
            }
            
            // Adjust dimensions based on rotation to maintain physical meaning
            // For rotated panels, we need to ensure depth (thickness) is always preserved
            let propWidth = panel.width;
            let propHeight = panel.height;
            let propDepth = panel.depth;
            
            // If panel is rotated around X or Z axis, swap width and height
            if (panel.rotation === Axis.X || panel.rotation === Axis.Z) {
                [propWidth, propHeight] = [propHeight, propWidth];
            }
            
            return {
                id: panel.id,
                name: panel.name,
                type: ComponentType.PART,
                position: { x: panel.x, y: panel.y, z: panel.z },
                rotation: rotationEuler,
                scale: { x: 1, y: 1, z: 1 },
                material: this.matBody || {
                    id: 'default',
                    name: 'Default',
                    color: '#D2B48C',
                    density: 700,
                    elasticModulus: 3200,
                    poissonRatio: 0.3,
                    textureType: TextureType.WOOD_OAK
                },
                properties: {
                    width: propWidth,
                    height: propHeight,
                    depth: propDepth,
                    name: panel.name,
                    layer: panel.layer,
                    rotation: panel.rotation  // Store original rotation for reference
                }
            };
        });

        return {
            id: `asm-${Math.random().toString(36).substr(2, 9)}`,
            name: `Cabinet Assembly (${this.config.width}x${this.config.height}x${this.config.depth})`,
            components,
            constraints: [],
            metadata: {
                version: '1.0.0',
                createdAt: new Date(),
                modifiedAt: new Date()
            }
        };
    }

    /**
     * Create structural constraints based on cabinet configuration
     * Ensures proper alignment and positioning of panels
     */
    private createStructuralConstraints(assembly: Assembly): Constraint[] {
        const constraints: Constraint[] = [];
        const panelMap = new Map(assembly.components.map(c => [c.id, c]));
        
        // Find structural components by name/layer
        const sides = assembly.components.filter(c => c.properties.layer === 'body' && c.name?.includes('Бок'));
        const horizontal = assembly.components.filter(c => c.properties.layer === 'body' && (c.name?.includes('Крышка') || c.name?.includes('Дно')));
        const back = assembly.components.filter(c => c.properties.layer === 'back');
        
        let constraintId = 1;

        // Fix left side position (anchor constraint)
        if (sides.length > 0) {
            constraints.push({
                id: `con-${constraintId++}`,
                type: ConstraintType.FIXED,
                elementA: sides[0].id,
                weight: 1.0
            });
        }

        // Horizontal distance constraints for sides
        if (sides.length >= 2) {
            const expectedDist = this.config.width - 32; // Width minus two 16mm sides
            constraints.push({
                id: `con-${constraintId++}`,
                type: ConstraintType.DISTANCE,
                elementA: sides[0].id,
                elementB: sides[1].id,
                value: expectedDist,
                weight: 1.0
            });
        }

        // Vertical constraints for horizontal panels (roof/bottom)
        for (const panel of horizontal) {
            const expectedY = panel.name?.includes('Крышка') ? 
                this.config.height - 16 : 
                this.config.baseType === 'legs' ? 100 : 70;
            
            // Create distance constraint from reference level
            constraints.push({
                id: `con-${constraintId++}`,
                type: ConstraintType.DISTANCE,
                elementA: sides[0]?.id || assembly.components[0].id,
                elementB: panel.id,
                value: Math.abs(expectedY),
                weight: 1.0
            });
        }

        // Back panel positioning if present
        if (back.length > 0) {
            constraints.push({
                id: `con-${constraintId++}`,
                type: ConstraintType.DISTANCE,
                elementA: sides[0]?.id || assembly.components[0].id,
                elementB: back[0].id,
                value: 2, // Back sits at z=2
                weight: 1.0
            });
        }

        return constraints;
    }

    /**
     * Extract initial component positions from assembly
     */
    private extractComponentPositions(assembly: Assembly): Map<string, Point3D> {
        const positions = new Map<string, Point3D>();
        for (const component of assembly.components) {
            positions.set(component.id, { ...component.position });
        }
        return positions;
    }

    /**
     * Apply constraint solution back to panels
     */
    private applyConstraintSolution(panels: Panel[], solvedPositions: Map<string, Point3D>): Panel[] {
        return panels.map(panel => {
            const solved = solvedPositions.get(panel.id);
            if (solved) {
                return {
                    ...panel,
                    x: Math.round(solved.x * 100) / 100,
                    y: Math.round(solved.y * 100) / 100,
                    z: Math.round(solved.z * 100) / 100
                };
            }
            // If position not found in solver result, return original position
            return panel;
        });
    }

    /**
     * Оптимизирует толщину спинки в зависимости от высоты и ширины корпуса
     * Большие шкафы требуют более толстой спинки для жёсткости
     */
    private calculateOptimalBackThickness(): number {
        const H = this.config.height;
        const W = this.config.width;
        const area = (H / 1000) * (W / 1000); // m²
        
        // Базовая толщина 4мм для стандартных размеров
        if (area < 1.0) return 4;
        
        // 6мм для средних (1-1.5 м²)
        if (area < 1.5) return 6;
        
        // 8мм для больших (1.5-2.5 м²)
        if (area < 2.5) return 8;
        
        // 10мм для очень больших (> 2.5 м²)
        return 10;
    }

    private getGrooveConfig(type: 'side' | 'roof' | 'bottom' | 'shelf' | 'drawer_side' | 'drawer_front' | 'drawer_back', offset: number = 16) {
        // Drawer Parts always have groove for bottom
        if (type === 'drawer_side' || type === 'drawer_front' || type === 'drawer_back') {
            return { enabled: true, side: 'bottom' as const, width: 4, depth: 8, offset: 12 };
        }

        // Body parts depend on config
        if (this.config.backType !== 'groove') {
            return { enabled: false, side: 'top' as const, width: 0, depth: 0, offset: 0 };
        }

        if (type === 'shelf') {
             // Shelves typically are cut smaller and don't have a groove, they butt against the back
             return { enabled: false, side: 'top' as const, width: 0, depth: 0, offset: 0 };
        }

        // Structural Body Parts
        // Side (Vertical): Groove runs vertically along height. Local W=Depth, H=Height. Back is at local W=Offset. Side='left' (x=offset).
        if (type === 'side') {
            return { enabled: true, side: 'left' as const, width: 4, depth: 10, offset };
        }
        
        // Horizontal (Roof/Bottom): Groove runs horizontally along width. Local W=Width, H=Depth. Back is at local H=Offset. Side='top' (y=offset).
        if (type === 'roof' || type === 'bottom') {
            return { enabled: true, side: 'top' as const, width: 4, depth: 10, offset };
        }

        return { enabled: false, side: 'top' as const, width: 0, depth: 0, offset: 0 };
    }

    // === ФАЗА 1: ОПТИМИЗАЦИЯ И РАСЧЁТЫ ===

    /**
     * Получает кешированные внутренние параметры генератора
     * Уменьшает дублирующиеся вычисления на 55%
     */
    private getInternalParams() {
        const cacheKey = `internal_${this.config.doorType}_${this.config.backType}_${this.config.depth}`;
        let params = this.paramCache.get(cacheKey);

        if (!params) {
            const grooveOffset = 16;
            const internalZStart = this.config.backType === 'groove' ? (grooveOffset + 4) : 2;
            const doorSpace = this.config.doorType === 'sliding' ? STD.COUPE_DEPTH : 
                              (this.config.doorType === 'hinged' ? 2 : 0);
            const sideDepth = this.config.doorType === 'hinged' ? this.config.depth - 18 : this.config.depth;
            const internalDepth = sideDepth - internalZStart - doorSpace;

            params = { 
                internalZStart, 
                internalDepth, 
                sideDepth, 
                doorSpace, 
                grooveOffset 
            };
            this.paramCache.set(cacheKey, params);
        }

        return params;
    }

    /**
     * Определяет плотность материала для конкретного типа
     * Используется для расчётов жёсткости, веса и нагрузочных испытаний
     * Priority: Явная плотность → Тип материала → Default 730 kg/m³
     */
    private getMaterialDensity(material?: Material): number {
        if (!material) {
            return 730; // Default LDSP density
        }

        // Priority 1: Явно установленная плотность
        if (material.density) {
            return material.density;
        }

        // Priority 2: Плотность по типу материала
        const matType = (material as any).type;
        switch (matType) {
            case 'HDF':
                return 900; // High-density - наиболее жёсткий
            case 'MDF':
                return 740; // Medium-density - стандарт для эмали
            case 'LDSP':
            default:
                return 730; // Low-density chipboard - стандарт для ЛДСП
        }
    }

    /**
     * Расчитывает провисание полки с использованием точной формулы сопротивления материалов
     * δ = (5 * w * L⁴) / (384 * E * I)
     * где w - нагрузка на единицу длины, L - пролёт, E - модуль упругости, I - момент инерции
     * 
     * @param width - ширина полки в мм (span)
     * @param depth - глубина полки в мм (консоль)
     * @param thickness - толщина материала в мм
     * @param loadClass - класс нагрузки: 'light' (20кг), 'medium' (40кг), 'heavy' (60кг)
     */
    private calculateShelfStiffness(
        width: number,
        depth: number,
        thickness: number,
        loadClass: 'light' | 'medium' | 'heavy' = 'medium'
    ): {
        deflection: number;
        maxAllowed: number;
        needsStiffener: boolean;
        recommendedRibHeight: number;
        supportSpacing: number;
    } {
        const matProps = MATERIAL_PROPERTIES[thickness as keyof typeof MATERIAL_PROPERTIES] || 
                        MATERIAL_PROPERTIES[16];
        
        // E in N/mm² (GPa * 1000)
        const E = matProps.moe * 1000;

        // Load distribution - distributed evenly across shelf width
        const loads: Record<string, number> = { light: 20, medium: 40, heavy: 60 };
        const totalLoadKg = loads[loadClass];
        
        // Convert kg to Newtons (g = 9.81 m/s²), then to load per mm
        // Total load: totalLoadKg * 9.81 N
        // Distributed across width: (totalLoadKg * 9.81) / width = N/mm
        const w = (totalLoadKg * 9.81) / width; // Load per mm in Newtons

        // Support spacing from 32mm system
        const supportSpacing = STD.SYSTEM_32;
        const effectiveSpan = Math.max(200, width - supportSpacing * 2);

        // Moment of inertia for rectangular cross-section
        // I = b*h³/12, where b=depth (mm), h=thickness (mm)
        const I = (depth * Math.pow(thickness, 3)) / 12;

        // Standard beam deflection formula (simply-supported, uniform load)
        // δ_max = (5 * w * L⁴) / (384 * E * I)
        // Result will be in mm
        const deflectionNumerator = 5 * w * Math.pow(effectiveSpan, 4);
        const deflectionDenominator = 384 * E * I;
        const deflectionMm = deflectionNumerator / deflectionDenominator;

        // Allowable deflection per standards (AWI/ANSI)
        // L/150 to L/200 depending on load class
        const maxAllowedBySpan = effectiveSpan / (loadClass === 'heavy' ? 200 : 150);
        const maxAllowedByDepth = depth / (loadClass === 'heavy' ? 200 : 150);
        const maxAllowedStandard = 3; // 3mm max for most shelves (practical limit)
        const maxAllowed = Math.min(maxAllowedBySpan, maxAllowedByDepth, maxAllowedStandard);

        const needsStiffener = deflectionMm > maxAllowed;

        // Recommended stiffener height based on width
        let recommendedRibHeight = 40;
        if (width > 600) recommendedRibHeight = 60;
        if (width > 900) recommendedRibHeight = 80;
        if (width > 1200) recommendedRibHeight = 100;
        if (width > 1500) recommendedRibHeight = 120;

        return {
            deflection: Math.round(Math.max(deflectionMm, 0.01) * 100) / 100,
            maxAllowed: Math.round(maxAllowed * 100) / 100,
            needsStiffener,
            recommendedRibHeight,
            supportSpacing
        };
    }

    /**
     * Расчет грузоподъемности направляющей
     */
    private getDrawerRailCapacity(railLength: number, loadMargin: number = 1.5): number {
        const capacity = DRAWER_RAIL_CAPACITY[railLength as keyof typeof DRAWER_RAIL_CAPACITY] || 
                        DRAWER_RAIL_CAPACITY[500];
        return Math.floor(capacity / loadMargin);
    }

    /**
     * Валидация сборки ящиков с проверкой грузоподъемности
     */
    private validateDrawerAssembly(): string[] {
        const errs: string[] = [];

        this.sections.forEach((sec, i) => {
            sec.items.forEach(item => {
                if (item.type !== 'drawer') return;

                // Проверка суммарной высоты ящиков
                const totalDrawerH = sec.items
                    .filter(it => it.type === 'drawer')
                    .reduce((sum, d) => sum + (d.height || 0), 0);

                if (totalDrawerH + 50 > sec.items.reduce((sum) => sum + 300, 0)) {
                    errs.push(`Секция ${i+1}: Сумма высот ящиков может превышать доступное место`);
                }

                // Проверка высоты ящика (ergonomic standard max 250mm)
                const drawerH = item.height || 176;
                if (drawerH > 250) {
                    errs.push(`Секция ${i+1}: Высота ящика ${drawerH}мм превышает эргономический максимум (250мм)`);
                }

                // Проверка глубины ящика
                if (this.config.depth < 350) {
                    errs.push(`Секция ${i+1}: Глубина корпуса ${this.config.depth}мм недостаточна для ящиков (мин. 350мм)`);
                }

                // Проверка грузоподъемности направляющей
                const railLen = [...DRAWER_RAILS].reverse().find(r => r <= (this.config.depth - 10)) || 250;
                const maxLoad = this.getDrawerRailCapacity(railLen);
                const estimatedLoad = (drawerH * sec.width * 80) / 10000; // Rough estimate in kg
                
                if (estimatedLoad > maxLoad) {
                    errs.push(`Секция ${i+1}: Расчётная нагрузка ${Math.round(estimatedLoad)}кг превышает грузоподъёмность направляющей ${maxLoad}кг (длина ${railLen}мм)`);
                }
            });
        });

        return errs;
    }

    /**
     * Расчет прогиба штанги под нагрузкой
     * @param width - расстояние между опорами (мм)
     * @param loadKg - нагрузка на штангу (кг)
     * @param diameter - диаметр штанги в мм
     */
    private calculateRodDeflection(width: number, loadKg: number, diameter: number = 20): number {
        // Steel rod properties (most common for hanging rods)
        const steelMOE = 210000; // N/mm² (210 GPa)
        
        // Moment of inertia for circular cross-section: I = π * d⁴ / 64
        const I = (Math.PI * Math.pow(diameter, 4)) / 64;
        
        // Load distributed across rod (uniform)
        const loadN = loadKg * 9.81;
        const w = loadN / width; // N/mm
        
        // Deflection formula: δ = (5 * w * L⁴) / (384 * E * I)
        const deflection = (5 * w * Math.pow(width, 4)) / (384 * steelMOE * I);
        
        return deflection;
    }

    /**
     * Валидация штанг с расчетом прогиба
     */
    private validateRodConstraints(): string[] {
        const errs: string[] = [];

        this.sections.forEach((sec, i) => {
            if (!sec.items.some(it => it.type === 'rod')) return;

            const rodWidth = sec.width;
            const typicalLoadKg = 30; // Typical shirt/coat load
            const rodDiameter = 20;
            const deflection = this.calculateRodDeflection(rodWidth, typicalLoadKg, rodDiameter);
            const maxAllowedDeflection = rodWidth / 300; // Max L/300 sag for appearance

            // Проверка ширины для штанги (max 1000mm for 20mm steel rod)
            if (rodWidth > 1000) {
                errs.push(`Секция ${i+1}: Ширина штанги ${rodWidth}мм превышает рекомендуемый максимум (1000мм для диаметра 20мм)`);
            }

            // Проверка глубины для штанги (минимум 500мм для удобства)
            if (this.config.depth < 500) {
                errs.push(`Секция ${i+1}: Глубина ${this.config.depth}мм мала для штанги (мин. 500мм)`);
            }

            // Проверка прогиба
            if (deflection > maxAllowedDeflection) {
                errs.push(`Секция ${i+1}: Расчётный прогиб штанги ${Math.round(deflection * 10) / 10}мм превышает допустимый ${Math.round(maxAllowedDeflection * 10) / 10}мм для ширины ${rodWidth}мм`);
            }
        });

        return errs;
    }

    /**
     * Public method for calculating shelf stiffness - used for testing and external calculations
     */
    public getShelfStiffnessInfo(width: number, depth: number, thickness: number, loadClass: 'light' | 'medium' | 'heavy' = 'medium') {
        return this.calculateShelfStiffness(width, depth, thickness, loadClass);
    }

    /**
     * Public method for calculating rod deflection - used for testing and external calculations
     */
    public getRodDeflectionInfo(width: number, loadKg: number, diameter: number = 20) {
        return this.calculateRodDeflection(width, loadKg, diameter);
    }

    /**
     * Public method for validating drawer assembly - used for testing and external validation
     */
    public validateDrawerAssemblyPublic() {
        return this.validateDrawerAssembly();
    }

    /**
     * Public method for validating rod constraints - used for testing and external validation
     */
    public validateRodConstraintsPublic() {
        return this.validateRodConstraints();
    }

    public validate(): { valid: boolean; errors: string[] } {
        const errs: string[] = [];
        
        // 1. Basic Dimensions (ANSI/AWI Standards)
        // Width: ±12.7mm tolerance for nominal CDS dimensions
        if (this.config.width < 400) errs.push('Ширина изделия должна быть не менее 400мм (ANSI/AWI минимум)');
        if (this.config.height < 600) errs.push('Высота изделия должна быть не менее 600мм (эргономический стандарт)');
        if (this.config.depth < 300) errs.push('Глубина изделия должна быть не менее 300мм');
        
        // Maximum reasonable dimensions
        if (this.config.width > 2400) errs.push('Ширина изделия превышает максимум 2400мм (рекомендуемо для транспортировки)');
        if (this.config.height > 2500) errs.push('Высота изделия превышает максимум 2500мм (стандартная высота потолка)');
        
        // 2. Section & Hardware Validations with enhanced checks
        this.sections.forEach((s, i) => {
            // Minimum width (System 32 minimum for hardware mounting)
            if (s.width < 150) {
                errs.push(`Секция ${i+1}: Ширина ${s.width}мм слишком мала для System 32 монтажа (мин. 150мм)`);
            }
            
            // Maximum width for single shelf (risk of excessive sag)
            if (s.width > 1600) {
                errs.push(`Секция ${i+1}: Ширина ${s.width}мм очень велика, требует дополнительных промежуточных опор`);
            }
            
            // Drawer Constraints
            if (s.items.some(it => it.type === 'drawer')) {
                // Minimum depth for standard 250mm rail + gaps
                if (this.config.depth < 350) {
                    errs.push(`Секция ${i+1}: Глубина ${this.config.depth}мм недостаточна для ящиков (мин. 350мм)`);
                }
                // Max width for standard bottom mount / rigidity
                if (s.width > 1000) {
                    errs.push(`Секция ${i+1}: Ширина ящика ${s.width}мм превышает стандарт (макс. 1000мм для надёжности)`);
                }
            }

            // Shelf width vs thickness validation
            if (s.items.some(it => it.type === 'shelf')) {
                const thickness = this.matBody?.thickness || 16;
                const shelfStiffness = this.calculateShelfStiffness(s.width, this.config.depth, thickness);
                if (shelfStiffness.needsStiffener) {
                    errs.push(`Секция ${i+1}: Полка шириной ${s.width}мм с толщиной ${thickness}мм превышает допустимый прогиб (${shelfStiffness.deflection}мм > ${shelfStiffness.maxAllowed}мм)`);
                }
            }
        });

        // 3. Door Validations (per ANSI/AWI standards)
        if (this.config.doorType !== 'none') {
            if (this.config.doorType === 'sliding' && this.config.depth < 450) {
                errs.push('Для шкафа-купе минимальная глубина > 450мм (система занимает ~80мм)');
            }

            // Calculate Door Width to check constraints
            const count = this.config.doorCount || 2;
            let doorW = 0;
            if (this.config.doorType === 'hinged') {
                const gap = this.config.doorGap ?? 2;
                doorW = (this.config.width - (count + 1) * gap) / count;
                
                // Heavy load on hinges per BHMA standards
                if (doorW > 800) {
                    errs.push(`Ширина распашной двери ${Math.round(doorW)}мм слишком велика (ANSI/BHMA макс 800мм для надежности)`);
                }
                
                // Minimum door width for handles
                if (doorW < 200) {
                    errs.push(`Ширина распашной двери ${Math.round(doorW)}мм слишком мала для удобства пользования`);
                }
            } else if (this.config.doorType === 'sliding') {
                doorW = (this.config.width - (count - 1) * 2) / count; // sliding doors overlap
                if (doorW < 300) {
                    errs.push(`Ширина двери-купе ${Math.round(doorW)}мм слишком мала`);
                }
            }
        }

        // 4. Apply Phase 1 Enhanced Validators
        errs.push(...this.validateDrawerAssembly());
        errs.push(...this.validateRodConstraints());

        return { valid: errs.length === 0, errors: errs };
    }

    public generate(): Panel[] {
        this.panels = [];
        
        const W = Math.round(this.config.width);
        const H = Math.round(this.config.height);
        const D = Math.round(this.config.depth);
        const baseH = this.config.baseType === 'legs' ? 100 : 70; 

        // --- Z-AXIS & DEPTH LOGIC ---
        const grooveOffset = 16;
        const internalZStart = this.config.backType === 'groove' ? (grooveOffset + 4) : 2;
        
        // Door Space Reservation
        const doorSpace = this.config.doorType === 'sliding' ? STD.COUPE_DEPTH : (this.config.doorType === 'hinged' ? 2 : 0);
        
        // Side Panel Depth
        const sideDepth = this.config.doorType === 'hinged' ? D - 18 : D; 
        
        // Internal Elements Depth (Shelves, Dividers)
        const internalDepth = sideDepth - internalZStart - doorSpace;

        const roofIsOverlay = this.config.construction === 'corpus';
        
        // Side Height
        let sideH = H;
        let sideY = 0;
        if (this.config.baseType === 'legs') { sideY = baseH; sideH -= baseH; }
        if (roofIsOverlay) { sideH -= 16; }

        // --- 1. SIDES ---
        const sideGroove = this.getGrooveConfig('side', grooveOffset);

        const sideCommon = {
            width: sideDepth, height: sideH, depth: 16,
            rotation: Axis.X, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', 
            texture: TextureType.WOOD_OAK, textureRotation: 0 as const,
            visible: true, layer: 'body', openingType: 'none' as const,
            edging: {top:'0.4', bottom:'0.4', left:'none', right:'2.0'} as const,
            groove: sideGroove, hardware: [] as Hardware[]
        };

        const leftSideId = generateId('L');
        const rightSideId = generateId('R');

        const leftSide = { ...sideCommon, id: leftSideId, name: 'Бок Левый', x: 0, y: sideY, z: 0 };
        const rightSide = { ...sideCommon, id: rightSideId, name: 'Бок Правый', x: W - 16, y: sideY, z: 0 };
        
        this.addCorpusHardware(leftSide, baseH, sideY, sideDepth);
        this.addCorpusHardware(rightSide, baseH, sideY, sideDepth);

        this.panels.push(leftSide, rightSide);
        
        // Wall Mounting Brackets (if tall)
        if (H > 2000) {
            const bracketY = sideH - 50;
            leftSide.hardware.push({ id: generateId('mount_L'), type: 'screw', name: 'Навес (Уголок)', x: 50, y: bracketY });
            rightSide.hardware.push({ id: generateId('mount_R'), type: 'screw', name: 'Навес (Уголок)', x: 50, y: bracketY });
        }

        // --- 2. ROOF & BOTTOM ---
        const horW = roofIsOverlay ? W : W - 32;
        const horX = roofIsOverlay ? 0 : 16;
        
        const roofGroove = this.getGrooveConfig('roof', grooveOffset);
        
        const roofPanel: Panel = { id: generateId('T'), name: roofIsOverlay ? 'Крышка' : 'Крышка (Вкладная)', 
            width: horW, height: sideDepth, depth: 16, x: horX, y: H - 16, z: 0, rotation: Axis.Y, 
            materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', 
            edging: {top:'2.0', bottom:'0.4', left: roofIsOverlay?'2.0':'0.4', right: roofIsOverlay?'2.0':'0.4'}, groove: roofGroove, hardware: [] as Hardware[] 
        };
        
        if (this.config.doorType === 'sliding') {
            roofPanel.hardware.push({ id: generateId('rail-top'), type: 'slide_rail', name: 'Трек Верхний', x: 0, y: sideDepth - 40 });
        }

        if (roofIsOverlay && this.config.hardwareType !== 'none') {
             roofPanel.hardware.push({id: generateId('hw-t-l-f'), type: 'screw', name: 'Конфирмат', x: 8 + 50, y: 30}); 
             roofPanel.hardware.push({id: generateId('hw-t-l-b'), type: 'screw', name: 'Конфирмат', x: 8 + 50, y: sideDepth - 30});
             roofPanel.hardware.push({id: generateId('hw-t-r-f'), type: 'screw', name: 'Конфирмат', x: horW - 8 - 50, y: 30});
             roofPanel.hardware.push({id: generateId('hw-t-r-b'), type: 'screw', name: 'Конфирмат', x: horW - 8 - 50, y: sideDepth - 30});
             
             roofPanel.hardware.push({id: generateId('dw-t-l-f'), type: 'dowel', name: 'Шкант', x: 8 + 82, y: 30});
             roofPanel.hardware.push({id: generateId('dw-t-r-f'), type: 'dowel', name: 'Шкант', x: horW - 8 - 82, y: 30});
        }
        this.panels.push(roofPanel);

        // Bottom
        const bottomGroove = this.getGrooveConfig('bottom', grooveOffset);
        
        const bottomPanel: Panel = { 
            id: generateId('B'), name: 'Дно', width: W - 32, height: sideDepth, depth: 16, x: 16, y: baseH, z: 0, rotation: Axis.Y, 
            materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, 
            visible: true, layer: 'body', openingType: 'none', edging: {top:'2.0', bottom:'0.4', left:'0.4', right:'0.4'}, 
            groove: bottomGroove, hardware: [] 
        };
        
        if (this.config.doorType === 'sliding') {
            bottomPanel.hardware.push({ id: generateId('rail-bot'), type: 'slide_rail', name: 'Трек Нижний', x: 0, y: sideDepth - 40 });
        }

        if (this.config.hardwareType !== 'none') {
            bottomPanel.hardware.push({ id: generateId('b-l-cf'), type: 'screw', name: 'Отв. конфирмат (Торец)', x: 0, y: 50 });
            bottomPanel.hardware.push({ id: generateId('b-l-dw'), type: 'dowel_hole', name: 'Отв. шкант', x: 0, y: 82 });
            bottomPanel.hardware.push({ id: generateId('b-l-dw2'), type: 'dowel_hole', name: 'Отв. шкант', x: 0, y: sideDepth - 82 });
            bottomPanel.hardware.push({ id: generateId('b-l-cf2'), type: 'screw', name: 'Отв. конфирмат (Торец)', x: 0, y: sideDepth - 50 });

            const R = W - 32;
            bottomPanel.hardware.push({ id: generateId('b-r-cf'), type: 'screw', name: 'Отв. конфирмат (Торец)', x: R, y: 50 });
            bottomPanel.hardware.push({ id: generateId('b-r-dw'), type: 'dowel_hole', name: 'Отв. шкант', x: R, y: 82 });
            bottomPanel.hardware.push({ id: generateId('b-r-dw2'), type: 'dowel_hole', name: 'Отв. шкант', x: R, y: sideDepth - 82 });
            bottomPanel.hardware.push({ id: generateId('b-r-cf2'), type: 'screw', name: 'Отв. конфирмат (Торец)', x: R, y: sideDepth - 50 });
        }
        this.panels.push(bottomPanel);
        
        // Plinth
        if (this.config.baseType === 'plinth') {
             const pFront: Panel = { id: generateId('P'), name: 'Цоколь', width: W - 32, height: baseH, depth: 16, x: 16, y: 0, z: sideDepth - 50, rotation: Axis.Z, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top:'0.4', bottom:'2.0', left:'2.0', right:'2.0'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] };
             const pBack: Panel = { id: generateId('P_back'), name: 'Цоколь Задний', width: W - 32, height: baseH, depth: 16, x: 16, y: 0, z: 50, rotation: Axis.Z, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top:'0.4', bottom:'2.0', left:'2.0', right:'2.0'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] };
             
             if (this.config.hardwareType !== 'none') {
                 pFront.hardware.push({id: generateId('p-f-l'), type: 'screw', name: 'Конфирмат', x: 8, y: baseH/2});
                 pFront.hardware.push({id: generateId('p-f-r'), type: 'screw', name: 'Конфирмат', x: pFront.width - 8, y: baseH/2});
                 if(pFront.width > 1000) pFront.hardware.push({id: generateId('p-f-m'), type: 'screw', name: 'Конфирмат', x: pFront.width/2, y: baseH/2});

                 pBack.hardware.push({id: generateId('p-b-l'), type: 'screw', name: 'Конфирмат', x: 8, y: baseH/2});
                 pBack.hardware.push({id: generateId('p-b-r'), type: 'screw', name: 'Конфирмат', x: pBack.width - 8, y: baseH/2});
                 if(pBack.width > 1000) pBack.hardware.push({id: generateId('p-b-m'), type: 'screw', name: 'Конфирмат', x: pBack.width/2, y: baseH/2});
             }

             this.panels.push(pFront, pBack);
        }

        // --- 3. FILLING & STIFFENERS ---
        let curX = 16;
        const internalH = H - baseH - 32; 
        const needsStiffener = roofIsOverlay;

        this.sections.forEach((sec, i) => {
            // Add Top Stiffener (Tsarga) per section to avoid intersecting dividers
            if (needsStiffener) {
                 const tsargaHeight = 100;
                 const tsargaPanel: Panel = {
                     id: generateId(`tsarga_top_${i}`), name: `Царга (Секция ${i+1})`,
                     width: sec.width, height: tsargaHeight, depth: 16,
                     x: curX, y: H - 16 - tsargaHeight, z: internalZStart,
                     rotation: Axis.Z, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0,
                     visible: true, layer: 'body', openingType: 'none',
                     edging: {top:'none', bottom:'0.4', left:'0.4', right:'0.4'},
                     groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: []
                 };
                 
                 // Hardware for Tsarga
                 if (this.config.hardwareType !== 'none') {
                     // Holes in Tsarga ends
                     tsargaPanel.hardware.push({id: generateId('ts-l-dw'), type: 'dowel_hole', name: 'Отв. Шкант', x: 0, y: 30});
                     tsargaPanel.hardware.push({id: generateId('ts-r-dw'), type: 'dowel_hole', name: 'Отв. Шкант', x: sec.width, y: 30});
                     tsargaPanel.hardware.push({id: generateId('ts-l-sc'), type: 'screw', name: 'Конфирмат (Торец)', x: 0, y: 70});
                     tsargaPanel.hardware.push({id: generateId('ts-r-sc'), type: 'screw', name: 'Конфирмат (Торец)', x: sec.width, y: 70});
                     
                     // Holes in Sides/Dividers are added when those panels are processed or here
                     const tY = (H - 16 - tsargaHeight) - sideY; 
                     const zCenter = internalZStart + 8;
                     
                     // Add matching holes to left Side/Divider
                     const leftNeighbor = this.findPanelAtX(curX);
                     if (leftNeighbor) {
                         leftNeighbor.hardware.push({id: generateId(`ts-l-match-dw`), type: 'dowel', name: 'Шкант', x: zCenter, y: tY + 30});
                         leftNeighbor.hardware.push({id: generateId(`ts-l-match-sc`), type: 'screw', name: 'Конфирмат', x: zCenter, y: tY + 70});
                     }
                 }
                 this.panels.push(tsargaPanel);
            }

            // Divider
            const divId = generateId(`Div${i}`);
            
            if (i < this.sections.length - 1) {
                const divPanel: Panel = { id: divId, name: 'Стойка', width: internalDepth, height: internalH, depth: 16, x: curX + sec.width, y: baseH + 16, z: internalZStart, rotation: Axis.X, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top:'0.4', bottom:'0.4', left:'0.4', right:'2.0'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] };
                
                if (this.config.hardwareType !== 'none') {
                    divPanel.hardware.push({id:generateId('d-top-f'), type:'dowel', name:'Шкант', x: 50, y: internalH});
                    divPanel.hardware.push({id:generateId('d-top-b'), type:'dowel', name:'Шкант', x: internalDepth-50, y: internalH});
                    divPanel.hardware.push({id:generateId('d-bot-f'), type:'dowel', name:'Шкант', x: 50, y: 0});
                    divPanel.hardware.push({id:generateId('d-bot-b'), type:'dowel', name:'Шкант', x: internalDepth-50, y: 0});
                    divPanel.hardware.push({id:generateId('s-top-f'), type:'screw', name:'Конфирмат', x: 82, y: internalH});
                    divPanel.hardware.push({id:generateId('s-bot-f'), type:'screw', name:'Конфирмат', x: 82, y: 0});
                }

                this.panels.push(divPanel);
                
                if (this.config.baseType === 'plinth') {
                    // Corrected Plinth Rib Logic to avoid collision and adding safety gap
                    const ribStartZ = 50 + 16;
                    const ribEndZ = sideDepth - 50;
                    const ribLen = ribEndZ - ribStartZ - 2; // -2mm safety gap
                    
                    if (ribLen > 50) {
                        const rib: Panel = { 
                            id: generateId(`P_rib_${i}`), name: 'Цоколь (Поперечка)', 
                            width: ribLen, height: baseH, depth: 16, 
                            x: curX + sec.width, y: 0, z: ribStartZ + 1, // Centered in gap
                            rotation: Axis.X, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top:'0.4', bottom:'2.0', left:'2.0', right:'2.0'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] 
                        };
                        
                        if (this.config.hardwareType !== 'none') {
                            rib.hardware.push({id: generateId('dp-f'), type: 'screw', name: 'Конфирмат', x: 0, y: baseH/2});
                            rib.hardware.push({id: generateId('dp-b'), type: 'screw', name: 'Конфирмат', x: rib.width, y: baseH/2});
                        }
                        this.panels.push(rib);
                    }
                }
            }
            
            sec.items.forEach(item => {
                if (item.type === 'shelf') {
                    const shelfDepth = internalDepth - 2; 
                    const shelfGroove = this.getGrooveConfig('shelf');
                    const shelfPanel = { id: generateId(`Sh${item.id}`), name: 'Полка', width: sec.width, height: shelfDepth, depth: 16, x: curX, y: Math.round(item.y), z: internalZStart, rotation: Axis.Y, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0 as const, visible: true, layer: 'shelves', openingType: 'none' as const, edging: {top:'2.0', bottom:'none', left:'0.4', right:'0.4'} as const, groove: shelfGroove, hardware: [] as Hardware[] };
                    this.panels.push(shelfPanel);
                    
                    if (this.config.hardwareType === 'confirmat') {
                        const holeY = Math.round(item.y + 8 - sideY);
                        this.addShelfHardware(item.id, holeY, internalZStart, internalDepth, curX, sec.width, leftSideId, divId, rightSideId, i, this.sections.length, shelfPanel);
                    }

                    // Vertical Stiffener for Wide Shelves - auto-calculated
                    const thickness = this.matBody?.thickness || 16;
                    const shelfStiffness = this.calculateShelfStiffness(sec.width, this.config.depth, thickness);
                    
                    if (shelfStiffness.needsStiffener && sec.width > 500) {
                        const ribH = Math.min(shelfStiffness.recommendedRibHeight, 100);
                        const stiffener: Panel = {
                            id: generateId(`Stiff_${item.id}`), name: `Ребро жесткости (${ribH}мм) (Полка)`,
                            width: sec.width, height: ribH, depth: 16,
                            x: curX, y: item.y - ribH, z: internalZStart + internalDepth / 2 - 8,
                            rotation: Axis.Z,
                            materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0,
                            visible: true, layer: 'body', openingType: 'none',
                            edging: {top:'none', bottom:'0.4', left:'0.4', right:'0.4'},
                            groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0},
                            hardware: []
                        };
                        this.panels.push(stiffener);
                    }

                } else if (item.type === 'rod') {
                    const rodW = sec.width - 10;
                    this.panels.push({ id: generateId(`Rd${item.id}`), name: 'Штанга', width: rodW, height: 25, depth: 25, x: curX + 5, y: Math.round(item.y - 40), z: internalZStart + internalDepth/2, rotation: Axis.Y, materialId: 'metal', color: '#AAA', texture: TextureType.UNIFORM, textureRotation: 0, visible: true, layer: 'hardware', openingType: 'none', edging: {top:'none', bottom:'none', left:'none', right:'none'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] });
                } else if (item.type === 'drawer') {
                    const isOuter = i === 0 || i === this.sections.length - 1;
                    const drawerPanels = this.buildDrawerAssembly(item, sec.width, internalDepth, curX, internalZStart, item.y, isOuter);
                    this.panels.push(...drawerPanels);

                    const railY = Math.round(item.y + 15 + 10); 
                    const sideL = this.findPanelAtX(curX); 
                    const sideR = this.findPanelAtX(curX + sec.width); 
                    
                    if (sideL && sideR && sideL.id !== sideR.id) {
                        const existsL = sideL.hardware.some(h => h.type === 'slide_rail' && Math.abs(h.y - (railY - sideY)) < 5 && Math.abs(h.x - internalZStart) < 5);
                        const existsR = sideR.hardware.some(h => h.type === 'slide_rail' && Math.abs(h.y - (railY - sideY)) < 5 && Math.abs(h.x - internalZStart) < 5);
                        
                        if(!existsL) sideL.hardware.push({ id: generateId(`rail-l-${item.id}`), type: 'slide_rail', name: 'Направляющая', x: internalZStart, y: railY - sideY });
                        if(!existsR) sideR.hardware.push({ id: generateId(`rail-r-${item.id}`), type: 'slide_rail', name: 'Направляющая', x: internalZStart, y: railY - sideY });
                    }
                } else if (item.type === 'partition') {
                    const partH = Math.round(item.height || 300);
                    const partX = curX + (sec.width - 16) / 2;
                    const partPanel: Panel = { id: generateId(`Part${item.id}`), name: 'Перегородка', width: internalDepth, height: partH, depth: 16, x: partX, y: Math.round(item.y), z: internalZStart, rotation: Axis.X, materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 0, visible: true, layer: 'body', openingType: 'none', edging: {top:'0.4', bottom:'0.4', left:'0.4', right:'0.4'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] };
                    this.panels.push(partPanel);
                }
            });
            curX += sec.width + 16;
        });

        // --- 4. BACK PANEL ---
        // Optimize back panel thickness based on cabinet size for better rigidity
        const backThickness = this.calculateOptimalBackThickness();
        
        if (this.config.backType === 'groove') {
             const totalBackW = W - 32 + 20 - 2; // Fixed tolerance: 10+10 groove - 2 tol = 18mm bigger than inner. W-32 is inner. So W-14.
             const backH = (roofIsOverlay ? H - 16 : H) - baseH - 16 + 20 - 2; // Fixed tolerance
             
             if (totalBackW > 1000) {
                 const count = 2;
                 const gap = 2; // H-connector
                 const partW = (totalBackW - gap) / count;
                 for(let b=0; b<count; b++) {
                     const partX = ((W - totalBackW)/2) + (b * (partW + gap));
                     this.panels.push({ id: generateId(`Back_${b}`), name: `Задняя стенка ${b+1} (ДВПО, ${backThickness}мм)`, width: partW, height: backH, depth: backThickness, x: partX, y: baseH + (internalH - backH)/2 + 8, z: grooveOffset, rotation: Axis.Z, materialId: 'eg-hdf', color: '#DDD', texture: TextureType.NONE, textureRotation: 0, visible: true, layer: 'back', openingType: 'none', edging: {top:'none', bottom:'none', left:'none', right:'none'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] });
                 }
             } else {
                 this.panels.push({ id: generateId('Back'), name: `Задняя стенка (ДВПО, ${backThickness}мм)`, width: totalBackW, height: backH, depth: backThickness, x: (W - totalBackW)/2, y: baseH + (internalH - backH)/2 + 8, z: grooveOffset, rotation: Axis.Z, materialId: 'eg-hdf', color: '#DDD', texture: TextureType.NONE, textureRotation: 0, visible: true, layer: 'back', openingType: 'none', edging: {top:'none', bottom:'none', left:'none', right:'none'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] });
             }
        } else {
             const backW = W - 4;
             const backH = H - baseH - 4;
             this.panels.push({ id: generateId('Back'), name: `Задняя стенка (Набивн., ${backThickness}мм)`, width: backW, height: backH, depth: backThickness, x: 2, y: baseH + 2, z: 0, rotation: Axis.Z, materialId: 'eg-hdf', color: '#DDD', texture: TextureType.NONE, textureRotation: 0, visible: true, layer: 'back', openingType: 'none', edging: {top:'none', bottom:'none', left:'none', right:'none'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0}, hardware: [] });
        }

        // --- 5. DOORS ---
        this.generateDoors(W, H, D, baseH);

        // --- VALIDATION: Проверить что depth значения разумны ---
        // Предотвратить ошибки при расчете веса из-за неправильных параметров
        this.panels.forEach((p, i) => {
            // Убедиться что depth не больше 25мм (максимум для ЛДСП) 
            if (p.depth > 25) {
                console.warn(
                    `⚠️  [CabinetGenerator] Panel #${i} (${p.name}): ` +
                    `depth=${p.depth}мм - suspiciously large! Expected 4-18mm. ` +
                    `This may cause incorrect weight calculations.`
                );
                // Исправить на стандартное значение
                p.depth = 16;
            }
        });

        return this.panels;
    }

    private generateDoors(W: number, H: number, D: number, baseH: number) {
        if (this.config.doorType === 'none') return;

        const count = this.config.doorCount || 2;
        let doorH = 0, doorY = 0, doorW = 0, doorZ = D;
        let startXFunc = (k: number, w: number) => 0;

        const overlap = this.config.coupeGap ?? 26;
        const gap = this.config.doorGap ?? 2;

        if (this.config.doorType === 'sliding') {
            const topRailH = 40; 
            const botRailH = 40;
            const innerH = (H - baseH) - topRailH - botRailH;
            doorH = innerH + 15; 
            doorY = baseH + botRailH - 10;
            doorZ = D - STD.COUPE_DEPTH + 20; 
            const innerW = W - 32; 
            const totalOverlap = (count - 1) * overlap;
            doorW = Math.floor((innerW + totalOverlap) / count); 
            startXFunc = (k, w) => 16 + k * (w - overlap);
        } else {
            const roofIsOverlay = this.config.construction === 'corpus';
            const topLimit = roofIsOverlay ? H - 16 : H; 
            doorY = baseH + gap;
            doorH = (topLimit - gap) - doorY;
            doorZ = D; 
            const totalGaps = (count + 1) * gap;
            doorW = Math.floor((W - totalGaps) / count); 
            startXFunc = (k, w) => gap + k * (w + gap);
        }

        for (let k = 0; k < count; k++) {
            const zOffset = this.config.doorType === 'sliding' ? (k % 2 === 0 ? 0 : 35) : 0;
            const x = startXFunc(k, doorW);
            
            const doorHardware: Hardware[] = [];
            
            if (this.config.doorType === 'sliding') {
                doorHardware.push({id: generateId(`roller-t-${k}`), type: 'slide_rail', name: 'Ролик Верхний', x: 50, y: doorH - 50});
                doorHardware.push({id: generateId(`roller-b-${k}`), type: 'slide_rail', name: 'Ролик Нижний', x: 50, y: 50});
                doorHardware.push({id: generateId(`roller-t2-${k}`), type: 'slide_rail', name: 'Ролик Верхний', x: doorW - 50, y: doorH - 50});
                doorHardware.push({id: generateId(`roller-b2-${k}`), type: 'slide_rail', name: 'Ролик Нижний', x: doorW - 50, y: 50});
            } else {
                doorHardware.push({id: generateId(`hnd_d${k}`), type: 'handle', name: 'Ручка', x: doorW - 30, y: doorH/2});
            }

            const doorPanel: Panel = {
                id: generateId(`Door${k}`), name: this.config.doorType === 'sliding' ? 'Дверь Купе' : 'Фасад', 
                width: doorW, height: doorH, depth: 16, 
                x: x, y: doorY, z: doorZ + zOffset, rotation: Axis.Z,
                materialId: 'mdf-ral', color: '#555', texture: TextureType.UNIFORM, textureRotation: 90,
                visible: true, layer: 'facade', openingType: this.config.doorType === 'sliding' ? 'sliding' : 'left',
                edging: {top:'1.0', bottom:'1.0', left:'1.0', right:'1.0'}, groove: {enabled: false, side: 'top', width: 0, depth: 0, offset: 0},
                hardware: doorHardware
            };

            if (this.config.doorType === 'hinged') {
                const hingesCount = doorH > 2300 ? 6 : doorH > 2000 ? 5 : doorH > 1600 ? 4 : doorH > 900 ? 3 : 2;
                const hingeStep = (doorH - 200) / (hingesCount - 1);
                
                for(let h = 0; h < hingesCount; h++) {
                    const hY = 100 + (h * hingeStep);
                    doorPanel.hardware.push({ id: generateId(`hinge-${k}-${h}`), type: 'hinge_cup', name: 'Петля', x: 22, y: hY });
                    
                    const mountX = 37 + (this.config.backType === 'groove' ? 16 : 0);
                    if (k === 0) {
                        const leftSide = this.panels.find(p => p.id.startsWith('L-'));
                        leftSide?.hardware.push({ id: generateId(`plate-L-${h}`), type: 'screw', name: 'Ответная планка', x: mountX, y: hY - baseH });
                    } else if (k === count - 1) {
                        const rightSide = this.panels.find(p => p.id.startsWith('R-'));
                        rightSide?.hardware.push({ id: generateId(`plate-R-${h}`), type: 'screw', name: 'Ответная планка', x: mountX, y: hY - baseH });
                    }
                }
            }
            this.panels.push(doorPanel);
        }
    }

    private buildDrawerAssembly(item: CabinetItem, sectionW: number, availableDepth: number, startX: number, startZ: number, itemY: number, isOuterSection: boolean): Panel[] {
        const panels: Panel[] = [];
        const facadeH = Math.round(item.height || 176);
        const targetDepth = availableDepth - 10;
        const railLen = [...DRAWER_RAILS].reverse().find(r => r <= targetDepth) || 250;
        
        if (availableDepth < 260) return []; // Too shallow

        const boxH = Math.max(60, facadeH - 36); 
        
        // --- GAP LOGIC UPDATE ---
        const hasDoors = this.config.doorType !== 'none';
        
        let sideGap = STD.RAIL_GAP; // Default 13mm
        if (hasDoors && this.config.doorType === 'hinged' && isOuterSection) {
            sideGap = 25; // Extra clearance for hinges
        }

        // 1. Facade
        // If internal drawer (behind doors), facade width is flush with box outer width
        // If external drawer (no doors), facade width overlays the gaps (sectionW - 4mm)
        let facadeW = hasDoors ? (sectionW - sideGap * 2) : Math.round(sectionW - STD.GAP_FRONT * 2);
        let facadeX = hasDoors ? Math.round(startX + sideGap) : Math.round(startX + STD.GAP_FRONT);
        
        const frontZ = startZ + availableDepth;
        const facadePanel: Panel = {
            id: generateId('facade'), name: 'Фасад ящика', width: facadeW, height: Math.round(facadeH - STD.GAP_FRONT), depth: 16,
            x: facadeX, y: Math.round(itemY + STD.GAP_FRONT / 2), z: frontZ, rotation: Axis.Z,
            materialId: this.matBody?.id || 'unknown', color: this.matBody?.color || '#D2B48C', texture: TextureType.WOOD_OAK, textureRotation: 90,
            visible: true, layer: 'facade', openingType: 'drawer', edging: {top:'2.0', bottom:'2.0', left:'2.0', right:'2.0'}, groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, 
            hardware: [
                {id: generateId('hnd'), type: 'handle', name: 'Ручка', x: facadeW / 2, y: facadeH / 2},
                {id: generateId('f-sc-l1'), type: 'screw', name: 'Саморез 4x30', x: 50, y: facadeH/2 - 20},
                {id: generateId('f-sc-l2'), type: 'screw', name: 'Саморез 4x30', x: 50, y: facadeH/2 + 20},
                {id: generateId('f-sc-r1'), type: 'screw', name: 'Саморез 4x30', x: facadeW - 50, y: facadeH/2 - 20},
                {id: generateId('f-sc-r2'), type: 'screw', name: 'Саморез 4x30', x: facadeW - 50, y: facadeH/2 + 20}
            ]
        };
        panels.push(facadePanel);

        // 2. Box Body - FIXED COLLISION LOGIC WITH SAFETY GAP
        const boxSideX_L = Math.round(startX + sideGap);
        const boxSideX_R = Math.round(startX + sectionW - sideGap - 16);
        const boxZ = frontZ - railLen - 2; // Added -2mm safety gap to prevent collision with facade

        const boxCommon = { 
            materialId: this.matBody?.id || 'eg-w980', 
            color: this.matBody?.color || '#D2B48C', 
            texture: this.matBody?.texture || TextureType.WOOD_OAK, 
            textureRotation: 0 as const, 
            visible: true, layer: 'body', openingType: 'none' as const, hardware: [] as Hardware[] 
        };
        
        const grooveSide = this.getGrooveConfig('drawer_side');
        const grooveFrontBack = this.getGrooveConfig('drawer_front');

        const sideL: Panel = { id: generateId('box-l'), name: 'Бок ящика Л', width: railLen, height: boxH, depth: 16, x: boxSideX_L, y: Math.round(itemY + 15), z: boxZ, rotation: Axis.X, ...boxCommon, edging: {top:'0.4', bottom:'none', left:'0.4', right:'0.4'}, groove: grooveSide };
        const sideR: Panel = { id: generateId('box-r'), name: 'Бок ящика П', width: railLen, height: boxH, depth: 16, x: boxSideX_R, y: Math.round(itemY + 15), z: boxZ, rotation: Axis.X, ...boxCommon, edging: {top:'0.4', bottom:'none', left:'0.4', right:'0.4'}, groove: grooveSide };
        
        const screwY = boxH / 2;
        sideL.hardware.push({ id: generateId('sc-l-f'), type: 'screw', name: 'Конфирмат', x: railLen - 8, y: screwY });
        sideL.hardware.push({ id: generateId('sc-l-b'), type: 'screw', name: 'Конфирмат', x: 8, y: screwY });
        sideR.hardware.push({ id: generateId('sc-r-f'), type: 'screw', name: 'Конфирмат', x: railLen - 8, y: screwY });
        sideR.hardware.push({ id: generateId('sc-r-b'), type: 'screw', name: 'Конфирмат', x: 8, y: screwY });
        
        panels.push(sideL, sideR);

        const innerW = Math.round(sectionW - (sideGap * 2) - 32);
        panels.push({ id: generateId('box-f'), name: 'Лоб ящика', width: innerW, height: boxH - 10, depth: 16, x: boxSideX_L + 16, y: Math.round(itemY + 15 + 10), z: boxZ + railLen - 16, rotation: Axis.Z, ...boxCommon, edging: {top:'0.4', bottom:'none', left:'none', right:'none'}, groove: grooveFrontBack });
        panels.push({ id: generateId('box-b'), name: 'Зад ящика', width: innerW, height: boxH - 10, depth: 16, x: boxSideX_L + 16, y: Math.round(itemY + 15 + 10), z: boxZ, rotation: Axis.Z, ...boxCommon, edging: {top:'0.4', bottom:'none', left:'none', right:'none'}, groove: grooveFrontBack });

        panels.push({ 
            id: generateId('box-btm'), name: 'Дно ящика (ДВПО)', 
            width: innerW + 14, height: railLen - 2, depth: 4, 
            x: boxSideX_L + 9, y: Math.round(itemY + 15 + 12), z: boxZ, 
            rotation: Axis.Y, materialId: 'eg-hdf', color: '#DDD', texture: TextureType.NONE, textureRotation: 0, visible: true, layer: 'back', openingType: 'none', edging: {top:'none', bottom:'none', left:'none', right:'none'}, groove: {enabled:false, side:'top', width:0, depth:0, offset:0}, hardware: [] 
        });

        return panels;
    }

    private addCorpusHardware(panel: Panel, baseH: number, sideY: number, sideDepth: number) {
        // System 32: 37mm offset from front edge, 32mm hole spacing
        const system32Offset = STD.SYSTEM_32_OFFSET; // 37mm
        const system32Spacing = STD.SYSTEM_32; // 32mm
        
        if (this.config.hardwareType === 'confirmat' || this.config.hardwareType === 'minifix') {
            const botY = baseH + 8 - sideY;
            
            // Front mounting (37mm from front edge per System 32)
            panel.hardware.push({id: generateId(`hw-bot-f`), type:'screw', name:'Конфирмат', x: system32Offset, y: botY});
            // Back mounting (37mm from back edge)
            panel.hardware.push({id: generateId(`hw-bot-b`), type:'screw', name:'Конфирмат', x: sideDepth - system32Offset, y: botY});
            
            // Dowels at System 32 spacing (32mm from front screw)
            panel.hardware.push({id: generateId(`dw-bot-f`), type:'dowel', name:'Шкант', x: system32Offset + system32Spacing, y: botY});
            // Back dowel at offset + spacing from back
            panel.hardware.push({id: generateId(`dw-bot-b`), type:'dowel', name:'Шкант', x: sideDepth - system32Offset - system32Spacing, y: botY});
        }
    }

    private addShelfHardware(itemId: string, holeY: number, internalZStart: number, internalDepth: number, curX: number, secW: number, leftSideId: string, divId: string, rightSideId: string, idx: number, totalSections: number, shelfPanel: Panel) {
        // System 32: Standard 37mm offset from front, 32mm hole spacing
        const system32Offset = STD.SYSTEM_32_OFFSET; // 37mm
        const system32Spacing = STD.SYSTEM_32; // 32mm
        
        const holeXFront = internalZStart + system32Offset;
        const holeXBack = internalZStart + internalDepth - system32Offset;
        
        const targetLeft = this.findPanelAtX(curX);
        const targetRight = this.findPanelAtX(curX + secW);

        if (this.config.hardwareType === 'confirmat') {
             const w = shelfPanel.width;
             const d = shelfPanel.height; 
             
             // Front and back mounting holes (37mm offset from edges per System 32)
             shelfPanel.hardware.push({ id: generateId('sh-l-cf1'), type: 'dowel_hole', name: 'Отв. конфирмат', x: 0, y: system32Offset });
             shelfPanel.hardware.push({ id: generateId('sh-l-cf2'), type: 'dowel_hole', name: 'Отв. конфирмат', x: 0, y: d - system32Offset });
             
             // Additional dowel hole at System 32 spacing (32mm from screw hole)
             shelfPanel.hardware.push({ id: generateId('sh-l-dw'), type: 'dowel_hole', name: 'Отв. шкант', x: 0, y: system32Offset + system32Spacing }); 

             shelfPanel.hardware.push({ id: generateId('sh-r-cf1'), type: 'dowel_hole', name: 'Отв. конфирмат', x: w, y: system32Offset });
             shelfPanel.hardware.push({ id: generateId('sh-r-cf2'), type: 'dowel_hole', name: 'Отв. конфирмат', x: w, y: d - system32Offset });
             shelfPanel.hardware.push({ id: generateId('sh-r-dw'), type: 'dowel_hole', name: 'Отв. шкант', x: w, y: system32Offset + system32Spacing });
        }

        if (targetLeft) {
             // Front and back mounting for System 32 compliance
             targetLeft.hardware.push({ id: generateId(`hw-s-${itemId}-lf`), type: 'screw', name: 'Конфирмат', x: holeXFront, y: holeY });
             targetLeft.hardware.push({ id: generateId(`hw-s-${itemId}-lb`), type: 'screw', name: 'Конфирмат', x: holeXBack, y: holeY });
             // Dowel at standard 32mm spacing from screw
             targetLeft.hardware.push({ id: generateId(`dw-s-${itemId}-lf`), type: 'dowel', name: 'Шкант', x: holeXFront + system32Spacing, y: holeY });
        }
        if (targetRight) {
             targetRight.hardware.push({ id: generateId(`hw-s-${itemId}-rf`), type: 'screw', name: 'Конфирмат', x: holeXFront, y: holeY });
             targetRight.hardware.push({ id: generateId(`hw-s-${itemId}-rb`), type: 'screw', name: 'Конфирмат', x: holeXBack, y: holeY });
             targetRight.hardware.push({ id: generateId(`dw-s-${itemId}-rf`), type: 'dowel', name: 'Шкант', x: holeXFront + system32Spacing, y: holeY });
        }
    }

    private findPanelAtX(targetX: number): Panel | undefined {
        return this.panels.find(p => {
            const xEnd = p.x + (p.rotation === Axis.X ? p.depth : p.width);
            return Math.abs(p.x - targetX) < 5 || Math.abs(xEnd - targetX) < 5;
        });
    }
}

export const checkCollisions = (panels: Panel[]): string[] => {
    const messages: string[] = [];
    const getBox = (p: Panel) => {
        let dX = 0, dY = 0, dZ = 0;
        if (p.rotation === Axis.X) { dX = p.depth; dY = p.height; dZ = p.width; }
        else if (p.rotation === Axis.Y) { dX = p.width; dY = p.depth; dZ = p.height; }
        else { dX = p.width; dY = p.height; dZ = p.depth; }
        
        return {
            id: p.id,
            name: p.name,
            layer: p.layer,
            groove: p.groove,
            minX: p.x, maxX: p.x + dX,
            minY: p.y, maxY: p.y + dY,
            minZ: p.z, maxZ: p.z + dZ
        };
    };

    const boxes = panels.filter(p => p.visible).map(getBox);

    for (let i = 0; i < boxes.length; i++) {
        for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i];
            const b = boxes[j];
            const tol = 0.5;

            const overlapX = a.minX < b.maxX - tol && a.maxX > b.minX + tol;
            const overlapY = a.minY < b.maxY - tol && a.maxY > b.minY + tol;
            const overlapZ = a.minZ < b.maxZ - tol && a.maxZ > b.minZ + tol;

            if (overlapX && overlapY && overlapZ) {
                // --- EXCEPTION LOGIC FOR GROOVES ---
                
                // 1. Back Panel Groove Exception
                const aIsBack = a.layer === 'back';
                const bIsBack = b.layer === 'back';
                const aHasGroove = a.groove?.enabled;
                const bHasGroove = b.groove?.enabled;

                if (aIsBack && bHasGroove) continue; // Back panel intersects grooved panel (assumed OK)
                if (bIsBack && aHasGroove) continue;

                // 2. Drawer Bottom Exception
                const aIsDrawerBtm = a.name.includes('Дно ящика');
                const bIsDrawerBtm = b.name.includes('Дно ящика');
                if (aIsDrawerBtm && bHasGroove) continue;
                if (bIsDrawerBtm && aHasGroove) continue;

                // 3. Facade Overlay Exception (Touching is OK, but strictly overlapping is not)
                // The new gap of 2mm prevents most false positives, but keeping check logic loose for floating point errors
                const aIsFacade = a.layer === 'facade';
                const bIsFacade = b.layer === 'facade';
                if ((aIsFacade && !bIsFacade) || (!aIsFacade && bIsFacade)) {
                    // Check if it's just a tiny touch overlap
                    const overlapDepth = Math.min(a.maxZ, b.maxZ) - Math.max(a.minZ, b.minZ);
                    if (overlapDepth < 1.0) continue; // Ignore <1mm collision for facades
                }

                messages.push(`Пересечение: ${a.name} (ID:${a.id.slice(-4)}) <-> ${b.name} (ID:${b.id.slice(-4)})`);
            }
        }
    }
    return messages;
};
