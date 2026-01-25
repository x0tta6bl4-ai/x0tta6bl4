# ПРАКТИЧЕСКОЕ РУКОВОДСТВО: РЕАЛИЗАЦИЯ ВЕБ-CAD СИСТЕМЫ

## ЧАСТЬ 1: БАЗОВЫЙ SETUP ПРОЕКТА

### Структура проекта

```
web-cad-engine/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── CADEditor.tsx
│   │   │   ├── Viewport3D.tsx
│   │   │   ├── PropertyPanel.tsx
│   │   │   └── ToolPanel.tsx
│   │   ├── services/
│   │   │   ├── GeometryService.ts
│   │   │   ├── RenderService.ts
│   │   │   └── CollaborationService.ts
│   │   ├── models/
│   │   │   ├── Document.ts
│   │   │   ├── Feature.ts
│   │   │   └── Selection.ts
│   │   └── App.tsx
│   ├── package.json
│   └── tsconfig.json
├── backend/
│   ├── src/
│   │   ├── server.js
│   │   ├── routes/
│   │   ├── services/
│   │   └── middleware/
│   └── package.json
├── geometry-wasm/
│   ├── src/
│   │   ├── lib.rs
│   │   └── geometry.rs
│   └── Cargo.toml
└── docs/
    └── architecture.md
```

### package.json (Frontend)

```json
{
  "name": "web-cad-frontend",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "three": "^r158",
    "babylon": "^6.0.0",
    "occt": "^1.0.0",
    "zustand": "^4.4.0",
    "socket.io-client": "^4.5.0",
    "typescript": "^5.0.0"
  },
  "devDependencies": {
    "@types/three": "^r158",
    "@types/react": "^18.0.0",
    "vite": "^4.0.0",
    "ts-loader": "^9.4.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

---

## ЧАСТЬ 2: ЯДРО СИСТЕМЫ

### 1. Модель документа (TypeScript)

```typescript
// src/models/Document.ts
import { v4 as uuidv4 } from 'uuid';

export interface Property {
  name: string;
  type: 'number' | 'string' | 'boolean' | 'vector3' | 'color';
  value: any;
  min?: number;
  max?: number;
  editable: boolean;
}

export interface Feature {
  id: string;
  name: string;
  type: 'Sketch' | 'Pad' | 'Pocket' | 'Fillet' | 'Chamfer' | 'Boolean';
  properties: Map<string, Property>;
  dependencies: string[];
  visible: boolean;
  geometry?: THREE.BufferGeometry;
  mesh?: THREE.Mesh;
}

export class CADDocument {
  private static instance: CADDocument;
  
  id: string;
  name: string;
  features: Feature[] = [];
  version: number = 0;
  lastModified: Date = new Date();
  history: CommandHistory;
  
  private constructor() {
    this.id = uuidv4();
    this.name = 'Untitled Document';
    this.history = new CommandHistory();
  }
  
  static getInstance(): CADDocument {
    if (!CADDocument.instance) {
      CADDocument.instance = new CADDocument();
    }
    return CADDocument.instance;
  }
  
  addFeature(feature: Feature): void {
    this.features.push(feature);
    this.version++;
    this.lastModified = new Date();
  }
  
  removeFeature(featureId: string): void {
    const index = this.features.findIndex(f => f.id === featureId);
    if (index !== -1) {
      this.features.splice(index, 1);
      this.version++;
      this.lastModified = new Date();
    }
  }
  
  getFeature(featureId: string): Feature | undefined {
    return this.features.find(f => f.id === featureId);
  }
  
  getFeaturesByType(type: string): Feature[] {
    return this.features.filter(f => f.type === type);
  }
  
  reorder(featureId: string, newIndex: number): void {
    const feature = this.getFeature(featureId);
    if (!feature) return;
    
    const oldIndex = this.features.indexOf(feature);
    if (oldIndex !== -1) {
      this.features.splice(oldIndex, 1);
      this.features.splice(newIndex, 0, feature);
      this.version++;
    }
  }
  
