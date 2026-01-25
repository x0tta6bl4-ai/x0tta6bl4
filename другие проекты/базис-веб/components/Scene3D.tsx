import React, { useEffect, useRef, useState, memo, useCallback } from 'react';
import * as THREE from 'three';
import { useProjectStore } from '../store/projectStore';
import { Axis, Panel } from '../types';
import { Component, MonitorPlay } from 'lucide-react';
import { createScene3DRenderer, disposeScene3DRenderer, Scene3DRendererSetup } from '../services/Scene3DRenderer';
import { Scene3DMaterialManager } from '../services/Scene3DMaterial';
import { reconcileMeshGeometry, disposeMeshGeometryCache } from '../services/Scene3DMesh';
import { Scene3DLODManager } from '../services/Scene3DLOD';
import { PerformanceMonitor3D, PerformanceMetrics } from '../services/PerformanceMonitor3D';
import ToolbarControls from './Scene3D/ToolbarControls';
import ViewCube from './Scene3D/ViewCube';
import UnityViewer from './UnityViewer';

interface Scene3DProps {
  previewMode?: boolean;
  panels?: any[];
}

const Scene3D: React.FC<Scene3DProps> = ({ previewMode = false, panels: propPanels }) => {
  const { panels: storePanels, layers, selectedPanelId, selectPanel, bulkUpdatePanels } = useProjectStore();
  const panels = previewMode && propPanels ? propPanels : storePanels;

  const [renderEngine, setRenderEngine] = useState<'three' | 'unity'>('three');
  const [visualStyle, setVisualStyle] = useState<'realistic' | 'wireframe' | 'xray'>('realistic');
  const [gizmoMode, setGizmoMode] = useState<'translate' | 'rotate'>('translate');
  const [showGrid, setShowGrid] = useState(true);
  const [showAxes, setShowAxes] = useState(true);
  const [enabledAxes, setEnabledAxes] = useState({ x: true, y: true, z: true });
  const [useLOD, setUseLOD] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const setupRef = useRef<Scene3DRendererSetup | null>(null);
  const materialManagerRef = useRef<Scene3DMaterialManager | null>(null);
  const lodManagerRef = useRef<Scene3DLODManager | null>(null);
  const requestRef = useRef<number>(0);
  const isInitializedRef = useRef(false);
  const debugCubeRef = useRef<THREE.Mesh | null>(null);
  const debugPanelRef = useRef<THREE.Mesh | null>(null);
  const [diag, setDiag] = useState({
    total: 0,
    visibleAfterFilters: 0,
    invalidDims: 0,
    groupChildren: 0,
    boxEmpty: true,
    bbox: { x: 0, y: 0, z: 0 },
    first: null as null | {
      id: string;
      x: number;
      y: number;
      z: number;
      w: number;
      h: number;
      d: number;
      rot: any;
      layer: any;
      visible: any;
    }
  });
  const isCubeDragging = useRef(false);
  const prevCubeMouse = useRef({ x: 0, y: 0 });
  const performanceMonitorRef = useRef<PerformanceMonitor3D | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics>({
    fps: 0,
    gpuMemory: 0,
    cpuUsage: 0,
    frameTime: 0,
    drawCalls: 0,
    triangleCount: 0,
    renderTime: 0
  });

  const setView = useCallback((view: 'front' | 'back' | 'left' | 'right' | 'top' | 'bottom') => {
    if (!setupRef.current) return;
    const { panelsGroup, orbitControls, trackballControls, camera } = setupRef.current;
    const box = new THREE.Box3().setFromObject(panelsGroup);
    const center = box.isEmpty() ? new THREE.Vector3(0, 0, 0) : box.getCenter(new THREE.Vector3());
    const size = box.isEmpty() ? new THREE.Vector3(1000, 1000, 1000) : box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const dist = Math.max(maxDim * 2.0, 2000);
    const targetPos = new THREE.Vector3();
    switch (view) {
      case 'front': targetPos.set(center.x, center.y, center.z + dist); break;
      case 'back': targetPos.set(center.x, center.y, center.z - dist); break;
      case 'right': targetPos.set(center.x + dist, center.y, center.z); break;
      case 'left': targetPos.set(center.x - dist, center.y, center.z); break;
      case 'top': targetPos.set(center.x, center.y + dist, center.z + 0.1); break;
      case 'bottom': targetPos.set(center.x, center.y - dist, center.z + 0.1); break;
    }
    const startPos = camera.position.clone();
    const startLookAt = orbitControls.target.clone();
    const startTime = Date.now();
    const animate = () => {
      const progress = Math.min((Date.now() - startTime) / 600, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      camera.position.lerpVectors(startPos, targetPos, ease);
      orbitControls.target.lerpVectors(startLookAt, center, ease);
      trackballControls.target.lerpVectors(startLookAt, center, ease);
      orbitControls.update();
      trackballControls.update();
      if (progress < 1) requestAnimationFrame(animate);
    };
    animate();
  }, []);

  const fitCameraToScene = useCallback(() => {
    if (!setupRef.current) return;
    const { panelsGroup, trackballControls, camera, orbitControls } = setupRef.current;
    const box = new THREE.Box3().setFromObject(panelsGroup);
    if (box.isEmpty()) return;
    const center = new THREE.Vector3();
    box.getCenter(center);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    if (trackballControls) {
      trackballControls.minDistance = Math.max(10, maxDim * 0.1);
      trackballControls.maxDistance = Math.max(50000, maxDim * 15);
    }
    const distance = Math.max(2000, maxDim * 2.5);
    const targetPos = new THREE.Vector3(center.x + distance, center.y + distance * 0.5, center.z + distance);
    const startPos = camera.position.clone();
    const startLookAt = orbitControls.target.clone();
    const startTime = Date.now();
    const animate = () => {
      const progress = Math.min((Date.now() - startTime) / 600, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      camera.position.lerpVectors(startPos, targetPos, ease);
      orbitControls.target.lerpVectors(startLookAt, center, ease);
      trackballControls.target.lerpVectors(startLookAt, center, ease);
      orbitControls.update();
      trackballControls.update();
      if (progress < 1) requestAnimationFrame(animate);
    };
    animate();
    isInitializedRef.current = true;
  }, []);

  const handleCubeDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!setupRef.current) return;
    isCubeDragging.current = true;
    prevCubeMouse.current = { x: e.clientX, y: e.clientY };
    const { camera, orbitControls } = setupRef.current;
    const handleMove = (evt: PointerEvent) => {
      if (!isCubeDragging.current || !setupRef.current) return;
      const deltaX = evt.clientX - prevCubeMouse.current.x;
      const deltaY = evt.clientY - prevCubeMouse.current.y;
      const offset = new THREE.Vector3().copy(camera.position).sub(orbitControls.target);
      const spherical = new THREE.Spherical().setFromVector3(offset);
      spherical.theta -= deltaX * 0.005;
      spherical.phi -= deltaY * 0.005;
      spherical.phi = Math.max(0.01, Math.min(Math.PI - 0.01, spherical.phi));
      offset.setFromSpherical(spherical);
      camera.position.copy(orbitControls.target).add(offset);
      camera.lookAt(orbitControls.target);
      orbitControls.update();
      prevCubeMouse.current = { x: evt.clientX, y: evt.clientY };
    };
    const handleUp = () => {
      isCubeDragging.current = false;
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      document.body.style.cursor = '';
    };
    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    document.body.style.cursor = 'grabbing';
  }, []);

  useEffect(() => {
    if (!containerRef.current || renderEngine === 'unity') return;

    const setup = createScene3DRenderer(containerRef.current);
    setupRef.current = setup;
    materialManagerRef.current = new Scene3DMaterialManager(setup.renderer);
    lodManagerRef.current = new Scene3DLODManager(setup.camera, materialManagerRef.current);
    performanceMonitorRef.current = new PerformanceMonitor3D();
    performanceMonitorRef.current.start();

    try {
      const geo = new THREE.BoxGeometry(200, 200, 200);
      const mat = new THREE.MeshBasicMaterial({ color: 0xff0000, wireframe: true });
      const dbg = new THREE.Mesh(geo, mat);
      dbg.position.set(0, 100, 0);
      dbg.userData.__debug = true;
      setup.scene.add(dbg);
      debugCubeRef.current = dbg;
    } catch {
      // ignore
    }

    if (setup.transformControls && setup.transformControls.addEventListener) {
      setup.transformControls.addEventListener('dragging-changed', (event: any) => {
        setup.orbitControls.enabled = !event.value;
        setup.trackballControls.enabled = !event.value;
        if (!event.value && setup.transformControls.object && setup.transformControls.object.userData.panelId) {
          const obj = setup.transformControls.object;
          const dims = obj.userData.dims || { x: 0, y: 0, z: 0 };
          bulkUpdatePanels([
            {
              id: obj.userData.panelId,
              changes: {
                x: Math.round(obj.position.x - dims.x / 2),
                y: Math.round(obj.position.y - dims.y / 2),
                z: Math.round(obj.position.z - dims.z / 2),
              },
            },
          ]);
        }
      });
    }

    const animate = () => {
      requestRef.current = requestAnimationFrame(animate);
      setup.orbitControls.update();
      setup.trackballControls.target.copy(setup.orbitControls.target);
      setup.trackballControls.update();

      // Update LOD system
      if (lodManagerRef.current) {
        lodManagerRef.current.update();
      }

      setup.renderer.render(setup.scene, setup.camera);

      // Update performance metrics
      if (performanceMonitorRef.current) {
        const metrics = performanceMonitorRef.current.update();
        setPerformanceMetrics(metrics);
      }
    };
    animate();

    const handleResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      setup.camera.aspect = w / h;
      setup.camera.updateProjectionMatrix();
      setup.renderer.setSize(w, h);
      setup.trackballControls.handleResize();
    };
    window.addEventListener('resize', handleResize);

    const handlePanelSelection = (e: PointerEvent) => {
      if (!containerRef.current || !setup.camera || !setup.panelsGroup) return;
      const target = e.target as HTMLElement;
      if (target.closest('.cube-face') || target.closest('button')) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(new THREE.Vector2(x, y), setup.camera);
      const intersects = raycaster.intersectObjects(setup.panelsGroup.children, false);
      if (intersects.length > 0) {
        const hit = intersects.find(i => i.object instanceof THREE.InstancedMesh && i.object.userData.isPanel);
        if (hit && hit.instanceId !== undefined) {
          const pid = hit.object.userData.panelMap[hit.instanceId];
          if (pid) { selectPanel(pid, e.ctrlKey || e.shiftKey); return; }
        }
      }
      if (!e.ctrlKey && !e.shiftKey) selectPanel(null);
    };
    setup.renderer.domElement.addEventListener('pointerup', handlePanelSelection);

    return () => {
      window.removeEventListener('resize', handleResize);
      setup.renderer.domElement.removeEventListener('pointerup', handlePanelSelection);
      cancelAnimationFrame(requestRef.current);
      if (materialManagerRef.current) materialManagerRef.current.dispose();
      if (lodManagerRef.current) lodManagerRef.current.dispose();
      if (performanceMonitorRef.current) performanceMonitorRef.current.stop();
      if (debugCubeRef.current) {
        const dbg = debugCubeRef.current;
        debugCubeRef.current = null;
        setup.scene.remove(dbg);
        (dbg.geometry as any)?.dispose?.();
        (dbg.material as any)?.dispose?.();
      }
      if (debugPanelRef.current) {
        const dbg = debugPanelRef.current;
        debugPanelRef.current = null;
        setup.scene.remove(dbg);
        (dbg.geometry as any)?.dispose?.();
        (dbg.material as any)?.dispose?.();
      }
      disposeScene3DRenderer(setup, containerRef.current!);
      disposeMeshGeometryCache();
    };
  }, [renderEngine, bulkUpdatePanels, selectPanel]);

  useEffect(() => {
    if (setupRef.current) {
      setupRef.current.gridHelper.visible = showGrid;
      setupRef.current.axesHelper.visible = showAxes;
    }
  }, [showGrid, showAxes]);

  useEffect(() => {
    if (setupRef.current) {
      setupRef.current.transformControls.showX = enabledAxes.x;
      setupRef.current.transformControls.showY = enabledAxes.y;
      setupRef.current.transformControls.showZ = enabledAxes.z;
    }
  }, [enabledAxes]);

  useEffect(() => {
    if (!setupRef.current || !materialManagerRef.current) return;
    const { panelsGroup, selectionGroup, transformControls, scene } = setupRef.current;

    const isLayerVisible = (layerId: any) => {
      const layer = layers.find(l => l.id === layerId);
      return !layer || layer.visible;
    };
    let visibleAfterFilters = 0;
    let invalidDims = 0;
    let first: (typeof diag.first) = null;
    panels.forEach(p => {
      if (!p.visible || !isLayerVisible(p.layer)) return;
      visibleAfterFilters++;
      const nums = [p.x, p.y, p.z, p.width, p.height, p.depth];
      if (!nums.every(v => Number.isFinite(v)) || p.width <= 0 || p.height <= 0 || p.depth <= 0) invalidDims++;
      if (!first) {
        first = {
          id: p.id,
          x: p.x,
          y: p.y,
          z: p.z,
          w: p.width,
          h: p.height,
          d: p.depth,
          rot: p.rotation,
          layer: p.layer,
          visible: p.visible
        };
      }
    });

    // Use LOD system if enabled, otherwise fallback to standard rendering
    if (useLOD && lodManagerRef.current) {
      // Clear existing meshes
      const toRemove = [...panelsGroup.children].filter((c: any) => !(c && c.userData && c.userData.__debug));
      toRemove.forEach((child: any) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) child.material.forEach((m: any) => m.dispose());
          else child.material.dispose();
        }
        panelsGroup.remove(child);
      });

      // Group panels by material for LOD
      const panelGroups = new Map<string, any[]>();
      const isUniformBatch = visualStyle === 'wireframe' || visualStyle === 'xray';

      panels.forEach(p => {
        if (!p.visible || !isLayerVisible(p.layer)) return;
        let groupKey = 'all';
        if (!isUniformBatch) {
          const mat = materialManagerRef.current.getMaterial(p.color, p.texture, p.textureRotation);
          groupKey = mat.uuid;
        }
        if (!panelGroups.has(groupKey)) panelGroups.set(groupKey, []);
        panelGroups.get(groupKey)!.push(p);
      });

      // Create LOD objects for each group
      panelGroups.forEach((groupPanels, groupKey) => {
        if (groupPanels.length > 0) {
          const lod = lodManagerRef.current!.createLODForPanels(groupPanels, groupKey);
          panelsGroup.add(lod);
        }
      });
    } else {
      // Fallback to standard rendering
      reconcileMeshGeometry(panelsGroup, panels, layers, materialManagerRef.current, visualStyle);
    }

    fitCameraToScene();

    const box = new THREE.Box3().setFromObject(panelsGroup);
    const size = new THREE.Vector3();
    const isEmpty = box.isEmpty();
    if (!isEmpty) box.getSize(size);
    setDiag({
      total: panels.length,
      visibleAfterFilters,
      invalidDims,
      groupChildren: panelsGroup.children.length,
      boxEmpty: isEmpty,
      bbox: { x: isEmpty ? 0 : size.x, y: isEmpty ? 0 : size.y, z: isEmpty ? 0 : size.z },
      first
    });

    // Debug: render first visible panel as a separate wireframe mesh (bypasses instancing)
    try {
      if (debugPanelRef.current) {
        scene.remove(debugPanelRef.current);
        (debugPanelRef.current.geometry as any)?.dispose?.();
        (debugPanelRef.current.material as any)?.dispose?.();
        debugPanelRef.current = null;
      }
      if (first) {
        const geo = new THREE.BoxGeometry(first.w || 1, first.h || 1, first.d || 1);
        const mat = new THREE.MeshBasicMaterial({ color: 0x00ffff, wireframe: true, depthTest: false });
        const m = new THREE.Mesh(geo, mat);
        m.userData.__debug = true;
        m.renderOrder = 1000;
        m.position.set(first.x + (first.w || 1) / 2, first.y + (first.h || 1) / 2, first.z + (first.d || 1) / 2);
        scene.add(m);
        debugPanelRef.current = m;
      }
    } catch {
      // ignore
    }

    selectionGroup.clear();
    transformControls.detach();

    if (selectedPanelId) {
      const panel = panels.find(p => p.id === selectedPanelId);
      if (panel && panel.visible) {
        let dX = 0, dY = 0, dZ = 0;
        if (panel.rotation === Axis.X) {
          dX = panel.depth;
          dY = panel.height;
          dZ = panel.width;
        } else if (panel.rotation === Axis.Y) {
          dX = panel.width;
          dY = panel.depth;
          dZ = panel.height;
        } else {
          dX = panel.width;
          dY = panel.height;
          dZ = panel.depth;
        }

        const geometry = new THREE.BoxGeometry(dX + 1, dY + 1, dZ + 1);
        const material = new THREE.MeshBasicMaterial({ color: 0x3b82f6, transparent: true, opacity: 0.3, depthTest: false });
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geometry),
          new THREE.LineBasicMaterial({ color: 0x60a5fa, depthTest: false })
        );
        const selectionBox = new THREE.Mesh(geometry, material);
        selectionBox.add(edges);
        selectionBox.renderOrder = 999;
        selectionBox.position.set(panel.x + dX / 2, panel.y + dY / 2, panel.z + dZ / 2);
        selectionBox.userData = { panelId: panel.id, dims: { x: dX, y: dY, z: dZ } };

        selectionGroup.add(selectionBox);
        transformControls.attach(selectionBox);
        transformControls.setMode(gizmoMode);
      }
    }
  }, [panels, layers, selectedPanelId, visualStyle, gizmoMode, useLOD, fitCameraToScene]);

  const toggleAxis = useCallback((axis: 'x' | 'y' | 'z') => {
    setEnabledAxes(prev => ({ ...prev, [axis]: !prev[axis] }));
  }, []);

  return (
    <div className="flex-1 relative bg-gradient-to-br from-gray-900 to-black overflow-hidden h-full group/scene">
      <div className="absolute bottom-4 right-4 z-50 text-[10px] text-slate-200 bg-black/70 px-3 py-2 rounded border border-gray-700 font-mono space-y-1">
        <div className="text-blue-400 font-bold border-b border-blue-500/50 pb-1 mb-1">📊 Performance Metrics</div>
        <div>FPS: {performanceMetrics.fps} fps</div>
        <div>Frame Time: {performanceMetrics.frameTime.toFixed(1)} ms</div>
        <div>Render Time: {performanceMetrics.renderTime.toFixed(1)} ms</div>
        <div>Draw Calls: {performanceMetrics.drawCalls}</div>
        <div>Triangles: {performanceMetrics.triangleCount}</div>
        <div>GPU Mem: {performanceMetrics.gpuMemory} MB</div>
        <div>CPU Usage: {performanceMetrics.cpuUsage}%</div>
        <div className="mt-2 pt-2 border-t border-gray-700">
          <div>panels: {diag.total}</div>
          <div>visible: {diag.visibleAfterFilters}</div>
          <div>invalid: {diag.invalidDims}</div>
          <div>groupChildren: {diag.groupChildren}</div>
          <div>bboxEmpty: {String(diag.boxEmpty)}</div>
          <div>bbox: {Math.round(diag.bbox.x)}×{Math.round(diag.bbox.y)}×{Math.round(diag.bbox.z)}</div>
          <div>first: {diag.first ? `${diag.first.id} ${Math.round(diag.first.x)},${Math.round(diag.first.y)},${Math.round(diag.first.z)} ${Math.round(diag.first.w)}×${Math.round(diag.first.h)}×${Math.round(diag.first.d)} ${diag.first.layer} ${String(diag.first.rot)}` : 'none'}</div>
        </div>
      </div>
      <div className="absolute top-4 right-4 z-50 flex gap-2">
        <button
          onClick={() => setRenderEngine('three')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded font-bold text-xs transition ${
            renderEngine === 'three' ? 'bg-blue-600 text-white shadow-lg' : 'bg-slate-800 text-slate-400 hover:text-white'
          }`}
        >
          <Component size={16} /> <span className="hidden sm:inline">WebGL</span>
        </button>
        <button
          onClick={() => setRenderEngine('unity')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded font-bold text-xs transition ${
            renderEngine === 'unity' ? 'bg-black border border-slate-600 text-white shadow-lg' : 'bg-slate-800 text-slate-400 hover:text-white'
          }`}
        >
          <MonitorPlay size={16} /> <span className="hidden sm:inline">Unity</span>
        </button>
      </div>

      {renderEngine === 'three' && (
        <>
          <ToolbarControls
            visualStyle={visualStyle}
            gizmoMode={gizmoMode}
            showGrid={showGrid}
            showAxes={showAxes}
            enabledAxes={enabledAxes}
            onVisualStyleChange={setVisualStyle}
            onGizmoModeChange={setGizmoMode}
            onShowGridChange={setShowGrid}
            onShowAxesChange={setShowAxes}
            onToggleAxis={toggleAxis}
          />
          <ViewCube camera={setupRef.current?.camera || null} onViewChange={setView} onPointerDown={handleCubeDown} />
        </>
      )}

      {renderEngine === 'unity' ? <UnityViewer panels={panels} /> : <div ref={containerRef} className="w-full h-full" />}
    </div>
  );
};

export default memo(Scene3D);
