
import React, { useEffect, useRef, useMemo, useState } from 'react';
import { CabinetProvider, useCabinet } from './CabinetContext';
import { CabinetGenerator } from '../services/CabinetGenerator';
import { InputValidator } from '../services/InputValidator';
import { CollisionValidator, CollisionResult } from '../services/CollisionValidator';
import { useProjectStore } from '../store/projectStore';
import { CabinetParams, Panel, Section } from '../types';
import { Scene, PerspectiveCamera, WebGLRenderer, Group, Color, DirectionalLight, AmbientLight, Raycaster, Vector2 } from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { 
  Settings, Box, Minus, Archive, Trash2, AlertTriangle, MonitorPlay, ArrowUp, Scale, AlertOctagon, Undo2, Redo2, Plus, MousePointerClick
} from 'lucide-react';
import { ShelfInfoPanel } from './ShelfInfoPanel';
import { MaterialSelector } from './MaterialSelector';
import { ProjectManager } from './ProjectManager';
import { ExportPanel } from './ExportPanel';
import { Tooltip } from './Tooltip';

interface CabinetWizardProps {
  onGenerate: (panels: Panel[]) => void;
  materialLibrary: any[]; 
  initialState?: { config: CabinetParams; sections: Section[] } | null;
}

// --- INNER COMPONENT USING CONTEXT ---
const WizardContent: React.FC<{ onGenerateFinal: (p: Panel[]) => void }> = ({ onGenerateFinal }) => {
    const { params, updateParams, addShelf, addDrawer, removeItem, undo, redo, canUndo, canRedo } = useCabinet();
    const { addToast } = useProjectStore(); 
    const canvasRef = useRef<HTMLDivElement>(null);
    const threeRef = useRef<{ scene: Scene, camera: PerspectiveCamera, renderer: WebGLRenderer, group: Group, orbit: OrbitControls, transform: TransformControls } | null>(null);
    
    // Selection state for Drag & Drop
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const isDraggingRef = useRef(false);

    // Validators
    const inputValidator = useMemo(() => new InputValidator(), []);
    const collisionValidator = useMemo(() => new CollisionValidator(), []);
    
    const [validation, setValidation] = useState<CollisionResult>({ 
        hasCriticalErrors: false, 
        errors: new Map(), 
        warnings: new Map() 
    });

    // Run Validation
    useEffect(() => {
        const result = collisionValidator.validate(params);
        setValidation(result);
    }, [params, collisionValidator]);

    // Keyboard Undo/Redo
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
                e.preventDefault();
                e.stopPropagation(); // Stop global undo
                if (canUndo) undo();
            }
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
                e.preventDefault();
                e.stopPropagation();
                if (canRedo) redo();
            }
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (selectedId) {
                    // Try to delete selected item
                    if (params.shelves.some(s => s.id === selectedId)) removeItem(selectedId, 'shelf');
                    else if (params.drawers.some(d => d.id === selectedId)) removeItem(selectedId, 'drawer');
                    setSelectedId(null);
                }
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [undo, redo, canUndo, canRedo, selectedId, params, removeItem]);

    // 3D Preview Init
    useEffect(() => {
        if (!canvasRef.current) return;
        const width = canvasRef.current.clientWidth;
        const height = canvasRef.current.clientHeight;

        const scene = new Scene();
        scene.background = new Color('#222');

        const camera = new PerspectiveCamera(50, width / height, 0.1, 5000);
        camera.position.set(1500, 1500, 2500);

        const renderer = new WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(width, height);
        canvasRef.current.appendChild(renderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 1.0;

        const light = new DirectionalLight(0xffffff, 1);
        light.position.set(500, 1000, 500);
        scene.add(light);
        scene.add(new AmbientLight(0xffffff, 0.5));

        const group = new Group();
        scene.add(group);

        // Transform Controls for Drag & Drop
        const transformControl = new TransformControls(camera, renderer.domElement);
        // Only allow Y axis movement for shelves/drawers typically
        transformControl.showX = false;
        transformControl.showZ = false;
        
        transformControl.addEventListener('dragging-changed', (event) => {
            controls.enabled = !event.value;
            isDraggingRef.current = event.value;
            controls.autoRotate = false; // Stop rotating when user interacts

            if (!event.value && transformControl.object) {
                // Drag Ended - Commit changes
                const mesh = transformControl.object;
                const itemId = mesh.userData.id;
                
                // Calculate new Y based on mesh position.
                // CabinetGenerator generates mesh at: p.y + dY/2. 
                // Since dY (thickness) is 16 usually:
                // New Y = Mesh Y - 8.
                const thickness = 16; 
                const newY = Math.round(mesh.position.y - thickness / 2);

                if (itemId) {
                    // Determine if shelf or drawer and update
                    // We need to access the LATEST params, but we are inside a callback closure.
                    // However, we can infer type by checking if it exists in the *current* render's params via a ref or by assuming structure.
                    // For simplicity, we dispatch an update that checks both.
                    
                    // Note: We use the context's update function which will process based on current state in context
                    // We must pass the logic to the parent or use a ref for params. 
                    // Since `updateParams` is stable, we can call it. But we need to know what to update.
                    // We'll optimistically update both arrays if found.
                    
                    // Actually, we can just trigger a special event or use the props.
                    // But here we don't have access to "current" params inside this callback unless we use a Ref for params.
                    // Let's rely on the fact that `updateParams` merges.
                    
                    // We need a way to send this update back. 
                    // We will emit a custom event or use a mutable ref for the callback.
                    onDragEnd(itemId, newY);
                }
            }
        });
        scene.add(transformControl);

        threeRef.current = { scene, camera, renderer, group, orbit: controls, transform: transformControl };

        const animate = () => {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();

        // Raycasting for Selection
        const onPointerDown = (event: PointerEvent) => {
            if (isDraggingRef.current) return; // Don't select while dragging

            // Calculate mouse position in normalized device coordinates
            const rect = renderer.domElement.getBoundingClientRect();
            const mouse = new Vector2(
                ((event.clientX - rect.left) / rect.width) * 2 - 1,
                -((event.clientY - rect.top) / rect.height) * 2 + 1
            );

            const raycaster = new Raycaster();
            raycaster.setFromCamera(mouse, camera);

            const intersects = raycaster.intersectObjects(group.children);

            if (intersects.length > 0) {
                // Find the first object that has an ID
                const hit = intersects.find(i => i.object.userData.id);
                if (hit) {
                    const id = hit.object.userData.id;
                    if (id !== selectedId) {
                        setSelectedId(id);
                        controls.autoRotate = false; // Stop rotation on selection
                    }
                    return;
                }
            }
            
            // If clicked empty space, deselect
            setSelectedId(null);
        };

        renderer.domElement.addEventListener('pointerdown', onPointerDown);

        const handleResize = () => {
            if (!canvasRef.current || !camera || !renderer) return;
            const w = canvasRef.current.clientWidth;
            const h = canvasRef.current.clientHeight;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            renderer.domElement.removeEventListener('pointerdown', onPointerDown);
            transformControl.dispose();
            renderer.dispose();
            if (canvasRef.current) canvasRef.current.innerHTML = '';
        };
    }, []);

    // Helper to handle updates from the persistent 3D callback
    const onDragEnd = (id: string, y: number) => {
        // We use a functional update to ensure we have latest state if we were using setState,
        // but here we use the context's updateParams which merges.
        // However, we need to know if it's a shelf or drawer to form the correct partial object.
        // We can check the ID prefix we generate. 'sh-' vs 'dr-'
        
        if (id.startsWith('sh-')) {
            // It's a shelf. We need the current list of shelves to update one item.
            // Since we can't access `params` inside the useEffect closure easily without adding it to dependency (which resets scene),
            // we will pass this logic to a ref-based handler or force a re-render.
            // Actually, `updateParams` is stable. The issue is `params.shelves` is needed.
            
            // Workaround: We'll use a Ref to store current params so the cleanup-less useEffect can access it.
            // See paramsRef below.
            const currentShelves = paramsRef.current.shelves;
            const newShelves = currentShelves.map(s => s.id === id ? { ...s, y } : s);
            updateParams({ shelves: newShelves });
            addToast(`Высота изменена: ${y} мм`, 'info');
        } else if (id.startsWith('dr-') || id.startsWith('fa-')) { // drawer or facade
            const currentDrawers = paramsRef.current.drawers;
            // Drawers might have facade ID separate, assuming grouped logic or finding by prefix
            const newDrawers = currentDrawers.map(d => d.id === id ? { ...d, y } : d);
            updateParams({ drawers: newDrawers });
            addToast(`Высота ящика изменена: ${y} мм`, 'info');
        }
    };

    // Keep a ref to params for the 3D event handlers
    const paramsRef = useRef(params);
    useEffect(() => { paramsRef.current = params; }, [params]);

    // Update 3D Content
    useEffect(() => {
        if (!threeRef.current) return;
        const { group, transform } = threeRef.current;
        
        // If dragging, DO NOT regenerate geometry, otherwise we lose the handle
        if (isDraggingRef.current) return;

        // Remove old
        group.clear();

        // Generate new
        const previewGroup = CabinetGenerator.generatePreviewGroup(params);
        group.add(previewGroup);

        // Re-attach transform controls if selection persists
        if (selectedId) {
            const selectedMesh = group.children.find(c => c.userData.id === selectedId);
            if (selectedMesh) {
                transform.attach(selectedMesh);
            } else {
                transform.detach();
                setSelectedId(null);
            }
        } else {
            transform.detach();
        }

    }, [params, selectedId]); // Re-run when params change or selection changes

    const handleGenerate = () => {
        if (validation.hasCriticalErrors) {
            addToast('Исправьте критические ошибки перед генерацией', 'error');
            return;
        }
        const panels = CabinetGenerator.generateFromParams(params);
        onGenerateFinal(panels);
    };

    const handleDistributeShelves = () => {
        const count = params.shelves.length;
        if (count < 2) return;

        const newYPositions = inputValidator.getOptimalSpacing(count, params.height);
        const sortedShelves = [...params.shelves].sort((a, b) => a.y - b.y);
        const updatedShelves = sortedShelves.map((shelf, index) => ({
            ...shelf,
            y: newYPositions[index]
        }));

        updateParams({ shelves: updatedShelves });
        const gap = newYPositions.length > 1 ? (newYPositions[1] - newYPositions[0]) : newYPositions[0];
        addToast(`✓ Полки распределены равномерно! Расстояние: ~${Math.round(gap)} мм`, 'success');
    };

    return (
        <div className="flex flex-col md:flex-row h-full bg-[#111] text-slate-300">
            {/* LEFT COLUMN: Controls */}
            <div className="w-full md:w-96 flex flex-col border-r border-slate-700 bg-[#1a1a1a] shadow-2xl z-10 overflow-hidden">
                <div className="p-4 border-b border-slate-700 bg-[#222]">
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                        <Settings className="text-blue-500" /> Параметры Шкафа
                    </h2>
                    <div className="flex justify-end gap-2 mt-2">
                        <Tooltip content="Отменить (Ctrl+Z)">
                            <button onClick={undo} disabled={!canUndo} className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30"><Undo2 size={16}/></button>
                        </Tooltip>
                        <Tooltip content="Повторить (Ctrl+Y)">
                            <button onClick={redo} disabled={!canRedo} className="p-1.5 rounded hover:bg-slate-700 disabled:opacity-30"><Redo2 size={16}/></button>
                        </Tooltip>
                        <ProjectManager />
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-6 no-scrollbar">
                    {/* Dimensions */}
                    <div className="space-y-4">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Габариты</label>
                        <div className="grid grid-cols-3 gap-3">
                            <div><span className="text-[10px] text-slate-400">Ширина</span><input type="number" value={params.width} onChange={e => updateParams({width: +e.target.value})} className="w-full bg-[#111] border border-slate-600 rounded p-2 text-sm text-white focus:border-blue-500 outline-none" /></div>
                            <div><span className="text-[10px] text-slate-400">Высота</span><input type="number" value={params.height} onChange={e => updateParams({height: +e.target.value})} className="w-full bg-[#111] border border-slate-600 rounded p-2 text-sm text-white focus:border-blue-500 outline-none" /></div>
                            <div><span className="text-[10px] text-slate-400">Глубина</span><input type="number" value={params.depth} onChange={e => updateParams({depth: +e.target.value})} className="w-full bg-[#111] border border-slate-600 rounded p-2 text-sm text-white focus:border-blue-500 outline-none" /></div>
                        </div>
                    </div>

                    {/* Material */}
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Материал</label>
                        <MaterialSelector />
                    </div>

                    {/* Filling */}
                    <div className="space-y-3">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Наполнение</label>
                        <div className="grid grid-cols-2 gap-2">
                            <Tooltip content="Добавить горизонтальную полку (толщина 16мм)">
                                {/* Removing hardcoded 1500 value to use smart calculation */}
                                <button onClick={() => addShelf()} className="flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 text-white p-2 rounded text-xs font-bold transition w-full">
                                    <Plus size={14} /> Полка
                                </button>
                            </Tooltip>
                            <Tooltip content="Добавить выдвижной ящик с направляющими">
                                <button onClick={() => addDrawer(600)} className="flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 text-white p-2 rounded text-xs font-bold transition w-full">
                                    <Archive size={14} /> Ящик
                                </button>
                            </Tooltip>
                        </div>
                        <Tooltip content="Автоматически распределить полки по высоте">
                            <button 
                                onClick={handleDistributeShelves}
                                disabled={params.shelves.length < 2}
                                className="w-full py-2 bg-[#0066CC] hover:bg-[#0052a3] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded text-[10px] uppercase font-bold flex items-center justify-center gap-2 transition shadow-md"
                            >
                                <Scale size={14} /> Распределить равномерно
                            </button>
                        </Tooltip>
                    </div>

                    {/* Items List */}
                    <div className="space-y-2">
                        {[...params.shelves, ...params.drawers]
                            .sort((a, b) => b.y - a.y)
                            .map((item, idx) => (
                                'type' in item 
                                ? (
                                    // Shelf Panel
                                    <ShelfInfoPanel 
                                        key={item.id} 
                                        shelf={item} 
                                        index={idx}
                                        cabinetWidth={params.width}
                                        cabinetDepth={params.depth}
                                        material={params.material}
                                        maxHeight={params.height}
                                        isSelected={selectedId === item.id}
                                        onSelect={() => setSelectedId(item.id)}
                                        validationError={validation.errors.get(item.id)}
                                        validationWarning={validation.warnings.get(item.id)}
                                        onUpdate={(updated) => updateParams({ shelves: params.shelves.map(s => s.id === item.id ? updated : s) })}
                                        onDelete={() => removeItem(item.id, 'shelf')}
                                    />
                                ) 
                                : (
                                    // Drawer Panel
                                    <div 
                                        key={item.id} 
                                        onClick={() => setSelectedId(item.id)}
                                        className={`bg-[#222] p-3 rounded border flex justify-between items-center cursor-pointer transition
                                            ${selectedId === item.id ? 'border-blue-500 bg-blue-900/20' : 'border-slate-700 hover:border-slate-500'}
                                        `}
                                    >
                                        <div className="flex items-center gap-2">
                                            <Archive size={14} className="text-orange-400"/>
                                            <span className="text-xs font-bold">Ящик H={item.height}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs font-mono text-blue-400">Y: {item.y}</span>
                                            <button onClick={(e) => { e.stopPropagation(); removeItem(item.id, 'drawer'); }} className="text-red-500 hover:bg-slate-700 p-1 rounded"><Trash2 size={12}/></button>
                                        </div>
                                    </div>
                                )
                        ))}
                        {params.shelves.length === 0 && params.drawers.length === 0 && (
                            <div className="text-center text-slate-600 text-xs py-4 border border-dashed border-slate-700 rounded">
                                Пусто
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer Action */}
                <div className="p-4 border-t border-slate-700 bg-[#222]">
                    <button 
                        onClick={handleGenerate}
                        disabled={validation.hasCriticalErrors}
                        className={`w-full py-3 rounded font-bold text-sm flex items-center justify-center gap-2 transition
                            ${validation.hasCriticalErrors ? 'bg-red-900/50 text-red-300 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg'}
                        `}
                    >
                        {validation.hasCriticalErrors ? <AlertOctagon size={18}/> : <MonitorPlay size={18}/>}
                        {validation.hasCriticalErrors ? 'Ошибки в конструкции' : 'Сгенерировать'}
                    </button>
                </div>
            </div>

            {/* RIGHT COLUMN: 3D Preview */}
            <div className="flex-1 relative bg-[#000]">
                <div ref={canvasRef} className="w-full h-full cursor-move" />
                
                {/* Overlay Info */}
                <div className="absolute top-4 right-4 bg-black/70 backdrop-blur p-4 rounded-xl border border-white/10 text-right pointer-events-none">
                    <div className="text-2xl font-bold text-white">{params.width} <span className="text-slate-500 text-sm">x</span> {params.height}</div>
                    <div className="text-xs text-slate-400 mt-1 uppercase font-bold">Глубина: {params.depth} мм</div>
                </div>

                {/* Tooltip Overlay */}
                <div className="absolute top-4 left-4 pointer-events-none">
                    <div className="text-[10px] text-slate-400 bg-black/50 px-2 py-1 rounded border border-white/5 flex items-center gap-2">
                        <MousePointerClick size={12} className="text-blue-400"/>
                        Нажмите на полку для перемещения (Drag & Drop)
                    </div>
                </div>

                <div className="absolute bottom-4 left-4">
                    <ExportPanel />
                </div>
            </div>
        </div>
    );
};

export const CabinetWizard: React.FC<CabinetWizardProps> = (props) => {
    const initialParams = props.initialState?.config; 
    
    return (
        <CabinetProvider initialParams={initialParams}>
            <WizardContent onGenerateFinal={props.onGenerate} />
        </CabinetProvider>
    );
};
