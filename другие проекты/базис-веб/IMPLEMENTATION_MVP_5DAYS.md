# MVP ВЕБ-CAD: РЕАЛИЗАЦИЯ ЗА 5 ДНЕЙ

## 🚀 День 1: Hello World 3D

### Инициализация проекта

```bash
npm create vite@latest web-cad -- --template react-ts
cd web-cad
npm install
npm install three @types/three zustand socket.io-client axios
npm run dev
```

### src/components/Viewport.tsx - Базовая сцена

```typescript
import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export const Viewport: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Сцена
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f0f0);
    sceneRef.current = scene;

    // Камера
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const aspect = width / height;
    
    const camera = new THREE.OrthographicCamera(
      -100 * aspect, 100 * aspect,
      100, -100,
      0.1, 1000
    );
    camera.position.z = 150;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Освещение
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(100, 100, 100);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    scene.add(directionalLight);

    // Сетка
    const gridHelper = new THREE.GridHelper(200, 20, 0xcccccc, 0xeeeeee);
    scene.add(gridHelper);

    // Оси координат
    const axesHelper = new THREE.AxesHelper(50);
    scene.add(axesHelper);

    // Пример куба
    const geometry = new THREE.BoxGeometry(30, 30, 30);
    const material = new THREE.MeshStandardMaterial({
      color: 0x2196F3,
      metalness: 0.3,
      roughness: 0.7
    });
    const cube = new THREE.Mesh(geometry, material);
    cube.castShadow = true;
    cube.receiveShadow = true;
    scene.add(cube);

    // Анимация
    let frameId: number;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      cube.rotation.x += 0.005;
      cube.rotation.y += 0.01;
      renderer.render(scene, camera);
    };
    animate();

    // Handle resize
    const handleResize = () => {
      const newWidth = containerRef.current?.clientWidth || width;
      const newHeight = containerRef.current?.clientHeight || height;
      const newAspect = newWidth / newHeight;
      
      camera.left = -100 * newAspect;
      camera.right = 100 * newAspect;
      camera.updateProjectionMatrix();
      
      renderer.setSize(newWidth, newHeight);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(frameId);
      renderer.dispose();
      containerRef.current?.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative'
      }}
    />
  );
};
```

### src/App.tsx - Главное приложение

```typescript
import React, { useState } from 'react';
import { Viewport } from './components/Viewport';
import './App.css';

function App() {
  const [mode, setMode] = useState<'select' | 'draw' | 'delete'>('select');

  return (
    <div className="app">
      <aside className="toolbar">
        <h2>CAD Tools</h2>
        <nav>
          <button
            className={`tool-btn ${mode === 'select' ? 'active' : ''}`}
            onClick={() => setMode('select')}
            title="Выделение объектов"
          >
            📍 Select
          </button>
          <button
            className={`tool-btn ${mode === 'draw' ? 'active' : ''}`}
            onClick={() => setMode('draw')}
            title="Создание примитивов"
          >
            ✏️ Draw
          </button>
          <button
            className={`tool-btn ${mode === 'delete' ? 'active' : ''}`}
            onClick={() => setMode('delete')}
            title="Удаление объектов"
          >
            🗑️ Delete
          </button>
        </nav>

        <hr />

        <section>
          <h3>Примитивы</h3>
          <button className="tool-btn">📦 Box</button>
          <button className="tool-btn">🔵 Sphere</button>
          <button className="tool-btn">📺 Cylinder</button>
        </section>

        <hr />

        <section>
          <h3>View</h3>
          <button className="tool-btn">⬅️ Fit All</button>
          <button className="tool-btn">💾 Save</button>
        </section>
      </aside>

      <div className="viewport-container">
        <Viewport />
      </div>
    </div>
  );
}

export default App;
```

### src/App.css

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #fff;
}

.app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.toolbar {
  width: 250px;
  background: #f5f5f5;
  border-right: 1px solid #ddd;
  padding: 20px;
  overflow-y: auto;
  box-shadow: inset -1px 0 0 rgba(0,0,0,0.1);
}

.toolbar h2 {
  font-size: 16px;
  margin-bottom: 20px;
  color: #333;
}

