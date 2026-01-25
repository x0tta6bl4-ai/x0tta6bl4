# АРХИТЕКТУРА WEB-CAD: BEST PRACTICES И ПАТТЕРНЫ

## 📐 Многослойная архитектура

```
┌─────────────────────────────────────────────────────────┐
│               PRESENTATION LAYER                         │
│  React Components (Viewport, Toolbar, PropertyPanel)    │
├─────────────────────────────────────────────────────────┤
│             INTERACTION LAYER                            │
│  Selection, Transform, Input Handlers, Raycasting       │
├─────────────────────────────────────────────────────────┤
│             RENDERING LAYER                              │
│  Three.js Scene, Camera, Materials, LOD System          │
├─────────────────────────────────────────────────────────┤
│            GEOMETRY LAYER                                │
│  CAD Geometries, Boolean Operations, Caching            │
├─────────────────────────────────────────────────────────┤
│          DATA MANAGEMENT LAYER                           │
│  Document Model, Feature Tree, Command History          │
├─────────────────────────────────────────────────────────┤
│           BACKEND LAYER                                  │
│  API, WebSocket, OCCT Kernel, Database                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗️ Паттерны проектирования

### 1. Command Pattern (для Undo/Redo)

```typescript
// ✅ ХОРОШО: Каждое действие - отдельная команда
export abstract class Command {
  abstract execute(): void;
  abstract undo(): void;
  abstract redo(): void;
}

export class MoveObjectCommand extends Command {
  private originalPosition: THREE.Vector3;
  private newPosition: THREE.Vector3;

  constructor(
    private object: THREE.Object3D,
    targetPosition: THREE.Vector3
  ) {
    super();
    this.originalPosition = object.position.clone();
    this.newPosition = targetPosition;
  }

  execute() {
    this.object.position.copy(this.newPosition);
    // Emit event
  }

  undo() {
    this.object.position.copy(this.originalPosition);
  }

  redo() {
    this.execute();
  }
}

// ✅ ХОРОШО: CommandHistory управляет стеком команд
export class CommandHistory {
  private stack: Command[] = [];
  private index = -1;

  execute(command: Command) {
    // Удалить все команды после текущей позиции (если было undo)
    this.stack = this.stack.slice(0, this.index + 1);
    
    command.execute();
    this.stack.push(command);
    this.index++;
  }

  undo() {
    if (this.index >= 0) {
      this.stack[this.index].undo();
      this.index--;
    }
  }

  redo() {
    if (this.index < this.stack.length - 1) {
      this.index++;
      this.stack[this.index].redo();
    }
  }

  get canUndo() { return this.index >= 0; }
  get canRedo() { return this.index < this.stack.length - 1; }
}
```

### 2. Observer Pattern (для синхронизации)

```typescript
// ✅ ХОРОШО: EventEmitter для реактивного обновления
export class EventEmitter<T extends Record<string, any>> {
  private listeners: Map<keyof T, Set<Function>> = new Map();

  on<K extends keyof T>(event: K, handler: (data: T[K]) => void) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)!.delete(handler);
    };
  }

  emit<K extends keyof T>(event: K, data: T[K]) {
    this.listeners.get(event)?.forEach(handler => handler(data));
  }
}

// Использование
export const cadEvents = new EventEmitter<{
  objectAdded: { id: string };
  objectSelected: { id: string };
  objectTransformed: { id: string; position: THREE.Vector3 };
}>();

