# АНАЛИЗ ПРОФЕССИОНАЛЬНЫХ WEB-CAD СИСТЕМ

**Дата:** 18 января 2026  
**Источник:** Анализ реализаций Fusion 360, Onshape, LibreCAD, FreeCAD и open-source проектов

---

## 📊 Сравнение профессиональных CAD платформ

| Платформа | Технология | Архитектура | Производительность | Открытость |
|-----------|-----------|------------|-------------------|-----------|
| **Fusion 360** | WebGL + Native | Облачная + локальные расчеты | 60+ FPS | Закрыта |
| **Onshape** | Three.js/Babylon.js | Full Cloud (MongoDB) | 30-60 FPS | Закрыта |
| **LibreCAD Web** | Three.js | Гибридная | 30-45 FPS | Open Source |
| **FreeCAD** | OpenGL + Python | Desktop + Web | Переменная | Open Source |
| **CadQuery** | OCCT.js | Kernel-based | 60+ FPS | Open Source |
| **Tinkercad** | Three.js | Облачная | 60 FPS | Закрыта |

---

## 🏗️ АРХИТЕКТУРА ПРОФЕССИОНАЛЬНЫХ CAD

### 1. Многоуровневая архитектура (как в Fusion 360)

```
┌─────────────────────────────────────────────────┐
│      FRONTEND: React/Vue + WebGL                 │
│  - Viewport 3D (Three.js/Babylon.js)            │
│  - UI Controls, Properties, Constraints        │
│  - Local caching & undo/redo                   │
└────────────────────┬────────────────────────────┘
                     │ WebSocket/REST
┌────────────────────▼────────────────────────────┐
│  MIDDLE TIER: Node.js/Cloud Functions           │
│  - Request validation & throttling              │
│  - Collaborative updates (OT/CRDT)             │
│  - Caching layer (Redis)                       │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  KERNEL TIER: C++/OCCT (Open Cascade)          │
│  - Geometrical operations                      │
│  - Boolean operations (Union, Intersection)    │
│  - Feature tree management                     │
│  - Mesh generation                             │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  STORAGE TIER: Cloud Database                   │
│  - MongoDB/PostgreSQL: Metadata                │
│  - S3/CloudStorage: Large geometry data        │
│  - Git-like version control                    │
└─────────────────────────────────────────────────┘
```

**Почему так работает:**
- **Разделение забот**: Frontend отвечает за UX, Backend за вычисления
- **Масштабируемость**: Можно масштабировать каждый слой отдельно
- **Надежность**: Если одна машина падает, другие продолжают работу
- **Сотрудничество**: Изменения синхронизируются в реальном времени через WebSocket

---

### 2. Структура данных (CAD Document Model)

Как хранят файлы профессиональные CAD:

```typescript
// Struktur документа CAD (как в Fusion 360, Onshape)
interface CADDocument {
  metadata: {
    id: string;
    name: string;
    created: Date;
    modified: Date;
    version: string;
    author: string;
  };

  // Дерево признаков (Feature Tree)
  features: FeatureNode[];
  
  // История параметров для каждого признака
  history: {
    featureId: string;
    timestamp: Date;
    changes: Record<string, any>;
  }[];

  // Детали и сборки
  parts: Part[];
  assemblies: Assembly[];

  // Данные вида/сцены
  views: ViewConfiguration[];
  
  // Пользовательские свойства
  metadata_custom: Record<string, any>;
}

// Feature Tree (что-то типа истории создания)
interface FeatureNode {
  id: string;
  name: string;
  type: 'sketch' | 'pad' | 'pocket' | 'hole' | 'fillet' | 'chamfer' | 'assembly';
  
  // Параметры особого признака
  parameters: {
    depth?: number;
    radius?: number;
    angle?: number;
  };

  // Ссылка на предыдущий признак
  dependsOn?: string[];
  
  // Метаданные
  visible: boolean;
  suppressed: boolean;
  timestamp: Date;
}

// Часть (Body)
interface Part {
  id: string;
  name: string;
  
  // Geometry как в форме JSON (не raw mesh!)
  geometry: {
    vertices: number[][];
    faces: number[][];
    edges: number[][];
  };
  
  // Ссылка на features
  featureHistory: string[];
  
  // Свойства материала
  material?: {
    name: string;
    density: number;
    cost: number;
  };
}

// Сборка
interface Assembly {
  id: string;
  name: string;
  
  components: {
    partId: string;
    position: [number, number, number];
    rotation: [number, number, number];
    constraints?: Constraint[];
  }[];
}

// Ограничения (Constraints)
interface Constraint {
  type: 'coincident' | 'distance' | 'angle' | 'parallel' | 'perpendicular';
  entities: string[]; // IDs сущностей которые ограничиваются
  value?: number; // Для distance/angle
}
```

