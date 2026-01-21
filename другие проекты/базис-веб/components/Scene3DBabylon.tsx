import React, { useEffect, useRef, useState } from 'react';
import * as BABYLON from '@babylonjs/core';
import { useProjectStore } from '../store/projectStore';
import { Axis } from '../types';
import { Grid3X3, RotateCcw } from 'lucide-react';
import { PerformanceMonitor3D, PerformanceMetrics } from '../services/PerformanceMonitor3D';

const Scene3DBabylon: React.FC = () => {
  const { panels, selectPanel } = useProjectStore();
  
  const containerRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<BABYLON.Engine | null>(null);
  const sceneRef = useRef<BABYLON.Scene | null>(null);
  const [showGrid, setShowGrid] = useState(true);
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

  useEffect(() => {
    if (!containerRef.current) return;

    const canvas = document.createElement('canvas');
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    containerRef.current.appendChild(canvas);

    const engine = new BABYLON.Engine(canvas, true);
    engineRef.current = engine;
    engine.resize();

    const scene = new BABYLON.Scene(engine);
    scene.clearColor = new BABYLON.Color4(0.1, 0.1, 0.1, 1);
    sceneRef.current = scene;

    const camera = new BABYLON.ArcRotateCamera(
      'camera',
      -Math.PI / 2,
      Math.PI / 2.5,
      6000,
      new BABYLON.Vector3(900, 1200, 0),
      scene
    );
    camera.attachControl(canvas, true);
    camera.wheelPrecision = 40;
    camera.panningSensibility = 0;
    camera.lowerRadiusLimit = 50;
    camera.upperRadiusLimit = 500000;
    camera.minZ = 10;
    camera.maxZ = 200000;

    const light = new BABYLON.HemisphericLight('light', new BABYLON.Vector3(0, 1, 0), scene);
    light.intensity = 1.5;

    const light2 = new BABYLON.PointLight('point', new BABYLON.Vector3(1500, 2000, 1500), scene);
    light2.intensity = 1.2;

    const ground = BABYLON.MeshBuilder.CreateGround('ground', { width: 10000, height: 10000 }, scene);
    ground.position.y = -100;
    const groundMat = new BABYLON.StandardMaterial('gmat', scene);
    groundMat.diffuseColor = new BABYLON.Color3(0.15, 0.15, 0.15);
    groundMat.specularColor = new BABYLON.Color3(0, 0, 0);
    ground.material = groundMat;

    scene.onPointerDown = (evt, pickResult) => {
      const pickedMesh = pickResult?.pickedMesh as BABYLON.AbstractMesh | null;
      if (!pickResult?.hit || !pickedMesh) return;
      const panelId = (pickedMesh as any).metadata?.panelId;
      if (panelId) {
        selectPanel(panelId);
      }
    };

    engine.runRenderLoop(() => {
      scene.render();
      if (performanceMonitorRef.current) {
        const metrics = performanceMonitorRef.current.update();
        setPerformanceMetrics(metrics);
      }
    });

    const resize = () => engine.resize();
    window.addEventListener('resize', resize);

    performanceMonitorRef.current = new PerformanceMonitor3D();
    performanceMonitorRef.current.start();

    return () => {
      window.removeEventListener('resize', resize);
      if (performanceMonitorRef.current) {
        performanceMonitorRef.current.stop();
      }
      engine.dispose();
    };
  }, [selectPanel]);

  useEffect(() => {
    if (!sceneRef.current) return;

    const existingPanels = sceneRef.current.meshes.filter(m => m.name.startsWith('p-'));
    existingPanels.forEach(mesh => mesh.dispose(false, true));

    console.log('[Babylon] Rendering', panels.length, 'panels');

    panels.forEach((panel) => {
      try {
        const dX = panel.width;
        const dY = panel.height;
        const dZ = panel.depth;

        const pos = {
          x: panel.x + dX / 2,
          y: panel.y + dY / 2,
          z: panel.z + dZ / 2
        };

        const box = BABYLON.MeshBuilder.CreateBox(`p-${panel.id}`, {
          width: dX,
          height: dY,
          depth: dZ
        }, sceneRef.current!);
        
        box.position = new BABYLON.Vector3(pos.x, pos.y, pos.z);
        box.isPickable = true;
        box.metadata = { panelId: panel.id };
        box.isVisible = true;

        const material = new BABYLON.StandardMaterial(`mat-${panel.id}`, sceneRef.current!);
        material.diffuseColor = new BABYLON.Color3(0, 1, 0);
        material.emissiveColor = new BABYLON.Color3(0, 0.5, 0);
        material.wireframe = true;
        box.material = material;

        console.log('[Babylon] Panel created:', panel.id, box.position);

      } catch (e) {
        console.error(`[Babylon] Error rendering panel ${panel.id}:`, e);
      }
    });

    const testCube = BABYLON.MeshBuilder.CreateBox('test-cube', {
      width: 200,
      height: 200,
      depth: 200
    }, sceneRef.current!);
    testCube.position = new BABYLON.Vector3(0, 100, 0);
    testCube.isPickable = false;
    testCube.isVisible = true;
    const testMat = new BABYLON.StandardMaterial('test-mat', sceneRef.current!);
    testMat.diffuseColor = new BABYLON.Color3(1, 0, 0);
    testMat.emissiveColor = new BABYLON.Color3(0.5, 0, 0);
    testMat.wireframe = true;
    testCube.material = testMat;

  }, [panels]);

  useEffect(() => {
    if (!sceneRef.current) return;
    const g = sceneRef.current.getMeshByName('ground');
    if (g) g.isVisible = showGrid;
  }, [showGrid]);

  return (
    <div className="relative w-full h-full bg-black">
      <div ref={containerRef} className="w-full h-full" />
      
      <div className="absolute top-4 right-4 text-[10px] text-slate-200 bg-black/70 px-3 py-2 rounded border border-gray-700 z-20 font-mono space-y-1">
        <div className="text-blue-400 font-bold border-b border-blue-500/50 pb-1 mb-1">📊 Performance Metrics</div>
        <div>FPS: {performanceMetrics.fps} fps</div>
        <div>Frame Time: {performanceMetrics.frameTime.toFixed(1)} ms</div>
        <div>Render Time: {performanceMetrics.renderTime.toFixed(1)} ms</div>
        <div>Draw Calls: {performanceMetrics.drawCalls}</div>
        <div>Triangles: {performanceMetrics.triangleCount}</div>
        <div>GPU Mem: {performanceMetrics.gpuMemory} MB</div>
        <div>CPU Usage: {performanceMetrics.cpuUsage}%</div>
        <div className="mt-2 pt-2 border-t border-gray-700">
          <div>panels: {panels.length}</div>
        </div>
      </div>

      <div className="absolute top-4 left-4 bg-black/80 p-2 rounded border border-gray-700 flex gap-1 z-10">
        <button
          onClick={() => setShowGrid(!showGrid)}
          className={`p-2 rounded ${showGrid ? 'bg-blue-600' : 'bg-gray-700'}`}
          title="Toggle Grid"
        >
          <Grid3X3 size={16} />
        </button>
        <button
          onClick={() => {
            if (sceneRef.current?.activeCamera) {
              const cam = sceneRef.current.activeCamera as any;
              if (typeof cam.setTarget === 'function') {
                cam.setTarget(new BABYLON.Vector3(0, 1000, 0));
              }
              if (typeof cam.radius === 'number') {
                cam.radius = 6000;
              }
            }
          }}
          className="p-2 rounded bg-gray-700 hover:bg-gray-600"
          title="Reset View"
        >
          <RotateCcw size={16} />
        </button>
      </div>
    </div>
  );
};

export default Scene3DBabylon;