// В React компоненте
useEffect(() => {
  const unsubscribe = cadEvents.on('objectTransformed', (data) => {
    console.log(`Object ${data.id} moved to`, data.position);
  });
  
  return unsubscribe;
}, []);
```

### 3. Factory Pattern (для создания объектов)

```typescript
// ✅ ХОРОШО: Factory для создания primitives
export class PrimitiveFactory {
  static create(type: 'box' | 'sphere' | 'cylinder', size: number = 30): THREE.Mesh {
    let geometry: THREE.BufferGeometry;

    switch (type) {
      case 'box':
        geometry = new THREE.BoxGeometry(size, size, size);
        break;
      case 'sphere':
        geometry = new THREE.SphereGeometry(size / 2, 32, 32);
        break;
      case 'cylinder':
        geometry = new THREE.CylinderGeometry(size / 2, size / 2, size, 32);
        break;
    }

    const material = new THREE.MeshStandardMaterial({
      color: Math.random() * 0xffffff,
      metalness: 0.3,
      roughness: 0.7,
      side: THREE.DoubleSide
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.type = type;
    mesh.userData.id = generateUUID();

    return mesh;
  }
}
```

### 4. Singleton Pattern (для сервисов)

```typescript
// ✅ ХОРОШО: Singleton для RenderService
export class RenderService {
  private static instance: RenderService;
  private scene: THREE.Scene;
  private renderer: THREE.WebGLRenderer;
  private camera: THREE.OrthographicCamera;

  private constructor(canvas: HTMLCanvasElement) {
    this.scene = new THREE.Scene();
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.camera = new THREE.OrthographicCamera(
      -100, 100, 100, -100, 0.1, 1000
    );
  }

  static getInstance(canvas?: HTMLCanvasElement): RenderService {
    if (!RenderService.instance && canvas) {
      RenderService.instance = new RenderService(canvas);
    }
    return RenderService.instance;
  }

  getScene() { return this.scene; }
  getRenderer() { return this.renderer; }
  getCamera() { return this.camera; }
}
```

### 5. Strategy Pattern (для разных алгоритмов)

```typescript
// ✅ ХОРОШО: Strategy для экспорта в разные форматы
export interface ExportStrategy {
  export(scene: THREE.Scene): Promise<Blob>;
  getMimeType(): string;
  getExtension(): string;
}

export class STLExportStrategy implements ExportStrategy {
  async export(scene: THREE.Scene): Promise<Blob> {
    // STL export logic
    return new Blob();
  }

  getMimeType() { return 'model/stl'; }
  getExtension() { return '.stl'; }
}

export class GLTFExportStrategy implements ExportStrategy {
  async export(scene: THREE.Scene): Promise<Blob> {
    const exporter = new GLTFExporter();
    return new Promise((resolve) => {
      exporter.parse(scene, (gltf) => {
        resolve(new Blob([JSON.stringify(gltf)], { type: 'application/json' }));
      });
    });
  }

  getMimeType() { return 'model/gltf+json'; }
  getExtension() { return '.gltf'; }
}

export class ExportService {
  constructor(private strategy: ExportStrategy) {}

  setStrategy(strategy: ExportStrategy) {
    this.strategy = strategy;
  }

  async export(scene: THREE.Scene): Promise<Blob> {
    return this.strategy.export(scene);
  }
}
```

---

## 🎯 Performance Best Practices

### 1. Кэширование геометрий

```typescript
// ✅ ХОРОШО: LRU Cache для геометрий
export class GeometryCache {
  private cache: Map<string, THREE.BufferGeometry> = new Map();
  private maxSize = 100;
  private accessOrder: string[] = [];

  get(key: string): THREE.BufferGeometry | null {
    if (this.cache.has(key)) {
      // Move to end (most recently used)
      this.accessOrder = this.accessOrder.filter(k => k !== key);
      this.accessOrder.push(key);
      return this.cache.get(key)!;
    }
    return null;
  }

  set(key: string, geometry: THREE.BufferGeometry) {
    if (this.cache.size >= this.maxSize) {
      const oldest = this.accessOrder.shift();
      if (oldest) {
        const geom = this.cache.get(oldest);
        geom?.dispose();
        this.cache.delete(oldest);
      }
    }

    this.cache.set(key, geometry);
    this.accessOrder.push(key);
  }

  clear() {
    this.cache.forEach(geom => geom.dispose());
    this.cache.clear();
    this.accessOrder = [];
  }
}
```

### 2. Level of Detail (LOD)

```typescript
// ✅ ХОРОШО: LOD для оптимизации производительности
export class LODManager {
  private lods: Map<string, THREE.LOD> = new Map();

  createLOD(id: string, highPoly: THREE.Mesh, lowPoly: THREE.Mesh): THREE.LOD {
    const lod = new THREE.LOD();
    lod.addLevel(highPoly, 0);      // На расстояниях < 100
    lod.addLevel(lowPoly, 100);     // На расстояниях >= 100
    lod.addLevel(new THREE.Mesh(), 500); // На расстояниях >= 500 - скрыть
    
    this.lods.set(id, lod);
    return lod;
  }

  update(camera: THREE.Camera) {
    this.lods.forEach(lod => {
      lod.update(camera);
    });
  }
}
```

### 3. Frustum Culling

```typescript
// ✅ ХОРОШО: Frustum culling для скрытия невидимых объектов
export class CullingManager {
  private frustum: THREE.Frustum = new THREE.Frustum();
  private frustumMatrix: THREE.Matrix4 = new THREE.Matrix4();

  update(camera: THREE.Camera) {
    this.frustumMatrix.multiplyMatrices(
      camera.projectionMatrix,
      camera.matrixWorldInverse
    );
    this.frustum.setFromProjectionMatrix(this.frustumMatrix);
  }

  isVisible(object: THREE.Object3D): boolean {
    const box = new THREE.Box3().setFromObject(object);
    return this.frustum.intersectsBox(box);
  }

  cullScene(scene: THREE.Scene) {
    scene.traverse(object => {
      if (object instanceof THREE.Mesh) {
        object.visible = this.isVisible(object);
      }
    });
  }
}
```

### 4. Web Workers для тяжелых вычислений

```typescript
// ✅ ХОРОШО: Web Worker pool
export class WorkerPool {
  private workers: Worker[] = [];
  private taskQueue: Array<{
    task: any;
    resolve: (result: any) => void;
  }> = [];

  constructor(scriptUrl: string, poolSize: number = 4) {
    for (let i = 0; i < poolSize; i++) {
      const worker = new Worker(scriptUrl);
      worker.onmessage = (e) => {
        const { task } = this.taskQueue.shift()!;
        task.resolve(e.data);

        if (this.taskQueue.length > 0) {
          const nextTask = this.taskQueue[0];
          worker.postMessage(nextTask.task);
        }
      };
      this.workers.push(worker);
    }
  }

  async process<T>(data: any): Promise<T> {
    return new Promise((resolve) => {
      this.taskQueue.push({ task: data, resolve });

      if (this.taskQueue.length <= this.workers.length) {
        const worker = this.workers[this.taskQueue.length - 1];
        worker.postMessage(data);
      }
    });
  }
}

// worker.js
self.onmessage = (e) => {
  // Сложные вычисления
  const result = heavyCalculation(e.data);
  self.postMessage(result);
};
```

### 5. Batch Rendering

```typescript
// ✅ ХОРОШО: InstancedMesh для множества объектов
export class BatchRenderer {
  createInstancedMesh(
    geometry: THREE.BufferGeometry,
    material: THREE.Material,
    count: number
  ): THREE.InstancedMesh {
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    
    const matrix = new THREE.Matrix4();
    for (let i = 0; i < count; i++) {
      matrix.makeTranslation(
        Math.random() * 200 - 100,
        Math.random() * 200 - 100,
        Math.random() * 200 - 100
      );
      mesh.setMatrixAt(i, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;

    return mesh;
  }

  updateInstance(
    mesh: THREE.InstancedMesh,
    index: number,
    position: THREE.Vector3,
    rotation: THREE.Euler,
    scale: THREE.Vector3
  ) {
    const matrix = new THREE.Matrix4();
    matrix.compose(position, new THREE.Quaternion().setFromEuler(rotation), scale);
    mesh.setMatrixAt(index, matrix);
    mesh.instanceMatrix.needsUpdate = true;
  }
}
```

---

## 🔒 Error Handling & Validation

### Input Validation

```typescript
// ✅ ХОРОШО: Валидация входных данных
export class Validator {
  static validatePosition(pos: any): THREE.Vector3 {
    if (!pos || typeof pos !== 'object') {
      throw new Error('Position must be an object');
    }

    const x = parseFloat(pos.x);
    const y = parseFloat(pos.y);
    const z = parseFloat(pos.z);

    if (isNaN(x) || isNaN(y) || isNaN(z)) {
      throw new Error('Position coordinates must be numbers');
    }

    if (Math.abs(x) > 10000 || Math.abs(y) > 10000 || Math.abs(z) > 10000) {
      throw new Error('Position out of bounds');
    }

    return new THREE.Vector3(x, y, z);
  }

  static validateObjectSize(size: any): number {
    const s = parseFloat(size);
    if (isNaN(s) || s <= 0 || s > 10000) {
      throw new Error('Size must be a positive number between 0 and 10000');
    }
    return s;
  }
}

// Использование
try {
  const pos = Validator.validatePosition({ x: 10, y: 20, z: 30 });
  const size = Validator.validateObjectSize(50);
} catch (error) {
  console.error('Validation error:', error.message);
}
```

### Error Boundaries

```typescript
// ✅ ХОРОШО: React Error Boundary
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Caught error:', error, errorInfo);
    // Отправить в сервис логирования
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'red' }}>
          <h1>Something went wrong</h1>
          <p>{this.state.error?.message}</p>
        </div>
      );
    }

    return this.props.children;
  }
}
```

---

## 🔄 State Management Best Practices

### Using Zustand

```typescript
// ✅ ХОРОШО: Правильная организация state
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { devtools } from 'zustand/middleware/devtools';