  serialize(): string {
    return JSON.stringify({
      id: this.id,
      name: this.name,
      version: this.version,
      features: this.features.map(f => ({
        ...f,
        properties: Array.from(f.properties.entries())
      }))
    });
  }
  
  static deserialize(json: string): CADDocument {
    const data = JSON.parse(json);
    const doc = CADDocument.getInstance();
    doc.id = data.id;
    doc.name = data.name;
    doc.version = data.version;
    doc.features = data.features.map((f: any) => ({
      ...f,
      properties: new Map(f.properties)
    }));
    return doc;
  }
}

// История команд для Undo/Redo
abstract class Command {
  abstract execute(): void;
  abstract undo(): void;
}

class AddFeatureCommand extends Command {
  constructor(private doc: CADDocument, private feature: Feature) {
    super();
  }
  
  execute(): void {
    this.doc.addFeature(this.feature);
  }
  
  undo(): void {
    this.doc.removeFeature(this.feature.id);
  }
}

class CommandHistory {
  private history: Command[] = [];
  private index: number = 0;
  
  execute(command: Command): void {
    command.execute();
    this.history = this.history.slice(0, this.index);
    this.history.push(command);
    this.index++;
  }
  
  undo(): void {
    if (this.index > 0) {
      this.index--;
      this.history[this.index].undo();
    }
  }
  
  redo(): void {
    if (this.index < this.history.length) {
      this.history[this.index].execute();
      this.index++;
    }
  }
  
  canUndo(): boolean {
    return this.index > 0;
  }
  
  canRedo(): boolean {
    return this.index < this.history.length;
  }
}

export { Command, AddFeatureCommand, CommandHistory };
```

### 2. Сервис геометрии

```typescript
// src/services/GeometryService.ts
import * as THREE from 'three';

export class GeometryService {
  private static instance: GeometryService;
  private geometryCache: Map<string, THREE.BufferGeometry> = new Map();
  
  private constructor() {}
  
  static getInstance(): GeometryService {
    if (!GeometryService.instance) {
      GeometryService.instance = new GeometryService();
    }
    return GeometryService.instance;
  }
  
  // Создание примитивов
  createBox(width: number, height: number, depth: number): THREE.BufferGeometry {
    return new THREE.BoxGeometry(width, height, depth);
  }
  
  createSphere(radius: number, widthSegments: number = 32, heightSegments: number = 32): THREE.BufferGeometry {
    return new THREE.SphereGeometry(radius, widthSegments, heightSegments);
  }
  
  createCylinder(radiusTop: number, radiusBottom: number, height: number, radialSegments: number = 32): THREE.BufferGeometry {
    return new THREE.CylinderGeometry(radiusTop, radiusBottom, height, radialSegments);
  }
  
  // Булевы операции (требует Three-CSG)
  async performBooleanOperation(
    geom1: THREE.BufferGeometry,
    geom2: THREE.BufferGeometry,
    operation: 'union' | 'subtract' | 'intersect'
  ): Promise<THREE.BufferGeometry> {
    // Для реальной реализации используйте CSG библиотеку
    // или OCCT.js через Web Worker
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(geom1); // Placeholder
      }, 100);
    });
  }
  
  // Скругление ребер (Fillet)
  async performFillet(
    geometry: THREE.BufferGeometry,
    radius: number,
    edgeIndices?: number[]
  ): Promise<THREE.BufferGeometry> {
    // Реализовать через Web Worker
    return geometry.clone();
  }
  
  // Создание краевых линий
  createEdgeGeometry(geometry: THREE.BufferGeometry): THREE.BufferGeometry {
    return new THREE.EdgesGeometry(geometry);
  }
  
  // Оптимизация геометрии
  optimizeGeometry(geometry: THREE.BufferGeometry, vertexReduction: number = 0.5): THREE.BufferGeometry {
    const optimized = geometry.clone();
    
    // Удалить дублирующиеся вершины
    const posAttr = optimized.getAttribute('position');
    // ... реализовать упрощение
    
    return optimized;
  }
  
  // Кэширование
  cacheGeometry(key: string, geometry: THREE.BufferGeometry): void {
    this.geometryCache.set(key, geometry);
  }
  
  getCachedGeometry(key: string): THREE.BufferGeometry | undefined {
    return this.geometryCache.get(key);
  }
  
  // Экспорт/Импорт
  exportToSTL(geometry: THREE.BufferGeometry): ArrayBuffer {
    // Реализовать экспорт в STL
    return new ArrayBuffer(0);
  }
  
  exportToGLB(mesh: THREE.Mesh): ArrayBuffer {
    // Использовать THREE.GLTFExporter
    return new ArrayBuffer(0);
  }
  
  async importFromSTL(data: ArrayBuffer): Promise<THREE.BufferGeometry> {
    // Использовать THREE.STLLoader
    return new THREE.BufferGeometry();
  }
}
```

### 3. Сервис рендеринга

```typescript
// src/services/RenderService.ts
import * as THREE from 'three';
import { Feature } from '../models/Document';

