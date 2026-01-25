import React, { useEffect, useRef, useState } from 'react';
import { 
  Scene, PerspectiveCamera, WebGLRenderer, Group, MeshStandardMaterial, 
  TextureLoader, Texture, Color, PCFSoftShadowMap, Vector2, HemisphereLight, 
  DirectionalLight, GridHelper, AxesHelper, SRGBColorSpace, RepeatWrapping, 
  BoxGeometry, Mesh, EdgesGeometry, LineSegments, LineBasicMaterial, Box3, Vector3 
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

import { useProjectStore } from '../store/projectStore';
import { Axis } from '../types';
import { MATERIAL_LIBRARY } from '../data/materials';
import { Camera, Monitor, Box as BoxIcon, Sun, Eye } from 'lucide-react';

const Scene3D: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { panels, selectedPanelId } = useProjectStore();
  const [activeCameraView, setActiveCameraView] = useState('perspective');
  
  // Refs for Three.js objects
  const sceneRef = useRef<Scene | null>(null);
  const cameraRef = useRef<PerspectiveCamera | null>(null);
  const rendererRef = useRef<WebGLRenderer | null>(null);
  const composerRef = useRef<EffectComposer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cabinetGroupRef = useRef<Group | null>(null);
  
  // Cache
  const materialCache = useRef<Record<string, MeshStandardMaterial>>({});
  const edgeMaterialCache = useRef<Record<string, MeshStandardMaterial>>({}); 
  const textureLoader = useRef<TextureLoader>(new TextureLoader());

  // 1. INITIALIZATION
  useEffect(() => {
    if (!containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // --- SCENE ---
    const scene = new Scene();
    scene.background = new Color('#1e1e1e');
    sceneRef.current = scene;

    // --- CAMERA ---
    const camera = new PerspectiveCamera(45, width / height, 10, 20000);
    camera.position.set(2000, 2000, 3000);
    cameraRef.current = camera;

    // --- RENDERER ---
    const renderer = new WebGLRenderer({ 
      antialias: false, // Handled by Composer/SSAO
      powerPreference: "high-performance",
      stencil: false,
      depth: true
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = PCFSoftShadowMap;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // --- COMPOSER (Post-Processing) ---
    const composer = new EffectComposer(renderer);
    
    // 1. Render Pass
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    // 2. SSAO (Ambient Occlusion) - Tuned for mm scale
    const ssaoPass = new SSAOPass(scene, camera, width, height);
    ssaoPass.kernelRadius = 32; // Smoother occlusion
    ssaoPass.minDistance = 0.001; // Close range
    ssaoPass.maxDistance = 0.05;  // ~500-1000mm fade off relative to camera far clip
    composer.addPass(ssaoPass);

    // 3. Bloom (Glow for highlights)
    const bloomPass = new UnrealBloomPass(new Vector2(width, height), 0.3, 0.5, 0.9);
    composer.addPass(bloomPass);

    // 4. Output (Tone Mapping)
    const outputPass = new OutputPass();
    composer.addPass(outputPass);
    
    composerRef.current = composer;

    // --- CONTROLS ---
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 100;
    controls.maxDistance = 10000;
    controlsRef.current = controls;

    // --- LIGHTING ---
    // 1. Hemisphere (Sky/Ground Ambient)
    const hemiLight = new HemisphereLight(0xffffff, 0x444444, 0.7);
    hemiLight.position.set(0, 2000, 0);
    scene.add(hemiLight);

    // 2. Directional (Sun/Key Light) - 45 deg angle
    const dirLight = new DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(1500, 3000, 1500); // ~45 deg
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 10000;
    const d = 2500;
    dirLight.shadow.camera.left = -d;
    dirLight.shadow.camera.right = d;
    dirLight.shadow.camera.top = d;
    dirLight.shadow.camera.bottom = -d;
    dirLight.shadow.bias = -0.0005;
    dirLight.shadow.radius = 2; // Soft shadows
    scene.add(dirLight);

    // 3. Fill Light
    const fillLight = new DirectionalLight(0xffeedd, 0.4);
    fillLight.position.set(-1500, 1000, -1500);
    scene.add(fillLight);

    // --- HELPERS ---
    const gridHelper = new GridHelper(4000, 40, 0x333333, 0x1a1a1a);
    scene.add(gridHelper);
    
    const axesHelper = new AxesHelper(100);
    scene.add(axesHelper);

    // --- GROUP ---
    const group = new Group();
    scene.add(group);
    cabinetGroupRef.current = group;

    // --- ANIMATION LOOP ---
    let frameId: number;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      composer.render();
    };
    animate();

    // --- RESIZE ---
    const handleResize = () => {
        if (!containerRef.current) return;
        const w = containerRef.current.clientWidth;
        const h = containerRef.current.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        composer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(frameId);
      controls.dispose();
      renderer.dispose();
      composer.dispose();
      if (containerRef.current) containerRef.current.innerHTML = '';
    };
  }, []);

  // 2. MATERIALS
  const getMaterial = (matId: string, isEdge = false): MeshStandardMaterial => {
      const cache = isEdge ? edgeMaterialCache : materialCache;
      const cacheKey = matId + (isEdge ? '_edge' : '');
      
      if (cache.current[cacheKey]) return cache.current[cacheKey];

      const def = MATERIAL_LIBRARY.find(m => m.id === matId) || MATERIAL_LIBRARY.find(m => m.name === 'Белый Платиновый') || MATERIAL_LIBRARY[0];
      
      let map: Texture | null = null;
      let normalMap: Texture | null = null;

      if (def.textureUrl && !isEdge) { 
          map = textureLoader.current.load(def.textureUrl);
          map.colorSpace = SRGBColorSpace;
          if (def.isTextureStrict) {
              map.wrapS = RepeatWrapping;
              map.wrapT = RepeatWrapping;
          }
      }

      if (def.normalMapUrl && !isEdge) {
          normalMap = textureLoader.current.load(def.normalMapUrl);
          normalMap.wrapS = RepeatWrapping;
          normalMap.wrapT = RepeatWrapping;
      }

      const mat = new MeshStandardMaterial({
          color: isEdge ? new Color(def.color).multiplyScalar(0.85) : def.color, // Edges 15% darker
          map: map,
          normalMap: normalMap,
          roughness: def.category === 'wood' ? 0.8 : 0.4,
          metalness: 0.1,
      });

      cache.current[cacheKey] = mat;
      return mat;
  };

  // 3. GEOMETRY BUILDER
  useEffect(() => {
    if (!cabinetGroupRef.current) return;
    const group = cabinetGroupRef.current;
    
    // Clear old
    group.clear();

    panels.forEach(p => {
        if (!p.visible) return;

        let dX = 0, dY = 0, dZ = 0;
        if (p.rotation === Axis.X) { dX=p.depth; dY=p.height; dZ=p.width; }
        else if (p.rotation === Axis.Y) { dX=p.width; dY=p.depth; dZ=p.height; }
        else { dX=p.width; dY=p.height; dZ=p.depth; }

        const geometry = new BoxGeometry(dX, dY, dZ);
        
        // Materials Array for 6 faces: Right(+x), Left(-x), Top(+y), Bot(-y), Front(+z), Back(-z)
        const baseMat = getMaterial(p.materialId);
        const edgeMat = getMaterial(p.materialId, true);
        
        const materials = [baseMat, baseMat, baseMat, baseMat, baseMat, baseMat];

        // Apply Edging Visualization
        if (p.rotation === Axis.X) { // Vertical Side (X=Thick)
            // Faces 0(+x), 1(-x) are main faces (inside/outside)
            if (p.edging.top !== 'none') materials[2] = edgeMat;
            if (p.edging.bottom !== 'none') materials[3] = edgeMat;
            if (p.edging.left !== 'none') materials[4] = edgeMat; // Front edge
            if (p.edging.right !== 'none') materials[5] = edgeMat; // Back edge
        } else if (p.rotation === Axis.Y) { // Horizontal Shelf (Y=Thick)
            // Faces 2(+y), 3(-y) are main faces
            if (p.edging.left !== 'none') materials[1] = edgeMat;
            if (p.edging.right !== 'none') materials[0] = edgeMat;
            if (p.edging.bottom !== 'none') materials[4] = edgeMat; // Front edge
            if (p.edging.top !== 'none') materials[5] = edgeMat; // Back edge
        } else { // Frontal (Z=Thick)
            // Faces 4(+z), 5(-z) are main faces
            if (p.edging.top !== 'none') materials[2] = edgeMat;
            if (p.edging.bottom !== 'none') materials[3] = edgeMat;
            if (p.edging.left !== 'none') materials[1] = edgeMat;
            if (p.edging.right !== 'none') materials[0] = edgeMat;
        }

        const mesh = new Mesh(geometry, materials);
        mesh.position.set(p.x + dX/2, p.y + dY/2, p.z + dZ/2);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.userData = { panelId: p.id };

        // Selection Highlight
        if (p.id === selectedPanelId) {
            const edgeGeo = new EdgesGeometry(geometry);
            const edgeHighlight = new LineSegments(edgeGeo, new LineBasicMaterial({ color: 0x3b82f6, linewidth: 2 }));
            mesh.add(edgeHighlight);
        }

        group.add(mesh);
    });

    // Center camera on first load
    if (controlsRef.current && group.children.length > 0 && controlsRef.current.target.length() === 0) {
        const box = new Box3().setFromObject(group);
        const center = box.getCenter(new Vector3());
        controlsRef.current.target.copy(center);
        controlsRef.current.update();
    }

  }, [panels, selectedPanelId]);

  // 4. CAMERA PRESETS
  const setCameraView = (view: string) => {
      if (!cameraRef.current || !controlsRef.current) return;
      setActiveCameraView(view);
      
      const center = controlsRef.current.target;
      const offset = 2500;

      switch(view) {
          case 'front':
              cameraRef.current.position.set(center.x, center.y, center.z + offset);
              break;
          case 'iso':
              cameraRef.current.position.set(center.x + offset, center.y + offset/2, center.z + offset);
              break;
          case 'top':
              cameraRef.current.position.set(center.x, center.y + offset, center.z);
              break;
          case 'perspective':
          default:
              cameraRef.current.position.set(center.x + 1500, center.y + 1000, center.z + 2500);
              break;
      }
      controlsRef.current.update();
  };

  return (
    <div className="w-full h-full relative group bg-[#151515]">
      <div ref={containerRef} className="w-full h-full" />
      
      {/* HUD Controls */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[#222]/90 backdrop-blur border border-white/10 p-1.5 rounded-full flex gap-2 shadow-2xl z-20">
          <button 
            onClick={() => setCameraView('perspective')}
            className={`p-2 rounded-full transition ${activeCameraView === 'perspective' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
            title="Перспектива"
          >
              <Camera size={18} />
          </button>
          <button 
            onClick={() => setCameraView('front')}
            className={`p-2 rounded-full transition ${activeCameraView === 'front' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
            title="Фронтальный вид"
          >
              <Monitor size={18} />
          </button>
          <button 
            onClick={() => setCameraView('iso')}
            className={`p-2 rounded-full transition ${activeCameraView === 'iso' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
            title="Изометрия"
          >
              <BoxIcon size={18} />
          </button>
          <button 
            onClick={() => setCameraView('top')}
            className={`p-2 rounded-full transition ${activeCameraView === 'top' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
            title="Вид сверху"
          >
              <Sun size={18} />
          </button>
      </div>

      <div className="absolute top-4 left-4 pointer-events-none z-20">
          <div className="text-[10px] font-mono text-slate-500 bg-black/40 px-2 py-1 rounded border border-white/5 flex items-center gap-2">
              <Eye size={12} className="text-blue-500"/>
              RENDER: HIGH-QUALITY (PBR + SSAO + BLOOM)
          </div>
      </div>
    </div>
  );
};

export default Scene3D;