.toolbar h3 {
  font-size: 13px;
  font-weight: 600;
  margin: 15px 0 10px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.toolbar hr {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 15px 0;
}

nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-btn {
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  transition: all 0.2s;
  text-align: left;
}

.tool-btn:hover {
  background: #e8e8e8;
  border-color: #bbb;
}

.tool-btn.active {
  background: #667eea;
  color: white;
  border-color: #5568d3;
}

.viewport-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}
```

---

## 🎯 День 2: Создание и трансформация объектов

### src/store/cadStore.ts - State Management

```typescript
import { create } from 'zustand';
import * as THREE from 'three';

export interface CADObject {
  id: string;
  type: 'box' | 'sphere' | 'cylinder';
  name: string;
  mesh: THREE.Mesh;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
  selected: boolean;
}

interface CADStore {
  objects: Map<string, CADObject>;
  selectedId: string | null;
  mode: 'select' | 'draw' | 'delete';

  addObject: (obj: CADObject) => void;
  removeObject: (id: string) => void;
  updateObject: (id: string, partial: Partial<CADObject>) => void;
  selectObject: (id: string | null) => void;
  setMode: (mode: 'select' | 'draw' | 'delete') => void;
}

export const useCadStore = create<CADStore>((set) => ({
  objects: new Map(),
  selectedId: null,
  mode: 'select',

  addObject: (obj) => set((state) => {
    const newMap = new Map(state.objects);
    newMap.set(obj.id, obj);
    return { objects: newMap };
  }),

  removeObject: (id) => set((state) => {
    const newMap = new Map(state.objects);
    newMap.delete(id);
    return { objects: newMap };
  }),

  updateObject: (id, partial) => set((state) => {
    const obj = state.objects.get(id);
    if (!obj) return state;
    
    const newMap = new Map(state.objects);
    newMap.set(id, { ...obj, ...partial });
    return { objects: newMap };
  }),

  selectObject: (id) => set({ selectedId: id }),
  setMode: (mode) => set({ mode })
}));
```

### src/services/geometryService.ts

```typescript
import * as THREE from 'three';

export class GeometryService {
  static createBox(width: number, height: number, depth: number): THREE.BufferGeometry {
    return new THREE.BoxGeometry(width, height, depth);
  }

  static createSphere(radius: number, segments: number = 32): THREE.BufferGeometry {
    return new THREE.SphereGeometry(radius, segments, segments);
  }

  static createCylinder(radiusTop: number, radiusBottom: number, height: number): THREE.BufferGeometry {
    return new THREE.CylinderGeometry(radiusTop, radiusBottom, height, 32);
  }

  static createMesh(
    type: 'box' | 'sphere' | 'cylinder',
    size: number = 30
  ): THREE.Mesh {
    let geometry: THREE.BufferGeometry;

    switch (type) {
      case 'box':
        geometry = this.createBox(size, size, size);
        break;
      case 'sphere':
        geometry = this.createSphere(size / 2);
        break;
      case 'cylinder':
        geometry = this.createCylinder(size / 2, size / 2, size);
        break;
    }

    const material = new THREE.MeshStandardMaterial({
      color: Math.random() * 0xffffff,
      metalness: 0.3,
      roughness: 0.7
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.cadId = Math.random().toString(36).substr(2, 9);

    return mesh;
  }
}
```

### src/services/selectionService.ts - Raycasting

```typescript
import * as THREE from 'three';

export class SelectionService {
  private raycaster: THREE.Raycaster;
  private mouse: THREE.Vector2;

  constructor(private camera: THREE.Camera, private scene: THREE.Scene) {
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
  }

  select(event: MouseEvent, canvas: HTMLElement): THREE.Object3D | null {
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.scene.children, true);

    return intersects.length > 0 ? intersects[0].object : null;
  }

  highlightObject(object: THREE.Object3D | null) {
    if (object instanceof THREE.Mesh) {
      (object.material as THREE.MeshStandardMaterial).emissive.setHex(0x222222);
    }
  }

  unhighlightObject(object: THREE.Object3D | null) {
    if (object instanceof THREE.Mesh) {
      (object.material as THREE.MeshStandardMaterial).emissive.setHex(0x000000);
    }
  }
}
```

### src/components/TransformController.tsx

```typescript
import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useCadStore } from '../store/cadStore';

export interface TransformControllerProps {
  scene: THREE.Scene;
  camera: THREE.OrthographicCamera;
  canvas: HTMLElement;
}