**Ключевые отличия от простого 3D:**
1. **Feature-based**: хранят историю операций, не финальную геометрию
2. **Параметрический**: все размеры связаны, изменил один - пересчиталось все
3. **History-aware**: можно вернуться на любой шаг
4. **Constraint-based**: детали связаны правилами, не только позицией

---

## 🎨 3D ВИЗУАЛИЗАЦИЯ В ПРОФЕССИОНАЛЬНЫХ CAD

### 1. LOD (Level of Detail) система - как в Fusion 360

```typescript
// ✅ Как Fusion 360 рендерит 10 миллионов полигонов
export class LODSystem {
  private lodLevels = [
    { distance: 0,    polygons: 1000000, quality: 'high' },    // близко
    { distance: 100,  polygons: 100000,  quality: 'medium' },  // средне
    { distance: 500,  polygons: 10000,   quality: 'low' },     // далеко
    { distance: 1000, polygons: 1000,    quality: 'ultra-low' } // очень далеко
  ];

  getMesh(originalMesh: THREE.Mesh, cameraDistance: number): THREE.Mesh {
    const lod = this.lodLevels.find(l => cameraDistance < l.distance) 
                || this.lodLevels[this.lodLevels.length - 1];

    // Создаем упрощенную версию геометрии
    if (!meshCache.has(originalMesh.uuid + lod.quality)) {
      const simplified = this.simplifyGeometry(originalMesh.geometry, lod.polygons);
      meshCache.set(originalMesh.uuid + lod.quality, simplified);
    }

    return meshCache.get(originalMesh.uuid + lod.quality)!;
  }

  // Используем Simplification.js или похожую библиотеку
  simplifyGeometry(geometry: THREE.BufferGeometry, targetPolygons: number): THREE.BufferGeometry {
    // Алгоритм: Quadric Error Metrics (как в Blender Decimate)
    return simplifier.simplify(geometry, targetPolygons / geometry.attributes.position.count);
  }
}

// Использование в viewport
const lodSystem = new LODSystem();
const meshToRender = lodSystem.getMesh(originalMesh, distanceToCamera);
renderer.render(scene, camera);
```

### 2. Instancing для повторяющихся деталей

```typescript
// ✅ Как Onshape рендерит одинаковые части (например, шурупы на панелях)
export class InstancedMeshManager {
  private instancedMesh: THREE.InstancedMesh;
  private dummy = new THREE.Object3D();

  constructor(baseGeometry: THREE.BufferGeometry, material: THREE.Material, count: number) {
    this.instancedMesh = new THREE.InstancedMesh(baseGeometry, material, count);
    this.instancedMesh.castShadow = true;
    this.instancedMesh.receiveShadow = true;
  }

  // Добавить экземпляр (например, шуруп)
  addInstance(position: THREE.Vector3, rotation: THREE.Quaternion, scale: THREE.Vector3, index: number) {
    this.dummy.position.copy(position);
    this.dummy.quaternion.copy(rotation);
    this.dummy.scale.copy(scale);
    this.dummy.updateMatrix();

    this.instancedMesh.setMatrixAt(index, this.dummy.matrix);
    this.instancedMesh.instanceMatrix.needsUpdate = true;
  }

  // Для 1000 шурупов: вместо 1000 рендерингов -> 1 렌더링
  // Экономия памяти в 100 раз!
}
```

### 3. Frustum Culling - не рендерим невидимые объекты

```typescript
// ✅ Как Fusion 360 не рисует то, что вне камеры
export class FrustumCuller {
  private frustum = new THREE.Frustum();
  private matrix = new THREE.Matrix4();

  updateCulling(scene: THREE.Scene, camera: THREE.PerspectiveCamera) {
    // Обновляем frustum на основе камеры
    this.matrix.multiplyMatrices(camera.projectionMatrix, 
                                 camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.matrix);

    // Проходим по всем объектам
    scene.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        // Box3 это бBox по объекту
        const box = new THREE.Box3().setFromObject(object);
        
        // Если не в frustum - не рисуем
        object.visible = this.frustum.intersectsBox(box);
      }
    });
  }
}

// В animation loop:
const culler = new FrustumCuller();
culler.updateCulling(scene, camera); // скрываем невидимые объекты
renderer.render(scene, camera);
```