export class RenderService {
  private scene: THREE.Scene;
  private camera: THREE.Camera;
  private renderer: THREE.WebGLRenderer;
  private meshes: Map<string, THREE.Mesh> = new Map();
  private selectedMeshes: THREE.Mesh[] = [];
  private animationFrameId: number | null = null;
  
  constructor(canvas: HTMLCanvasElement) {
    // Инициализация сцены
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xffffff);
    
    // Ортографическая камера для CAD
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    this.camera = new THREE.OrthographicCamera(
      -w / 2, w / 2, h / 2, -h / 2, 0.1, 10000
    );
    this.camera.position.z = 100;
    
    // Renderer
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    
    // Освещение
    this.setupLighting();
    
    // Сетка
    this.setupGrid();
    
    // Обработчик resize
    window.addEventListener('resize', () => this.onWindowResize());
  }
  
  private setupLighting(): void {
    // Ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);
    
    // Directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(50, 50, 50);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    this.scene.add(directionalLight);
    
    // Point light
    const pointLight = new THREE.PointLight(0xffffff, 0.5);
    pointLight.position.set(-50, -50, 50);
    this.scene.add(pointLight);
  }
  
  private setupGrid(): void {
    const gridHelper = new THREE.GridHelper(200, 20);
    gridHelper.position.z = 0;
    this.scene.add(gridHelper);
  }
  
  addFeatureToScene(feature: Feature): void {
    if (!feature.geometry) return;
    
    const material = new THREE.MeshPhysicalMaterial({
      color: 0x2196F3,
      metalness: 0.1,
      roughness: 0.4,
      emissive: 0x000000
    });
    
    const mesh = new THREE.Mesh(feature.geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.featureId = feature.id;
    
    this.scene.add(mesh);
    this.meshes.set(feature.id, mesh);
    
    // Добавить краевые линии
    const edges = new THREE.EdgesGeometry(feature.geometry);
    const line = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: 0x000000 })
    );
    mesh.add(line);
  }
  
  removeFeatureFromScene(featureId: string): void {
    const mesh = this.meshes.get(featureId);
    if (mesh) {
      this.scene.remove(mesh);
      this.meshes.delete(featureId);
    }
  }
  
  selectMesh(mesh: THREE.Mesh): void {
    (mesh.material as THREE.MeshPhysicalMaterial).emissive.setHex(0xffaa00);
    this.selectedMeshes.push(mesh);
  }
  
  deselectMesh(mesh: THREE.Mesh): void {
    (mesh.material as THREE.MeshPhysicalMaterial).emissive.setHex(0x000000);
    const index = this.selectedMeshes.indexOf(mesh);
    if (index !== -1) {
      this.selectedMeshes.splice(index, 1);
    }
  }
  
  clearSelection(): void {
    this.selectedMeshes.forEach(mesh => {
      (mesh.material as THREE.MeshPhysicalMaterial).emissive.setHex(0x000000);
    });
    this.selectedMeshes = [];
  }
  
  // Фит камеры на объект
  fitCameraToObject(mesh: THREE.Mesh): void {
    const box = new THREE.Box3().setFromObject(mesh);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = (this.camera as THREE.OrthographicCamera).zoom;
    let distance = maxDim / 2 / Math.tan(Math.PI / 4);
    
    const direction = new THREE.Vector3();
    box.getCenter(direction);
    
    this.camera.position.copy(direction);
    this.camera.position.z += distance;
    this.camera.lookAt(direction);
  }
  
  // Фит все объекты в кадр
  fitAllToView(): void {
    const box = new THREE.Box3();
    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        box.expandByObject(obj);
      }
    });
    
    if (box.isEmpty()) return;
    
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    
    const maxDim = Math.max(size.x, size.y, size.z);
    const distance = maxDim / 2 / Math.tan(Math.PI / 4);
    
    this.camera.position.copy(center);
    this.camera.position.z += distance;
    this.camera.lookAt(center);
  }
  
  startRender(): void {
    const animate = () => {
      this.animationFrameId = requestAnimationFrame(animate);
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }
  
  stopRender(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }
  
  getScene(): THREE.Scene {
    return this.scene;
  }
  
  getCamera(): THREE.Camera {
    return this.camera;
  }
  
  private onWindowResize(): void {
    const w = this.renderer.domElement.clientWidth;
    const h = this.renderer.domElement.clientHeight;
    
    if (this.camera instanceof THREE.OrthographicCamera) {
      this.camera.left = -w / 2;
      this.camera.right = w / 2;
      this.camera.top = h / 2;
      this.camera.bottom = -h / 2;
      this.camera.updateProjectionMatrix();
    }
    
    this.renderer.setSize(w, h);
  }
}
```

---

## ЧАСТЬ 3: КОМПОНЕНТЫ REACT

### Главный компонент редактора

```typescript
// src/components/CADEditor.tsx
import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { CADDocument, Feature } from '../models/Document';
import { RenderService } from '../services/RenderService';
import { GeometryService } from '../services/GeometryService';
import Viewport3D from './Viewport3D';
import PropertyPanel from './PropertyPanel';
import ToolPanel from './ToolPanel';