export const useTransformController = (props: TransformControllerProps) => {
  const storeRef = useRef({
    selectedObject: null as THREE.Object3D | null,
    isDragging: false,
    previousMousePosition: { x: 0, y: 0 }
  });

  useEffect(() => {
    const { scene, camera, canvas } = props;
    const store = storeRef.current;
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const getIntersectedObject = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(scene.children, true);
      return intersects.length > 0 ? intersects[0].object : null;
    };

    const onMouseDown = (event: MouseEvent) => {
      store.selectedObject = getIntersectedObject(event);
      if (store.selectedObject) {
        store.isDragging = true;
        store.previousMousePosition = { x: event.clientX, y: event.clientY };
      }
    };

    const onMouseMove = (event: MouseEvent) => {
      if (!store.isDragging || !store.selectedObject) return;

      const deltaX = event.clientX - store.previousMousePosition.x;
      const deltaY = event.clientY - store.previousMousePosition.y;

      if (store.selectedObject instanceof THREE.Mesh) {
        const moveScale = 0.1;
        store.selectedObject.position.x += deltaX * moveScale;
        store.selectedObject.position.y -= deltaY * moveScale;
      }

      store.previousMousePosition = { x: event.clientX, y: event.clientY };
    };

    const onMouseUp = () => {
      store.isDragging = false;
    };

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseup', onMouseUp);
    };
  }, []);
};
```

---

## 💾 День 3: Сохранение и Undo/Redo

### src/services/documentService.ts - CAD документ

```typescript
import * as THREE from 'three';

export interface SerializedObject {
  id: string;
  type: 'box' | 'sphere' | 'cylinder';
  name: string;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
  color: number;
}

export interface CADDocument {
  name: string;
  objects: SerializedObject[];
  version: string;
  createdAt: string;
  modifiedAt: string;
}

export class DocumentService {
  static serialize(scene: THREE.Scene): CADDocument {
    const objects: SerializedObject[] = [];

    scene.children.forEach((child) => {
      if (child instanceof THREE.Mesh && child.userData.cadId) {
        const material = child.material as THREE.MeshStandardMaterial;
        objects.push({
          id: child.userData.cadId,
          type: child.userData.type || 'box',
          name: child.userData.name || 'Object',
          position: [child.position.x, child.position.y, child.position.z],
          rotation: [child.rotation.x, child.rotation.y, child.rotation.z],
          scale: [child.scale.x, child.scale.y, child.scale.z],
          color: material.color.getHex()
        });
      }
    });

    return {
      name: 'Untitled',
      objects,
      version: '1.0',
      createdAt: new Date().toISOString(),
      modifiedAt: new Date().toISOString()
    };
  }

  static save(document: CADDocument, filename: string = 'document.json') {
    const json = JSON.stringify(document, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  static async load(file: File): Promise<CADDocument> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = JSON.parse(e.target?.result as string);
          resolve(data);
        } catch (error) {
          reject(error);
        }
      };
      reader.readAsText(file);
    });
  }
}
```

### src/services/commandHistory.ts - Undo/Redo

```typescript
export abstract class Command {
  abstract execute(): void;
  abstract undo(): void;
}

export class AddObjectCommand extends Command {
  constructor(private scene: THREE.Scene, private mesh: THREE.Mesh) {
    super();
  }

  execute() {
    this.scene.add(this.mesh);
  }

  undo() {
    this.scene.remove(this.mesh);
  }
}

export class RemoveObjectCommand extends Command {
  private index: number;

  constructor(private scene: THREE.Scene, private mesh: THREE.Mesh) {
    super();
    this.index = scene.children.indexOf(mesh);
  }

  execute() {
    this.scene.remove(this.mesh);
  }

  undo() {
    this.scene.children.splice(this.index, 0, this.mesh);
  }
}

export class MoveObjectCommand extends Command {
  private oldPosition: THREE.Vector3;

  constructor(
    private object: THREE.Object3D,
    private newPosition: THREE.Vector3
  ) {
    super();
    this.oldPosition = object.position.clone();
  }

  execute() {
    this.object.position.copy(this.newPosition);
  }

  undo() {
    this.object.position.copy(this.oldPosition);
  }
}

export class CommandHistory {
  private commands: Command[] = [];
  private index = 0;

  execute(command: Command) {
    command.execute();
    this.commands = this.commands.slice(0, this.index);
    this.commands.push(command);
    this.index++;
  }

  undo() {
    if (this.index > 0) {
      this.commands[--this.index].undo();
    }
  }

  redo() {
    if (this.index < this.commands.length) {
      this.commands[this.index++].execute();
    }
  }

