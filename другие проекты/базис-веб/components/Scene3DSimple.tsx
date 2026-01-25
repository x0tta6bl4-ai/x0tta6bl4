import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { useProjectStore } from '../store/projectStore';

interface Scene3DSimpleProps {
  previewMode?: boolean;
  panels?: any[];
}

/**
 * Scene3DSimple - Оптимизированная 3D визуализация шкафа с освещением и тенями
 */
const Scene3DSimple: React.FC<Scene3DSimpleProps> = ({ previewMode = false, panels: propPanels }) => {
  const { panels: storePanels, layers } = useProjectStore();
  const panels = previewMode && propPanels ? propPanels : storePanels;
  const [fps, setFps] = useState(60);
  const [shadowsEnabled, setShadowsEnabled] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const panelsGroupRef = useRef<THREE.Group | null>(null);
  const requestRef = useRef<number>(0);
  const controlsRef = useRef<any>(null);
  const fpsCounterRef = useRef({ frames: 0, lastTime: Date.now() });
  const meshCacheRef = useRef<Map<string, THREE.Mesh>>(new Map());

  useEffect(() => {
    if (!containerRef.current) {
      console.error('[Scene3DSimple] containerRef is null');
      return;
    }

    try {
      console.log('[Scene3DSimple] Initializing...');

      // Scene
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x1a1a2e);
      sceneRef.current = scene;
      console.log('[Scene3DSimple] Scene created');

      // Camera - получить размеры родительского контейнера
      const container = containerRef.current;
      let width = container.clientWidth;
      let height = container.clientHeight;
      
      // Fallback на 800x600 если размеры не получены
      if (width === 0 || !Number.isFinite(width)) width = 800;
      if (height === 0 || !Number.isFinite(height)) height = 600;
      
      console.log('[Scene3DSimple] Container size:', { width, height });

      const camera = new THREE.PerspectiveCamera(75, width / height || 1, 0.1, 100000);
      camera.position.set(2000, 1500, 2000);
      camera.lookAt(0, 0, 0);
      cameraRef.current = camera;
      console.log('[Scene3DSimple] Camera created');

      // Renderer
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setClearColor(0x1a1a2e);
      
      // Очистить контейнер перед добавлением
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
      container.appendChild(renderer.domElement);
      rendererRef.current = renderer;
      console.log('[Scene3DSimple] Renderer created and added to DOM');

      // Lighting - улучшенное освещение с тенями (управляется shadowsEnabled)
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
      scene.add(ambientLight);

      const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
      directionalLight.position.set(2000, 2500, 2000);
      directionalLight.castShadow = shadowsEnabled;
      directionalLight.shadow.mapSize.width = 2048;
      directionalLight.shadow.mapSize.height = 2048;
      directionalLight.shadow.camera.far = 5000;
      directionalLight.shadow.camera.left = -2000;
      directionalLight.shadow.camera.right = 2000;
      directionalLight.shadow.camera.top = 2000;
      directionalLight.shadow.camera.bottom = -2000;
      scene.add(directionalLight);
      sceneRef.current.directionalLight = directionalLight; // Store reference for toggle

      // Fill light для лучшей освещённости
      const fillLight = new THREE.DirectionalLight(0x88aaff, 0.4);
      fillLight.position.set(-2000, 1500, 1000);
      scene.add(fillLight);
      
      console.log('[Scene3DSimple] Enhanced lighting added (shadows: ' + (shadowsEnabled ? 'ON' : 'OFF') + ')');

      // Grid
      const gridHelper = new THREE.GridHelper(5000, 50, 0x444444, 0x333333);
      gridHelper.position.y = -1;
      scene.add(gridHelper);
      console.log('[Scene3DSimple] Grid added');

      // Axes
      const axesHelper = new THREE.AxesHelper(500);
      scene.add(axesHelper);
      console.log('[Scene3DSimple] Axes added');

      // Panels group
      const panelsGroup = new THREE.Group();
      scene.add(panelsGroup);
      panelsGroupRef.current = panelsGroup;
      console.log('[Scene3DSimple] Panels group created');

      // Simple Orbit Controls
      const controls = {
        target: new THREE.Vector3(0, 0, 0),
        distance: 3000,
        phi: Math.PI / 3,
        theta: Math.PI / 4,
        update: function () {
          const x = this.target.x + this.distance * Math.sin(this.phi) * Math.cos(this.theta);
          const y = this.target.y + this.distance * Math.cos(this.phi);
          const z = this.target.z + this.distance * Math.sin(this.phi) * Math.sin(this.theta);
          camera.position.set(x, y, z);
          camera.lookAt(this.target);
        },
        handleWheel: (event: WheelEvent) => {
          event.preventDefault();
          controls.distance += event.deltaY * 0.5;
          controls.distance = Math.max(100, Math.min(10000, controls.distance));
          controls.update();
        },
        handleMouseDown: (event: MouseEvent) => {
          const startX = event.clientX;
          const startY = event.clientY;
          const startTheta = controls.theta;
          const startPhi = controls.phi;

          const handleMouseMove = (moveEvent: MouseEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;
            controls.theta = startTheta - deltaX * 0.005;
            controls.phi = startPhi + deltaY * 0.005;
            controls.phi = Math.max(0.1, Math.min(Math.PI - 0.1, controls.phi));
            controls.update();
          };

          const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
          };

          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
        }
      };

      controlsRef.current = controls;
      controls.update();
      console.log('[Scene3DSimple] Controls initialized');

      // Event listeners
      renderer.domElement.addEventListener('wheel', controls.handleWheel);
      renderer.domElement.addEventListener('mousedown', controls.handleMouseDown);

      const handleResize = () => {
        if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
        const w = containerRef.current.clientWidth;
        const h = containerRef.current.clientHeight;
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      };

      window.addEventListener('resize', handleResize);

      // Animation loop with FPS tracking
      let lastFrameTime = Date.now();
      const animate = () => {
        requestRef.current = requestAnimationFrame(animate);
        
        const now = Date.now();
        const deltaTime = (now - lastFrameTime) / 1000;
        lastFrameTime = now;

        // FPS counter
        fpsCounterRef.current.frames++;
        const elapsed = now - fpsCounterRef.current.lastTime;
        if (elapsed >= 1000) {
          const currentFps = fpsCounterRef.current.frames;
          setFps(currentFps);
          fpsCounterRef.current.frames = 0;
          fpsCounterRef.current.lastTime = now;
        }

        renderer.render(scene, camera);
      };
      animate();
      console.log('[Scene3DSimple] Animation loop started');

      return () => {
        console.log('[Scene3DSimple] Cleanup');
        try {
          window.removeEventListener('resize', handleResize);
          renderer.domElement.removeEventListener('wheel', controls.handleWheel);
          renderer.domElement.removeEventListener('mousedown', controls.handleMouseDown);
          cancelAnimationFrame(requestRef.current);
          renderer.dispose();
          if (container && renderer.domElement.parentNode === container) {
            container.removeChild(renderer.domElement);
          }
        } catch (e) {
          console.error('[Scene3DSimple] Cleanup error:', e);
        }
      };
    } catch (error) {
      console.error('[Scene3DSimple] Init error:', error);
      return () => {};
    }
  }, []);

  // Update panels with optimized rendering
  useEffect(() => {
    if (!panelsGroupRef.current || !sceneRef.current) {
      console.warn('[Scene3DSimple] panelsGroup or scene is null');
      return;
    }

    console.log('[Scene3DSimple] Rendering panels:', panels.length);

    // Clear old meshes and cache
    while (panelsGroupRef.current.children.length > 0) {
      const child = panelsGroupRef.current.children[0];
      panelsGroupRef.current.remove(child);
      if ((child as any).geometry) (child as any).geometry.dispose();
      if ((child as any).material) {
        if (Array.isArray((child as any).material)) {
          (child as any).material.forEach((m: any) => m.dispose());
        } else {
          ((child as any).material as any).dispose();
        }
      }
    }
    meshCacheRef.current.clear();

    // Get visible panels
    const isLayerVisible = (layerId: string) => {
      const layer = layers.find(l => l.id === layerId);
      return !layer || layer.visible;
    };

    const visiblePanels = panels.filter(p => p.visible && isLayerVisible(p.layer));
    console.log('[Scene3DSimple] Visible panels:', visiblePanels.length);

    // Create meshes with optimized material
    let successCount = 0;
    const geometryCache = new Map<string, THREE.BoxGeometry>();

    visiblePanels.forEach((panel, idx) => {
      try {
        const { x, y, z, width, height, depth, color, id } = panel;

        // Validate
        if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
          console.warn(`[Panel ${idx}] Invalid position`, { x, y, z });
          return;
        }
        if (!Number.isFinite(width) || !Number.isFinite(height) || !Number.isFinite(depth)) {
          console.warn(`[Panel ${idx}] Invalid dimensions`, { width, height, depth });
          return;
        }
        if (width <= 0 || height <= 0 || depth <= 0) {
          console.warn(`[Panel ${idx}] Non-positive dimensions`, { width, height, depth });
          return;
        }

        // Reuse geometry for similar dimensions
        const geomKey = `${width},${height},${depth}`;
        let geometry = geometryCache.get(geomKey);
        if (!geometry) {
          geometry = new THREE.BoxGeometry(width, height, depth);
          geometryCache.set(geomKey, geometry);
        }

        // Create optimized material
        let hexColor = 0xd2b48c;
        try {
          const colorStr = String(color || '#d2b48c').replace('#', '0x');
          const parsed = parseInt(colorStr, 16);
          if (Number.isFinite(parsed)) {
            hexColor = parsed;
          }
        } catch (e) {
          console.warn(`[Panel ${idx}] Invalid color: ${color}`);
        }

        // Use higher quality material with better lighting response
        const material = new THREE.MeshPhongMaterial({
          color: hexColor,
          shininess: 100,
          emissive: 0x000000,
          side: THREE.DoubleSide
        });

        // Create mesh
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.set(x + width / 2, y + height / 2, z + depth / 2);
        mesh.castShadow = shadowsEnabled;
        mesh.receiveShadow = shadowsEnabled;

        panelsGroupRef.current!.add(mesh);
        meshCacheRef.current.set(id, mesh);
        successCount++;
      } catch (error) {
        console.error(`[Panel ${idx}] Error:`, error);
      }
    });

    console.log(`[Scene3DSimple] Created ${successCount} meshes`);

    // Fit camera to content with smooth transition
    if (visiblePanels.length > 0 && panelsGroupRef.current.children.length > 0) {
      const box = new THREE.Box3().setFromObject(panelsGroupRef.current);
      if (!box.isEmpty()) {
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const distance = maxDim * 2.5; // 2.5x multiplier for better view

        if (controlsRef.current) {
          controlsRef.current.target = center;
          controlsRef.current.distance = distance;
          controlsRef.current.update();
          console.log('[Scene3DSimple] Camera fitted to content');
        }
      }
    }

    // Cleanup cached geometries
    return () => {
      geometryCache.forEach(geom => geom.dispose());
    };
  }, [panels, layers, shadowsEnabled]);

  return (
    <>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          overflow: 'hidden',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0
        }}
      />
      
      {/* Stats Panel */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          background: 'linear-gradient(135deg, rgba(0,0,0,0.8) 0%, rgba(20,20,40,0.8) 100%)',
          color: '#fff',
          padding: '12px 16px',
          borderRadius: '8px',
          fontSize: '12px',
          zIndex: 10,
          border: '1px solid rgba(100,150,255,0.3)',
          fontFamily: 'monospace',
          minWidth: '180px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
          <span style={{ color: '#88ff88' }}>FPS:</span>
          <span style={{ fontWeight: 'bold', color: fps > 50 ? '#88ff88' : fps > 30 ? '#ffff88' : '#ff6666' }}>
            {fps}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
          <span style={{ color: '#88aaff' }}>Panels:</span>
          <span style={{ fontWeight: 'bold' }}>{panels.length}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ color: '#88aaff' }}>Visible:</span>
          <span style={{ fontWeight: 'bold' }}>{panels.filter(p => p.visible).length}</span>
        </div>
        <div style={{ height: '1px', background: 'rgba(100,150,255,0.3)', margin: '8px 0' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ color: '#ffaa88', fontSize: '11px' }}>Shadows:</span>
          <button
            onClick={() => setShadowsEnabled(!shadowsEnabled)}
            style={{
              padding: '3px 8px',
              background: shadowsEnabled ? 'rgba(100,150,255,0.5)' : 'rgba(100,100,100,0.3)',
              color: shadowsEnabled ? '#88ff88' : '#888',
              border: '1px solid rgba(100,150,255,0.3)',
              borderRadius: '4px',
              fontSize: '10px',
              cursor: 'pointer',
              fontWeight: 'bold',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              (e.target as HTMLButtonElement).style.background = shadowsEnabled ? 'rgba(100,150,255,0.7)' : 'rgba(100,100,100,0.5)';
            }}
            onMouseLeave={(e) => {
              (e.target as HTMLButtonElement).style.background = shadowsEnabled ? 'rgba(100,150,255,0.5)' : 'rgba(100,100,100,0.3)';
            }}
          >
            {shadowsEnabled ? 'ON' : 'OFF'}
          </button>
        </div>
        <div style={{ fontSize: '10px', color: '#888', lineHeight: '1.4' }}>
          <div>🖱️ Drag: Rotate</div>
          <div>⚙️ Wheel: Zoom</div>
          <div>📍 Double-click: Focus</div>
        </div>
      </div>

      {/* Debug Info */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: 10,
          background: 'rgba(0,0,0,0.6)',
          color: '#888',
          padding: '8px 12px',
          borderRadius: '5px',
          fontSize: '10px',
          zIndex: 5,
          border: '1px solid rgba(100,100,100,0.3)',
          maxWidth: '250px'
        }}
      >
        Scene3DSimple v1.0 | Three.js optimized rendering
      </div>
    </>
  );
};

export default Scene3DSimple;