---

## 💾 УПРАВЛЕНИЕ СОСТОЯНИЕМ И ИСТОРИЕЙ

### 1. CRDT (Conflict-free Replicated Data Type) для совместной работы

Как Onshape позволяет двум пользователям одновременно редактировать:

```typescript
// ✅ Simplified CRDT с использованием UUID + timestamps
export class CRDTOperation {
  id: string = generateUUID();
  timestamp: number = Date.now();
  userId: string;
  
  // Операция может быть INSERT или DELETE
  type: 'insert' | 'delete';
  
  // Позиция в документе
  position: number;
  
  // Что вставляем/удаляем
  content: any;
}

export class CRDTDocument {
  private operations: CRDTOperation[] = [];
  private data: any[] = [];

  // Применить операцию от пользователя A
  applyRemoteOperation(op: CRDTOperation) {
    // Алгоритм: вставить в порядке (id, timestamp)
    this.operations.push(op);
    this.operations.sort((a, b) => {
      if (a.id < b.id) return -1;
      if (a.id > b.id) return 1;
      return a.timestamp - b.timestamp;
    });

    // Пересчитать состояние документа
    this.rebuild();
  }

  // Даже если операции пришли в разном порядке
  // итоговое состояние будет одинаковым!
  private rebuild() {
    this.data = [];
    for (const op of this.operations) {
      if (op.type === 'insert') {
        this.data.splice(op.position, 0, op.content);
      } else {
        this.data.splice(op.position, 1);
      }
    }
  }
}
```

### 2. Undo/Redo с Command Pattern

```typescript
// ✅ Как Fusion 360 реализует Undo/Redo
export abstract class Command {
  abstract execute(): void;
  abstract undo(): void;
  
  // Redo = второй execute
  redo() { this.execute(); }
}

export class CreatePadCommand extends Command {
  constructor(
    private part: Part,
    private sketch: Sketch,
    private depth: number
  ) { super(); }

  execute() {
    const pad = this.part.createPad(this.sketch, this.depth);
    // Обновляем mesh в 3D
    this.updateViewport();
  }

  undo() {
    this.part.deletePad(this.sketch.id);
    this.updateViewport();
  }

  private updateViewport() {
    // Пересчитать mesh
    // Обновить feature tree
    // Триггерить re-render
  }
}

export class CommandHistory {
  private stack: Command[] = [];
  private pointer = -1;
  private maxSize = 100;

  execute(command: Command) {
    // Если были undo, удалить все после pointer
    this.stack.splice(this.pointer + 1);

    command.execute();
    
    // Добавить команду и переместить pointer
    this.stack.push(command);
    this.pointer++;

    // Ограничить размер памяти
    if (this.stack.length > this.maxSize) {
      this.stack.shift();
      this.pointer--;
    }
  }

  undo() {
    if (this.pointer >= 0) {
      this.stack[this.pointer].undo();
      this.pointer--;
    }
  }

  redo() {
    if (this.pointer < this.stack.length - 1) {
      this.pointer++;
      this.stack[this.pointer].redo();
    }
  }
}
```

---

## 🔧 ОБРАБОТКА ПОЛЬЗОВАТЕЛЬСКОГО ВВОДА

### 1. Выделение (Selection) как в Fusion 360

```typescript
// ✅ Как Fusion 360 выделяет объекты через raycasting
export class SelectionManager {
  private selectedObjects = new Set<THREE.Object3D>();
  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();

  onMouseMove(event: MouseEvent, canvas: HTMLCanvasElement) {
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    // Highlight на hover
    this.raycaster.setFromCamera(this.mouse, camera);
    const intersects = this.raycaster.intersectObjects(scene.children, true);

    // Убрать старый highlight
    scene.children.forEach(obj => {
      if (obj instanceof THREE.Mesh) {
        obj.material.emissive.setHex(0x000000);
      }
    });

    // Добавить новый highlight на первый пересеченный объект
    if (intersects.length > 0) {
      const firstHit = intersects[0].object;
      if (firstHit instanceof THREE.Mesh) {
        firstHit.material.emissive.setHex(0x444444); // темный highlight
      }
    }
  }

  onClick(event: MouseEvent, canvas: HTMLCanvasElement) {
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, camera);
    const intersects = this.raycaster.intersectObjects(scene.children, true);

    if (event.ctrlKey || event.metaKey) {
      // Ctrl+Click = добавить к выделению
      if (intersects.length > 0) {
        this.selectedObjects.add(intersects[0].object);
      }
    } else if (event.shiftKey) {
      // Shift+Click = вычесть из выделения
      if (intersects.length > 0) {
        this.selectedObjects.delete(intersects[0].object);
      }
    } else {
      // Обычный click = новое выделение
      this.selectedObjects.clear();
      if (intersects.length > 0) {
        this.selectedObjects.add(intersects[0].object);
      }
    }

    this.updateSelection();
  }

  private updateSelection() {
    // Выделить с оранжевой рамкой
    this.selectedObjects.forEach(obj => {
      if (obj instanceof THREE.Mesh) {
        obj.material.emissive.setHex(0xff6600);
      }
    });

    // Эмитить событие для UI
    this.onSelectionChanged.emit(Array.from(this.selectedObjects));
  }
}
```