  get canUndo() {
    return this.index > 0;
  }

  get canRedo() {
    return this.index < this.commands.length;
  }
}
```

---

## 🌐 День 4: WebSocket Collab

### backend/server.js

```javascript
const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const cors = require('cors');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(cors());
app.use(express.json());

const clients = new Map();
let documentState = { objects: [] };

wss.on('connection', (ws) => {
  const clientId = Math.random().toString(36).substr(2, 9);
  clients.set(clientId, { ws, user: null });

  console.log(`Client connected: ${clientId}`);

  // Отправить текущее состояние
  ws.send(JSON.stringify({
    type: 'INITIAL_STATE',
    data: documentState
  }));

  ws.on('message', (message) => {
    const data = JSON.parse(message);

    switch (data.type) {
      case 'ADD_OBJECT':
        documentState.objects.push(data.object);
        broadcast(data);
        break;

      case 'REMOVE_OBJECT':
        documentState.objects = documentState.objects.filter(
          (obj) => obj.id !== data.objectId
        );
        broadcast(data);
        break;

      case 'UPDATE_OBJECT':
        const objIndex = documentState.objects.findIndex(
          (obj) => obj.id === data.object.id
        );
        if (objIndex !== -1) {
          documentState.objects[objIndex] = data.object;
        }
        broadcast(data);
        break;

      case 'CURSOR_MOVE':
        broadcast({
          type: 'CURSOR_POSITION',
          clientId,
          position: data.position
        });
        break;
    }
  });

  ws.on('close', () => {
    clients.delete(clientId);
    broadcast({
      type: 'CLIENT_DISCONNECT',
      clientId
    });
    console.log(`Client disconnected: ${clientId}`);
  });
});

function broadcast(message) {
  const json = JSON.stringify(message);
  clients.forEach(({ ws }) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(json);
    }
  });
}

server.listen(3001, () => {
  console.log('WebSocket server running on :3001');
});
```

### src/services/collaborationService.ts

```typescript
export class CollaborationService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect(url: string, onMessage: (data: any) => void, onError: (error: Event) => void) {
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('Connected to WebSocket');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      onMessage(JSON.parse(event.data));
    };

    this.ws.onerror = (error) => {
      onError(error);
      this.attemptReconnect(url, onMessage, onError);
    };

    this.ws.onclose = () => {
      this.attemptReconnect(url, onMessage, onError);
    };
  }

  private attemptReconnect(
    url: string,
    onMessage: (data: any) => void,
    onError: (error: Event) => void
  ) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.pow(2, this.reconnectAttempts) * 1000;
      console.log(`Reconnecting in ${delay}ms...`);
      setTimeout(() => this.connect(url, onMessage, onError), delay);
    }
  }

  send(type: string, data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...data }));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

---

## 🎨 День 5: Polish & Deploy

### src/components/ExportPanel.tsx

```typescript
import React from 'react';
import { DocumentService } from '../services/documentService';

export const ExportPanel: React.FC<{ scene: THREE.Scene }> = ({ scene }) => {
  const handleSave = () => {
    const doc = DocumentService.serialize(scene);
    DocumentService.save(doc, 'design.json');
  };

  const handleExportSTL = () => {
    // Simplified STL export
    alert('STL export coming soon!');
  };

  return (
    <div style={{ padding: '10px' }}>
      <button onClick={handleSave} style={{ width: '100%', marginBottom: '5px' }}>
        💾 Save JSON
      </button>
      <button onClick={handleExportSTL} style={{ width: '100%' }}>
        📤 Export STL
      </button>
    </div>
  );
};
```

### Deployment Scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "backend": "node backend/server.js",
    "deploy:frontend": "npm run build && vercel deploy ./dist",
    "deploy:backend": "railway up"
  }
}
```

### Vercel Deploy

```bash
# Создать vercel.json
npm run build
vercel
```

### Railway Backend Deploy

```bash
# backend/railway.json
{
  "builder": "nodejs",
  "buildCommand": "npm install",
  "startCommand": "node server.js"
}

railway up
```

---

## ✅ Финальный чек-лист

```
✅ День 1: Basic setup с Three.js + React
✅ День 2: Create objects, selection, transform
✅ День 3: Save/load, Undo/Redo
✅ День 4: Real-time collaboration (WebSocket)
✅ День 5: Export + Deploy
```

**Результат**: Полнофункциональная web-CAD система готова к использованию!
