import React, { useEffect, useRef, useState } from 'react';
import { 
    Scene, PerspectiveCamera, WebGLRenderer, Group, Vector3, Color, 
    AmbientLight, DirectionalLight, LineBasicMaterial, MeshLambertMaterial, 
    MeshBasicMaterial, BoxGeometry, Mesh, LineSegments, EdgesGeometry, SphereGeometry 
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { useProjectStore } from '../store/projectStore';
import { Axis } from '../types';
import { Expand, Download, Info } from 'lucide-react';

const AssemblyDiagram: React.FC = () => {
    const { panels } = useProjectStore();
    const containerRef = useRef<HTMLDivElement>(null);
    const [explodeFactor, setExplodeFactor] = useState(0.5); // 0 to 2
    
    // Explicitly use THREE namespace for types to avoid ambiguity
    const sceneRef = useRef<Scene | null>(null);
    const cameraRef = useRef<PerspectiveCamera | null>(null);
    const rendererRef = useRef<WebGLRenderer | null>(null);
    const groupRef = useRef<Group | null>(null);
    const labelsRef = useRef<HTMLDivElement>(null);

    // Calculate center of assembly
    const center = useRef(new Vector3());

    // Init Scene
    useEffect(() => {
        if (!containerRef.current) return;

        const scene = new Scene();
        scene.background = new Color('#ffffff');
        sceneRef.current = scene;

        const camera = new PerspectiveCamera(45, containerRef.current.clientWidth / containerRef.current.clientHeight, 1, 10000);
        camera.position.set(2000, 2000, 3000);
        cameraRef.current = camera;

        const renderer = new WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
        renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
        renderer.shadowMap.enabled = true;
        containerRef.current.appendChild(renderer.domElement);
        rendererRef.current = renderer;

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        
        // Lighting
        const ambientLight = new AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);
        const dirLight = new DirectionalLight(0xffffff, 0.7);
        dirLight.position.set(1000, 2000, 1000);
        dirLight.castShadow = true;
        scene.add(dirLight);

        // Group
        const group = new Group();
        groupRef.current = group;
        scene.add(group);

        const animate = () => {
            requestAnimationFrame(animate);
            controls.update();
            updateLabels();
            renderer.render(scene, camera);
        };
        animate();

        return () => {
            renderer.dispose();
            if(containerRef.current) containerRef.current.innerHTML = '';
        };
    }, []);

    // Build Objects
    useEffect(() => {
        if (!groupRef.current || panels.length === 0) return;
        
        const group = groupRef.current;
        group.clear();

        // Calculate Bounding Box to find center
        let minX = Infinity, minY = Infinity, minZ = Infinity;
        let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

        panels.forEach(p => {
            minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); minZ = Math.min(minZ, p.z);
            let dX = p.width, dY = p.height, dZ = p.depth;
            if (p.rotation === Axis.X) { dX=p.depth; dY=p.height; dZ=p.width; }
            else if (p.rotation === Axis.Y) { dX=p.width; dY=p.depth; dZ=p.height; }
            else { dX=p.width; dY=p.height; dZ=p.depth; } // Z
            
            maxX = Math.max(maxX, p.x + dX);
            maxY = Math.max(maxY, p.y + dY);
            maxZ = Math.max(maxZ, p.z + dZ);
        });

        center.current.set((minX+maxX)/2, (minY+maxY)/2, (minZ+maxZ)/2);

        // Materials
        const edgeMat = new LineBasicMaterial({ color: 0x000000, linewidth: 2 });
        const faceMat = new MeshLambertMaterial({ color: 0xf0f0f0, transparent: true, opacity: 0.9 });
        const fastenerMat = new MeshBasicMaterial({ color: 0xff0000 });

        panels.forEach((p, idx) => {
            if(!p.visible) return;

            // Dimensions based on rotation
            let dX = 0, dY = 0, dZ = 0;
            if (p.rotation === Axis.X) { dX=p.depth; dY=p.height; dZ=p.width; }
            else if (p.rotation === Axis.Y) { dX=p.width; dY=p.depth; dZ=p.height; }
            else { dX=p.width; dY=p.height; dZ=p.depth; }

            const geometry = new BoxGeometry(dX, dY, dZ);
            const mesh = new Mesh(geometry, faceMat);
            const edges = new LineSegments(new EdgesGeometry(geometry), edgeMat);
            
            mesh.add(edges);
            
            // Store original position and dimensions in userData
            const originalPos = new Vector3(p.x + dX/2, p.y + dY/2, p.z + dZ/2);
            mesh.userData = { 
                originalPos: originalPos,
                id: idx + 1,
                panelId: p.id
            };
            
            // Initial position
            mesh.position.copy(originalPos);
            group.add(mesh);

            // Add Fasteners Visuals (Simplified Rules)
            if (p.hardware && p.hardware.length > 0) {
                p.hardware.forEach(hw => {
                     const fGeo = new SphereGeometry(3, 8, 8);
                     const fMesh = new Mesh(fGeo, fastenerMat);
                     fMesh.position.set(0, 0, 0); 
                     mesh.add(fMesh);
                });
            }
        });

    }, [panels]);

    // Handle Explosion
    useEffect(() => {
        if (!groupRef.current) return;
        
        groupRef.current.children.forEach(child => {
            const mesh = child as Mesh;
            const originalPos = mesh.userData.originalPos as Vector3;
            if (!originalPos) return;

            // Vector from center to part center
            const dir = new Vector3().subVectors(originalPos, center.current);
            
            // Explode logic: Move away from center
            const newPos = new Vector3().copy(originalPos).add(dir.multiplyScalar(explodeFactor));
            mesh.position.lerp(newPos, 0.5); 
            mesh.position.copy(newPos);
        });
    }, [explodeFactor, panels]);

    // Label Update Logic
    const updateLabels = () => {
        if (!groupRef.current || !labelsRef.current || !cameraRef.current) return;
        
        const camera = cameraRef.current;
        const widthHalf = containerRef.current!.clientWidth / 2;
        const heightHalf = containerRef.current!.clientHeight / 2;
        
        labelsRef.current.innerHTML = '';

        groupRef.current.children.forEach(child => {
             const mesh = child as Mesh;
             const pos = mesh.position.clone();
             pos.project(camera);
             
             const x = (pos.x * widthHalf) + widthHalf;
             const y = -(pos.y * heightHalf) + heightHalf;

             if (pos.z < 1) {
                 const el = document.createElement('div');
                 el.className = 'absolute bg-white border border-black rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shadow-md';
                 el.style.left = `${x}px`;
                 el.style.top = `${y}px`;
                 el.innerText = mesh.userData.id;
                 labelsRef.current?.appendChild(el);
             }
        });
    };

    const handleExport = () => {
        if (rendererRef.current) {
            const imgData = rendererRef.current.domElement.toDataURL('image/png');
            const link = document.createElement('a');
            link.download = 'assembly_scheme.png';
            link.href = imgData;
            link.click();
        }
    };

    return (
        <div className="flex flex-col h-full bg-slate-100">
            <div className="bg-white p-3 border-b border-slate-200 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-slate-700 font-bold">
                        <Expand size={20}/>
                        Взрыв-Схема
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">Разлёт деталей:</span>
                        <input 
                            type="range" 
                            min="0" max="2" step="0.1" 
                            value={explodeFactor} 
                            onChange={e => setExplodeFactor(parseFloat(e.target.value))}
                            className="w-32"
                        />
                    </div>
                </div>
                <button onClick={handleExport} className="flex items-center gap-2 px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                    <Download size={16}/> Скачать PNG
                </button>
            </div>
            
            <div className="flex-1 relative overflow-hidden">
                 <div ref={containerRef} className="w-full h-full cursor-move" />
                 {/* Labels Layer */}
                 <div ref={labelsRef} className="absolute inset-0 pointer-events-none overflow-hidden"></div>
                 
                 <div className="absolute bottom-4 left-4 bg-white/90 p-3 rounded shadow border border-slate-200 text-xs max-w-xs">
                     <div className="font-bold flex items-center gap-2 mb-1"><Info size={14}/> Справка</div>
                     <p>Номера деталей соответствуют позициям в спецификации. Используйте слайдер сверху для настройки вида.</p>
                 </div>
            </div>
        </div>
    );
};

export default AssemblyDiagram;