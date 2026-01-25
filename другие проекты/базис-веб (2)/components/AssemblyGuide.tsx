import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Panel, Axis, Hardware } from '../types';
import { 
    ChevronRight, ChevronLeft, Printer, Clock, Wrench, 
    AlertTriangle, CheckCircle2, Box, ArrowRight 
} from 'lucide-react';
import { 
    Scene, PerspectiveCamera, WebGLRenderer, Group, Color, 
    AmbientLight, DirectionalLight, MeshStandardMaterial, 
    BoxGeometry, Mesh, LineSegments, LineBasicMaterial, EdgesGeometry, Vector3, PCFSoftShadowMap, Box3
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// --- TYPES ---

interface AssemblyStep {
    step: number;
    title: string;
    description: string;
    panels: string[]; // IDs of panels to install in this step
    hardware: { name: string; qty: number }[];
    timeEstimate: number; // minutes
    warning?: string;
}

// --- LOGIC ENGINE ---

const getPanelBounds = (p: Panel) => {
    let w=0, h=0, d=0;
    if(p.rotation === Axis.X) { w=p.depth; h=p.height; d=p.width; }
    else if(p.rotation === Axis.Y) { w=p.width; h=p.depth; d=p.height; }
    else { w=p.width; h=p.height; d=p.depth; }
    return { minY: p.y, maxY: p.y + h, minZ: p.z, maxZ: p.z + d };
};

const getHardwareName = (type: string): string => {
    const map: Record<string, string> = {
        'screw': 'Конфирмат 5x50',
        'minifix_cam': 'Эксцентрик (камера)',
        'minifix_pin': 'Эксцентрик (шток)',
        'dowel': 'Шкант 8x30',
        'shelf_support': 'Полкодержатель',
        'handle': 'Ручка',
        'hinge_cup': 'Петля мебельная',
        'legs': 'Опора регулируемая',
        'slide_rail': 'Направляющая ящика'
    };
    return map[type] || type;
};

const generateSteps = (panels: Panel[]): AssemblyStep[] => {
    const steps: AssemblyStep[] = [];
    let stepCounter = 1;
    const remainingPanels = new Set(panels.map(p => p.id));

    // Helper to create a step
    const addStep = (
        title: string, 
        desc: string, 
        stepPanels: Panel[], 
        warn?: string
    ) => {
        if (stepPanels.length === 0) return;
        
        // Aggregate hardware for these panels
        const hwMap: Record<string, number> = {};
        stepPanels.forEach(p => {
            p.hardware.forEach(h => {
                // Filter out manufacturing-only markers if needed, but usually we count installation hardware
                const name = getHardwareName(h.type);
                hwMap[name] = (hwMap[name] || 0) + 1;
            });
            remainingPanels.delete(p.id);
        });

        const hwList = Object.entries(hwMap).map(([name, qty]) => ({ name, qty }));
        // Estimate time: 2 min per panel + 30s per hardware piece
        const time = Math.ceil(stepPanels.length * 2 + hwList.reduce((acc, i) => acc + i.qty, 0) * 0.5);

        steps.push({
            step: stepCounter++,
            title,
            description: desc,
            panels: stepPanels.map(p => p.id),
            hardware: hwList,
            timeEstimate: time < 5 ? 5 : time,
            warning: warn
        });
    };

    // 1. BASE / BOTTOM
    // Find horizontal panels near Y=0 or Base Height (e.g. < 200mm)
    const bottoms = panels.filter(p => remainingPanels.has(p.id) && p.rotation === Axis.Y && p.y < 200);
    if (bottoms.length > 0) {
        addStep(
            "Сборка основания", 
            "Установите дно конструкции. Если предусмотрены цокольные планки или ножки, закрепите их на этом этапе.", 
            bottoms,
            "Работайте на чистой ровной поверхности или картоне, чтобы не повредить кромку."
        );
    }

    // 2. VERTICALS (Sides & Partitions)
    // Vertical panels (Rotation X)
    const verticals = panels.filter(p => remainingPanels.has(p.id) && p.rotation === Axis.X);
    if (verticals.length > 0) {
        addStep(
            "Установка стоек", 
            "Установите боковые стенки и внутренние перегородки. Закрепите их к основанию конфирматами или эксцентриками.", 
            verticals,
            "Может потребоваться помощник для удержания вертикальных деталей."
        );
    }

    // 3. FIXED SHELVES (Structural horizontal)
    // Horizontal panels that act as stiffeners (usually marked as body or have hardware)
    // Exclude removable shelves (often layer 'shelves' without hard connections, but we'll use layer heuristic)
    const structuralShelves = panels.filter(p => remainingPanels.has(p.id) && p.rotation === Axis.Y && p.layer !== 'shelves');
    
    // Also include Roof if it's not at the very top (e.g. intermediate fixed shelf)
    const highY = Math.max(...panels.map(p => p.y));
    const fixedShelves = structuralShelves.filter(s => s.y < highY - 50); // Not the top roof yet

    if (fixedShelves.length > 0) {
        addStep(
            "Жесткие горизонты", 
            "Установите горизонтальные связи и полки жесткости. Это придаст конструкции устойчивость и геометрию.", 
            fixedShelves
        );
    }

    // 4. ROOF / TOP
    const tops = panels.filter(p => remainingPanels.has(p.id) && p.rotation === Axis.Y); // Remaining Y-rot panels (should be top)
    if (tops.length > 0) {
        addStep(
            "Установка крыши", 
            "Накройте конструкцию крышкой. Проверьте равенство диагоналей перед окончательной затяжкой крепежа.", 
            tops,
            "Обязательно проверьте диагонали рулеткой (A = B)."
        );
    }

    // 5. BACK PANEL
    const backs = panels.filter(p => remainingPanels.has(p.id) && (p.layer === 'back' || p.materialId.includes('hdf') || p.depth <= 4));
    if (backs.length > 0) {
        addStep(
            "Задняя стенка", 
            "Закрепите заднюю стенку (ХДФ/ДВП). Используйте гвозди или саморезы с шагом 150мм.", 
            backs,
            "Задняя стенка фиксирует геометрию шкафа. Убедитесь, что углы прямые."
        );
    }

    // 6. INTERNAL FILLING (Removable Shelves)
    const removableShelves = panels.filter(p => remainingPanels.has(p.id) && p.layer === 'shelves');
    if (removableShelves.length > 0) {
        addStep(
            "Внутреннее наполнение", 
            "Установите полкодержатели в подготовленные отверстия и вложите съемные полки.", 
            removableShelves
        );
    }

    // 7. FACADES & DRAWERS
    // Drawers first
    const drawers = panels.filter(p => remainingPanels.has(p.id) && p.openingType === 'drawer');
    if (drawers.length > 0) {
        addStep(
            "Сборка ящиков", 
            "Соберите короба ящиков, установите дно и прикрутите фасады. Вставьте ящики в направляющие.", 
            drawers
        );
    }

    // Doors/Facades
    const doors = panels.filter(p => remainingPanels.has(p.id) && (p.layer === 'facade' || p.openingType === 'left' || p.openingType === 'right'));
    if (doors.length > 0) {
        addStep(
            "Навеска фасадов", 
            "Установите петли на фасады и прикрутите ответные планки к корпусу. Навесьте двери и отрегулируйте зазоры.", 
            doors,
            "Не затягивайте регулировочные винты сразу до упора, оставьте ход для настройки."
        );
    }

    // Catch leftovers (anything missed by logic)
    const leftovers = panels.filter(p => remainingPanels.has(p.id));
    if (leftovers.length > 0) {
        addStep("Завершение", "Установите оставшиеся детали, заглушки и декоративные элементы.", leftovers);
    }

    return steps;
};

// --- 3D STEP VISUALIZER ---

const StepVisualizer: React.FC<{ panels: Panel[], activePanelIds: string[], completedPanelIds: string[] }> = ({ panels, activePanelIds, completedPanelIds }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const sceneRef = useRef<Scene | null>(null);
    const groupRef = useRef<Group | null>(null);
    const rendererRef = useRef<WebGLRenderer | null>(null);

    // Initial Setup
    useEffect(() => {
        if (!containerRef.current) return;
        const width = containerRef.current.clientWidth;
        const height = containerRef.current.clientHeight;

        const scene = new Scene();
        scene.background = new Color('#f1f5f9'); // Light slate bg
        sceneRef.current = scene;

        const camera = new PerspectiveCamera(45, width / height, 10, 10000);
        camera.position.set(2000, 2000, 3000);

        const renderer = new WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
        renderer.setSize(width, height);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = PCFSoftShadowMap;
        containerRef.current.appendChild(renderer.domElement);
        rendererRef.current = renderer;

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 1.0;

        // Lights
        const ambientLight = new AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);
        
        const dirLight = new DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(1500, 2500, 1500);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.width = 1024;
        dirLight.shadow.mapSize.height = 1024;
        scene.add(dirLight);

        const group = new Group();
        groupRef.current = group;
        scene.add(group);

        // Animation Loop
        let frameId: number;
        const animate = () => {
            frameId = requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();

        // Handle Resize
        const handleResize = () => {
            if(!containerRef.current) return;
            const w = containerRef.current.clientWidth;
            const h = containerRef.current.clientHeight;
            camera.aspect = w/h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            cancelAnimationFrame(frameId);
            renderer.dispose();
            if (containerRef.current) containerRef.current.innerHTML = '';
        };
    }, []);

    // Update Objects based on step
    useEffect(() => {
        if (!groupRef.current) return;
        const group = groupRef.current;
        group.clear();

        // Materials
        const matCompleted = new MeshStandardMaterial({ 
            color: 0xffffff, 
            transparent: true, 
            opacity: 0.5,
            roughness: 0.5 
        }); // Ghostly white
        
        const matActive = new MeshStandardMaterial({ 
            color: 0x22c55e, // Green 500
            roughness: 0.4,
            metalness: 0.1
        }); 
        
        const edgeColor = 0x94a3b8;

        panels.forEach(p => {
            const isActive = activePanelIds.includes(p.id);
            const isCompleted = completedPanelIds.includes(p.id);

            if (!isActive && !isCompleted) return; // Hide future steps

            let dX = 0, dY = 0, dZ = 0;
            if (p.rotation === Axis.X) { dX=p.depth; dY=p.height; dZ=p.width; }
            else if (p.rotation === Axis.Y) { dX=p.width; dY=p.depth; dZ=p.height; }
            else { dX=p.width; dY=p.height; dZ=p.depth; }

            const geometry = new BoxGeometry(dX, dY, dZ);
            const material = isActive ? matActive : matCompleted;
            
            const mesh = new Mesh(geometry, material);
            mesh.position.set(p.x + dX/2, p.y + dY/2, p.z + dZ/2);
            mesh.castShadow = true;
            mesh.receiveShadow = true;

            // Edges for definition
            const edges = new LineSegments(
                new EdgesGeometry(geometry),
                new LineBasicMaterial({ color: isActive ? 0x14532d : edgeColor, transparent: !isActive, opacity: isActive ? 1 : 0.3 })
            );
            mesh.add(edges);

            group.add(mesh);
        });

        // Auto Center Camera Target (Keep camera position, just look at center)
        if (group.children.length > 0) {
            const box = new Box3().setFromObject(group);
            // We usually want to keep the floor at y=0 visually, but center X/Z
            // const center = box.getCenter(new Vector3());
            // group.position.x = -center.x;
            // group.position.z = -center.z;
        }

    }, [panels, activePanelIds, completedPanelIds]);

    return <div ref={containerRef} className="w-full h-full bg-slate-100" />;
};

// --- MAIN COMPONENT ---

export const AssemblyGuide: React.FC<{ onClose?: () => void }> = ({ onClose }) => {
    const { panels } = useProjectStore();
    const [currentStepIdx, setCurrentStepIdx] = useState(0);
    const steps = useMemo(() => generateSteps(panels), [panels]);

    const currentStep = steps[currentStepIdx];
    
    // Accumulate all panel IDs from step 0 to current-1
    const completedPanelIds = useMemo(() => {
        const ids: string[] = [];
        for (let i = 0; i < currentStepIdx; i++) {
            ids.push(...steps[i].panels);
        }
        return ids;
    }, [currentStepIdx, steps]);

    const totalTime = useMemo(() => steps.reduce((acc, s) => acc + s.timeEstimate, 0), [steps]);

    return (
        <div className="flex flex-col h-full bg-white text-slate-800 font-sans">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-white print:hidden shadow-sm z-20">
                <div className="flex items-center gap-3">
                    {onClose && (
                        <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-500">
                            <ArrowRight className="rotate-180" size={20}/>
                        </button>
                    )}
                    <div>
                        <h2 className="text-xl font-bold flex items-center gap-2">
                            <Wrench className="text-blue-600"/> Инструкция по сборке
                        </h2>
                        <p className="text-xs text-slate-500">Всего шагов: {steps.length} • Время: ~{Math.floor(totalTime/60)}ч {totalTime%60}мин</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => window.print()} className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 transition">
                        <Printer size={16}/> Печать PDF
                    </button>
                </div>
            </div>

            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                
                {/* LEFT: Step Info */}
                <div className="w-full md:w-96 flex flex-col border-r border-slate-200 bg-slate-50 overflow-y-auto print:w-full print:border-none print:h-auto print:overflow-visible">
                    
                    {/* Controls */}
                    <div className="p-4 flex items-center justify-between bg-white border-b border-slate-200 shadow-sm sticky top-0 z-10 print:hidden">
                        <button 
                            onClick={() => setCurrentStepIdx(Math.max(0, currentStepIdx - 1))}
                            disabled={currentStepIdx === 0}
                            className="p-2 rounded hover:bg-slate-100 disabled:opacity-30 transition"
                        >
                            <ChevronLeft size={24}/>
                        </button>
                        <div className="text-center">
                            <div className="text-xs font-bold text-slate-400 uppercase">Шаг</div>
                            <div className="text-xl font-black text-blue-600">{currentStepIdx + 1} / {steps.length}</div>
                        </div>
                        <button 
                            onClick={() => setCurrentStepIdx(Math.min(steps.length - 1, currentStepIdx + 1))}
                            disabled={currentStepIdx === steps.length - 1}
                            className="p-2 rounded hover:bg-slate-100 disabled:opacity-30 transition"
                        >
                            <ChevronRight size={24}/>
                        </button>
                    </div>

                    {/* Step Content */}
                    <div className="p-6 space-y-6">
                        {currentStep ? (
                            <>
                                <div>
                                    <div className="text-sm font-bold text-slate-400 uppercase mb-1 print:hidden">Текущее действие</div>
                                    <h1 className="text-2xl font-bold mb-2 text-slate-900">{currentStep.title}</h1>
                                    <p className="text-slate-600 leading-relaxed text-sm">{currentStep.description}</p>
                                </div>

                                {currentStep.warning && (
                                    <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg flex items-start gap-3 text-amber-800 text-xs font-medium">
                                        <AlertTriangle size={16} className="shrink-0 mt-0.5"/>
                                        {currentStep.warning}
                                    </div>
                                )}

                                <div>
                                    <h3 className="font-bold text-xs text-slate-400 uppercase mb-3 flex items-center gap-2">
                                        <Box size={14}/> Фурнитура и Детали
                                    </h3>
                                    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100 shadow-sm">
                                        {currentStep.hardware.map((hw, i) => (
                                            <div key={i} className="flex justify-between items-center p-3">
                                                <span className="text-sm font-medium text-slate-700">{hw.name}</span>
                                                <span className="bg-slate-100 text-slate-700 px-2 py-1 rounded text-xs font-bold">x{hw.qty}</span>
                                            </div>
                                        ))}
                                        {currentStep.hardware.length === 0 && (
                                            <div className="p-3 text-xs text-slate-400 italic">Без дополнительной фурнитуры</div>
                                        )}
                                    </div>
                                </div>

                                <div className="flex items-center gap-2 text-xs text-slate-500 bg-white p-3 rounded-lg border border-slate-200">
                                    <Clock size={14} className="text-blue-500"/>
                                    Примерное время: <span className="font-bold text-slate-800">{currentStep.timeEstimate} мин</span>
                                </div>
                            </>
                        ) : (
                            <div className="text-center py-20 text-slate-400">Нет шагов для отображения. Возможно, проект пуст.</div>
                        )}
                    </div>

                    {/* Printable Full List (Hidden on Screen) */}
                    <div className="hidden print:block p-8">
                        <div className="text-2xl font-bold mb-6 text-center">План сборки мебели</div>
                        {steps.map((step, i) => (
                            <div key={i} className="mb-8 break-inside-avoid border-b border-slate-300 pb-6">
                                <div className="flex items-center gap-4 mb-2">
                                    <div className="w-8 h-8 bg-black text-white rounded-full flex items-center justify-center font-bold">{step.step}</div>
                                    <div className="font-bold text-xl">{step.title}</div>
                                </div>
                                <p className="mb-4 text-sm text-gray-700 pl-12">{step.description}</p>
                                {step.warning && <div className="ml-12 mb-4 font-bold text-xs bg-gray-100 p-2 border-l-4 border-black">⚠ {step.warning}</div>}
                                
                                {step.hardware.length > 0 && (
                                    <div className="ml-12 grid grid-cols-2 gap-2 text-xs">
                                        {step.hardware.map((h, hi) => <div key={hi} className="font-mono">• {h.name}: <b>{h.qty}</b></div>)}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* RIGHT: 3D Visualization */}
                <div className="flex-1 bg-slate-100 relative print:hidden h-[50vh] md:h-auto">
                    {currentStep && (
                        <StepVisualizer 
                            panels={panels} 
                            activePanelIds={currentStep.panels} 
                            completedPanelIds={completedPanelIds} 
                        />
                    )}
                    
                    <div className="absolute bottom-6 left-6 bg-white/90 backdrop-blur p-4 rounded-xl shadow-lg border border-white/20 max-w-xs">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                            <span className="text-xs font-bold text-green-700">АКТИВНЫЕ ДЕТАЛИ (ШАГ {currentStepIdx+1})</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 bg-slate-300 rounded-full border border-slate-400"></div>
                            <span className="text-xs font-bold text-slate-500">УСТАНОВЛЕНО РАНЕЕ</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};