export interface CADState {
  // State
  objects: Map<string, CADObject>;
  selectedId: string | null;
  camera: { position: THREE.Vector3; zoom: number };

  // Actions
  addObject: (obj: CADObject) => void;
  removeObject: (id: string) => void;
  selectObject: (id: string | null) => void;
  updateCamera: (pos: THREE.Vector3, zoom: number) => void;
  reset: () => void;
}

export const useCadStore = create<CADState>()(
  devtools(
    immer((set) => ({
      objects: new Map(),
      selectedId: null,
      camera: { position: new THREE.Vector3(0, 0, 100), zoom: 1 },

      addObject: (obj) => set((state) => {
        state.objects.set(obj.id, obj);
      }),

      removeObject: (id) => set((state) => {
        state.objects.delete(id);
      }),

      selectObject: (id) => set({ selectedId: id }),

      updateCamera: (pos, zoom) => set((state) => {
        state.camera.position = pos;
        state.camera.zoom = zoom;
      }),

      reset: () => set({
        objects: new Map(),
        selectedId: null,
        camera: { position: new THREE.Vector3(0, 0, 100), zoom: 1 }
      })
    })),
    { name: 'CADStore' }
  )
);
```

---

## 📝 Type Safety

```typescript
// ✅ ХОРОШО: Строгая типизация
export enum ObjectType {
  Box = 'box',
  Sphere = 'sphere',
  Cylinder = 'cylinder',
  Custom = 'custom'
}