interface CADEditorProps {
  documentId?: string;
}

const CADEditor: React.FC<CADEditorProps> = ({ documentId }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [renderService, setRenderService] = useState<RenderService | null>(null);
  const [document, setDocument] = useState<CADDocument | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Инициализация
  useEffect(() => {
    if (!canvasRef.current) return;
    
    try {
      const doc = CADDocument.getInstance();
      const renderer = new RenderService(canvasRef.current);
      
      setDocument(doc);
      setRenderService(renderer);
      
      renderer.startRender();
      
      return () => {
        renderer.stopRender();
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, []);
  
  // Загрузка документа
  useEffect(() => {
    if (!documentId || !document) return;
    
    setIsLoading(true);
    fetch(`/api/documents/${documentId}`)
      .then(res => res.json())
      .then(data => {
        const loaded = CADDocument.deserialize(JSON.stringify(data));
        loaded.features.forEach(feature => {
          if (renderService && feature.geometry) {
            renderService.addFeatureToScene(feature);
          }
        });
        setDocument(loaded);
      })
      .catch(err => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [documentId]);
  
  const handleCreateBox = (): void => {
    if (!document || !renderService) return;
    
    const geomService = GeometryService.getInstance();
    const geometry = geomService.createBox(10, 10, 10);
    
    const feature: Feature = {
      id: Math.random().toString(36),
      name: 'Box',
      type: 'Pad',
      properties: new Map([
        ['width', { name: 'Width', type: 'number', value: 10, editable: true }],
        ['height', { name: 'Height', type: 'number', value: 10, editable: true }],
        ['depth', { name: 'Depth', type: 'number', value: 10, editable: true }]
      ]),
      dependencies: [],
      visible: true,
      geometry
    };
    
    document.addFeature(feature);
    renderService.addFeatureToScene(feature);
    setDocument({ ...document });
  };
  
  const handleSelectFeature = (feature: Feature): void => {
    setSelectedFeature(feature);
  };
  
  const handleDeleteFeature = (featureId: string): void => {
    if (!document || !renderService) return;
    
    document.removeFeature(featureId);
    renderService.removeFeatureFromScene(featureId);
    setSelectedFeature(null);
    setDocument({ ...document });
  };
  
  if (error) {
    return <div className="error">Error: {error}</div>;
  }
  
  return (
    <div className="cad-editor">
      <header className="editor-header">
        <h1>CAD Editor</h1>
      </header>
      
      <div className="editor-main">
        <aside className="editor-sidebar">
          <ToolPanel
            onCreateBox={handleCreateBox}
            onDelete={() => selectedFeature && handleDeleteFeature(selectedFeature.id)}
            hasSelection={selectedFeature !== null}
          />
        </aside>
        
        <main className="editor-content">
          <Viewport3D
            canvasRef={canvasRef}
            document={document}
            onSelectFeature={handleSelectFeature}
            renderService={renderService}
            isLoading={isLoading}
          />
        </main>
        
        <aside className="editor-properties">
          {selectedFeature && (
            <PropertyPanel
              feature={selectedFeature}
              onChange={(properties) => {
                if (document) {
                  const updated = { ...selectedFeature, properties };
                  const index = document.features.findIndex(f => f.id === selectedFeature.id);
                  if (index !== -1) {
                    document.features[index] = updated;
                    setSelectedFeature(updated);
                    setDocument({ ...document });
                  }
                }
              }}
            />
          )}
        </aside>
      </div>
    </div>
  );
};

export default CADEditor;
```

### Компонент 3D viewport

```typescript
// src/components/Viewport3D.tsx
import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { CADDocument, Feature } from '../models/Document';
import { RenderService } from '../services/RenderService';

interface Viewport3DProps {
  canvasRef: React.RefObject<HTMLCanvasElement>;
  document: CADDocument | null;
  onSelectFeature: (feature: Feature) => void;
  renderService: RenderService | null;
  isLoading: boolean;
}

const Viewport3D: React.FC<Viewport3DProps> = ({
  canvasRef,
  document,
  onSelectFeature,
  renderService,
  isLoading
}) => {
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());
  
  useEffect(() => {
    if (!canvasRef.current || !renderService) return;
    
    const handleMouseDown = (event: MouseEvent) => {
      if (!canvasRef.current) return;
      
      const rect = canvasRef.current.getBoundingClientRect();
      mouseRef.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      
      raycasterRef.current.setFromCamera(mouseRef.current, renderService.getCamera());
      
      const scene = renderService.getScene();
      const meshes: THREE.Mesh[] = [];
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.userData.featureId) {
          meshes.push(obj);
        }
      });
      
      const intersects = raycasterRef.current.intersectObjects(meshes);
      
      if (intersects.length > 0) {
        const mesh = intersects[0].object as THREE.Mesh;
        const featureId = mesh.userData.featureId;
        const feature = document?.getFeature(featureId);
        if (feature) {
          onSelectFeature(feature);
          renderService.clearSelection();
          renderService.selectMesh(mesh);
        }
      } else {
        renderService.clearSelection();
      }
    };
    
    canvasRef.current.addEventListener('mousedown', handleMouseDown);
    
    return () => {
      canvasRef.current?.removeEventListener('mousedown', handleMouseDown);
    };
  }, [canvasRef, renderService, document, onSelectFeature]);
  
  return (
    <div className="viewport-container">
      <canvas ref={canvasRef} className="viewport-canvas" />
      {isLoading && <div className="loading-indicator">Loading...</div>}
    </div>
  );
};

export default Viewport3D;
```

---

## ЧАСТЬ 4: BACKEND API

### Server Setup (Express.js)

```javascript
// backend/src/server.js
const express = require('express');
const cors = require('cors');
const http = require('http');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// Middleware
app.use(cors());
app.use(express.json());

// In-memory storage (в продакшене использовать БД)
const documents = new Map();
const sessions = new Map();

// REST API Routes
app.get('/api/documents/:id', (req, res) => {
  const doc = documents.get(req.params.id);
  if (!doc) {
    return res.status(404).json({ error: 'Document not found' });
  }
  res.json(doc);
});

app.post('/api/documents', (req, res) => {
  const id = uuidv4();
  const doc = {
    id,
    name: req.body.name || 'Untitled',
    version: 0,
    features: [],
    createdAt: new Date(),
    updatedAt: new Date()
  };
  documents.set(id, doc);
  res.json(doc);
});

app.put('/api/documents/:id', (req, res) => {
  const doc = documents.get(req.params.id);
  if (!doc) {
    return res.status(404).json({ error: 'Document not found' });
  }
  
  Object.assign(doc, req.body);
  doc.updatedAt = new Date();
  documents.set(req.params.id, doc);
  
  // Broadcast to connected clients
  broadcastToDocument(req.params.id, {
    type: 'DOCUMENT_UPDATE',
    document: doc
  });
  
  res.json(doc);
});

// WebSocket для коллаборации
wss.on('connection', (ws) => {
  const sessionId = uuidv4();
  const session = { id: sessionId, ws, documentId: null };
  sessions.set(sessionId, session);
  
  ws.on('message', (message) => {
    const data = JSON.parse(message);
    
    switch (data.type) {
      case 'OPEN_DOCUMENT':
        session.documentId = data.documentId;
        const doc = documents.get(data.documentId);
        if (doc) {
          ws.send(JSON.stringify({
            type: 'DOCUMENT_STATE',
            document: doc
          }));
        }
        break;
        
      case 'MODIFY_FEATURE':
        broadcastToDocument(data.documentId, {
          type: 'FEATURE_MODIFIED',
          feature: data.feature,
          sessionId
        });
        break;
    }
  });
  
  ws.on('close', () => {
    sessions.delete(sessionId);
  });
});

function broadcastToDocument(documentId, message) {
  sessions.forEach((session, sessionId) => {
    if (session.documentId === documentId && session.ws.readyState === WebSocket.OPEN) {
      session.ws.send(JSON.stringify(message));
    }
  });
}

// Запуск сервера
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

---

## ЧАСТЬ 5: СТИЛИ И УЛУЧШЕНИЕ UX

### CSS (Tailwind + Custom)

```css
/* src/styles/CADEditor.css */
.cad-editor {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
}

.editor-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.editor-main {
  display: grid;
  grid-template-columns: 250px 1fr 300px;
  flex: 1;
  gap: 1px;
  background-color: #ddd;
}

.editor-sidebar {
  background-color: white;
  border-right: 1px solid #ddd;
  overflow-y: auto;
}

.editor-content {
  background-color: white;
  position: relative;
}

.editor-properties {
  background-color: white;
  border-left: 1px solid #ddd;
  overflow-y: auto;
}

.viewport-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.viewport-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.loading-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 2rem;
  border-radius: 8px;
  font-size: 1.1rem;
}

/* Tool Panel */
.tool-panel {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tool-button {
  padding: 0.75rem 1rem;
  background-color: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.tool-button:hover {
  background-color: #764ba2;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.tool-button:active {
  transform: translateY(0);
}

.tool-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

/* Property Panel */
.property-panel {
  padding: 1.5rem;
}

.property-group {
  margin-bottom: 1.5rem;
}

.property-group-title {
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #333;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.property-item {
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.property-label {
  font-size: 0.85rem;
  color: #666;
  font-weight: 500;
}

.property-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9rem;
}

.property-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* Responsive */
@media (max-width: 1024px) {
  .editor-main {
    grid-template-columns: 1fr 300px;
  }
  
  .editor-sidebar {
    display: none;
  }
}

@media (max-width: 768px) {
  .editor-main {
    grid-template-columns: 1fr;
  }
  
  .editor-properties {
    display: none;
  }
}
```

---

## ЗАКЛЮЧЕНИЕ

Этот набор кода обеспечивает:

✅ **Архитектуру:** MVC паттерн с разделением concerns
✅ **Рендеринг:** Three.js интеграция с оптимизацией
✅ **Функциональность:** Создание, модификация, сохранение features
✅ **UI/UX:** React компоненты и современный дизайн
✅ **Коллаборация:** WebSocket для real-time синхронизации
✅ **Производительность:** Кэширование и оптимизация

Для полной реализации требуется:
1. Расширить геометрические операции (OCCT.js)
2. Добавить персистентность БД
3. Реализовать полноценный интерфейс
4. Добавить тестирование
5. Оптимизировать для масштабирования
