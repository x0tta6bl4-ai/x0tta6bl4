
import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { useProjectStore } from '../store/projectStore';
import { Axis } from '../types';
import { Expand, Download, Info } from 'lucide-react';

const AssemblyDiagram: React.FC = () => {
    const { panels } = useProjectStore();
    const containerRef = useRef<HTMLDivElement>(null);
    const [explodeFactor, setExplodeFactor] = useState(0.5); // 0 to 2
    
    const sceneRef = useRef<THREE.Scene | null>(null);
    const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
    const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
    const groupRef = useRef<THREE.Group | null>(null);
    const labelsRef = useRef<HTMLDivElement>(null);

    // Calculate center of assembly
    const center = useRef(new THREE.Vector3());

    // Init Scene
    useEffect(() => {
        if (!containerRef.current) return;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color('#ffffff');
        sceneRef.current = scene;

        const camera = new THREE.PerspectiveCamera(45, containerRef.current.clientWidth / containerRef.current.clientHeight, 1, 10000);
        camera.position.set(2000, 2000, 3000);
        cameraRef.current = camera;

        const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
        renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
        renderer.shadowMap.enabled = true;
        containerRef.current.appendChild(renderer.domElement);
        rendererRef.current = renderer;

        const controls = new OrbitControls(camera, renderer.domElement as unknown as HTMLElement);
        controls.enableDamping = true;
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.7);
        dirLight.position.set(1000, 2000, 1000);
        dirLight.castShadow = true;
        scene.add(dirLight);

        // Group
        const group = new THREE.Group();
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
            if(containerRef.current && containerRef.current.parentElement) {
                containerRef.current.innerHTML = '';
            }
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
        const edgeMat = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 2 });
        const faceMat = new THREE.MeshLambertMaterial({ color: 0xf0f0f0, transparent: true, opacity: 0.9 });
        const fastenerMat = new THREE.MeshBasicMaterial({ color: 0xff0000 });

        panels.forEach((p, idx) => {
            if(!p.visible) return;

            // Dimensions based on rotation
            let dX = 0, dY = 0, dZ = 0;
            if (p.rotation === Axis.X) { dX=p.depth; dY=p.height; dZ=p.width; }
            else if (p.rotation === Axis.Y) { dX=p.width; dY=p.depth; dZ=p.height; }
            else { dX=p.width; dY=p.height; dZ=p.depth; }

            const geometry = new THREE.BoxGeometry(dX, dY, dZ);
            const mesh = new THREE.Mesh(geometry, faceMat);
            const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), edgeMat);
            
            mesh.add(edges);
            
            // Store original position and dimensions in userData
            const originalPos = new THREE.Vector3(p.x + dX/2, p.y + dY/2, p.z + dZ/2);
            mesh.userData = { 
                originalPos: originalPos,
                id: idx + 1,
                panelId: p.id
            };
            
            // Initial position
            mesh.position.copy(originalPos);
            group.add(mesh);

            // Add Fasteners Visuals (Simplified Rules)
            // Example: Screws at corners if edge thickness allows
            if (p.hardware && p.hardware.length > 0) {
                p.hardware.forEach(hw => {
                     const fGeo = new THREE.SphereGeometry(3, 8, 8);
                     const fMesh = new THREE.Mesh(fGeo, fastenerMat);
                     // Calculate local pos based on rotation (simplified approximation)
                     // In real app, need complex matrix transform. Here we place relative to center roughly
                     // This is a "nice to have" visual, keeping it simple
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
            const mesh = child as THREE.Mesh;
            const originalPos = mesh.userData.originalPos as THREE.Vector3;
            if (!originalPos) return;

            // Vector from center to part center
            const dir = new THREE.Vector3().subVectors(originalPos, center.current);
            
            // Explode logic: Move away from center
            // Factor scales the distance
            const newPos = new THREE.Vector3().copy(originalPos).add(dir.multiplyScalar(explodeFactor));
            mesh.position.lerp(newPos, 0.5); // Smooth transition handled by frequent updates or direct set
            mesh.position.copy(newPos);
        });
    }, [explodeFactor, panels]);

    // Label Update Logic
    const updateLabels = () => {
        if (!groupRef.current || !labelsRef.current || !cameraRef.current || !containerRef.current) return;
        
        const camera = cameraRef.current;
        const widthHalf = containerRef.current.clientWidth / 2;
        const heightHalf = containerRef.current.clientHeight / 2;
        
        // Clear existing labels (naive approach, better to reuse DOM elements in prod)
        if (labelsRef.current) {
            labelsRef.current.innerHTML = '';
        }

        groupRef.current.children.forEach(child => {
             const mesh = child as THREE.Mesh;
             const pos = mesh.position.clone();
             pos.project(camera);
             
             const x = (pos.x * widthHalf) + widthHalf;
             const y = -(pos.y * heightHalf) + heightHalf;

             // Only render if roughly in front of camera
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