export interface CADObject {
  readonly id: string;
  readonly type: ObjectType;
  readonly name: string;
  position: Readonly<THREE.Vector3>;
  rotation: Readonly<THREE.Euler>;
  scale: Readonly<THREE.Vector3>;
  visible: boolean;
  properties: ReadonlyMap<string, any>;
}

export interface TransformData {
  position?: THREE.Vector3;
  rotation?: THREE.Euler;
  scale?: THREE.Vector3;
}

export function updateObject(
  object: CADObject,
  data: TransformData
): CADObject {
  return {
    ...object,
    position: data.position ?? object.position,
    rotation: data.rotation ?? object.rotation,
    scale: data.scale ?? object.scale
  };
}
```

---

## 🧪 Testing Best Practices

```typescript
// ✅ ХОРОШО: Unit tests для сервисов
import { describe, it, expect } from 'vitest';

describe('GeometryService', () => {
  it('should create box with correct dimensions', () => {
    const geom = GeometryService.createBox(20, 30, 40);
    const box = new THREE.Box3().setFromBufferGeometry(geom);
    
    expect(box.getSize(new THREE.Vector3()).x).toBeCloseTo(20);
    expect(box.getSize(new THREE.Vector3()).y).toBeCloseTo(30);
    expect(box.getSize(new THREE.Vector3()).z).toBeCloseTo(40);
  });
});

describe('CommandHistory', () => {
  it('should undo command', () => {
    const scene = new THREE.Scene();
    const mesh = new THREE.Mesh();
    const history = new CommandHistory();

    const cmd = new AddObjectCommand(scene, mesh);
    history.execute(cmd);
    expect(scene.children.length).toBe(1);

    history.undo();
    expect(scene.children.length).toBe(0);
  });
});
```

---

## 🚀 Масштабируемость

### Архитектура для больших моделей

```typescript
// ✅ ХОРОШО: Streaming geometry для больших моделей
export class StreamingGeometryLoader {
  async loadChunks(
    url: string,
    onProgress: (loaded: number, total: number) => void
  ): Promise<THREE.BufferGeometry[]> {
    const chunks: THREE.BufferGeometry[] = [];
    
    const response = await fetch(url);
    const reader = response.body!.getReader();
    const total = response.headers.get('content-length');

    let loaded = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      loaded += value.length;
      onProgress(loaded, parseInt(total || '0'));

      // Parse chunk
      const geom = this.parseGeometryChunk(value);
      chunks.push(geom);
    }

    return chunks;
  }

  private parseGeometryChunk(data: Uint8Array): THREE.BufferGeometry {
    // Implementation
    return new THREE.BufferGeometry();
  }
}
```

---

## ✨ Итоговый чек-лист архитектуры

```
🏗️ АРХИТЕКТУРА
  ✅ Многослойная архитектура соблюдается
  ✅ Слои независимы и расширяемы
  ✅ Четкие границы ответственности

🎯 ПАТТЕРНЫ
  ✅ Command Pattern для Undo/Redo
  ✅ Observer Pattern для синхронизации
  ✅ Factory Pattern для создания объектов
  ✅ Singleton Pattern для сервисов
  ✅ Strategy Pattern для алгоритмов

⚡ ПРОИЗВОДИТЕЛЬНОСТЬ
  ✅ LOD система реализована
  ✅ Frustum culling активирован
  ✅ Кэширование геометрий настроено
  ✅ Web Workers используются
  ✅ InstancedMesh для批处理

🔒 НАДЕЖНОСТЬ
  ✅ Валидация входных данных
  ✅ Error Boundaries установлены
  ✅ Обработка ошибок сетей
  ✅ Type safety максимален

🧪 КАЧЕСТВО
  ✅ Unit tests написаны
  ✅ Integration tests покрывают flow
  ✅ Performance tests проводились

📦 МАСШТАБИРУЕМОСТЬ
  ✅ Архитектура поддерживает рост
  ✅ Streaming для больших моделей
  ✅ Backend масштабируется горизонтально
```

Используйте эти паттерны и лучшие практики для создания профессиональной, надежной и масштабируемой web-CAD системы!