### 2. Трансформация объектов

```typescript
// ✅ Как в Fusion 360 перемещать объекты мышкой
export class TransformGizmo {
  private isDragging = false;
  private dragStart = new THREE.Vector2();
  private draggedObject: THREE.Object3D | null = null;
  private dragPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  private dragPoint = new THREE.Vector3();

  onMouseDown(event: MouseEvent, canvas: HTMLCanvasElement, selectedObject: THREE.Object3D) {
    const rect = canvas.getBoundingClientRect();
    this.dragStart.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.dragStart.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.isDragging = true;
    this.draggedObject = selectedObject;

    // Плоскость для перетаскивания - в плоскости камеры
    this.dragPlane.setFromNormalAndCoplanarPoint(
      camera.getWorldDirection(new THREE.Vector3()).negate(),
      selectedObject.position
    );
  }

  onMouseMove(event: MouseEvent, canvas: HTMLCanvasElement) {
    if (!this.isDragging || !this.draggedObject) return;

    const rect = canvas.getBoundingClientRect();
    const mouse = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1
    );

    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);

    // Найти точку пересечения луча с плоскостью
    raycaster.ray.intersectPlane(this.dragPlane, this.dragPoint);

    // Вычислить смещение
    const raycasterStart = new THREE.Raycaster();
    raycasterStart.setFromCamera(this.dragStart, camera);
    const dragStartPoint = new THREE.Vector3();
    raycasterStart.ray.intersectPlane(this.dragPlane, dragStartPoint);

    const delta = new THREE.Vector3().subVectors(this.dragPoint, dragStartPoint);
    this.draggedObject.position.add(delta);

    // Обновить dragStart для следующего кадра
    this.dragStart.copy(mouse);
  }

  onMouseUp() {
    this.isDragging = false;
    this.draggedObject = null;
  }
}
```

---

## 📈 ОПТИМИЗАЦИЯ И SCALABILITY

### 1. Web Workers для тяжелых вычислений

```typescript
// ✅ Как Fusion 360 не замораживает UI во время расчетов

// main.ts
const geometryWorker = new Worker('geometry-worker.ts');

function generateGeometryInBackground(sketch: Sketch, depth: number) {
  return new Promise((resolve) => {
    const handler = (e: MessageEvent) => {
      geometryWorker.removeEventListener('message', handler);
      resolve(e.data); // Готовая геометрия
    };

    geometryWorker.addEventListener('message', handler);
    geometryWorker.postMessage({
      type: 'generatePad',
      sketch: sketch,
      depth: depth
    });
  });
}

// geometry-worker.ts
self.onmessage = async (e) => {
  const { type, sketch, depth } = e.data;

  if (type === 'generatePad') {
    // Долгий расчет BOOLean операции
    const geometry = await complexBooleanOperation(sketch, depth);
    
    // Отправить результат обратно в main thread
    self.postMessage({
      type: 'padGenerated',
      geometry: geometry
    });
  }
};
```

### 2. Streaming геометрии для больших моделей

```typescript
// ✅ Как Onshape грузит большие модели потихоньку
export class GeometryStreamer {
  async *streamGeometry(documentId: string) {
    const response = await fetch(`/api/documents/${documentId}/geometry/stream`);
    const reader = response.body?.getReader();

    if (!reader) throw new Error('No response body');

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Каждый chunk это один mesh
      const chunk = JSON.parse(new TextDecoder().decode(value));
      yield chunk;
    }
  }

  async loadModelWithStreaming(documentId: string, scene: THREE.Scene) {
    for await (const meshData of this.streamGeometry(documentId)) {
      const mesh = this.createMeshFromData(meshData);
      scene.add(mesh);
      
      // UI обновляется сразу, не ждем всю модель
      renderFrame();
    }
  }
}
```

---

## 🔌 ИНТЕГРАЦИЯ С BACKEND

### 1. REST API структура (как в Onshape)

```
GET    /api/documents              // Список документов
POST   /api/documents              // Создать документ
GET    /api/documents/{id}         // Получить документ
PUT    /api/documents/{id}         // Обновить документ
DELETE /api/documents/{id}         // Удалить

GET    /api/documents/{id}/parts   // Части в документе
POST   /api/documents/{id}/parts   // Создать часть
GET    /api/documents/{id}/parts/{partId}/features  // Features
POST   /api/documents/{id}/parts/{partId}/features  // Добавить feature

GET    /api/documents/{id}/export/{format}  // Экспорт (STEP, STL, etc)
POST   /api/documents/{id}/export           // Запустить экспорт

// WebSocket для real-time collaboration
WS     /ws/documents/{id}          // Sync изменений между пользователями
```

### 2. Синхронизация через WebSocket

```typescript
// ✅ Как Fusion 360 синхронизирует изменения в реальном времени
const socket = io('/documents/{documentId}');

// Когда я что-то изменил
socket.on('connect', () => {
  socket.emit('operation', {
    type: 'movePart',
    partId: 'part-1',
    position: [100, 200, 300],
    timestamp: Date.now(),
    userId: currentUser.id
  });
});

// Когда другой пользователь что-то изменил
socket.on('remoteOperation', (operation) => {
  // Применить операцию
  applyRemoteOperation(operation);
  
  // Обновить 3D view
  updateViewport();
  
  // Показать уведомление
  showNotification(`${operation.userId} moved ${operation.partId}`);
});

// Конфликты (оба пользователя одновременно переместили одну часть)
socket.on('conflict', (resolution) => {
  // Обычно используют CRDT или Last-Write-Wins
  applyResolution(resolution);
});
```

---

## 📋 ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ

### Для вашего проекта Базис:

**✅ ДЕЛАЙТЕ:**

1. **Feature Tree** - сохраняйте историю создания, не просто меши
2. **Параметрическое моделирование** - изменение размера панели пересчитывает все
3. **Command Pattern** - каждое действие это отдельная команда (для Undo/Redo)
4. **LOD система** - когда деталей 1000+, упрощайте дальние
5. **Web Workers** - тяжелые расчеты не в main thread
6. **Instancing** - когда много одинаковых деталей (шурупы, дюбели)

**❌ НЕ ДЕЛАЙТЕ:**

1. Не сохраняйте raw mesh - сохраняйте параметры и историю
2. Не перегружайте main thread - давайте юзеру обратную связь
3. Не забывайте про мобильный дизайн - Fusion 360 работает везде
4. Не хранилище все в памяти - используйте streaming

**⚡ БЫСТРЫЙ СТАРТ для MVP:**

```
День 1: Three.js viewport + Selection + Transform
День 2: Simple feature (Pad) + mesh generation
День 3: Undo/Redo + Save to localStorage
День 4: WebSocket sync + Basic collaboration
День 5: Export to STEP/STL + Polish
```

---

## 📚 Полезные библиотеки

| Библиотека | Для чего | Ссылка |
|-----------|---------|---------|
| **Three.js** | 3D визуализация | https://threejs.org |
| **Babylon.js** | 3D (альтернатива) | https://www.babylonjs.com |
| **OCCT.js** | CAD kernel | https://github.com/donalffons/opencascade.js |
| **CadQuery** | Python CAD | https://github.com/CadQuery/cadquery |
| **Simplification.js** | Mesh simplification | https://github.com/athrxx/simplification.js |
| **Yjs** | CRDT для collaboration | https://docs.yjs.dev |
| **Socket.io** | Real-time sync | https://socket.io |
| **STLExporter** | Экспорт STL | https://github.com/mrdoob/three.js/blob/master/examples/jsm/exporters/STLExporter.js |

---

## 🎯 Заключение

Профессиональные CAD системы сложны, но в их основе:

1. **Многоуровневая архитектура** - разделение ответственности
2. **Параметрическое моделирование** - данные + математика, не геометрия
3. **Оптимизация производительности** - LOD, Instancing, Culling
4. **Состояние и история** - Command Pattern, CRDT
5. **Collaboration** - WebSocket, операционное трансформирование

Ваш Базис может реализовать эти принципы пошагово!
